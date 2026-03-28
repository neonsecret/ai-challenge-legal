"""Data retention policy for Vitreon Legal audit logs.

SOC 2 / ISO 27001 requirement: audit logs must be retained for a defined
period and must not be silently dropped or overwritten.

Environment variables:
    AUDIT_LOG_RETENTION_DAYS   Retention period for queries/events tables.
                               Default: 365 (1 year). Set to 0 to disable
                               automated purging (recommended during SOC 2
                               observation period).
    SOC2_OBSERVATION_PERIOD    If set to "1", "true", or "yes", purge is
                               blocked entirely to protect the audit trail
                               during a SOC 2 audit window.

Usage (CLI — dry run):
    python -m neolex.compliance.retention --dry-run

Usage (CLI — purge):
    python -m neolex.compliance.retention --purge

Usage (Python):
    from neolex.compliance.retention import RetentionPolicy
    policy = RetentionPolicy()
    if policy.purge_allowed:
        deleted = await policy.purge_old_entries(db)
        print(f"Purged {deleted} rows")

IMPORTANT: Never run purge during an active SOC 2 observation window.
Set SOC2_OBSERVATION_PERIOD=true in your environment during audits.
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neolex.db.audit import AuditDB

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RETENTION_DAYS = 365

# Tables subject to retention purging (append-only audit tables only).
# The `api_keys` and `documents` tables are NOT purged by this policy.
_PURGEABLE_TABLES = ("queries", "events")


# ---------------------------------------------------------------------------
# RetentionPolicy
# ---------------------------------------------------------------------------


class RetentionPolicy:
    """Encapsulates the data retention configuration for audit logs.

    Reads from environment variables on instantiation. Call `purge_old_entries`
    to delete rows older than the configured retention period.

    Attributes:
        retention_days: Number of days to retain audit log entries.
        observation_period_active: Whether SOC 2 observation mode blocks purging.
        purge_allowed: True only if retention_days > 0 and not in observation mode.
    """

    def __init__(self) -> None:
        self.retention_days: int = int(
            os.environ.get("AUDIT_LOG_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS))
        )
        self.observation_period_active: bool = os.environ.get(
            "SOC2_OBSERVATION_PERIOD", ""
        ).lower() in ("1", "true", "yes")

    @property
    def purge_allowed(self) -> bool:
        """True if purging is allowed under current configuration."""
        if self.observation_period_active:
            return False
        if self.retention_days <= 0:
            return False
        return True

    @property
    def cutoff_date(self) -> datetime.datetime:
        """ISO 8601 cutoff: entries before this timestamp are eligible for purging."""
        return datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            days=self.retention_days
        )

    def describe(self) -> dict:
        """Return a human-readable description of the current policy."""
        return {
            "retention_days": self.retention_days,
            "observation_period_active": self.observation_period_active,
            "purge_allowed": self.purge_allowed,
            "cutoff_date": self.cutoff_date.isoformat() if self.purge_allowed else None,
        }

    async def count_purgeable_entries(self, db: "AuditDB") -> dict[str, int]:
        """Count how many rows in each table are older than the cutoff.

        Returns a dict mapping table name -> row count eligible for deletion.
        """
        cutoff_iso = self.cutoff_date.isoformat()
        counts: dict[str, int] = {}
        for table in _PURGEABLE_TABLES:
            async with db._conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE ts < ?", (cutoff_iso,)
            ) as cur:
                row = await cur.fetchone()
                counts[table] = row[0] if row else 0
        return counts

    async def purge_old_entries(
        self, db: "AuditDB", *, dry_run: bool = False
    ) -> dict[str, int]:
        """Delete audit log entries older than the retention cutoff.

        Args:
            db: Open AuditDB instance (caller must commit the transaction).
            dry_run: If True, count but do not delete rows.

        Returns:
            Dict mapping table name -> number of rows deleted (or would-be-deleted).

        Raises:
            RuntimeError: If purging is not allowed (observation period active
                          or retention_days <= 0).
        """
        if not self.purge_allowed:
            reason = (
                "SOC 2 observation period is active"
                if self.observation_period_active
                else f"retention_days={self.retention_days} (purging disabled)"
            )
            raise RuntimeError(f"Purge not allowed: {reason}")

        cutoff_iso = self.cutoff_date.isoformat()
        deleted: dict[str, int] = {}

        for table in _PURGEABLE_TABLES:
            if dry_run:
                async with db._conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE ts < ?", (cutoff_iso,)
                ) as cur:
                    row = await cur.fetchone()
                    deleted[table] = row[0] if row else 0
                logger.info(
                    "[DRY RUN] Would delete %d rows from %s older than %s",
                    deleted[table],
                    table,
                    cutoff_iso,
                )
            else:
                cur = await db._conn.execute(
                    f"DELETE FROM {table} WHERE ts < ?", (cutoff_iso,)
                )
                deleted[table] = cur.rowcount
                logger.info(
                    "Purged %d rows from %s older than %s",
                    deleted[table],
                    table,
                    cutoff_iso,
                )

        return deleted


# ---------------------------------------------------------------------------
# Retention metadata record (stored in audit DB events table)
# ---------------------------------------------------------------------------


async def record_retention_run(
    db: "AuditDB",
    *,
    dry_run: bool,
    deleted: dict[str, int],
    policy: RetentionPolicy,
) -> None:
    """Append a retention_run event to the events table for audit trail.

    This ensures purge operations themselves are auditable.
    """
    await db.log_event(
        key_hash=None,
        event_type="retention_run",
        detail={
            "dry_run": dry_run,
            "retention_days": policy.retention_days,
            "cutoff_date": policy.cutoff_date.isoformat(),
            "deleted": deleted,
        },
        ip=None,
        user_agent="neolex.compliance.retention",
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def _cli_main(dry_run: bool) -> None:
    from neolex.db.audit import get_audit_db

    policy = RetentionPolicy()

    print(f"Retention policy: {policy.describe()}")

    if not policy.purge_allowed:
        if policy.observation_period_active:
            print("BLOCKED: SOC 2 observation period is active. Purge disabled.")
        else:
            print(
                "BLOCKED: AUDIT_LOG_RETENTION_DAYS=0 — automated purging is disabled."
            )
        return

    async with get_audit_db() as db:
        deleted = await policy.purge_old_entries(db, dry_run=dry_run)
        if not dry_run:
            await record_retention_run(db, dry_run=False, deleted=deleted, policy=policy)

    total = sum(deleted.values())
    if dry_run:
        print(f"[DRY RUN] Would delete {total} rows: {deleted}")
    else:
        print(f"Purged {total} rows: {deleted}")


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Vitreon Legal audit log retention purge tool"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many rows would be deleted without deleting them",
    )
    group.add_argument(
        "--purge",
        action="store_true",
        help="Delete rows older than the retention period (requires SOC2_OBSERVATION_PERIOD != true)",
    )
    args = parser.parse_args()

    asyncio.run(_cli_main(dry_run=args.dry_run))
