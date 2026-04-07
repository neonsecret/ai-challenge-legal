"""Tests for feedback state in load_full_conversation() (NEO-530).

Covers:
- feedback dict returned for assistant messages with a matching Feedback row
- feedback=None for assistant messages with no matching Feedback row
- feedback=None for all user messages
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neolex.services.conversation import load_full_conversation


def _make_msg_row(
    role: str,
    content: str,
    trace_id: str | None = None,
) -> MagicMock:
    row = MagicMock()
    row.role = role
    row.content = content
    row.sources_json = None
    row.trace_id = trace_id
    row.created_at = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)
    return row


def _make_feedback_row(trace_id: str, rating: str, comment: str | None = None) -> MagicMock:
    row = MagicMock()
    row.trace_id = trace_id
    row.rating = rating
    row.comment = comment
    return row


def _make_session(msg_rows: list, feedback_rows: list) -> AsyncMock:
    """Return an async session that yields msg_rows on the first execute,
    then feedback_rows on the second execute."""
    msg_result = MagicMock()
    msg_result.all.return_value = msg_rows

    fb_result = MagicMock()
    fb_result.all.return_value = feedback_rows

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[msg_result, fb_result])
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ---------------------------------------------------------------------------
# Feedback present for assistant message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_full_conversation_returns_feedback_for_assistant():
    """Assistant messages with a matching Feedback row carry the feedback dict."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    trace = "trace-abc123"

    msg_rows = [
        _make_msg_row("user", "What is the limitation period?"),
        _make_msg_row("assistant", "Six years under Article 10.", trace_id=trace),
    ]
    feedback_rows = [_make_feedback_row(trace, rating="positive", comment="Great answer")]

    session = _make_session(msg_rows, feedback_rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        messages = await load_full_conversation(user_id, conversation_id)

    assert len(messages) == 2
    user_msg, assistant_msg = messages

    assert user_msg["feedback"] is None
    assert assistant_msg["feedback"] == {"rating": "positive", "comment": "Great answer"}


# ---------------------------------------------------------------------------
# Feedback absent for assistant message (no matching row)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_full_conversation_feedback_none_when_no_row():
    """Assistant messages without a Feedback row return feedback=None."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    trace = "trace-xyz999"

    msg_rows = [
        _make_msg_row("assistant", "No feedback submitted.", trace_id=trace),
    ]
    feedback_rows: list = []  # no feedback in DB

    session = _make_session(msg_rows, feedback_rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        messages = await load_full_conversation(user_id, conversation_id)

    assert len(messages) == 1
    assert messages[0]["feedback"] is None


# ---------------------------------------------------------------------------
# User messages always get feedback=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_full_conversation_user_messages_have_null_feedback():
    """User role messages always carry feedback=None regardless of feedback rows."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    msg_rows = [
        _make_msg_row("user", "Tell me about contract law."),
    ]
    feedback_rows: list = []

    session = _make_session(msg_rows, feedback_rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        messages = await load_full_conversation(user_id, conversation_id)

    assert len(messages) == 1
    assert messages[0]["feedback"] is None


# ---------------------------------------------------------------------------
# Mixed conversation: multiple messages, partial feedback coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_full_conversation_mixed_feedback():
    """Mixed conversation: first assistant has feedback, second does not."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    trace1 = "trace-001"
    trace2 = "trace-002"

    msg_rows = [
        _make_msg_row("user", "Q1"),
        _make_msg_row("assistant", "A1", trace_id=trace1),
        _make_msg_row("user", "Q2"),
        _make_msg_row("assistant", "A2", trace_id=trace2),
    ]
    feedback_rows = [_make_feedback_row(trace1, rating="negative")]  # only first message rated

    session = _make_session(msg_rows, feedback_rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        messages = await load_full_conversation(user_id, conversation_id)

    assert len(messages) == 4
    assert messages[0]["feedback"] is None  # user
    assert messages[1]["feedback"] == {"rating": "negative", "comment": None}
    assert messages[2]["feedback"] is None  # user
    assert messages[3]["feedback"] is None  # assistant without feedback
