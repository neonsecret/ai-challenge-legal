"""Health check endpoints.

GET /health        — full status including metrics (uptime, request count, avg latency)
GET /health/live   — liveness probe: always returns 200 (for load balancers)
GET /health/ready  — readiness probe: checks pipeline + DB are ready (for k8s/ECS)
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _uptime_seconds(app) -> float:
    """Return seconds since startup_time was set in app.state."""
    startup = getattr(app.state, "startup_time", None)
    if startup is None:
        return 0.0
    return time.monotonic() - startup


@router.get("/health")
async def health_check(request: Request):
    """Full health status including uptime, throughput, and latency metrics.

    Returns 503 if the pipeline is not ready (still warming up or failed to start).
    """
    app = request.app
    ready = getattr(app.state, "ready", False)
    getattr(app.state, "workers", 0)

    uptime_s = _uptime_seconds(app)

    # Pull metrics from main module (single-process counters).
    import neolex.main as _main

    if _main._latency_count > 0:
        round(_main._latency_sum_ms / _main._latency_count, 1)

    if not ready:
        return JSONResponse(
            status_code=503,
            content={
                "status": "starting",
                "pipeline_ready": False,
                "uptime_seconds": round(uptime_s, 1),
            },
        )

    return {
        "status": "ready",
        "pipeline_ready": True,
    }


@router.get("/health/live")
async def liveness():
    """Liveness probe — always returns 200.

    Load balancers / k8s use this to decide whether to restart the container.
    This endpoint must ALWAYS respond even if the pipeline is still warming up.
    Do NOT add any dependency checks here.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(request: Request):
    """Readiness probe — returns 200 only when the server can handle traffic.

    Checks:
    1. Pipeline singletons are warmed (app.state.ready)
    2. Audit DB is reachable (quick SELECT)

    Returns 503 when either check fails so traffic is not routed to this instance.
    """
    app = request.app
    ready = getattr(app.state, "ready", False)

    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "pipeline_warming"},
        )

    # Check DB connectivity with a minimal query.
    try:
        from neolex.db.audit import get_audit_db

        async with get_audit_db() as db:
            await db.ping()
    except Exception as exc:
        logger.warning("Readiness check: DB unreachable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "db_unreachable"},
        )

    return {"status": "ready"}
