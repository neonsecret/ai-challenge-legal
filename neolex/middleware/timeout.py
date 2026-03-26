"""Request timeout middleware.

Wraps every request in asyncio.wait_for() with a configurable timeout.
Returns 504 JSON on timeout (not HTML).

Configuration:
    REQUEST_TIMEOUT_SECONDS env var (default: 30)

The timeout applies to the entire request including pipeline execution.
Query endpoints typically take 3-15s; 30s is a generous upper bound that
still protects against stuck requests consuming server resources.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Health endpoints are exempt — they must always respond even if the server is
# under load. Auth failures also return quickly; we want 401 not 504.
_EXEMPT_PREFIXES = ("/health",)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Returns 504 JSON when a request exceeds REQUEST_TIMEOUT_SECONDS."""

    def __init__(self, app, timeout_seconds: float | None = None) -> None:
        super().__init__(app)
        if timeout_seconds is not None:
            self._timeout = timeout_seconds
        else:
            self._timeout = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))

    async def dispatch(self, request: Request, call_next) -> Response:
        # Health checks are exempt from the timeout so they always respond.
        if any(request.url.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        request_id = getattr(request.state, "request_id", "unknown")

        try:
            return await asyncio.wait_for(call_next(request), timeout=self._timeout)
        except asyncio.TimeoutError:
            logger.error(
                "Request timeout",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "timeout_seconds": self._timeout,
                },
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Request timeout",
                    "detail": f"Request exceeded {self._timeout:.0f}s time limit.",
                    "request_id": request_id,
                },
                headers={"Retry-After": "10", "X-Request-ID": request_id},
            )
