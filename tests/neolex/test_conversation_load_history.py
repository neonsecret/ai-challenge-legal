"""Tests for load_history — verifies newest-N-first ordering fix (NEO-2317).

The bug: ORDER BY created_at ASC LIMIT 10 returned the oldest 10 messages.
The fix: subquery orders DESC + LIMIT, outer query re-sorts ASC for chronological flow.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neolex.services.conversation import MAX_HISTORY_TURNS, load_history


def _make_row(role: str, content: str, offset_seconds: int = 0) -> MagicMock:
    row = MagicMock()
    row.role = role
    row.content = content
    row.created_at = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=offset_seconds)
    return row


def _make_mock_session(rows: list) -> MagicMock:
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.mark.asyncio
async def test_load_history_returns_role_content_dicts():
    """load_history returns list of {role, content} dicts."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    # DB returns DESC (newest first); code reverses to chronological order.
    rows = [
        _make_row("assistant", "Six years under Article 10.", 1),
        _make_row("user", "What is the limitation period?", 0),
    ]
    mock_session = _make_mock_session(rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        result = await load_history(user_id, conversation_id)

    assert result == [
        {"role": "user", "content": "What is the limitation period?"},
        {"role": "assistant", "content": "Six years under Article 10."},
    ]


@pytest.mark.asyncio
async def test_load_history_empty_conversation_id_returns_empty():
    """load_history short-circuits to [] when conversation_id is empty/None."""
    assert await load_history(str(uuid.uuid4()), "") == []
    assert await load_history(str(uuid.uuid4()), None) == []  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_load_history_returns_at_most_max_history_turns():
    """load_history never returns more than MAX_HISTORY_TURNS messages.

    The DB subquery enforces LIMIT MAX_HISTORY_TURNS — here we verify the
    function handles exactly MAX_HISTORY_TURNS rows returned by the mock.
    """
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    # Simulate the DB already applying the limit (returns exactly MAX_HISTORY_TURNS rows)
    rows = [_make_row("user" if i % 2 == 0 else "assistant", f"msg {i}", i) for i in range(MAX_HISTORY_TURNS)]
    mock_session = _make_mock_session(rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        result = await load_history(user_id, conversation_id)

    assert len(result) == MAX_HISTORY_TURNS


@pytest.mark.asyncio
async def test_load_history_newest_messages_scenario():
    """Simulates the fix: a 20-message conversation should surface messages 11-20.

    DB returns newest 10 in DESC order (msg 20 first). Code reverses to get
    chronological order (msg 11 first). This test documents that contract.
    """
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    # DB returns DESC (newest first): msg20 … msg11; reversed() gives msg11 … msg20.
    newest_rows = [
        _make_row(
            "user" if i % 2 == 0 else "assistant",
            f"msg {10 + MAX_HISTORY_TURNS - i}",
            (MAX_HISTORY_TURNS - 1 - i) * 10,
        )
        for i in range(MAX_HISTORY_TURNS)
    ]
    mock_session = _make_mock_session(newest_rows)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=mock_session)):
        result = await load_history(user_id, conversation_id)

    assert len(result) == MAX_HISTORY_TURNS
    assert result[0]["content"] == "msg 11"
    assert result[-1]["content"] == f"msg {10 + MAX_HISTORY_TURNS}"


@pytest.mark.asyncio
async def test_load_history_returns_empty_on_db_error():
    """load_history swallows DB exceptions and returns []."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("DB down"))
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with patch("neolex.services.conversation.AsyncSessionLocal", MagicMock(return_value=session)):
        result = await load_history(user_id, conversation_id)

    assert result == []
