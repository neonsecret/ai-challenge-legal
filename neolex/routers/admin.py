"""Admin endpoints — require authenticated session with admin role.

GET  /api/v1/admin/audit  — paginated audit log.
"""

import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from neolex.auth.session import get_current_user
from neolex.db.audit import get_audit_db
from neolex.db.models import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Admin emails — configured via ADMIN_EMAILS env var (comma-separated).
# No default: forces explicit configuration to prevent unauthorized admin access.
_raw_admin_emails = os.environ.get("ADMIN_EMAILS", "")
if not _raw_admin_emails.strip():
    raise RuntimeError(
        "ADMIN_EMAILS environment variable is not set. Set it to a comma-separated list of admin email addresses."
    )
_ADMIN_EMAILS: set[str] = {e.strip() for e in _raw_admin_emails.split(",") if e.strip()}


async def get_admin(user: User = Depends(get_current_user)) -> User:
    """Verify that the authenticated user has admin privileges."""
    if user.email not in _ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/audit")
async def get_audit_log(
    admin: Annotated[User, Depends(get_admin)],
    table: Annotated[Literal["queries", "events"], Query()] = "queries",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
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
