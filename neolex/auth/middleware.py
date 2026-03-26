"""FastAPI dependency for API key authentication.

get_api_key() is the primary auth dependency. Add it to any endpoint that
requires authentication:

    @router.post("/query")
    async def query(request: Request, body: ..., key_row: dict = Depends(get_api_key)):
        ...

GET /health is exempt by design — it does not declare this dependency.

Rate limiting state is stored in a module-level dict. This is correct for a
single-process uvicorn server (v1 architecture). If multiple OS processes are
used in a future phase, this must move to Redis or SQLite-backed counters.
"""
import os
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from neolex.auth.keys import hash_key, key_prefix as get_prefix
from neolex.db.audit import get_audit_db

# Module-level rate limit state: key_hash -> (request_count, window_start_monotonic)
_rate_state: dict[str, tuple[int, float]] = {}


async def get_api_key(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """FastAPI dependency that validates Authorization: Bearer <key>.

    Also accepts ?api_key=<key> query param as fallback (needed for SSE
    EventSource which cannot send custom headers).

    Returns the api_keys row as a plain dict on success.
    Raises HTTPException(401) on missing, invalid, or revoked key.
    Raises HTTPException(429) when rate limit is exceeded.

    Logs auth failures to the events table (event_type='auth_failure').
    """
    # --- Extract raw key (header first, then query param for SSE) ---
    raw_key = None
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization.removeprefix("Bearer ").strip()
    elif request.query_params.get("api_key"):
        raw_key = request.query_params["api_key"]

    if not raw_key:
        async with get_audit_db() as db:
            await db.log_event(
                key_hash=None,
                event_type="auth_failure",
                detail={"reason": "missing_key"},
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Use 'Authorization: Bearer <key>' or ?api_key=<key>",
        )
    candidate_hash = hash_key(raw_key)
    prefix = get_prefix(raw_key)

    # --- Lookup key in DB ---
    async with get_audit_db() as db:
        row = await db.get_key_by_hash(candidate_hash)

        if row is None or not row["active"]:
            await db.log_event(
                key_hash=None,
                event_type="auth_failure",
                detail={"reason": "invalid_key", "key_prefix": prefix},
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid or revoked API key",
            )

        # Update last_used timestamp
        await db.update_last_used(row["id"])

    # --- Rate limiting ---
    rpm = int(os.environ.get("RATE_LIMIT_RPM", "60"))
    now = time.monotonic()
    count, window_start = _rate_state.get(candidate_hash, (0, now))
    if now - window_start >= 60.0:
        # New minute window
        count, window_start = 0, now
    count += 1
    _rate_state[candidate_hash] = (count, window_start)
    if count > rpm:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return dict(row)


async def get_admin_key(
    key_row: Annotated[dict, Depends(get_api_key)],
) -> dict:
    """Dependency that requires admin scope.

    Chains on top of get_api_key(). Returns same row dict.
    Raises HTTPException(403) if key scope is not 'admin'.

    Usage:
        @router.get("/api/v1/admin/audit")
        async def audit_log(key_row: dict = Depends(get_admin_key)):
            ...
    """
    if key_row.get("scope") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin scope required for this endpoint",
        )
    return key_row
