"""JSON error handler middleware.

Wraps the entire ASGI app to catch unhandled exceptions and return JSON 500
instead of Starlette's default HTML error page.

This must be registered as the OUTERMOST middleware so it catches exceptions
that escape all inner middleware and route handlers.

Why not @app.exception_handler(Exception)?
  In modern Starlette/FastAPI, unhandled exceptions from route handlers are
  caught by ServerErrorMiddleware (not the app's exception_handler registry)
  and returned as HTML. This middleware replaces that behavior with JSON.
"""
from __future__ import annotations

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class JSONErrorMiddleware(BaseHTTPMiddleware):
    """Catch any unhandled exception and return a structured JSON 500 response.

    This middleware ensures that API clients always receive JSON — never HTML —
    even when an unexpected exception occurs deep in the call stack.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            import datetime
            # Update last_error_ts in main module if available.
            try:
                import neolex.main as _main
                _main._last_error_ts = datetime.datetime.now(datetime.UTC).isoformat()
            except Exception:
                pass

            request_id = getattr(request.state, "request_id", "unknown")
            logger.exception(
                "Unhandled exception caught by JSONErrorMiddleware",
                extra={"request_id": request_id, "path": request.url.path},
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": "An unexpected error occurred.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )
