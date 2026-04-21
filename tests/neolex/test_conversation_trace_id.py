"""Unit tests for trace_id round-trip in conversation service (NEO-310).

Covers:
- save_turn stores trace_id on the assistant ConversationMessage row
- load_full_conversation returns trace_id on assistant messages
- load_full_conversation omits trace_id when it is None/absent
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neolex.services.conversation import load_full_conversation, save_turn


def _make_row(role: str, content: str, trace_id: str | None = None) -> MagicMock:
    """Build a mock DB row as returned by SQLAlchemy's result.all()."""
    row = MagicMock()
    row.role = role
    row.content = content
    row.sources_json = None
    row.trace_id = trace_id
    row.created_at = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)
    return row


# ---------------------------------------------------------------------------
# save_turn — trace_id stored on assistant row
# ---------------------------------------------------------------------------


def _make_mock_session() -> tuple[MagicMock, list]:
    """Return (session, added_objects) where session.add() is synchronous."""
    added_objects: list = []
    session = MagicMock()
    session.add.side_effect = added_objects.append
    session.commit = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session, added_objects


@pytest.mark.asyncio
async def test_save_turn_stores_trace_id():
    """save_turn passes trace_id to the assistant ConversationMessage."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    mock_session, added_objects = _make_mock_session()

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        await save_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            question="What is the limitation period?",
            answer="Six years under Article 10.",
            trace_id="trace-abc123",
        )

    assert len(added_objects) == 2  # user + assistant rows
    user_row, assistant_row = added_objects
    assert user_row.role == "user"
    assert assistant_row.role == "assistant"
    assert assistant_row.trace_id == "trace-abc123"


@pytest.mark.asyncio
async def test_save_turn_none_trace_id():
    """save_turn with trace_id=None stores None on the assistant row."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    mock_session, added_objects = _make_mock_session()

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        await save_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            question="What is the limitation period?",
            answer="Six years under Article 10.",
            trace_id=None,
        )

    _, assistant_row = added_objects
    assert assistant_row.trace_id is None


# ---------------------------------------------------------------------------
# load_full_conversation — trace_id returned on assistant messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_full_conversation_returns_trace_id():
    """load_full_conversation includes trace_id in assistant message dicts."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    rows = [
        _make_row("user", "What is the limitation period?"),
        _make_row("assistant", "Six years under Article 10.", trace_id="trace-abc123"),
    ]

    mock_result = MagicMock()
    mock_result.all.return_value = rows

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        messages = await load_full_conversation(user_id, conversation_id)

    assert len(messages) == 2
    user_msg, assistant_msg = messages
    assert "trace_id" not in user_msg  # user messages never carry trace_id
    assert assistant_msg["trace_id"] == "trace-abc123"


@pytest.mark.asyncio
async def test_load_full_conversation_omits_trace_id_when_none():
    """load_full_conversation does not include trace_id key when it is None."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    rows = [
        _make_row("assistant", "Six years under Article 10.", trace_id=None),
    ]

    mock_result = MagicMock()
    mock_result.all.return_value = rows

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        messages = await load_full_conversation(user_id, conversation_id)

    assert len(messages) == 1
    assert "trace_id" not in messages[0]


# ---------------------------------------------------------------------------
# save_turn — idempotency guard (NEO-2608)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_turn_idempotent_on_duplicate_trace_id():
    """Second save_turn with the same trace_id is a no-op (app-level guard)."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    mock_session, added_objects = _make_mock_session()
    # First call: scalar returns None → insert proceeds
    # Second call: scalar returns an existing row ID → skip
    mock_session.scalar = AsyncMock(side_effect=[None, uuid.uuid4()])

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        await save_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            question="Q1",
            answer="A1",
            trace_id="trace-dup",
        )
        await save_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            question="Q1",
            answer="A1",
            trace_id="trace-dup",
        )

    assert len(added_objects) == 2  # only one pair inserted, second call skipped
    assert mock_session.commit.await_count == 1
