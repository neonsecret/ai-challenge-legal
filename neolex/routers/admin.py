"""Admin endpoints — require authenticated session.

GET  /api/v1/admin/audit  — paginated audit log.
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
    """Return paginated audit log entries."""
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
        "rows": rows,
    }
