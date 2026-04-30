"""Integration tests for the promocode system and free-tier bump (NEO-2874).

Uses real PostgreSQL (vitreon_legal_test) — no DB mocking.
External calls (Stripe, corpus count) are mocked.

Run: uv run pytest tests/integration/test_promocodes.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

pytestmark = pytest.mark.asyncio(loop_scope="module")

import neolex.db.postgres as pg
from neolex.auth import email_auth
from neolex.auth.session import create_session
from neolex.config import settings
from neolex.db.models import Promocode, PromocodeRedemption, User
from neolex.routers import stripe_router

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_app_billing() -> FastAPI:
    """FastAPI test app with auth + billing routers."""
    from starlette.middleware.sessions import SessionMiddleware

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(email_auth.router)
    app.include_router(stripe_router.router)
    return app


@pytest.fixture(scope="module")
async def billing_client(test_app_billing) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=test_app_billing),
        base_url="http://test",
        follow_redirects=False,
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Per-test env patches
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def dev_mode_on(monkeypatch):
    monkeypatch.setattr(settings, "dev_mode", True)


@pytest.fixture(autouse=True)
async def no_rate_limit():
    with patch("neolex.auth.email_auth._auth_rate_check", new_callable=AsyncMock):
        yield


@pytest.fixture(autouse=True)
async def mock_email_services():
    with (
        patch("neolex.auth.email_auth.send_verification_email", new_callable=AsyncMock) as mv,
        patch("neolex.auth.email_auth.send_password_reset_email", new_callable=AsyncMock) as mr,
    ):
        yield mv, mr


@pytest.fixture(autouse=True)
async def mock_stripe_corpus():
    """Mock corpus counting and stripe calls used by billing_status."""
    with (
        patch("neolex.routers.stripe_router.asyncio.to_thread", new_callable=AsyncMock, return_value=[]),
        patch("neolex.routers.stripe_router.stripe"),
    ):
        yield


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _test_email() -> str:
    return f"inttest_promo_{uuid.uuid4().hex[:10]}@example.com"


async def _make_user(email: str, subscription_status: str = "free") -> User:
    """Insert a verified user directly into the DB."""
    async with pg.AsyncSessionLocal() as db:
        user = User(
            email=email,
            name="Promo Tester",
            email_verified=True,
            subscription_status=subscription_status,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _make_session_cookie(user: User, client: AsyncClient) -> None:
    """Insert a session and set the session cookie on the client."""
    async with pg.AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == user.email))
        fresh_user = result.scalar_one()
        token = await create_session(fresh_user, db, ip="127.0.0.1")
    client.cookies.set(settings.session_cookie_name, token)


async def _insert_promocode(
    code: str,
    tier: str = "starter",
    duration_days: int = 30,
    max_redemptions: int | None = None,
    valid_until: datetime | None = None,
    active: bool = True,
) -> Promocode:
    async with pg.AsyncSessionLocal() as db:
        promo = Promocode(
            code=code,
            tier=tier,
            duration_days=duration_days,
            max_redemptions=max_redemptions,
            valid_until=valid_until,
            active=active,
        )
        db.add(promo)
        await db.commit()
        await db.refresh(promo)
        return promo


@pytest.fixture(autouse=True)
async def cleanup():
    """Delete test users + promocodes before and after each test."""

    async def _clean():
        async with pg.AsyncSessionLocal() as db:
            await db.execute(delete(User).where(User.email.like("inttest_promo_%@example.com")))
            await db.execute(delete(Promocode).where(Promocode.code.like("TEST_%")))
            await db.commit()

    await _clean()
    yield
    await _clean()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_user_fresh(user_id) -> User:
    async with pg.AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Free tier bump: default is 10, not 3
# ---------------------------------------------------------------------------


def test_free_daily_limit_is_10():
    """Config default must be 10 after the bump."""
    assert settings.free_daily_limit == 10


# ---------------------------------------------------------------------------
# effective_subscription_tier helper
# ---------------------------------------------------------------------------


def test_effective_tier_no_promo():
    from neolex.services.billing import effective_subscription_tier

    user = User(subscription_status="free", promo_tier=None, promo_expires_at=None)
    assert effective_subscription_tier(user) == "free"


def test_effective_tier_active_promo_outranks_free():
    from neolex.services.billing import effective_subscription_tier

    user = User(
        subscription_status="free",
        promo_tier="starter",
        promo_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert effective_subscription_tier(user) == "starter"


def test_effective_tier_expired_promo_clears_and_returns_paid():
    from neolex.services.billing import effective_subscription_tier

    user = User(
        subscription_status="free",
        promo_tier="pro",
        promo_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    result = effective_subscription_tier(user)
    assert result == "free"
    assert user.promo_tier is None
    assert user.promo_expires_at is None


def test_effective_tier_promo_does_not_override_higher_paid():
    from neolex.services.billing import effective_subscription_tier

    user = User(
        subscription_status="pro",
        promo_tier="starter",
        promo_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert effective_subscription_tier(user) == "pro"


# ---------------------------------------------------------------------------
# Redemption endpoint: success
# ---------------------------------------------------------------------------


async def test_redeem_success(billing_client):
    """Successful redemption sets promo_tier on user and returns updated billing status."""
    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)
    promo = await _insert_promocode("TEST_HIVITREON", tier="starter", duration_days=30)

    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_HIVITREON"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["plan"] == "starter"
    assert data["promo_tier"] == "starter"
    assert data["promo_expires_at"] is not None

    # Verify DB state
    fresh = await _get_user_fresh(user.id)
    assert fresh.promo_tier == "starter"
    assert fresh.promo_expires_at is not None

    # Verify redemption row
    async with pg.AsyncSessionLocal() as db:
        result = await db.execute(
            select(PromocodeRedemption).where(
                PromocodeRedemption.promocode_id == promo.id,
                PromocodeRedemption.user_id == user.id,
            )
        )
        redemption = result.scalar_one_or_none()
    assert redemption is not None
    assert redemption.granted_tier == "starter"

    billing_client.cookies.clear()


# ---------------------------------------------------------------------------
# Redemption endpoint: invalid / expired code → 404
# ---------------------------------------------------------------------------


async def test_redeem_unknown_code_404(billing_client):
    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)

    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_DOES_NOT_EXIST"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Invalid promocode"

    billing_client.cookies.clear()


async def test_redeem_inactive_code_404(billing_client):
    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)
    await _insert_promocode("TEST_INACTIVE", active=False)

    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_INACTIVE"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Invalid promocode"

    billing_client.cookies.clear()


async def test_redeem_expired_code_404(billing_client):
    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)
    past = datetime.now(UTC) - timedelta(days=1)
    await _insert_promocode("TEST_EXPIRED", valid_until=past)

    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_EXPIRED"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Invalid promocode"

    billing_client.cookies.clear()


# ---------------------------------------------------------------------------
# Redemption endpoint: exhausted code → 409
# ---------------------------------------------------------------------------


async def test_redeem_exhausted_code_409(billing_client):
    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)
    await _insert_promocode("TEST_EXHAUSTED", max_redemptions=0)

    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_EXHAUSTED"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Promocode no longer available"

    billing_client.cookies.clear()


# ---------------------------------------------------------------------------
# Redemption endpoint: double-redeem → 409
# ---------------------------------------------------------------------------


async def test_redeem_double_redeem_409(billing_client):
    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)
    await _insert_promocode("TEST_DOUBLE", tier="starter", duration_days=30)

    resp1 = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_DOUBLE"})
    assert resp1.status_code == 200

    resp2 = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_DOUBLE"})
    assert resp2.status_code == 409
    assert resp2.json()["detail"] == "You have already used this promocode"

    billing_client.cookies.clear()


# ---------------------------------------------------------------------------
# Redemption endpoint: downgrade / same tier → 409
# ---------------------------------------------------------------------------


async def test_redeem_downgrade_rejected_409(billing_client):
    """Starter code rejected for Pro users — no downgrade."""
    email = _test_email()
    user = await _make_user(email, subscription_status="pro")
    await _make_session_cookie(user, billing_client)
    await _insert_promocode("TEST_DOWNGRADE", tier="starter", duration_days=30)

    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_DOWNGRADE"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "This promocode would not upgrade your plan"

    billing_client.cookies.clear()


async def test_redeem_same_tier_rejected_409(billing_client):
    """Starter code rejected for Starter users — not an upgrade."""
    email = _test_email()
    user = await _make_user(email, subscription_status="starter")
    await _make_session_cookie(user, billing_client)
    await _insert_promocode("TEST_SAME", tier="starter", duration_days=30)

    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_SAME"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "This promocode would not upgrade your plan"

    billing_client.cookies.clear()


# ---------------------------------------------------------------------------
# Redemption endpoint: per-user rate limit → 429
# ---------------------------------------------------------------------------


async def test_redeem_rate_limit_429(billing_client):
    """6th attempt within the rate window must be rejected with 429."""
    from neolex.services import billing as billing_svc

    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)

    user_id_str = str(user.id)

    # Reset any leftover state for this user
    with billing_svc._promo_lock:
        billing_svc._promo_attempts[user_id_str] = []

    # Make 5 attempts (all 404 for invalid code, but rate counter is incremented)
    for _ in range(5):
        await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_NONEXISTENT"})

    # 6th attempt must be 429
    resp = await billing_client.post("/stripe/promocode/redeem", json={"code": "TEST_NONEXISTENT"})
    assert resp.status_code == 429
    assert "Too many" in resp.json()["detail"]

    # Cleanup rate state
    with billing_svc._promo_lock:
        billing_svc._promo_attempts.pop(user_id_str, None)

    billing_client.cookies.clear()


# ---------------------------------------------------------------------------
# billing_status returns promo fields
# ---------------------------------------------------------------------------


async def test_billing_status_includes_promo_fields(billing_client):
    """billing_status must include promo_tier and promo_expires_at."""
    email = _test_email()
    user = await _make_user(email)
    await _make_session_cookie(user, billing_client)

    resp = await billing_client.get("/stripe/billing-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "promo_tier" in data
    assert "promo_expires_at" in data
    assert data["promo_tier"] is None
    assert data["promo_expires_at"] is None

    billing_client.cookies.clear()
