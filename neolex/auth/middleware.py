"""FastAPI dependency for API key authentication.

get_api_key() is the primary auth dependency. Add it to any endpoint that
requires authentication:

    @router.post("/query")
    async def query(request: Request, body: ..., key_row: dict = Depends(get_api_key)):
        ...

GET /health is exempt by design — it does not declare this dependency.

Rate limiting and IP brute-force counters are stored in SQLite (rate_limits
table) so they survive process restarts and work correctly under multi-worker
deployments.  asyncio.to_thread is used for the synchronous SQLite upsert to
avoid blocking the event loop.
"""
import asyncio
import os
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from neolex.auth.keys import hash_key, key_prefix as get_prefix
from neolex.db.audit import get_audit_db

# ---------------------------------------------------------------------------
# Module-level rate state — kept as in-memory fallback for tests that don't
# seed an audit DB.  Production traffic always goes through SQLite.
# The dict is also used by legacy tests that reference it directly.
# ---------------------------------------------------------------------------
_rate_state: dict[str, tuple[int, float]] = {}

# IP brute-force window (5 minutes, 20 auth failures).
_IP_FAIL_WINDOW = 300.0
_IP_FAIL_LIMIT = 20


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
    Raises HTTPException(429) when source IP has too many recent auth failures.

    Logs auth failures to the events table (event_type='auth_failure').
    """
    ip = getattr(request.client, "host", None) or "unknown"

    # --- IP brute-force gate ---
    # Check BEFORE extracting the key so we short-circuit hammered IPs cheaply.
    now = time.monotonic()
    ip_bucket = f"ip_fail:{ip}"
    try:
        async with get_audit_db() as db:
            # Read current failure count (no increment here — increment on failure below).
            async with db._conn.execute(
                "SELECT request_count, window_start FROM rate_limits WHERE bucket = ?",
                (ip_bucket,),
            ) as cur:
                ip_row = await cur.fetchone()

        if ip_row:
            ip_count, ip_window = ip_row[0], ip_row[1]
            if (now - ip_window) < _IP_FAIL_WINDOW and ip_count > _IP_FAIL_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail="Too many authentication failures. Try again later.",
                    headers={"Retry-After": str(int(_IP_FAIL_WINDOW))},
                )
    except HTTPException:
        raise
    except Exception:
        # Non-fatal: if DB is unavailable, don't block legitimate requests.
        pass

    # --- Extract raw key (header first, then query param for SSE) ---
    raw_key = None
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization.removeprefix("Bearer ").strip()
    elif request.query_params.get("api_key"):
        raw_key = request.query_params["api_key"]

    if not raw_key:
        await _record_ip_failure(ip, now)
        async with get_audit_db() as db:
            await db.log_event(
                key_hash=None,
                event_type="auth_failure",
                detail={"reason": "missing_key"},
                ip=ip,
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Use 'Authorization: Bearer <key>' or ?api_key=<key>",
        )
    candidate_hash = hash_key(raw_key)
    prefix = get_prefix(raw_key)

    # --- Lookup key in DB ---
    # IMPORTANT: log_event and the HTTPException raise must be separated.
    # Raising inside the `async with get_audit_db()` block causes the context
    # manager to roll back the transaction, losing the audit event.
    # Pattern: do all DB work first (log + update), exit the context manager
    # cleanly (commit), then raise the exception outside.
    _auth_failed = False
    async with get_audit_db() as db:
        row = await db.get_key_by_hash(candidate_hash)

        if row is None or not row["active"]:
            await db.log_event(
                key_hash=None,
                event_type="auth_failure",
                detail={"reason": "invalid_key", "key_prefix": prefix},
                ip=ip,
                user_agent=request.headers.get("user-agent"),
            )
            _auth_failed = True
        else:
            # Update last_used timestamp
            await db.update_last_used(row["id"])

    if _auth_failed:
        await _record_ip_failure(ip, now)
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key",
        )

    # --- Per-key rate limiting (SQLite-backed) ---
    rpm = int(os.environ.get("RATE_LIMIT_RPM", "60"))
    key_bucket = f"key:{candidate_hash}"
    try:
        async with get_audit_db() as db:
            new_count, exceeded = await db.check_and_increment_rate(
                bucket=key_bucket,
                window_seconds=60.0,
                limit=rpm,
                now=now,
            )
        if exceeded:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except HTTPException:
        raise
    except Exception:
        # SQLite unavailable — fall back to in-memory counter so we don't
        # block requests completely.
        count, window_start = _rate_state.get(candidate_hash, (0, now))
        if now - window_start >= 60.0:
            count, window_start = 0, now
        count += 1
        _rate_state[candidate_hash] = (count, window_start)
        if count > rpm:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return dict(row)


async def _record_ip_failure(ip: str, now: float) -> None:
    """Increment the IP failure counter in SQLite.  Non-fatal on DB error."""
    bucket = f"ip_fail:{ip}"
    try:
        async with get_audit_db() as db:
            await db.check_and_increment_rate(
                bucket=bucket,
                window_seconds=_IP_FAIL_WINDOW,
                limit=_IP_FAIL_LIMIT,
                now=now,
            )
    except Exception:
        pass  # Never block the response path for a counter write failure.


async def get_admin_key(
    key_row: Annotated[dict, Depends(get_api_key)],
) -> dict:
    """Dependency that requires admin scope.

    Chains on top of get_api_key(). Returns same row dict.
    Raises HTTPException(403) if key scope is not 'admin' or 'superadmin'.

    Usage:
        @router.get("/api/v1/admin/audit")
        async def audit_log(key_row: dict = Depends(get_admin_key)):
            ...
    """
    if key_row.get("scope") not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=403,
            detail="Admin scope required for this endpoint",
        )
    return key_row
