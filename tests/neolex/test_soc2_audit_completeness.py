"""SOC 2 Audit Log Completeness Tests.

SQLite-based row verification tests removed (audit DB migrated to PostgreSQL).
Retained: append-only interface checks, auth enforcement, health exemption.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


def test_audit_log_append_only_no_delete_methods():
    """AuditDB must not expose delete or update methods (AUDIT-05)."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from neolex.db.audit import AuditDB

    db = AuditDB(MagicMock(spec=AsyncSession))
    for name in ("delete_query", "delete_event", "update_query", "update_event", "truncate_queries", "purge_log"):
        assert not hasattr(db, name), f"AuditDB must not expose '{name}'"


def test_no_sql_delete_in_log_tables():
    """Audit module source must not DELETE from Query/Event tables."""
    import inspect

    from neolex.db import audit as m

    src = inspect.getsource(m).upper()
    for forbidden in ("DELETE FROM QUER", "DELETE FROM EVENT"):
        assert forbidden not in src, f"Found '{forbidden}' in audit source — append-only violation"


async def test_health_endpoints_accessible_without_auth(authed_client):
    """Health endpoints must be accessible without authentication."""
    client, _ = authed_client
    for path in ["/health", "/health/live", "/health/ready"]:
        resp = await client.get(path)
        assert resp.status_code in (200, 503), f"{path}: expected 200/503, got {resp.status_code}"


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/api/v1/query", {"question": "test question here at minimum", "answer_type": "free_text"}),
        ("get", "/api/v1/documents", None),
        ("get", "/api/v1/admin/audit", None),
    ],
)
async def test_all_protected_endpoints_require_auth(method, path, body):
    """All protected endpoints return 401 without a session cookie."""
    from neolex.main import app

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        resp = await client.post(path, json=body) if method == "post" else await client.get(path)

    assert resp.status_code == 401, f"{method.upper()} {path}: expected 401, got {resp.status_code}"
