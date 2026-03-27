"""NeoLex FastAPI application.

Entry point for the NeoLex legal QA API. The lifespan context manager pre-warms
all ML model singletons before serving requests — this prevents cross-encoder
deadlocks under concurrent cold-start load (see arlc/pipeline.py lines 1491-1493).
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from neolex.config import settings
from neolex.logging_config import configure_logging
from neolex.middleware.error_handler import JSONErrorMiddleware
from neolex.middleware.request_id import RequestIDMiddleware
from neolex.middleware.timeout import TimeoutMiddleware
from neolex.routers import health
from neolex.routers import query as query_router
from neolex.routers import admin as admin_router
from neolex.routers import documents as documents_router
from neolex.routers import demo as demo_router
from neolex.startup_validation import validate_startup

# Configure logging before anything else.
configure_logging()

logger = logging.getLogger(__name__)

# Server-wide metrics (single-process only — no Redis needed at this scale).
_startup_time: float = time.monotonic()
_request_count: int = 0
_last_error_ts: str | None = None
_latency_sum_ms: float = 0.0
_latency_count: int = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    # Fail fast if data/ or required env vars are missing.
    validate_startup(settings.data_dir)

    logger.info("NeoLex startup: importing pipeline modules...")
    try:
        # Import inside lifespan so errors are caught here, not at module level.
        # _import_pipeline_modules prints status to stdout for each submodule.
        from arlc.pipeline import _import_pipeline_modules
        route_fn, retrieve_fn, answer_fn = _import_pipeline_modules()

        app.state.route_fn = route_fn
        app.state.retrieve_fn = retrieve_fn
        app.state.answer_fn = answer_fn

        # Pre-warm retriever singletons.
        # CRITICAL: must happen before any request is served.
        # If singletons are not pre-warmed, concurrent cold-start requests race
        # to acquire threading.Lock objects. asyncio.wait_for cancellation leaves
        # the OS thread holding the lock — permanent deadlock.
        # (See arlc/pipeline.py lines 1491-1503 for original pattern.)
        import arlc.retriever as _ret
        logger.info("Pre-warming retriever singletons (FAISS, BM25, cross-encoder)...")
        await asyncio.to_thread(_ret.get_chunks_by_doc)
        await asyncio.to_thread(_ret.get_reranker)
        await asyncio.to_thread(_ret.get_embedding_model)
        logger.info("Retriever singletons warmed.")

        # Semaphore: 5 workers = cross-encoder lock contention limit (per PIPE-03).
        # Mirrors the --workers 5 flag in the CLI pipeline.
        app.state.semaphore = asyncio.Semaphore(settings.workers)
        app.state.workers = settings.workers

        # Initialize audit DB schema (WAL mode, idempotent).
        from neolex.db.audit import get_audit_db
        async with get_audit_db() as db:
            await db.init_schema()
        logger.info("Audit DB initialized at %s (WAL mode).", settings.db_path)

        # Demo mode: ensure a demo API key exists.
        if settings.demo_mode:
            from neolex.demo_setup import ensure_demo_key
            demo_key = await ensure_demo_key()
            if demo_key:
                logger.info("Demo mode: created demo API key with prefix %s", demo_key[:8])
            else:
                logger.info("Demo mode: demo API key already exists.")

        app.state.ready = True
        app.state.startup_time = time.monotonic()
        logger.info("NeoLex startup complete. Ready to serve requests.")

    except Exception as exc:
        logger.exception("Startup failed: %s", exc)
        app.state.ready = False
        # Re-raise so uvicorn exits with non-zero code on hard failure
        raise

    yield  # serve requests

    # --- SHUTDOWN ---
    logger.info("NeoLex shutting down.")
    app.state.ready = False


app = FastAPI(
    title="Vitreon Legal API",
    version="0.1.0",
    description="Legal QA API backed by the ARLC pipeline.",
    lifespan=lifespan,
    # Disable public API docs in production
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# ---------------------------------------------------------------------------
# Global exception handler — catch ALL unhandled exceptions and return JSON.
# Without this, Starlette returns an HTML 500 page which breaks API clients.
#
# Implementation note: @app.exception_handler(Exception) does NOT catch
# unhandled errors in modern Starlette — they bypass the exception handler
# stack and go to ServerErrorMiddleware which returns HTML by default.
# We override that middleware handler via app.middleware_stack is not safe
# to change after startup, so instead we provide a custom handler through
# the `exception_handler` kwarg on the ServerErrorMiddleware which is the
# outermost middleware in the Starlette stack.
# The cleanest approach is to add it as a middleware with a custom handler:
# ---------------------------------------------------------------------------

async def _json_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a JSON 500 response for any unhandled server-side exception."""
    global _last_error_ts
    import datetime
    _last_error_ts = datetime.datetime.now(datetime.UTC).isoformat()
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "Unhandled exception",
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


# Also register as @app.exception_handler to catch any exceptions that do
# reach the app-level exception handler (e.g. from middleware).
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return await _json_error_handler(request, exc)


# ---------------------------------------------------------------------------
# Middleware stack (order matters: outer middleware wraps inner ones).
# 1. RequestIDMiddleware — must be outermost to ensure request_id is available
#    to TimeoutMiddleware and all downstream handlers.
# 2. TimeoutMiddleware — wraps the entire request lifecycle.
# 3. CORSMiddleware — must be innermost so CORS headers appear on all responses
#    including error responses from the middleware above.
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(TimeoutMiddleware, timeout_seconds=settings.request_timeout_seconds)
app.add_middleware(RequestIDMiddleware)
# JSONErrorMiddleware must be outermost (registered last) so it wraps
# RequestIDMiddleware and all inner layers. Starlette processes add_middleware
# calls in reverse order — the last-added middleware is the outermost wrapper.
app.add_middleware(JSONErrorMiddleware)

# Routers
app.include_router(health.router)
app.include_router(query_router.router)
app.include_router(admin_router.router)
app.include_router(documents_router.router)
app.include_router(demo_router.router)
