"""Tests for append-only audit log (AUDIT-01, AUDIT-03, AUDIT-04, AUDIT-05, NFR-04)."""

import asyncio
import json
from unittest.mock import MagicMock

from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# NFR-04: WAL mode
# ---------------------------------------------------------------------------


async def test_wal_mode(tmp_db_path, monkeypatch):
    """SQLite DB must be opened in WAL mode (NFR-04)."""
    from neolex.config import settings

    monkeypatch.setattr(settings, "db_path", tmp_db_path)
    from neolex.db.audit import get_audit_db

    async with get_audit_db() as db:
        await db.init_schema()
        async with db._conn.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
    assert row[0] == "wal", f"Expected WAL mode, got {row[0]}"


# ---------------------------------------------------------------------------
# AUDIT-05: No delete methods on log tables
# ---------------------------------------------------------------------------


def test_no_delete_methods():
    """AuditDB must not expose delete or update methods for log tables (AUDIT-05)."""
    import unittest.mock as mock_module

    import aiosqlite

    from neolex.db.audit import AuditDB

    mock_conn = mock_module.MagicMock(spec=aiosqlite.Connection)
    db = AuditDB(mock_conn)

    assert not hasattr(db, "delete_query"), "AuditDB must not have delete_query"
    assert not hasattr(db, "delete_event"), "AuditDB must not have delete_event"
    assert not hasattr(db, "update_query"), "AuditDB must not have update_query"
    assert not hasattr(db, "update_event"), "AuditDB must not have update_event"


# ---------------------------------------------------------------------------
# AUDIT-01: Query logged after POST /query
# ---------------------------------------------------------------------------


async def test_query_logged(authed_client, seeded_db):
    """Successful POST /api/v1/query -> row appears in queries table (AUDIT-01)."""
    client, raw_key = authed_client
    db_path, _, _ = seeded_db

    response = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        rows = await db.get_queries(limit=10)

    assert len(rows) >= 1
    last = dict(rows[0])
    assert "limitation period" in last["question"]
    assert last["latency_ms"] >= 0
    assert last["model_name"] != ""


# ---------------------------------------------------------------------------
# AUDIT-03: Auth failure logged with IP and key_prefix
# ---------------------------------------------------------------------------


async def test_auth_failure_logged(authed_client, seeded_db):
    """POST /api/v1/query with no key -> auth_failure event logged (AUDIT-03)."""
    client, _ = authed_client
    db_path, _, _ = seeded_db

    response = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
        # No Authorization header
    )
    assert response.status_code == 401

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        rows = await db.get_events(limit=10)

    auth_failures = [dict(r) for r in rows if r["event_type"] == "auth_failure"]
    assert len(auth_failures) >= 1
    detail = json.loads(auth_failures[0]["detail_json"])
    assert detail["reason"] == "missing_key"


# ---------------------------------------------------------------------------
# AUDIT-04: Admin endpoint scoping
# ---------------------------------------------------------------------------


async def test_admin_audit_requires_admin_scope(seeded_db, monkeypatch):
    """Query-scoped key on GET /api/v1/admin/audit -> 403 (AUDIT-04)."""

    from neolex.config import settings
    from neolex.main import app

    db_path, raw_key, _ = seeded_db  # raw_key is query-scoped
    monkeypatch.setattr(settings, "db_path", db_path)

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/audit",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert response.status_code == 403


async def test_admin_audit_returns_rows(seeded_db, monkeypatch):
    """Admin-scoped key on GET /api/v1/admin/audit -> 200 with rows list."""
    from neolex.auth.keys import generate_key, hash_key
    from neolex.auth.keys import key_prefix as kp
    from neolex.config import settings
    from neolex.db.audit import get_audit_db
    from neolex.main import app

    db_path, _, _ = seeded_db
    monkeypatch.setattr(settings, "db_path", db_path)

    # Create an admin key
    admin_raw = generate_key()
    admin_hash = hash_key(admin_raw)
    admin_prefix = kp(admin_raw)

    async with get_audit_db() as db:
        await db.create_key(
            name="admin-test",
            key_hash=admin_hash,
            key_prefix=admin_prefix,
            client_slug="admin",
            scope="admin",
        )

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/audit?table=events&limit=10",
            headers={"Authorization": f"Bearer {admin_raw}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "rows" in body
    assert isinstance(body["rows"], list)
    assert body["table"] == "events"
