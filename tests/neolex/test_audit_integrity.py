"""Structural tests for the AuditDB append-only invariant (AUDIT-05).

Verifies the append-only constraint on audit log tables (queries, events)
without requiring a real PostgreSQL connection — class and source inspection
only.

AUDIT-05: AuditDB must not expose delete or update operations on audit log
entries. Only append (log_query, log_event) and read (get_queries, get_events)
operations are permitted on audit log data.
"""

import inspect
from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncSession


def test_audit_db_is_append_only():
    """AUDIT-05: AuditDB must not expose delete or update methods for audit log entries.

    Checks the public interface for forbidden method names and confirms that the
    required append-write methods are present.  No real database connection needed.
    """
    from neolex.db.audit import AuditDB  # noqa: I001

    db = AuditDB(MagicMock(spec=AsyncSession))

    # NOTE: purge_table() is intentionally excluded — retention-driven purging
    # is an authorized exception to the append-only rule (see retention.py).
    # AUDIT-05 covers ad-hoc delete/update, not scheduled retention.
    forbidden = (
        "delete_query",
        "delete_event",
        "update_query",
        "update_event",
        "truncate_queries",
        "truncate_events",
        "purge_log",
        "purge_queries",
        "purge_events",
    )
    for name in forbidden:
        assert not hasattr(db, name), (
            f"AUDIT-05 violation: AuditDB must not expose '{name}' — audit log entries are append-only"
        )

    # The write path must remain accessible.
    assert callable(getattr(db, "log_query", None)), "AuditDB must expose log_query()"
    assert callable(getattr(db, "log_event", None)), "AuditDB must expose log_event()"


def test_audit_source_has_no_raw_delete_on_log_tables():
    """AUDIT-05: audit module source must not contain raw DELETE SQL targeting log tables.

    Guards against accidental introduction of inline SQL that bypasses the
    SQLAlchemy ORM layer and hard-deletes query or event rows.
    """
    from neolex.db import audit as m  # noqa: I001

    src = inspect.getsource(m).upper()
    for forbidden in ("DELETE FROM QUER", "DELETE FROM EVENT"):
        assert forbidden not in src, (
            f"AUDIT-05 violation: found '{forbidden}' in audit.py source — append-only constraint broken"
        )
