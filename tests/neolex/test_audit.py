"""Tests for append-only audit log (AUDIT-05).

Rewritten when audit DB migrated from SQLite to PostgreSQL.
SQLite WAL mode and raw SQL insert tests have been removed.
"""

from neolex.db.audit import AuditDB


def test_no_delete_methods():
    """AuditDB must not expose delete/update methods for log tables (AUDIT-05)."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    db = AuditDB(MagicMock(spec=AsyncSession))
    assert not hasattr(db, "delete_query")
    assert not hasattr(db, "delete_event")
    assert not hasattr(db, "update_query")
    assert not hasattr(db, "update_event")


def test_audit_db_has_required_methods():
    """AuditDB must expose log_query for query auditing."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    db = AuditDB(MagicMock(spec=AsyncSession))
    assert hasattr(db, "log_query") and callable(db.log_query)
