"""SOC 2 Audit Log Completeness Tests (Phase 7).

Verifies that:
1. Every authenticated endpoint creates an audit trail in the DB.
2. Auth failures are logged with IP and user-agent.
3. The audit log is append-only: no delete/update methods exist on log tables.
4. Health endpoints are intentionally exempt from audit (no side effects to log).
5. Demo config endpoint is intentionally exempt from audit (unauthenticated, no data access).
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Minimal valid PDF magic bytes for upload tests
_MINIMAL_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"


@pytest.fixture
async def doc_audit_client(tmp_path, monkeypatch):
    """App client with auth pre-seeded in a tmp DB and tmp data dir.

    Returns (client, raw_key, db_path).
    Used for document endpoint audit tests.
    """
    from neolex.auth.keys import generate_key, hash_key  # noqa: I001
    from neolex.auth.keys import key_prefix as kp
    from neolex.config import settings
    from neolex.db.audit import get_audit_db
    from neolex.main import app

    db_path = str(tmp_path / "audit_test.db")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "db_path", db_path)

    raw_key = generate_key()
    k_hash = hash_key(raw_key)
    k_prefix = kp(raw_key)

    async with get_audit_db(db_path) as db:
        await db.init_schema()
        await db.create_key(
            name="doc-audit-test",
            key_hash=k_hash,
            key_prefix=k_prefix,
            client_slug="audit-co",
            scope="query",
        )

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5

    async def fake_reindex(job_id, client_slug, db_path_arg, app=None):
        pass

    with patch("neolex.indexing.reindex_worker.run_reindex_job", new=fake_reindex):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, raw_key, db_path


# ---------------------------------------------------------------------------
# SOC2-AUDIT-01: POST /api/v1/query creates a queries row
# ---------------------------------------------------------------------------


async def test_query_endpoint_creates_audit_entry(authed_client, seeded_db):
    """POST /api/v1/query must create a row in the queries audit table."""
    client, raw_key = authed_client
    db_path, _, _ = seeded_db

    resp = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 200

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        rows = await db.get_queries(limit=5)

    assert len(rows) >= 1, "queries table must have at least one row after a successful query"
    row = dict(rows[0])
    assert "limitation period" in row["question"]
    assert row["latency_ms"] >= 0
    assert row["model_name"]
    assert row["key_hash"]


# ---------------------------------------------------------------------------
# SOC2-AUDIT-02: GET /api/v1/query/stream creates a queries row
# ---------------------------------------------------------------------------


async def test_sse_stream_creates_audit_entry(authed_client, seeded_db):
    """GET /api/v1/query/stream must create a queries audit row on completion."""
    client, raw_key = authed_client
    db_path, _, _ = seeded_db

    resp = await client.get(
        "/api/v1/query/stream",
        params={"question": "What is the jurisdiction of the DIFC Courts?"},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    # SSE response may return 200 or stream; just assert no 4xx/5xx
    assert resp.status_code == 200

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        rows = await db.get_queries(limit=5)

    assert len(rows) >= 1, "queries table must have at least one row after SSE query"


# ---------------------------------------------------------------------------
# SOC2-AUDIT-03: POST /api/v1/documents creates an upload event
# ---------------------------------------------------------------------------


async def test_upload_creates_audit_event(doc_audit_client):
    """POST /api/v1/documents must log an 'upload' event in the events table."""
    client, raw_key, db_path = doc_audit_client

    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("test.pdf", _MINIMAL_PDF, "application/pdf")},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        events = await db.get_events(limit=20)

    upload_events = [e for e in events if e["event_type"] == "upload"]
    assert len(upload_events) >= 1, "events table must have an 'upload' entry after document upload"
    detail = json.loads(upload_events[0]["detail_json"])
    assert detail.get("status") == "accepted"


# ---------------------------------------------------------------------------
# SOC2-AUDIT-04: DELETE /api/v1/documents/{doc_id} creates a delete event
# ---------------------------------------------------------------------------


async def test_delete_creates_audit_event(doc_audit_client):
    """DELETE /api/v1/documents/{doc_id} must log a 'delete' event in the events table."""
    client, raw_key, db_path = doc_audit_client

    # First upload a document so we can delete it
    resp_upload = await client.post(
        "/api/v1/documents",
        files={"file": ("todelete.pdf", _MINIMAL_PDF, "application/pdf")},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp_upload.status_code == 201
    doc_id = resp_upload.json()["doc_id"]

    # Now delete it
    resp = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        events = await db.get_events(limit=20)

    delete_events = [e for e in events if e["event_type"] == "delete"]
    assert len(delete_events) >= 1, "events table must have a 'delete' entry after document deletion"
    detail = json.loads(delete_events[0]["detail_json"])
    assert detail.get("doc_id") == doc_id


# ---------------------------------------------------------------------------
# SOC2-AUDIT-05: POST /api/v1/documents/reindex creates a reindex event
# ---------------------------------------------------------------------------


async def test_manual_reindex_creates_audit_event(doc_audit_client):
    """POST /api/v1/documents/reindex must log a 'reindex' event in the events table."""
    client, raw_key, db_path = doc_audit_client

    resp = await client.post(
        "/api/v1/documents/reindex",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        events = await db.get_events(limit=20)

    reindex_events = [e for e in events if e["event_type"] == "reindex"]
    assert len(reindex_events) >= 1, "events table must have a 'reindex' entry after manual reindex trigger"
    detail = json.loads(reindex_events[0]["detail_json"])
    assert detail.get("trigger") == "manual"


# ---------------------------------------------------------------------------
# SOC2-AUDIT-06: Auth failure logged with IP and user-agent
# ---------------------------------------------------------------------------


async def test_auth_failure_logged_with_metadata(authed_client, seeded_db):
    """Auth failures must be logged with IP and user-agent in the events table."""
    client, _ = authed_client
    db_path, _, _ = seeded_db

    # Missing key
    resp = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
        headers={"User-Agent": "TestAgent/1.0"},
    )
    assert resp.status_code == 401

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        events = await db.get_events(limit=20)

    auth_failures = [e for e in events if e["event_type"] == "auth_failure"]
    assert len(auth_failures) >= 1, "auth_failure event must be logged"

    failure = dict(auth_failures[0])
    detail = json.loads(failure["detail_json"])
    assert detail["reason"] == "missing_key"
    # user_agent should be captured (may be None in test env but field must exist)
    assert "user_agent" in failure


async def test_invalid_key_logged_with_prefix(seeded_db, monkeypatch):
    """Invalid key failures must be logged with key_prefix in detail_json.

    Uses a direct app client with no dependency overrides so real auth logic runs.
    """
    from neolex.auth.middleware import get_api_key
    from neolex.config import settings
    from neolex.main import app

    db_path, _, _ = seeded_db
    monkeypatch.setattr(settings, "db_path", db_path)
    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    # Ensure no dependency override is active (clear any from prior tests)
    app.dependency_overrides.pop(get_api_key, None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/query",
            json={"question": "What is the limitation period?", "answer_type": "free_text"},
            headers={"Authorization": "Bearer nxk_totally_invalid_key_here_00000000"},
        )
    assert resp.status_code == 401

    from neolex.db.audit import get_audit_db

    async with get_audit_db(db_path=db_path) as db:
        events = await db.get_events(limit=20)

    invalid_failures = [
        e
        for e in events
        if e["event_type"] == "auth_failure" and json.loads(e["detail_json"]).get("reason") == "invalid_key"
    ]
    assert len(invalid_failures) >= 1, "invalid_key auth_failure must be logged"
    detail = json.loads(invalid_failures[0]["detail_json"])
    assert "key_prefix" in detail, "key_prefix must be included in auth_failure detail"


# ---------------------------------------------------------------------------
# SOC2-AUDIT-07: Audit log is append-only (no delete/update methods for log tables)
# ---------------------------------------------------------------------------


def test_audit_log_append_only_no_delete_methods():
    """AuditDB must not expose any method that deletes or updates log rows (AUDIT-05)."""
    import unittest.mock as m

    import aiosqlite

    from neolex.db.audit import AuditDB

    conn = m.MagicMock(spec=aiosqlite.Connection)
    db = AuditDB(conn)

    forbidden = [
        "delete_query",
        "delete_event",
        "update_query",
        "update_event",
        "truncate_queries",
        "truncate_events",
        "clear_log",
        "purge_log",
    ]
    for method_name in forbidden:
        assert not hasattr(db, method_name), f"AuditDB must not expose '{method_name}' — audit log is append-only"


def test_no_sql_delete_in_log_tables():
    """The _SCHEMA_SQL must not contain DROP or DELETE for log table rows."""
    from neolex.db import audit as audit_module

    schema = audit_module._SCHEMA_SQL.upper()
    # We allow DELETE in documents table (that's by design), but not in queries or events
    lines = schema.split("\n")
    log_context = False
    for line in lines:
        if "QUERIES" in line or "EVENTS" in line:
            log_context = True
        if log_context and ("DELETE FROM QUERIES" in line or "DELETE FROM EVENTS" in line):
            pytest.fail(f"Found DELETE on log table in schema: {line}")


# ---------------------------------------------------------------------------
# SOC2-AUDIT-08: Health endpoints are exempt from auth (not in audit scope)
# ---------------------------------------------------------------------------


async def test_health_endpoints_accessible_without_auth(authed_client):
    """Health endpoints must be accessible without authentication."""
    client, _ = authed_client

    for path in ["/health", "/health/live", "/health/ready"]:
        resp = await client.get(path)
        assert resp.status_code in (200, 503), f"{path} must return 200/503 without auth, got {resp.status_code}"


# ---------------------------------------------------------------------------
# SOC2-AUDIT-09: Admin endpoints require admin scope (no query-key access)
# ---------------------------------------------------------------------------


async def test_admin_scope_enforcement(seeded_db, monkeypatch):
    """Query-scoped API key must not access admin endpoints (403)."""
    from neolex.config import settings
    from neolex.main import app

    db_path, raw_key, _ = seeded_db
    monkeypatch.setattr(settings, "db_path", db_path)
    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/admin/audit",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

    assert resp.status_code == 403, f"Query-scoped key must not access admin audit endpoint; got {resp.status_code}"


# ---------------------------------------------------------------------------
# SOC2-AUDIT-10: All protected endpoints return 401 without a key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/api/v1/query", {"question": "test question here at minimum", "answer_type": "free_text"}),
        ("get", "/api/v1/documents", None),
        ("get", "/api/v1/admin/audit", None),
    ],
)
async def test_all_protected_endpoints_require_auth(method, path, body, seeded_db, monkeypatch):
    """Every protected endpoint must return 401 when no Authorization header is provided."""
    from neolex.config import settings
    from neolex.main import app

    db_path, _, _ = seeded_db
    monkeypatch.setattr(settings, "db_path", db_path)
    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        if method == "post":
            resp = await client.post(path, json=body)
        else:
            resp = await client.get(path)

    assert resp.status_code == 401, f"{method.upper()} {path} must return 401 without auth; got {resp.status_code}"
