"""Tests for NEO-491: send data-preserved email on re-subscription within grace period.

Covers:
  (a) _on_checkout_completed: email sent when corpus_deletion_scheduled_at was set
  (b) _on_checkout_completed: no email when corpus_deletion_scheduled_at was None
  (c) _on_subscription_changed (active): email sent when corpus_deletion_scheduled_at was set
  (d) _on_subscription_changed (active): no email when corpus_deletion_scheduled_at was None
  (e) email failure does not propagate (fire-and-forget)
  (f) send_resubscription_data_preserved_email HTML contains expected content
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STARTER_PRICE = "price_starter_m"


def _make_user(
    stripe_customer_id: str = "cus_test",
    corpus_deletion_scheduled_at: datetime | None = None,
) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "lawyer@example.com"
    user.stripe_customer_id = stripe_customer_id
    user.subscription_status = "canceled"
    user.max_corpora = 0
    user.payment_warning = False
    user.corpus_deletion_scheduled_at = corpus_deletion_scheduled_at
    user.daily_queries_used = 0
    user.daily_queries_reset_at = None
    return user


def _make_stripe_sub(price_id: str = _STARTER_PRICE) -> MagicMock:
    """Minimal Stripe Subscription object with items."""
    item = MagicMock()
    item.price.id = price_id
    item.current_period_start = int(datetime.now(UTC).timestamp())
    item.current_period_end = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
    sub = MagicMock()
    sub.items.data = [item]
    sub.start_date = item.current_period_start
    sub.cancel_at_period_end = False
    return sub


def _checkout_session(
    customer_id: str = "cus_test",
    subscription_id: str = "sub_new",
) -> dict:
    return {
        "id": "cs_test_001",
        "customer": customer_id,
        "subscription": subscription_id,
        "metadata": {},
    }


def _active_sub_event(
    customer_id: str = "cus_test",
    sub_id: str = "sub_active",
    price_id: str = _STARTER_PRICE,
) -> dict:
    return {
        "id": sub_id,
        "customer": customer_id,
        "status": "active",
        "cancel_at_period_end": False,
        "items": {
            "data": [
                {
                    "price": {"id": price_id},
                    "current_period_end": int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
                }
            ]
        },
    }


def _make_db_with_user(user: MagicMock | None) -> AsyncMock:
    """DB mock where first execute returns the user; subsequent calls return None."""
    db = AsyncMock()
    call_count = 0

    async def _execute(query):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = user if call_count == 1 else None
        return result

    db.execute = _execute
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# (a) _on_checkout_completed: email fired when deletion was scheduled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_completed_sends_email_when_deletion_was_scheduled() -> None:
    """Re-subscribing via Checkout clears deletion and sends data-preserved email."""
    from neolex.routers.stripe_router import _on_checkout_completed

    deletion_date = datetime.now(UTC) + timedelta(days=5)
    user = _make_user(corpus_deletion_scheduled_at=deletion_date)
    db = _make_db_with_user(user)
    session = _checkout_session()
    stripe_sub = _make_stripe_sub()

    with (
        patch("neolex.routers.stripe_router._PRICE_TO_PLAN", {_STARTER_PRICE: "starter"}),
        patch("asyncio.to_thread", return_value=stripe_sub),
        patch("asyncio.create_task") as mock_create_task,
        patch("neolex.auth.email_service.send_resubscription_data_preserved_email"),
    ):
        await _on_checkout_completed(session, db)

    assert user.corpus_deletion_scheduled_at is None
    # create_task called exactly once → email was scheduled
    mock_create_task.assert_called_once()


# ---------------------------------------------------------------------------
# (b) _on_checkout_completed: no email when deletion was not scheduled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_completed_no_email_when_no_deletion_scheduled() -> None:
    """No email sent when corpus_deletion_scheduled_at was already None."""
    from neolex.routers.stripe_router import _on_checkout_completed

    user = _make_user(corpus_deletion_scheduled_at=None)
    db = _make_db_with_user(user)
    session = _checkout_session()
    stripe_sub = _make_stripe_sub()

    with (
        patch("neolex.routers.stripe_router._PRICE_TO_PLAN", {_STARTER_PRICE: "starter"}),
        patch("asyncio.to_thread", return_value=stripe_sub),
        patch("asyncio.create_task") as mock_create_task,
    ):
        await _on_checkout_completed(session, db)

    assert user.corpus_deletion_scheduled_at is None
    mock_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# (c) _on_subscription_changed (active): email fired when deletion was scheduled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_changed_active_sends_email_when_deletion_was_scheduled() -> None:
    """customer.subscription.updated → active clears deletion and sends email."""
    from neolex.routers.stripe_router import _on_subscription_changed

    deletion_date = datetime.now(UTC) + timedelta(days=3)
    user = _make_user(corpus_deletion_scheduled_at=deletion_date)
    db = _make_db_with_user(user)
    sub_event = _active_sub_event()

    with (
        patch("neolex.routers.stripe_router._PRICE_TO_PLAN", {_STARTER_PRICE: "starter"}),
        patch("asyncio.create_task") as mock_create_task,
        patch("neolex.auth.email_service.send_resubscription_data_preserved_email"),
    ):
        await _on_subscription_changed(sub_event, db)

    assert user.corpus_deletion_scheduled_at is None
    # create_task called exactly once → email was scheduled
    mock_create_task.assert_called_once()


# ---------------------------------------------------------------------------
# (d) _on_subscription_changed (active): no email when deletion was not scheduled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_changed_active_no_email_when_no_deletion_scheduled() -> None:
    """No email when corpus_deletion_scheduled_at was already None on reactivation."""
    from neolex.routers.stripe_router import _on_subscription_changed

    user = _make_user(corpus_deletion_scheduled_at=None)
    db = _make_db_with_user(user)
    sub_event = _active_sub_event()

    with (
        patch("neolex.routers.stripe_router._PRICE_TO_PLAN", {_STARTER_PRICE: "starter"}),
        patch("asyncio.create_task") as mock_create_task,
    ):
        await _on_subscription_changed(sub_event, db)

    assert user.corpus_deletion_scheduled_at is None
    mock_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# (e) email failure does not propagate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_completed_email_failure_does_not_propagate() -> None:
    """If create_task raises (import error, etc.), webhook handler must not re-raise."""
    from neolex.routers.stripe_router import _on_checkout_completed

    deletion_date = datetime.now(UTC) + timedelta(days=5)
    user = _make_user(corpus_deletion_scheduled_at=deletion_date)
    db = _make_db_with_user(user)
    session = _checkout_session()
    stripe_sub = _make_stripe_sub()

    with (
        patch("neolex.routers.stripe_router._PRICE_TO_PLAN", {_STARTER_PRICE: "starter"}),
        patch("asyncio.to_thread", return_value=stripe_sub),
        patch("asyncio.create_task", side_effect=RuntimeError("event loop gone")),
    ):
        # Must not raise
        await _on_checkout_completed(session, db)

    # Billing state still updated despite email failure
    assert user.corpus_deletion_scheduled_at is None
    assert user.subscription_status == "starter"


# ---------------------------------------------------------------------------
# (f) email HTML content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resubscription_email_content() -> None:
    """Email must address preservation clearly and link to the account page."""
    from neolex.auth.email_service import send_resubscription_data_preserved_email

    with patch("resend.Emails.send") as mock_send:
        await send_resubscription_data_preserved_email("lawyer@example.com")

    mock_send.assert_called_once()
    kwargs = mock_send.call_args[0][0]
    assert kwargs["to"] == "lawyer@example.com"
    assert "preserved" in kwargs["subject"].lower() or "safe" in kwargs["subject"].lower()
    html = kwargs["html"]
    assert "preserved" in html.lower() or "safe" in html.lower()
    assert "no action" in html.lower()
    assert "/account" in html
