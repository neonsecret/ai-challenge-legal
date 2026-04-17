"""Tests for conversation title derivation (NEO-2318).

The title should be the chronologically first user message, not the
alphabetically smallest one (which MIN(text) would produce).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neolex.services.conversation import list_user_conversations


def _make_conv_row(
    conversation_id: uuid.UUID,
    message_count: int,
    last_message_at: datetime,
    first_user_content: str | None,
) -> MagicMock:
    row = MagicMock()
    row.conversation_id = conversation_id
    row.message_count = message_count
    row.last_message_at = last_message_at
    row.first_user_content = first_user_content
    return row


def _make_session(rows: list) -> AsyncMock:
    result = MagicMock()
    result.all.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.mark.asyncio
async def test_title_is_first_user_message_not_alphabetical():
    """Title must be the chronologically first user message.

    If MIN(text) were used, 'Alpha query' would win alphabetically.
    The correct answer is 'Zeta initial question' — the first message sent.
    """
    user_id = str(uuid.uuid4())
    conv_id = uuid.uuid4()
    now = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)

    rows = [
        _make_conv_row(conv_id, 4, now, "Zeta initial question"),
    ]
    session = _make_session(rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        conversations = await list_user_conversations(user_id)

    assert len(conversations) == 1
    assert conversations[0]["title"] == "Zeta initial question"


@pytest.mark.asyncio
async def test_title_fallback_for_no_user_messages():
    """Conversations with no user messages should show 'New chat'."""
    user_id = str(uuid.uuid4())
    conv_id = uuid.uuid4()
    now = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)

    rows = [_make_conv_row(conv_id, 1, now, None)]
    session = _make_session(rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        conversations = await list_user_conversations(user_id)

    assert conversations[0]["title"] == "New chat"


@pytest.mark.asyncio
async def test_title_truncated_at_80_chars():
    """Long first messages are truncated to 80 chars + ellipsis."""
    user_id = str(uuid.uuid4())
    conv_id = uuid.uuid4()
    now = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)
    long_msg = "A" * 120

    rows = [_make_conv_row(conv_id, 2, now, long_msg)]
    session = _make_session(rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        conversations = await list_user_conversations(user_id)

    assert conversations[0]["title"] == "A" * 80 + "..."
    assert len(conversations[0]["title"]) == 83


@pytest.mark.asyncio
async def test_multiple_conversations_each_get_own_title():
    """Each conversation gets its own first-user-message title."""
    user_id = str(uuid.uuid4())
    now = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)

    rows = [
        _make_conv_row(uuid.uuid4(), 3, now, "What is DIFC law?"),
        _make_conv_row(uuid.uuid4(), 5, now - timedelta(hours=1), "Czech contract question"),
    ]
    session = _make_session(rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        conversations = await list_user_conversations(user_id)

    assert len(conversations) == 2
    assert conversations[0]["title"] == "What is DIFC law?"
    assert conversations[1]["title"] == "Czech contract question"
