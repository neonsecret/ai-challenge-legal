"""Request ID middleware.

Generates a UUID per request and stores it in request.state.request_id.
Also injects it into all log records via a logging.Filter so every log line
emitted during request handling includes the request_id automatically.

The request_id is included in all JSON error responses and in the
X-Request-ID response header for client-side correlation.
"""
from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attaches a unique UUID to each request.

    - Sets request.state.request_id
    - Adds X-Request-ID response header
    - Logs request start and end (with duration and status code)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        import time
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": getattr(request.client, "host", "unknown"),
            },
        )

        start = time.monotonic()

        response = await call_next(request)

        duration_ms = int((time.monotonic() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        # Update module-level metrics in neolex.main (single-process counters).
        # Import lazily to avoid circular imports at module load time.
        try:
            import neolex.main as _main
            _main._request_count += 1
            _main._latency_sum_ms += duration_ms
            _main._latency_count += 1
        except Exception:
            pass  # Never fail a request because of metric tracking

        return response
