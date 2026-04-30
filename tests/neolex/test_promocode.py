"""Promocode system tests (NEO-2874).

Uses real PostgreSQL DB (vitreon_legal_test) — no DB mocking.
Follows the same pattern as test_billing.py.

Run with:
    uv run pytest tests/neolex/test_promocode.py -v
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import neolex.db.postgres as _pg
from neolex.auth.session import get_current_user
from neolex.db.models import Promocode, User
from neolex.db.postgres import get_db, init_db
from neolex.services import billing as billing_svc
from neolex.services.billing import effective_subscription_tier

pytestmark = pytest.mark.asyncio(loop_scope="module")


# ---------------------------------------------------------------------------
# Schema bootstrap and test app
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def ensure_promo_schema(_install_nullpool_engine):  # noqa: ARG001
    """Run init_db() once — ensures promocodes/redemptions tables exist."""
    asyncio.run(init_db())


@pytest.fixture(scope="module")
def promo_app() -> FastAPI:
    """FastAPI app with only the Stripe router — no pipeline."""
    from neolex.routers.stripe_router import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def unique_email() -> str:
    return f"promo_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def test_user(unique_email: str) -> User:
    """Free-tier user in the test DB."""
    user = User(
        email=unique_email,
        email_verified=True,
        subscription_status="free",
        max_corpora=0,
    )
    async with _pg.AsyncSessionLocal() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest.fixture(autouse=True)
async def cleanup_promo_data():
    """Remove test data before and after each test."""

    async def _cleanup():
        async with _pg.AsyncSessionLocal() as session:
            await session.execute(delete(User).where(User.email.like("promo_test_%@example.com")))
            await session.execute(delete(Promocode).where(Promocode.code.like("TEST_%")))
            await session.commit()

    await _cleanup()
    yield
    await _cleanup()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear the in-memory rate-limit state between tests."""
    billing_svc._promo_attempts.clear()
    yield
    billing_svc._promo_attempts.clear()


@pytest.fixture
async def client(promo_app: FastAPI, test_user: User) -> AsyncClient:
    """Client authenticated as test_user via dependency override."""
    user_id = test_user.id

    async def _auth(db: AsyncSession = Depends(get_db)) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    promo_app.dependency_overrides[get_current_user] = _auth
    async with AsyncClient(transport=ASGITransport(app=promo_app), base_url="http://test") as c:
        yield c
    promo_app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Unit tests — effective_subscription_tier
# ---------------------------------------------------------------------------


class TestEffectiveSubscriptionTier:
    def _user(self, subscription_status="free", promo_tier=None, promo_expires_at=None):
        u = User(
            email=f"unit_{uuid.uuid4().hex[:6]}@example.com",
            subscription_status=subscription_status,
        )
        u.promo_tier = promo_tier
        u.promo_expires_at = promo_expires_at
        return u

    def test_no_promo_returns_paid_tier(self):
        assert effective_subscription_tier(self._user("starter")) == "starter"

    def test_active_promo_upgrades_free_user(self):
        u = self._user("free", "starter", datetime.now(UTC) + timedelta(days=10))
        assert effective_subscription_tier(u) == "starter"

    def test_active_promo_lower_than_paid_ignored(self):
        u = self._user("pro", "starter", datetime.now(UTC) + timedelta(days=10))
        assert effective_subscription_tier(u) == "pro"

    def test_expired_promo_falls_back_to_paid(self):
        u = self._user("free", "starter", datetime.now(UTC) - timedelta(seconds=1))
        assert effective_subscription_tier(u) == "free"

    def test_expired_promo_clears_fields(self):
        u = self._user("free", "starter", datetime.now(UTC) - timedelta(seconds=1))
        effective_subscription_tier(u)
        assert u.promo_tier is None
        assert u.promo_expires_at is None

    def test_unknown_paid_tier_normalizes_to_free(self):
        u = self._user("legacy_trial")
        assert effective_subscription_tier(u) == "free"


# ---------------------------------------------------------------------------
# Integration tests — POST /stripe/promocode/redeem
# ---------------------------------------------------------------------------


async def _insert_promo(code: str, tier: str, **kwargs) -> Promocode:
    """Helper: insert a Promocode row into the test DB."""
    promo = Promocode(
        code=code,
        tier=tier,
        duration_days=kwargs.get("duration_days", 30),
        active=kwargs.get("active", True),
        valid_until=kwargs.get("valid_until", datetime.now(UTC) + timedelta(days=365)),
        max_redemptions=kwargs.get("max_redemptions", None),
        redemption_count=kwargs.get("redemption_count", 0),
    )
    async with _pg.AsyncSessionLocal() as session:
        session.add(promo)
        await session.commit()
        await session.refresh(promo)
    return promo


class TestPromocodeRedeem:
    """POST /stripe/promocode/redeem"""

    async def test_valid_code_free_user_returns_200(self, client):
        await _insert_promo("TEST_FREE_UP", "starter")
        resp = await client.post("/stripe/promocode/redeem", json={"code": "TEST_FREE_UP"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("promo_tier") == "starter"

    async def test_tier_applied_in_billing_status_response(self, client):
        await _insert_promo("TEST_TIER_RESP", "pro")
        resp = await client.post("/stripe/promocode/redeem", json={"code": "TEST_TIER_RESP"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("promo_tier") == "pro"
        assert data.get("promo_expires_at") is not None

    async def test_invalid_code_returns_404(self, client):
        resp = await client.post("/stripe/promocode/redeem", json={"code": "TEST_NONEXISTENT"})
        assert resp.status_code == 404
        assert "Invalid promocode" in resp.json()["detail"]

    async def test_expired_code_returns_404(self, client):
        await _insert_promo("TEST_EXPIRED", "starter", valid_until=datetime.now(UTC) - timedelta(days=1))
        resp = await client.post("/stripe/promocode/redeem", json={"code": "TEST_EXPIRED"})
        assert resp.status_code == 404
        assert "Invalid promocode" in resp.json()["detail"]

    async def test_inactive_code_returns_404(self, client):
        await _insert_promo("TEST_INACTIVE", "starter", active=False)
        resp = await client.post("/stripe/promocode/redeem", json={"code": "TEST_INACTIVE"})
        assert resp.status_code == 404

    async def test_exhausted_code_returns_409(self, client):
        await _insert_promo("TEST_EXHAUSTED", "starter", max_redemptions=1, redemption_count=1)
        resp = await client.post("/stripe/promocode/redeem", json={"code": "TEST_EXHAUSTED"})
        assert resp.status_code == 409
        assert "no longer available" in resp.json()["detail"]

    async def test_double_redeem_returns_409(self, client):
        await _insert_promo("TEST_DOUBLE", "starter")
        r1 = await client.post("/stripe/promocode/redeem", json={"code": "TEST_DOUBLE"})
        assert r1.status_code == 200
        r2 = await client.post("/stripe/promocode/redeem", json={"code": "TEST_DOUBLE"})
        assert r2.status_code == 409
        assert "already used" in r2.json()["detail"]

    async def test_promo_lower_than_current_returns_409(self, client, test_user):
        # Upgrade user to pro first
        async with _pg.AsyncSessionLocal() as session:
            u = await session.get(User, test_user.id)
            u.subscription_status = "pro"
            await session.commit()

        await _insert_promo("TEST_DOWNGRADE", "starter")
        resp = await client.post("/stripe/promocode/redeem", json={"code": "TEST_DOWNGRADE"})
        assert resp.status_code == 409
        assert "would not upgrade" in resp.json()["detail"]

    async def test_rate_limit_6th_attempt_returns_429(self, client):
        """First 5 invalid attempts should return 404; 6th must return 429."""
        for i in range(5):
            resp = await client.post("/stripe/promocode/redeem", json={"code": f"TEST_RATE_{i}"})
            assert resp.status_code == 404, f"Expected 404 on attempt {i}, got {resp.status_code}"
        resp6 = await client.post("/stripe/promocode/redeem", json={"code": "TEST_RATE_5"})
        assert resp6.status_code == 429
        assert "Too many attempts" in resp6.json()["detail"]

    async def test_redemption_count_incremented(self, client):
        await _insert_promo("TEST_COUNT", "starter")
        await client.post("/stripe/promocode/redeem", json={"code": "TEST_COUNT"})
        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(Promocode).where(Promocode.code == "TEST_COUNT"))
            promo = result.scalar_one()
        assert promo.redemption_count == 1
