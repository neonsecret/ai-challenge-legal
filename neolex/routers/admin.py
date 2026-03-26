"""Admin endpoints — require admin-scoped API key.

GET /api/v1/admin/audit — paginated audit log query.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from neolex.auth.middleware import get_admin_key
from neolex.db.audit import get_audit_db

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/audit")
async def get_audit_log(
    key_row: Annotated[dict, Depends(get_admin_key)],
    table: Annotated[Literal["queries", "events"], Query()] = "queries",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Return paginated audit log entries.

    Requires admin-scoped API key (Authorization: Bearer <admin-key>).
    Returns 403 if key is query-scoped.

    Query params:
        table: "queries" (default) or "events"
        limit: rows per page, 1-200 (default 50)
        offset: skip N rows (default 0)
    """
    async with get_audit_db() as db:
        if table == "queries":
            rows = await db.get_queries(limit=limit, offset=offset)
        else:
            rows = await db.get_events(limit=limit, offset=offset)

    return {
        "table": table,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "rows": [dict(row) for row in rows],
    }
