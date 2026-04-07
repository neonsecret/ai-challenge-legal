"""Admin CLI tests — show-log command.

NOTE: The old cmd_keys_create / cmd_keys_list / cmd_keys_revoke commands have
been removed from neolex.admin along with the SQLite API-key auth module.
The CLI now manages users and audit logs via PostgreSQL.

The only surviving command tested here is cmd_show_log (audit log viewer).
The audit DB (now PostgreSQL) is mocked so these tests run without a live DB.
"""

import argparse
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from neolex.admin import cmd_show_log

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ns(**kwargs) -> argparse.Namespace:
    """Create a minimal argparse.Namespace for testing."""
    return argparse.Namespace(**kwargs)


def _make_audit_db_ctx(queries=None, events=None):
    """Return an async context manager that yields a mock AuditDB.

    Args:
        queries: list of query dicts returned by get_queries() (default: [])
        events:  list of event dicts returned by get_events()  (default: [])
    """
    queries = queries or []
    events = events or []

    @asynccontextmanager
    async def _ctx():
        mock_db = AsyncMock()
        mock_db.get_queries = AsyncMock(return_value=queries)
        mock_db.get_events = AsyncMock(return_value=events)
        yield mock_db

    return _ctx


# ---------------------------------------------------------------------------
# show-log
# ---------------------------------------------------------------------------


async def test_show_log_empty(capsys):
    """show-log with no data prints 'No entries' message."""
    with patch("neolex.admin.get_audit_db", _make_audit_db_ctx(queries=[])):
        await cmd_show_log(make_ns(table="queries", limit=20))
    captured = capsys.readouterr()
    assert "No entries" in captured.out


async def test_show_log_after_query(capsys):
    """show-log prints question snippet and latency when a query row is present."""
    fake_row = {
        "ts": "2026-04-07T10:00:00",
        "latency_ms": 1234,
        "model_name": "claude-sonnet-4-6",
        "question": "What is the limitation period?",
        "answer_text": "6 years",
    }
    with patch("neolex.admin.get_audit_db", _make_audit_db_ctx(queries=[fake_row])):
        await cmd_show_log(make_ns(table="queries", limit=5))
    captured = capsys.readouterr()
    assert "limitation period" in captured.out
    assert "1234" in captured.out
