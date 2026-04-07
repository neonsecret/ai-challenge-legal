"""Tests for NEO-300: corpus deletion grace period, cancellation email, and GDPR export fix.

Covers three scenarios:
  (a) scheduled deletion is set on subscription cancel (not immediate)
  (b) _delete_user_corpora is NOT called immediately on cancel
  (c) GDPR export includes corpus metadata under the 'corpora' key
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    stripe_customer_id: str = "cus_test",
    subscription_status: str = "pro",
) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.stripe_customer_id = stripe_customer_id
    user.subscription_status = subscription_status
    user.max_corpora = 5
    user.payment_warning = False
    user.corpus_deletion_scheduled_at = None
    return user


def _make_subscription(stripe_id: str = "sub_other") -> MagicMock:
    sub = MagicMock()
    sub.stripe_subscription_id = stripe_id
    sub.status = "active"
    return sub


def _canceled_webhook(
    customer_id: str = "cus_test",
    sub_id: str = "sub_canceled",
) -> dict:
    """Minimal customer.subscription.deleted webhook payload."""
    return {
        "id": sub_id,
        "customer": customer_id,
        "status": "canceled",
        "items": {"data": []},
        "cancel_at_period_end": False,
    }


# ---------------------------------------------------------------------------
# (a) + (b)  Grace period is scheduled; immediate deletion does NOT fire
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_schedules_deletion_not_immediate() -> None:
    """On cancel with no other active sub: corpus_deletion_scheduled_at is set 7 days out.

    _delete_user_corpora must NOT be called during the webhook handler.
    """
    from neolex.routers.stripe_router import _on_subscription_changed

    user = _make_user()
    sub_payload = _canceled_webhook()

    # DB mock: no other active subscriptions, no existing Subscription record
    db = AsyncMock()

    async def _execute(query):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # no other active sub, no existing record
        return result

    db.execute = _execute
    db.commit = AsyncMock()

    before = datetime.now(UTC)

    with (
        patch("neolex.routers.stripe_router._delete_user_corpora", new_callable=AsyncMock) as mock_delete,
        patch("neolex.routers.stripe_router.asyncio.create_task"),
        patch("neolex.auth.email_service.send_corpus_deletion_warning_email", new_callable=AsyncMock),
    ):
        # Patch the DB select to return our mock user first, then None for other sub check
        call_count = 0

        async def _execute_ordered(query):
            nonlocal call_count
            result = MagicMock()
            call_count += 1
            if call_count == 1:
                # First call: look up user by stripe_customer_id
                result.scalar_one_or_none.return_value = user
            else:
                # Subsequent calls: no other active sub, no existing Subscription record
                result.scalar_one_or_none.return_value = None
            return result

        db.execute = _execute_ordered

        await _on_subscription_changed(sub_payload, db)

    after = datetime.now(UTC)

    # The grace-period timestamp must be set ~7 days from now
    assert user.corpus_deletion_scheduled_at is not None, "corpus_deletion_scheduled_at must be set"
    expected_low = before + timedelta(days=6, hours=23)
    expected_high = after + timedelta(days=7, seconds=5)
    assert expected_low <= user.corpus_deletion_scheduled_at <= expected_high, (
        f"Scheduled deletion {user.corpus_deletion_scheduled_at} not within expected 7-day window"
    )

    # Subscription status should be updated to canceled
    assert user.subscription_status == "canceled"
    assert user.max_corpora == 0

    # Immediate deletion must NOT have been called
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_with_other_active_sub_skips_scheduling() -> None:
    """On cancel when another active subscription exists, corpus_deletion_scheduled_at must NOT be set."""
    from neolex.routers.stripe_router import _on_subscription_changed

    user = _make_user()
    sub_payload = _canceled_webhook()

    call_count = 0

    async def _execute_ordered(query):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            result.scalar_one_or_none.return_value = user
        else:
            # Second call: another active subscription exists
            result.scalar_one_or_none.return_value = _make_subscription("sub_active_other")
        return result

    db = AsyncMock()
    db.execute = _execute_ordered
    db.commit = AsyncMock()

    with patch("neolex.routers.stripe_router._delete_user_corpora", new_callable=AsyncMock) as mock_delete:
        await _on_subscription_changed(sub_payload, db)

    # No scheduling, no immediate deletion — user has another active sub
    assert user.corpus_deletion_scheduled_at is None
    mock_delete.assert_not_called()


# ---------------------------------------------------------------------------
# (c) GDPR export includes corpus metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gdpr_export_includes_corpora() -> None:
    """export_my_data must include a 'corpora' key with document metadata."""
    from neolex.auth.email_auth import export_my_data

    user = _make_user()
    user.created_at = datetime.now(UTC)
    user.last_login = None
    user.avatar_url = None
    user.name = "Test User"
    user.email_verified = True

    fake_docs = [
        {
            "doc_id": "doc-abc",
            "filename": "contract.pdf",
            "collection": "My Contracts",
            "uploaded_at": "2026-03-01T10:00:00Z",
            "size_bytes": 102400,
            "indexed": True,
            "client_slug": str(user.id),
            "path": "/data/clients/x/docs/doc-abc_contract.pdf",
        }
    ]

    # Minimal DB mock — return empty result sets for sessions/messages/docs
    db = AsyncMock()

    async def _empty_execute(query):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value = iter([])
        return result

    db.execute = _empty_execute

    # _list_documents is imported inside the function body, so we patch where it lives.
    # asyncio.to_thread is replaced with a synchronous caller so the test stays fast.
    async def _fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with (
        patch("asyncio.to_thread", side_effect=_fake_to_thread),
        patch(
            "neolex.services.document_manager.list_documents",
            return_value=fake_docs,
        ),
    ):
        response = await export_my_data(user=user, db=db)

    assert "corpora" in response, "'corpora' key missing from GDPR export"
    corpora = response["corpora"]
    assert len(corpora) == 1
    doc = corpora[0]
    assert doc["doc_id"] == "doc-abc"
    assert doc["filename"] == "contract.pdf"
    assert doc["collection"] == "My Contracts"
    assert doc["uploaded_at"] == "2026-03-01T10:00:00Z"
    assert doc["size_bytes"] == 102400
    # Raw file bytes and internal fields must NOT be present
    assert "path" not in doc
    assert "indexed" not in doc


@pytest.mark.asyncio
async def test_gdpr_export_empty_corpora_when_no_docs() -> None:
    """export_my_data returns corpora=[] when the user has no uploaded documents."""
    from neolex.auth.email_auth import export_my_data

    user = _make_user()
    user.created_at = datetime.now(UTC)
    user.last_login = None
    user.avatar_url = None
    user.name = "Test User"
    user.email_verified = True

    db = AsyncMock()

    async def _empty_execute(query):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value = iter([])
        return result

    db.execute = _empty_execute

    async def _fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with (
        patch("asyncio.to_thread", side_effect=_fake_to_thread),
        patch("neolex.services.document_manager.list_documents", return_value=[]),
    ):
        response = await export_my_data(user=user, db=db)

    assert response["corpora"] == []
