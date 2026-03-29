"""Tests for neolex.compliance.retention (SOC 2 data retention policy).

Phase 7 — Task 2.
"""
import datetime
import pytest

from neolex.compliance.retention import RetentionPolicy, DEFAULT_RETENTION_DAYS


# ---------------------------------------------------------------------------
# Unit tests — RetentionPolicy config
# ---------------------------------------------------------------------------


def test_default_retention_days(monkeypatch):
    monkeypatch.delenv("AUDIT_LOG_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.retention_days == DEFAULT_RETENTION_DAYS
    assert policy.retention_days == 365


def test_custom_retention_days(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "90")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.retention_days == 90


def test_observation_period_blocks_purge(monkeypatch):
    monkeypatch.setenv("SOC2_OBSERVATION_PERIOD", "true")
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    policy = RetentionPolicy()
    assert policy.observation_period_active is True
    assert policy.purge_allowed is False


def test_zero_retention_blocks_purge(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "0")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.purge_allowed is False


def test_normal_config_allows_purge(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.purge_allowed is True


def test_cutoff_date_is_in_past(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    cutoff = policy.cutoff_date
    assert cutoff < datetime.datetime.now(datetime.UTC)
    # Cutoff should be roughly 365 days ago
    expected = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=365)
    diff = abs((cutoff - expected).total_seconds())
    assert diff < 5  # within 5 seconds


# ---------------------------------------------------------------------------
# Integration tests — purge logic against a real tmp DB
# ---------------------------------------------------------------------------


@pytest.fixture
async def retention_db(tmp_path, monkeypatch):
    """Seeded DB with some old and some recent audit entries."""
    from neolex.config import settings
    from neolex.db.audit import get_audit_db

    db_path = str(tmp_path / "retention_test.db")
    monkeypatch.setattr(settings, "db_path", db_path)

    async with get_audit_db(db_path) as db:
        await db.init_schema()
        # Insert 3 old entries (2 years ago) — should be purged
        old_ts = (
                datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=730)
        ).isoformat()
        for i in range(3):
            await db._conn.execute(
                "INSERT INTO queries (ts, key_hash, question, answer_text, sources_json, latency_ms, model_name) "
                "VALUES (?, 'hash', 'Q', 'A', '[]', 100, 'test')",
                (old_ts,),
            )
            await db._conn.execute(
                "INSERT INTO events (ts, key_hash, event_type, detail_json) "
                "VALUES (?, 'hash', 'test_event', '{}')",
                (old_ts,),
            )
        # Insert 2 recent entries (today) — must NOT be purged
        new_ts = datetime.datetime.now(datetime.UTC).isoformat()
        for i in range(2):
            await db._conn.execute(
                "INSERT INTO queries (ts, key_hash, question, answer_text, sources_json, latency_ms, model_name) "
                "VALUES (?, 'hash', 'Q', 'A', '[]', 100, 'test')",
                (new_ts,),
            )
    return db_path


async def test_dry_run_counts_without_deleting(retention_db, monkeypatch):
    """Dry run must report purgeable rows but not delete them."""
    from neolex.db.audit import get_audit_db
    from neolex.compliance.retention import RetentionPolicy

    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()

    async with get_audit_db(retention_db) as db:
        deleted = await policy.purge_old_entries(db, dry_run=True)

    # Should report 3 old entries per table
    assert deleted["queries"] == 3
    assert deleted["events"] == 3

    # Verify nothing was actually deleted
    async with get_audit_db(retention_db) as db:
        rows = await db.get_queries(limit=100)
        assert len(rows) == 5  # 3 old + 2 recent still present


async def test_purge_deletes_old_entries(retention_db, monkeypatch):
    """Purge must delete old entries and preserve recent ones."""
    from neolex.db.audit import get_audit_db
    from neolex.compliance.retention import RetentionPolicy

    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()

    async with get_audit_db(retention_db) as db:
        deleted = await policy.purge_old_entries(db, dry_run=False)

    assert deleted["queries"] == 3
    assert deleted["events"] == 3

    # Verify recent entries remain
    async with get_audit_db(retention_db) as db:
        rows = await db.get_queries(limit=100)
        assert len(rows) == 2  # Only 2 recent entries remain


async def test_purge_blocked_in_observation_mode(retention_db, monkeypatch):
    """Purge must raise RuntimeError if SOC2_OBSERVATION_PERIOD is active."""
    from neolex.db.audit import get_audit_db
    from neolex.compliance.retention import RetentionPolicy

    monkeypatch.setenv("SOC2_OBSERVATION_PERIOD", "true")
    policy = RetentionPolicy()

    async with get_audit_db(retention_db) as db:
        with pytest.raises(RuntimeError, match="observation period"):
            await policy.purge_old_entries(db, dry_run=False)


async def test_record_retention_run_creates_event(retention_db, monkeypatch):
    """record_retention_run must append a retention_run event to the events table."""
    from neolex.db.audit import get_audit_db
    from neolex.compliance.retention import RetentionPolicy, record_retention_run
    import json

    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()

    async with get_audit_db(retention_db) as db:
        await record_retention_run(
            db,
            dry_run=False,
            deleted={"queries": 2, "events": 1},
            policy=policy,
        )

    async with get_audit_db(retention_db) as db:
        events = await db.get_events(limit=50)

    retention_events = [e for e in events if e["event_type"] == "retention_run"]
    assert len(retention_events) >= 1
    detail = json.loads(retention_events[0]["detail_json"])
    assert detail["dry_run"] is False
    assert detail["deleted"] == {"queries": 2, "events": 1}
    assert detail["retention_days"] == 365
