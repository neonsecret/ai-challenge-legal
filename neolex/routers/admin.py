"""Admin endpoints — require admin-scoped API key.

GET  /api/v1/admin/audit         — paginated audit log query (client-isolated).
POST /api/v1/admin/keys/rotate   — revoke current key and issue a replacement.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from neolex.auth.middleware import get_admin_key
from neolex.db.audit import get_audit_db

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Scope value that grants cross-client (superadmin) access.
_SUPERADMIN_SCOPE = "superadmin"


@router.get("/audit")
async def get_audit_log(
    key_row: Annotated[dict, Depends(get_admin_key)],
    table: Annotated[Literal["queries", "events"], Query()] = "queries",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Return paginated audit log entries scoped to the caller's client.

    Requires admin-scoped API key (Authorization: Bearer <admin-key>).
    Returns 403 if key is query-scoped.

    A key with scope="superadmin" may read all clients' data.
    All other admin keys are restricted to their own client_slug.

    Query params:
        table: "queries" (default) or "events"
        limit: rows per page, 1-200 (default 50)
        offset: skip N rows (default 0)
    """
    # Determine client filter: None means superadmin (all clients).
    scope = key_row.get("scope", "admin")
    client_slug: str | None = (
        None if scope == _SUPERADMIN_SCOPE else key_row["client_slug"]
    )

    async with get_audit_db() as db:
        if table == "queries":
            rows = await db.get_queries(limit=limit, offset=offset, client_slug=client_slug)
        else:
            rows = await db.get_events(limit=limit, offset=offset, client_slug=client_slug)

    return {
        "table": table,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "rows": [dict(row) for row in rows],
    }


@router.post("/keys/rotate")
async def rotate_key(
    key_row: Annotated[dict, Depends(get_admin_key)],
):
    """Revoke the caller's current API key and issue a replacement.

    The new plaintext key is returned exactly once in the response body.
    Store it immediately — it cannot be recovered afterwards.

    Requires admin-scoped API key.
    """
    from neolex.auth.keys import generate_key, hash_key, key_prefix as get_prefix

    old_prefix = key_row["key_prefix"]
    client_slug = key_row["client_slug"]
    key_name = key_row["name"]

    new_raw = generate_key()
    new_hash = hash_key(new_raw)
    new_prefix = get_prefix(new_raw)

    async with get_audit_db() as db:
        # Revoke old key.
        await db.revoke_key(old_prefix)

        # Insert the replacement key with the same name, client, and scope.
        await db.create_key(
            name=key_name,
            key_hash=new_hash,
            key_prefix=new_prefix,
            client_slug=client_slug,
            scope=key_row.get("scope", "admin"),
        )

        # Audit the rotation event.
        await db.log_event(
            key_hash=new_hash,
            event_type="key_rotation",
            detail={
                "revoked_prefix": old_prefix,
                "new_prefix": new_prefix,
                "client_slug": client_slug,
            },
            ip=None,
            user_agent=None,
        )

    return {
        "rotated": True,
        "revoked_prefix": old_prefix,
        "new_key": new_raw,
        "new_prefix": new_prefix,
        "warning": "Store this key immediately — it will not be shown again.",
    }
