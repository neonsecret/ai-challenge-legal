"""Stripe billing test suite.

Tests all routes in neolex/routers/stripe_router.py.
Uses real PostgreSQL DB with NullPool (no cross-loop connection reuse).
All Stripe SDK calls are mocked — no real Stripe API calls.

Run with:
    uv run pytest tests/neolex/test_billing.py -v
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import neolex.db.postgres as _pg
from neolex.auth.session import get_current_user
from neolex.config import settings
from neolex.db.models import Invoice, Subscription, User
from neolex.db.postgres import get_db, init_db
from neolex.routers.stripe_router import _processed_events

# ---------------------------------------------------------------------------
# Known test price IDs — injected into router price maps for all tests
# ---------------------------------------------------------------------------

_STARTER_M = "price_test_starter_m"
_PRO_M = "price_test_pro_m"
_ENTERPRISE_M = "price_test_enterprise_m"
_STARTER_BW = "price_test_starter_bw"
_PRO_BW = "price_test_pro_bw"
_ENTERPRISE_BW = "price_test_enterprise_bw"

_TEST_PRICE_MAP: dict[tuple[str, str], str] = {
    ("starter", "monthly"): _STARTER_M,
    ("pro", "monthly"): _PRO_M,
    ("enterprise", "monthly"): _ENTERPRISE_M,
    ("starter", "biweekly"): _STARTER_BW,
    ("pro", "biweekly"): _PRO_BW,
    ("enterprise", "biweekly"): _ENTERPRISE_BW,
}


# ---------------------------------------------------------------------------
# NullPool engine — must be installed before any DB interaction
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def install_null_pool_billing_engine():
    """Replace global SQLAlchemy engine with NullPool to prevent cross-loop reuse."""
    _db_url = _pg._db_url
    test_engine = create_async_engine(_db_url, poolclass=NullPool)
    test_sessions = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    old_engine = _pg.engine
    old_sessions = _pg.AsyncSessionLocal

    _pg.engine = test_engine
    _pg.AsyncSessionLocal = test_sessions

    yield

    _pg.engine = old_engine
    _pg.AsyncSessionLocal = old_sessions


@pytest.fixture(scope="session", autouse=True)
def ensure_billing_schema(install_null_pool_billing_engine):  # noqa: ARG001
    """Create all tables once for the test session."""
    asyncio.run(init_db())


# ---------------------------------------------------------------------------
# Price map injection — populate router dicts with known test price IDs
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def inject_test_prices(ensure_billing_schema):  # noqa: ARG001
    """Populate stripe_router price maps with deterministic test price IDs."""
    from neolex.routers import stripe_router

    saved_price_to_plan = dict(stripe_router._PRICE_TO_PLAN)
    saved_plan_to_price = dict(stripe_router._PLAN_INTERVAL_TO_PRICE)

    stripe_router._PRICE_TO_PLAN.clear()
    stripe_router._PLAN_INTERVAL_TO_PRICE.clear()

    for (plan, interval), price_id in _TEST_PRICE_MAP.items():
        stripe_router._PRICE_TO_PLAN[price_id] = plan
        stripe_router._PLAN_INTERVAL_TO_PRICE[(plan, interval)] = price_id

    yield

    stripe_router._PRICE_TO_PLAN.clear()
    stripe_router._PLAN_INTERVAL_TO_PRICE.clear()
    stripe_router._PRICE_TO_PLAN.update(saved_price_to_plan)
    stripe_router._PLAN_INTERVAL_TO_PRICE.update(saved_plan_to_price)


# ---------------------------------------------------------------------------
# Minimal FastAPI test app (billing-only, no pipeline startup)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def billing_app() -> FastAPI:
    """FastAPI app with only the Stripe router — no pipeline, no auth middleware."""
    from neolex.routers.stripe_router import router

    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# DB session and user fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def unique_email() -> str:
    return f"billing_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def test_user(unique_email: str) -> User:
    """Free-tier user with no Stripe customer ID."""
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


@pytest.fixture
async def test_user_with_customer(unique_email: str) -> User:
    """Starter-tier user with an existing Stripe customer ID."""
    user = User(
        email=unique_email,
        email_verified=True,
        subscription_status="starter",
        max_corpora=settings.starter_max_corpora,
        stripe_customer_id="cus_test_existing",
    )
    async with _pg.AsyncSessionLocal() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest.fixture(autouse=True)
async def cleanup_test_users():
    """Delete all billing-test users after each test (cascades to subs/invoices)."""
    yield
    async with _pg.AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.email.like("billing_test_%@example.com")))
        await session.commit()


@pytest.fixture(autouse=True)
def clear_processed_events():
    """Reset idempotency cache between tests."""
    _processed_events.clear()
    yield
    _processed_events.clear()


# ---------------------------------------------------------------------------
# HTTP clients — auth overridden to inject a specific user via the request DB session
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(billing_app: FastAPI, test_user: User) -> AsyncClient:
    """Client that authenticates as test_user (free plan)."""
    user_id = test_user.id

    async def _auth(db: AsyncSession = Depends(get_db)) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    billing_app.dependency_overrides[get_current_user] = _auth
    async with AsyncClient(transport=ASGITransport(app=billing_app), base_url="http://test") as c:
        yield c
    billing_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def client_with_customer(billing_app: FastAPI, test_user_with_customer: User) -> AsyncClient:
    """Client that authenticates as test_user_with_customer (starter plan + stripe customer)."""
    user_id = test_user_with_customer.id

    async def _auth(db: AsyncSession = Depends(get_db)) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    billing_app.dependency_overrides[get_current_user] = _auth
    async with AsyncClient(transport=ASGITransport(app=billing_app), base_url="http://test") as c:
        yield c
    billing_app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_subscription(
    user_id: uuid.UUID,
    stripe_sub_id: str = "sub_test",
    stripe_price_id: str = _STARTER_M,
    status: str = "active",
    cancel_at_period_end: bool = False,
) -> Subscription:
    """Insert a Subscription row and return it (detached from any session)."""
    now = datetime.now(UTC)
    sub = Subscription(
        user_id=user_id,
        stripe_subscription_id=stripe_sub_id,
        stripe_price_id=stripe_price_id,
        status=status,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_at_period_end=cancel_at_period_end,
    )
    async with _pg.AsyncSessionLocal() as session:
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
    return sub


def _fake_event(event_type: str, data_obj: dict, event_id: str = "evt_test_001") -> MagicMock:
    """Build a MagicMock Stripe event as returned by stripe.Webhook.construct_event.

    data_obj is a plain dict — stripe_router._serialize() handles it via isinstance(obj, dict).
    """
    event = MagicMock()
    event.id = event_id
    event.type = event_type
    event.data.object = data_obj
    return event


@pytest.fixture
def mock_get_collection_names():
    """Patch get_collection_names to return an empty set (no corpora on disk)."""
    with patch("neolex.services.document_manager.get_collection_names", return_value=set()):
        yield


# ---------------------------------------------------------------------------
# 1. Webhook handler — event routing and idempotency
# ---------------------------------------------------------------------------


class TestWebhookHandler:
    """POST /stripe/webhook"""

    async def _post(self, client: AsyncClient, event: MagicMock) -> ...:
        with patch("neolex.routers.stripe_router.stripe.Webhook.construct_event", return_value=event):
            return await client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "sig_test"},
            )

    async def test_checkout_session_completed_creates_subscription(self, client: AsyncClient, test_user: User):
        """checkout.session.completed → user plan updated, Subscription row created."""
        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == test_user.id))
            u = result.scalar_one()
            u.stripe_customer_id = "cus_checkout_001"
            await session.commit()

        data_obj = {
            "customer": "cus_checkout_001",
            "subscription": "sub_checkout_001",
            "metadata": {"plan": "starter", "interval": "monthly"},
        }
        event = _fake_event("checkout.session.completed", data_obj)

        fake_item = MagicMock()
        fake_item.price.id = _STARTER_M
        fake_item.current_period_start = 1700000000
        fake_item.current_period_end = 1702592000
        fake_sub = MagicMock()
        fake_sub.items.data = [fake_item]
        fake_sub.start_date = 1700000000
        fake_sub.cancel_at_period_end = False

        with patch("neolex.routers.stripe_router.stripe.Subscription.retrieve", return_value=fake_sub):
            resp = await self._post(client, event)

        assert resp.status_code == 200

        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == test_user.id))
            u = result.scalar_one()
            assert u.subscription_status == "starter"

            sub = (
                await session.execute(
                    select(Subscription).where(Subscription.stripe_subscription_id == "sub_checkout_001")
                )
            ).scalar_one_or_none()
            assert sub is not None
            assert sub.status == "active"

    async def test_subscription_updated_active_updates_plan(self, client: AsyncClient, test_user: User):
        """customer.subscription.updated (status=active) → plan updated in DB."""
        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == test_user.id))
            u = result.scalar_one()
            u.stripe_customer_id = "cus_upd_001"
            u.subscription_status = "starter"
            await session.commit()

        await _seed_subscription(test_user.id, stripe_sub_id="sub_upd_001")

        data_obj = {
            "id": "sub_upd_001",
            "customer": "cus_upd_001",
            "status": "active",
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": _PRO_M}, "current_period_end": 1702592000}]},
        }
        resp = await self._post(client, _fake_event("customer.subscription.updated", data_obj, "evt_upd_001"))
        assert resp.status_code == 200

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            assert u.subscription_status == "pro"

    async def test_subscription_updated_past_due_revokes_access(self, client: AsyncClient, test_user: User):
        """customer.subscription.updated (status=past_due) → access preserved during retry window, payment_warning=True.

        Stripe retries failed payments for ~7 days before firing customer.subscription.deleted.
        We do NOT revoke access immediately on past_due — only flag payment_warning so the
        UI can surface a warning banner. Actual revocation happens on customer.subscription.deleted.
        """
        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == test_user.id))
            u = result.scalar_one()
            u.stripe_customer_id = "cus_past_001"
            u.subscription_status = "starter"
            u.max_corpora = settings.starter_max_corpora
            u.payment_warning = False
            await session.commit()

        await _seed_subscription(test_user.id, stripe_sub_id="sub_past_001")

        data_obj = {
            "id": "sub_past_001",
            "customer": "cus_past_001",
            "status": "past_due",
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": _STARTER_M}, "current_period_end": 1702592000}]},
        }
        resp = await self._post(client, _fake_event("customer.subscription.updated", data_obj, "evt_past_001"))
        assert resp.status_code == 200

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            # Access preserved — Stripe retry window still active
            assert u.subscription_status == "starter"
            assert u.max_corpora == settings.starter_max_corpora
            # Warning flag set so the UI can surface a payment-failure banner
            assert u.payment_warning is True

    async def test_subscription_deleted_revokes_access_and_schedules_cleanup(
        self, client: AsyncClient, test_user: User
    ):
        """customer.subscription.deleted (no other active sub) → access revoked, 7-day grace period scheduled.

        Since NEO-300, corpus deletion is deferred by 7 days (NEO-300):
        1. _delete_user_corpora is NOT called immediately
        2. corpus_deletion_scheduled_at is set ~7 days in the future
        3. subscription_status reverts to "canceled", max_corpora set to 0
        4. Warning email (send_corpus_deletion_warning_email) is dispatched
        """
        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == test_user.id))
            u = result.scalar_one()
            u.stripe_customer_id = "cus_del_001"
            u.subscription_status = "starter"
            u.max_corpora = settings.starter_max_corpora
            await session.commit()

        await _seed_subscription(test_user.id, stripe_sub_id="sub_del_001")

        data_obj = {
            "id": "sub_del_001",
            "customer": "cus_del_001",
            "status": "canceled",
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": _STARTER_M}, "current_period_end": 1702592000}]},
        }

        before = datetime.now(UTC)
        with (
            patch("neolex.routers.stripe_router._delete_user_corpora", new_callable=AsyncMock) as mock_cleanup,
            patch("neolex.auth.email_service.send_corpus_deletion_warning_email", new_callable=AsyncMock) as mock_email,
        ):
            resp = await self._post(client, _fake_event("customer.subscription.deleted", data_obj, "evt_del_001"))
        after = datetime.now(UTC)

        assert resp.status_code == 200

        # 1. Corpus deletion NOT triggered synchronously — grace period instead
        mock_cleanup.assert_not_called()

        # 4. Warning email dispatched (fire-and-forget via asyncio.create_task)
        mock_email.assert_called_once()

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            # 3. Access revoked
            assert u.subscription_status == "canceled"
            assert u.max_corpora == 0
            # 2. Grace period: corpus deletion scheduled ~7 days out
            assert u.corpus_deletion_scheduled_at is not None
            expected_min = before + timedelta(days=6, hours=23)
            expected_max = after + timedelta(days=7, hours=1)
            assert expected_min <= u.corpus_deletion_scheduled_at <= expected_max

    async def test_subscription_deleted_with_other_active_sub_does_not_revoke(
        self, client: AsyncClient, test_user: User
    ):
        """customer.subscription.deleted — another active sub exists → access NOT revoked (upgrade scenario)."""
        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == test_user.id))
            u = result.scalar_one()
            u.stripe_customer_id = "cus_upg_001"
            u.subscription_status = "pro"
            u.max_corpora = settings.pro_max_corpora
            await session.commit()

        # Old sub (being canceled) and new sub (already active from upgrade)
        await _seed_subscription(test_user.id, stripe_sub_id="sub_old_001", status="active")
        await _seed_subscription(test_user.id, stripe_sub_id="sub_new_001", stripe_price_id=_PRO_M, status="active")

        data_obj = {
            "id": "sub_old_001",
            "customer": "cus_upg_001",
            "status": "canceled",
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": _STARTER_M}, "current_period_end": 1702592000}]},
        }
        resp = await self._post(client, _fake_event("customer.subscription.deleted", data_obj, "evt_upg_001"))
        assert resp.status_code == 200

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            assert u.subscription_status == "pro"
            assert u.max_corpora == settings.pro_max_corpora

    async def test_invoice_paid_inserts_invoice_row(self, client: AsyncClient, test_user: User):
        """invoice.paid → Invoice row inserted with correct amounts."""
        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            u.stripe_customer_id = "cus_inv_001"
            await session.commit()

        data_obj = {"id": "inv_001", "customer": "cus_inv_001", "amount_paid": 2900, "currency": "usd"}
        resp = await self._post(client, _fake_event("invoice.paid", data_obj, "evt_inv_001"))
        assert resp.status_code == 200

        async with _pg.AsyncSessionLocal() as session:
            inv = (
                await session.execute(select(Invoice).where(Invoice.stripe_invoice_id == "inv_001"))
            ).scalar_one_or_none()
            assert inv is not None
            assert inv.amount_cents == 2900
            assert inv.currency == "usd"
            assert inv.status == "paid"

    async def test_invoice_payment_failed_does_not_revoke_access(self, client: AsyncClient, test_user: User):
        """invoice.payment_failed → warning logged, subscription_status unchanged."""
        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            u.stripe_customer_id = "cus_fail_001"
            u.subscription_status = "starter"
            await session.commit()

        data_obj = {"id": "inv_fail_001", "customer": "cus_fail_001"}
        resp = await self._post(client, _fake_event("invoice.payment_failed", data_obj, "evt_fail_001"))
        assert resp.status_code == 200

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            assert u.subscription_status == "starter"  # NOT revoked

    async def test_duplicate_event_id_returns_duplicate_status(self, client: AsyncClient, test_user: User):
        """Same event ID sent twice → second response is {"status": "duplicate"}, no second DB write."""
        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            u.stripe_customer_id = "cus_dup_001"
            await session.commit()

        data_obj = {"id": "inv_dup_001", "customer": "cus_dup_001", "amount_paid": 1000, "currency": "usd"}
        event = _fake_event("invoice.paid", data_obj, event_id="evt_dup_unique")

        with patch("neolex.routers.stripe_router.stripe.Webhook.construct_event", return_value=event):
            r1 = await client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "s"})
            r2 = await client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "s"})

        assert r1.status_code == 200
        assert r1.json().get("received") is True
        assert r2.status_code == 200
        assert r2.json() == {"status": "duplicate"}

        # Invoice row must exist exactly once
        async with _pg.AsyncSessionLocal() as session:
            rows = (
                (await session.execute(select(Invoice).where(Invoice.stripe_invoice_id == "inv_dup_001")))
                .scalars()
                .all()
            )
            assert len(rows) == 1

    async def test_invalid_stripe_signature_returns_400(self, client: AsyncClient):
        """Invalid Stripe signature → 400."""
        import stripe as _stripe

        with patch(
            "neolex.routers.stripe_router.stripe.Webhook.construct_event",
            side_effect=_stripe.SignatureVerificationError("bad sig", ""),
        ):
            resp = await client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "bad"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 2. POST /stripe/create-checkout-session
# ---------------------------------------------------------------------------


class TestCreateCheckoutSession:
    """POST /stripe/create-checkout-session"""

    _URL = "https://checkout.stripe.com/c/test_url"

    def _mock_session(self) -> MagicMock:
        s = MagicMock()
        s.url = self._URL
        return s

    async def test_valid_plan_returns_checkout_url(self, client: AsyncClient):
        with (
            patch("neolex.routers.stripe_router.stripe.Customer.create", return_value=MagicMock(id="cus_new")),
            patch("neolex.routers.stripe_router.stripe.checkout.Session.create", return_value=self._mock_session()),
            patch.object(settings, "stripe_enabled", True),
        ):
            resp = await client.post("/stripe/create-checkout-session", json={"plan": "starter", "interval": "monthly"})
        assert resp.status_code == 200
        assert resp.json()["url"] == self._URL

    async def test_invalid_plan_returns_400(self, client: AsyncClient):
        with patch.object(settings, "stripe_enabled", True):
            resp = await client.post(
                "/stripe/create-checkout-session",
                json={"plan": "superplan", "interval": "monthly"},
            )
        assert resp.status_code == 400
        assert "Invalid plan" in resp.json()["detail"]

    async def test_invalid_interval_returns_400(self, client: AsyncClient):
        with patch.object(settings, "stripe_enabled", True):
            resp = await client.post(
                "/stripe/create-checkout-session",
                json={"plan": "starter", "interval": "yearly"},
            )
        assert resp.status_code == 400
        assert "Invalid interval" in resp.json()["detail"]

    async def test_no_price_for_plan_interval_returns_400(self, client: AsyncClient):
        """Removing a price for a specific interval → 400 with "No price configured"."""
        from neolex.routers import stripe_router

        key = ("starter", "biweekly")
        saved = stripe_router._PLAN_INTERVAL_TO_PRICE.pop(key, None)
        try:
            with patch.object(settings, "stripe_enabled", True):
                resp = await client.post(
                    "/stripe/create-checkout-session",
                    json={"plan": "starter", "interval": "biweekly"},
                )
        finally:
            if saved is not None:
                stripe_router._PLAN_INTERVAL_TO_PRICE[key] = saved

        assert resp.status_code == 400
        assert "No price configured" in resp.json()["detail"]

    async def test_no_stripe_customer_id_creates_customer(self, client: AsyncClient, test_user: User):
        """User with no stripe_customer_id → stripe.Customer.create called, ID persisted."""
        mock_create = MagicMock(id="cus_brand_new")
        with (
            patch("neolex.routers.stripe_router.stripe.Customer.create", return_value=mock_create) as spy,
            patch("neolex.routers.stripe_router.stripe.checkout.Session.create", return_value=self._mock_session()),
            patch.object(settings, "stripe_enabled", True),
        ):
            resp = await client.post(
                "/stripe/create-checkout-session",
                json={"plan": "pro", "interval": "monthly"},
            )
        assert resp.status_code == 200
        spy.assert_called_once()

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            assert u.stripe_customer_id == "cus_brand_new"

    async def test_existing_stripe_customer_id_skips_create(self, client_with_customer: AsyncClient):
        """User already has stripe_customer_id → stripe.Customer.create NOT called."""
        with (
            patch("neolex.routers.stripe_router.stripe.Customer.create") as spy,
            patch("neolex.routers.stripe_router.stripe.checkout.Session.create", return_value=self._mock_session()),
            patch.object(settings, "stripe_enabled", True),
        ):
            resp = await client_with_customer.post(
                "/stripe/create-checkout-session",
                json={"plan": "pro", "interval": "monthly"},
            )
        assert resp.status_code == 200
        spy.assert_not_called()

    async def test_active_subscription_passes_previous_id_in_metadata(
        self, client_with_customer: AsyncClient, test_user_with_customer: User
    ):
        """Active existing subscription → previous_subscription_id included in checkout metadata."""
        await _seed_subscription(test_user_with_customer.id, stripe_sub_id="sub_prev_001")

        captured: dict = {}

        def _capture(**kwargs):
            captured.update(kwargs)
            return self._mock_session()

        with (
            patch("neolex.routers.stripe_router.stripe.checkout.Session.create", side_effect=_capture),
            patch.object(settings, "stripe_enabled", True),
        ):
            resp = await client_with_customer.post(
                "/stripe/create-checkout-session",
                json={"plan": "pro", "interval": "monthly"},
            )
        assert resp.status_code == 200
        assert captured.get("metadata", {}).get("previous_subscription_id") == "sub_prev_001"

    async def test_stripe_disabled_returns_503(self, client: AsyncClient):
        with patch.object(settings, "stripe_enabled", False):
            resp = await client.post("/stripe/create-checkout-session", json={"plan": "starter", "interval": "monthly"})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 3. POST /stripe/cancel-subscription
# ---------------------------------------------------------------------------


class TestCancelSubscription:
    """POST /stripe/cancel-subscription"""

    async def test_active_subscription_sets_cancel_at_period_end(
        self, client_with_customer: AsyncClient, test_user_with_customer: User
    ):
        """Active Subscription → stripe.Subscription.modify called, DB record updated."""
        await _seed_subscription(test_user_with_customer.id, stripe_sub_id="sub_cancel_001")

        mock_stripe_sub = MagicMock()
        mock_stripe_sub.items.data = [MagicMock()]
        mock_stripe_sub.items.data[0].current_period_end = 1702592000

        with (
            patch("neolex.routers.stripe_router.stripe.Subscription.modify", return_value=mock_stripe_sub) as spy,
            patch.object(settings, "stripe_enabled", True),
        ):
            resp = await client_with_customer.post("/stripe/cancel-subscription")

        assert resp.status_code == 200
        spy.assert_called_once_with("sub_cancel_001", cancel_at_period_end=True)

        async with _pg.AsyncSessionLocal() as session:
            sub = (
                await session.execute(
                    select(Subscription).where(Subscription.stripe_subscription_id == "sub_cancel_001")
                )
            ).scalar_one()
            assert sub.cancel_at_period_end is True

    async def test_no_active_subscription_returns_400(self, client_with_customer: AsyncClient):
        """No Subscription row with status=active → 400."""
        with patch.object(settings, "stripe_enabled", True):
            resp = await client_with_customer.post("/stripe/cancel-subscription")
        assert resp.status_code == 400
        assert "No active subscription" in resp.json()["detail"]

    async def test_stripe_disabled_returns_503(self, client: AsyncClient):
        with patch.object(settings, "stripe_enabled", False):
            resp = await client.post("/stripe/cancel-subscription")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 4. POST /stripe/sync-subscription
# ---------------------------------------------------------------------------


class TestSyncSubscription:
    """POST /stripe/sync-subscription"""

    async def test_no_stripe_customer_id_returns_400(self, client: AsyncClient):
        """User with no stripe_customer_id → 400."""
        resp = await client.post("/stripe/sync-subscription")
        assert resp.status_code == 400
        assert "No billing account" in resp.json()["detail"]

    async def test_no_active_stripe_sub_downgrades_to_free(
        self, client_with_customer: AsyncClient, test_user_with_customer: User
    ):
        """No active Stripe subscription found → user.subscription_status set to free."""
        mock_subs = MagicMock()
        mock_subs.data = []

        with patch("neolex.routers.stripe_router.stripe.Subscription.list", return_value=mock_subs):
            resp = await client_with_customer.post("/stripe/sync-subscription")

        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user_with_customer.id))).scalar_one()
            assert u.subscription_status == "free"

    async def test_active_stripe_sub_resolves_plan_from_price(
        self, client_with_customer: AsyncClient, test_user_with_customer: User
    ):
        """Active Stripe subscription → plan resolved from price ID, user.subscription_status updated."""
        mock_item = MagicMock()
        mock_item.price.id = _PRO_M
        mock_sub = MagicMock()
        mock_sub.items.data = [mock_item]
        mock_subs = MagicMock()
        mock_subs.data = [mock_sub]

        with patch("neolex.routers.stripe_router.stripe.Subscription.list", return_value=mock_subs):
            resp = await client_with_customer.post("/stripe/sync-subscription")

        assert resp.status_code == 200
        assert resp.json()["plan"] == "pro"

        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user_with_customer.id))).scalar_one()
            assert u.subscription_status == "pro"
            assert u.max_corpora == settings.pro_max_corpora


# ---------------------------------------------------------------------------
# 5. GET /stripe/billing-status
# ---------------------------------------------------------------------------


class TestBillingStatus:
    """GET /stripe/billing-status"""

    async def test_free_plan_returns_daily_limit_and_zero_usage(self, client: AsyncClient, mock_get_collection_names):
        resp = await client.get("/stripe/billing-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert data["daily_queries_limit"] == 3
        assert data["daily_queries_used"] == 0
        assert data["corpora_used"] == 0

    async def test_enterprise_plan_uses_unlimited_sentinel(
        self, client: AsyncClient, test_user: User, mock_get_collection_names
    ):
        """Enterprise plan → daily_queries_limit == -1 (unlimited sentinel)."""
        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            u.subscription_status = "enterprise"
            u.max_corpora = settings.enterprise_max_corpora
            await session.commit()

        resp = await client.get("/stripe/billing-status")
        assert resp.status_code == 200
        assert resp.json()["plan"] == "enterprise"
        assert resp.json()["daily_queries_limit"] == -1

    async def test_unknown_subscription_status_normalizes_to_free(
        self, client: AsyncClient, test_user: User, mock_get_collection_names
    ):
        async with _pg.AsyncSessionLocal() as session:
            u = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
            u.subscription_status = "completely_unknown_status"
            await session.commit()

        resp = await client.get("/stripe/billing-status")
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"

    async def test_cancel_at_period_end_reflected_in_response(
        self, client_with_customer: AsyncClient, test_user_with_customer: User, mock_get_collection_names
    ):
        """Subscription with cancel_at_period_end=True → flag reflected in billing-status response."""
        await _seed_subscription(
            test_user_with_customer.id,
            stripe_sub_id="sub_cancel_flag",
            cancel_at_period_end=True,
        )
        resp = await client_with_customer.get("/stripe/billing-status")
        assert resp.status_code == 200
        assert resp.json()["cancel_at_period_end"] is True


# ---------------------------------------------------------------------------
# 6. Helper function unit tests (no HTTP)
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Unit tests for _plan_from_price and _max_corpora_for_plan."""

    def test_plan_from_price_known_ids_return_correct_plans(self):
        from neolex.routers.stripe_router import _plan_from_price

        assert _plan_from_price(_STARTER_M) == "starter"
        assert _plan_from_price(_PRO_M) == "pro"
        assert _plan_from_price(_ENTERPRISE_M) == "enterprise"
        assert _plan_from_price(_STARTER_BW) == "starter"
        assert _plan_from_price(_PRO_BW) == "pro"

    def test_plan_from_price_unknown_id_defaults_to_free(self):
        from neolex.routers.stripe_router import _plan_from_price

        assert _plan_from_price("price_totally_unknown_xyzzy") == "free"

    def test_max_corpora_for_plan_matches_settings(self):
        from neolex.routers.stripe_router import _max_corpora_for_plan

        assert _max_corpora_for_plan("free") == 0
        assert _max_corpora_for_plan("starter") == settings.starter_max_corpora
        assert _max_corpora_for_plan("pro") == settings.pro_max_corpora
        assert _max_corpora_for_plan("enterprise") == settings.enterprise_max_corpora

    def test_max_corpora_for_unknown_plan_defaults_to_free_limits(self):
        from neolex.routers.stripe_router import _max_corpora_for_plan

        assert _max_corpora_for_plan("unknown_plan") == 0
