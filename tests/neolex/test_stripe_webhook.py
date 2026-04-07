"""Tests for NEO-306: invoice.payment_action_required webhook handler (3DS email).

Covers four scenarios:
  (a) known customer + hosted_invoice_url → email sent once with correct fields
  (b) unknown customer → no email, no exception
  (c) known customer but no hosted_invoice_url → no email, graceful return
  (d) email send raises an exception → webhook still returns {"received": True}
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(stripe_customer_id: str = "cus_test") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "uk-user@example.com"
    user.stripe_customer_id = stripe_customer_id
    return user


def _make_db(user: MagicMock | None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() yields the given user."""
    db = AsyncMock()

    async def _execute(query):
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        return result

    db.execute = _execute
    return db


def _payment_action_required_invoice(
    customer_id: str = "cus_test",
    hosted_invoice_url: str | None = "https://invoice.stripe.com/i/test_123",
) -> dict:
    payload = {
        "id": "in_test_001",
        "customer": customer_id,
        "status": "open",
    }
    if hosted_invoice_url is not None:
        payload["hosted_invoice_url"] = hosted_invoice_url
    return payload


def _build_webhook_payload(invoice: dict) -> bytes:
    return json.dumps(
        {
            "id": "evt_test_001",
            "type": "invoice.payment_action_required",
            "data": {"object": invoice},
        }
    ).encode()


# ---------------------------------------------------------------------------
# Unit tests for _on_payment_action_required handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_action_required_sends_email() -> None:
    """Known customer + hosted_invoice_url → email sent once with correct fields."""
    from neolex.routers.stripe_router import _on_payment_action_required

    user = _make_user()
    invoice = _payment_action_required_invoice(
        customer_id="cus_test",
        hosted_invoice_url="https://invoice.stripe.com/i/test_pay_123",
    )
    db = _make_db(user)

    with patch("resend.Emails.send") as mock_send:
        await _on_payment_action_required(invoice, db)

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == user.email
    assert "action required" in call_kwargs["subject"].lower()
    assert "https://invoice.stripe.com/i/test_pay_123" in call_kwargs["html"]


@pytest.mark.asyncio
async def test_payment_action_required_unknown_customer() -> None:
    """Unknown stripe_customer_id → no email sent, no exception raised."""
    from neolex.routers.stripe_router import _on_payment_action_required

    invoice = _payment_action_required_invoice(customer_id="cus_unknown")
    db = _make_db(user=None)  # user lookup returns None

    with patch("resend.Emails.send") as mock_send:
        # Must not raise
        await _on_payment_action_required(invoice, db)

    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_payment_action_required_missing_url() -> None:
    """Known customer but no hosted_invoice_url → no email sent, graceful return."""
    from neolex.routers.stripe_router import _on_payment_action_required

    user = _make_user()
    invoice = _payment_action_required_invoice(hosted_invoice_url=None)
    db = _make_db(user)

    with patch("resend.Emails.send") as mock_send:
        await _on_payment_action_required(invoice, db)

    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_payment_action_required_email_failure_does_not_break_webhook() -> None:
    """Email send raises → webhook handler does not re-raise (ack is unaffected)."""
    from neolex.routers.stripe_router import _on_payment_action_required

    user = _make_user()
    invoice = _payment_action_required_invoice()
    db = _make_db(user)

    with patch("resend.Emails.send", side_effect=RuntimeError("Resend unavailable")):
        # Must not raise — email failure is swallowed inside the handler
        await _on_payment_action_required(invoice, db)


# ---------------------------------------------------------------------------
# Integration-style test: full webhook dispatch path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_dispatches_payment_action_required() -> None:
    """Full stripe_webhook dispatch: invoice.payment_action_required calls the handler."""
    import stripe
    from httpx import ASGITransport, AsyncClient

    from neolex.main import app

    invoice = _payment_action_required_invoice()
    payload = _build_webhook_payload(invoice)

    fake_event = MagicMock()
    fake_event.id = "evt_test_dispatch_001"
    fake_event.type = "invoice.payment_action_required"
    fake_event.data.object = invoice

    with (
        patch.object(stripe.Webhook, "construct_event", return_value=fake_event),
        patch(
            "neolex.routers.stripe_router._on_payment_action_required",
            new_callable=AsyncMock,
        ) as mock_handler,
        patch("neolex.db.postgres.get_db", return_value=AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/stripe/webhook",
                content=payload,
                headers={"stripe-signature": "t=1,v1=sig"},
            )

    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    mock_handler.assert_called_once()
