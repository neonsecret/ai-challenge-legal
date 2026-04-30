"""Promocode system tests (NEO-2874)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from neolex.db.models import Promocode, User
from neolex.services.billing import effective_subscription_tier

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def app_client():
    """Create a test client with proper auth mocking."""
    from fastapi import FastAPI

    from neolex.auth.session import get_current_user
    from neolex.routers.stripe_router import router

    app = FastAPI()
    app.include_router(router)

    # Mock user
    test_user = User(
        email="promotest@example.com",
        subscription_status="free",
        daily_queries_used=0,
    )

    async def mock_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = mock_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, test_user

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TestPromocodeRedeem
# ---------------------------------------------------------------------------


class TestPromocodeRedeem:
    """POST /api/billing/promocode/redeem"""

    async def test_successful_redemption_free_user(self, app_client, db_session):
        """Valid code, free user → 200, tier updated."""
        client, user = app_client

        # Create a test promocode
        promo = Promocode(
            code="TESTFREE",
            tier="starter",
            duration_days=30,
            active=True,
            valid_until=datetime.now(UTC) + timedelta(days=365),
        )
        db_session.add(promo)
        await db_session.commit()

        # Redeem
        resp = await client.post(
            "/api/billing/promocode/redeem",
            json={"code": "TESTFREE"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["subscription_status"] == "starter" or "promo_tier" in data

    async def test_invalid_code_returns_404(self, app_client):
        """Unknown code → 404 generic message."""
        client, _ = app_client
        resp = await client.post(
            "/api/billing/promocode/redeem",
            json={"code": "INVALID_CODE_123"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "Invalid promocode" in resp.json()["detail"]

    async def test_expired_code_returns_404(self, app_client, db_session):
        """Expired code → 404 generic message."""
        client, _ = app_client

        promo = Promocode(
            code="EXPIRED",
            tier="starter",
            duration_days=30,
            active=True,
            valid_until=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.add(promo)
        await db_session.commit()

        resp = await client.post(
            "/api/billing/promocode/redeem",
            json={"code": "EXPIRED"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "Invalid promocode" in resp.json()["detail"]

    async def test_exhausted_redemptions_returns_409(self, app_client, db_session):
        """Max redemptions reached → 409."""
        client, _ = app_client

        promo = Promocode(
            code="LIMITED",
            tier="starter",
            duration_days=30,
            max_redemptions=1,
            redemption_count=1,
            active=True,
            valid_until=datetime.now(UTC) + timedelta(days=365),
        )
        db_session.add(promo)
        await db_session.commit()

        resp = await client.post(
            "/api/billing/promocode/redeem",
            json={"code": "LIMITED"},
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "no longer available" in resp.json()["detail"]

    async def test_double_redeem_same_user_returns_409(self, app_client, db_session):
        """Same user redeeming twice → 409."""
        client, user = app_client

        # Create promo
        promo = Promocode(
            code="DOUBLE",
            tier="starter",
            duration_days=30,
            active=True,
            valid_until=datetime.now(UTC) + timedelta(days=365),
        )
        db_session.add(promo)
        await db_session.commit()

        # First redemption
        resp1 = await client.post(
            "/api/billing/promocode/redeem",
            json={"code": "DOUBLE"},
        )
        assert resp1.status_code == status.HTTP_200_OK

        # Second redemption
        resp2 = await client.post(
            "/api/billing/promocode/redeem",
            json={"code": "DOUBLE"},
        )
        assert resp2.status_code == status.HTTP_409_CONFLICT
        assert "already used" in resp2.json()["detail"]

    async def test_promo_tier_lower_than_current_returns_409(self, app_client, db_session):
        """Promo tier <= current tier → 409."""
        client, user = app_client

        # Create promo with free tier
        promo = Promocode(
            code="DOWNGRADE",
            tier="free",
            duration_days=30,
            active=True,
            valid_until=datetime.now(UTC) + timedelta(days=365),
        )
        db_session.add(promo)
        await db_session.commit()

        # Set user to starter
        user.subscription_status = "starter"
        await db_session.commit()

        resp = await client.post(
            "/api/billing/promocode/redeem",
            json={"code": "DOWNGRADE"},
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "would not upgrade" in resp.json()["detail"]

    async def test_rate_limit_6th_attempt_returns_429(self, app_client):
        """5 attempts/hour limit → 429 on 6th."""
        client, _ = app_client

        for i in range(6):
            resp = await client.post(
                "/api/billing/promocode/redeem",
                json={"code": f"RATE{i}"},
            )
            if i < 5:
                assert resp.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_429_TOO_MANY_REQUESTS)
            else:
                assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                assert "Too many attempts" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# TestEffectiveSubscriptionTier
# ---------------------------------------------------------------------------


class TestEffectiveSubscriptionTier:
    """Unit tests for effective_subscription_tier() helper."""

    async def test_paid_wins_over_lower_promo(self, db_session):
        """Paid starter > promo free."""
        user = User(
            email="test@example.com",
            subscription_status="starter",
            promo_tier="free",
            promo_expires_at=datetime.now(UTC) + timedelta(days=10),
        )
        assert effective_subscription_tier(user) == "starter"

    async def test_promo_wins_over_free(self, db_session):
        """Promo starter > free."""
        user = User(
            email="test2@example.com",
            subscription_status="free",
            promo_tier="starter",
            promo_expires_at=datetime.now(UTC) + timedelta(days=10),
        )
        assert effective_subscription_tier(user) == "starter"

    async def test_expired_promo_falls_back_to_paid(self, db_session):
        """Expired promo → paid tier."""
        user = User(
            email="test3@example.com",
            subscription_status="free",
            promo_tier="starter",
            promo_expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert effective_subscription_tier(user) == "free"
