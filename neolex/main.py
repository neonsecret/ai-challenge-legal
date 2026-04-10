"""Vitreon Legal FastAPI application.

Entry point for the Vitreon Legal API. The lifespan context manager pre-warms
all ML model singletons before serving requests — this prevents cross-encoder
deadlocks under concurrent cold-start load (see arlc/pipeline.py lines 1491-1493).
"""

# Load .env BEFORE any other imports — Settings reads os.environ at class definition time.
from dotenv import load_dotenv as _load_dotenv

_load_dotenv(override=False)

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from neolex.auth import email_auth as email_auth_router
from neolex.auth import oauth as oauth_router
from neolex.config import settings
from neolex.logging_config import configure_logging
from neolex.middleware.error_handler import JSONErrorMiddleware
from neolex.middleware.request_id import RequestIDMiddleware
from neolex.middleware.timeout import TimeoutMiddleware
from neolex.routers import admin as admin_router
from neolex.routers import documents as documents_router
from neolex.routers import drafting as drafting_router
from neolex.routers import feedback as feedback_router
from neolex.routers import health, stripe_router
from neolex.routers import query as query_router
from neolex.routers import templates as templates_router
from neolex.routers import web_proxy as web_proxy_router
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


class CSRFMiddleware(BaseHTTPMiddleware):
    """Require X-Requested-With header on state-mutating requests.

    Browsers don't send custom headers on cross-origin form submissions,
    so this blocks CSRF when combined with SameSite=Lax cookies.
    Exempt: Stripe webhooks (signature-verified), health checks, OPTIONS,
    auth callbacks (OAuth redirects).
    """

    _EXEMPT = ("/health", "/stripe/webhook", "/auth/google/callback", "/auth/verify-email")
    _MUTATING = ("POST", "PUT", "DELETE", "PATCH")

    async def dispatch(self, request, call_next):
        if (
            request.method in self._MUTATING
            and not any(request.url.path.startswith(p) for p in self._EXEMPT)
            and request.headers.get("x-requested-with") != "XMLHttpRequest"
        ):
            return JSONResponse({"detail": "Missing CSRF header"}, status_code=403)
        return await call_next(request)


async def _cleanup_expired() -> None:
    """Periodic cleanup of expired sessions, auth tokens, and old conversation data.

    GDPR data retention enforcement:
    - Sessions and auth tokens: deleted when expired (30-day TTL set at creation)
    - Conversation messages: deleted after 90 days
    - Conversation docs: deleted when no messages remain for that conversation
    """
    from datetime import timedelta

    from sqlalchemy import delete as sql_delete
    from sqlalchemy import select as sql_select

    from neolex.db.models import AuthToken, ConversationDocs, ConversationMessage, PipelineJob, Session
    from neolex.db.postgres import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.now(UTC)

                # 1. Expired sessions and auth tokens
                await db.execute(sql_delete(Session).where(Session.expires_at < now))
                await db.execute(sql_delete(AuthToken).where(AuthToken.expires_at < now))

                # 2. Conversation messages older than 90 days (GDPR retention)
                cutoff_90d = now - timedelta(days=90)
                result = await db.execute(
                    sql_delete(ConversationMessage).where(ConversationMessage.created_at < cutoff_90d),
                )
                deleted_msgs = result.rowcount

                # 3. Orphaned conversation docs (no remaining messages)
                if deleted_msgs > 0:
                    result2 = await db.execute(
                        sql_delete(ConversationDocs).where(
                            ~ConversationDocs.conversation_id.in_(
                                sql_select(ConversationMessage.conversation_id).distinct(),
                            ),
                        ),
                    )
                    deleted_docs = result2.rowcount
                else:
                    deleted_docs = 0

                # 4. Pipeline jobs older than 24 hours (ephemeral status tracking)
                cutoff_24h = now - timedelta(hours=24)
                result3 = await db.execute(sql_delete(PipelineJob).where(PipelineJob.created_at < cutoff_24h))
                deleted_jobs = result3.rowcount

                await db.commit()
                logger.info(
                    "Cleanup complete: expired sessions/tokens, %d old messages, %d orphaned conv docs, %d old pipeline jobs",
                    deleted_msgs,
                    deleted_docs,
                    deleted_jobs,
                )
        except Exception:
            logger.exception("Periodic cleanup failed")
        await asyncio.sleep(3600)  # Every hour


async def _cleanup_scheduled_corpus_deletions() -> None:
    """Nightly job: execute corpus deletions whose grace period has expired.

    Queries users where corpus_deletion_scheduled_at <= now(), runs the
    corpus cleanup for each, then clears the column so they are not re-processed.
    Runs once per day — intentionally after the hourly session cleanup to avoid
    database contention during peak usage.
    """
    from sqlalchemy import select as sql_select

    from neolex.db.models import User
    from neolex.db.postgres import AsyncSessionLocal
    from neolex.routers.stripe_router import _delete_user_corpora

    async def _run_once() -> None:
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.now(UTC)
                result = await db.execute(
                    sql_select(User).where(
                        User.corpus_deletion_scheduled_at != None,  # noqa: E711
                        User.corpus_deletion_scheduled_at <= now,
                    )
                )
                users_due = result.scalars().all()

            for user in users_due:
                try:
                    # TOCTOU guard: re-fetch under a fresh query before deleting.
                    # The user may have re-subscribed between the bulk fetch and now,
                    # which clears corpus_deletion_scheduled_at — skip in that case.
                    async with AsyncSessionLocal() as guard_db:
                        guard = (
                            await guard_db.execute(
                                sql_select(User).where(
                                    User.id == user.id,
                                    User.corpus_deletion_scheduled_at != None,  # noqa: E711
                                    User.corpus_deletion_scheduled_at <= now,
                                )
                            )
                        ).scalar_one_or_none()
                    if guard is None:
                        logger.info("Corpus deletion skipped — field cleared since fetch (user %s)", user.id)
                        continue
                    await _delete_user_corpora(user)
                    async with AsyncSessionLocal() as db:
                        # Reload user in new session to safely clear the field
                        to_clear = (await db.execute(sql_select(User).where(User.id == user.id))).scalar_one_or_none()
                        if to_clear:
                            to_clear.corpus_deletion_scheduled_at = None
                            await db.commit()
                    logger.info("Corpus deletion complete for user %s", user.id)
                except Exception:
                    logger.exception("Corpus deletion failed for user %s", user.id)
        except Exception:
            logger.exception("Scheduled corpus deletion job failed")

    # Run once immediately at startup to catch any deletions that were due
    # while the server was offline (e.g. after a restart during the grace period).
    await _run_once()

    while True:
        await asyncio.sleep(86400)  # 24 hours between runs
        await _run_once()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    # Fail fast if data/ or required env vars are missing.
    validate_startup(settings.data_dir)

    logger.info("Vitreon Legal startup: importing pipeline modules...")
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

        logger.info("Pre-warming retriever singletons (PostgreSQL, cross-encoder)...")
        await asyncio.to_thread(_ret.get_chunk_count, "difc")
        await asyncio.to_thread(_ret.get_chunk_count, "czech")
        await asyncio.to_thread(_ret.get_chunk_count, "uk")
        await asyncio.to_thread(_ret.get_chunk_count, "au")
        await asyncio.to_thread(_ret.get_chunks_by_doc)
        reranker = await asyncio.to_thread(_ret.get_reranker)
        await asyncio.to_thread(_ret.get_embedding_model)
        # Fire one dummy rerank to compile the MPS Metal graph — first real call drops from 6s to 3.6s
        await asyncio.to_thread(reranker.predict, [("warm up", "warm up")])
        logger.info("Retriever singletons warmed.")

        # Semaphore: 5 workers = cross-encoder lock contention limit (per PIPE-03).
        # Mirrors the --workers 5 flag in the CLI pipeline.
        app.state.semaphore = asyncio.Semaphore(settings.workers)
        app.state.workers = settings.workers

        # Initialize all PostgreSQL tables (auth + billing + operational).
        if settings.database_url:
            from neolex.db.postgres import init_db as init_pg

            await init_pg()
            logger.info("PostgreSQL tables initialized.")

        # Start periodic cleanup of expired sessions and auth tokens.
        app.state.cleanup_task = asyncio.create_task(_cleanup_expired())

        # Start nightly corpus deletion job (executes grace-period deletions).
        app.state.corpus_deletion_task = asyncio.create_task(_cleanup_scheduled_corpus_deletions())

        # Initialize Langfuse observability (no-op when LANGFUSE_ENABLED is false).
        from neolex.observability import init_observability

        init_observability()

        app.state.ready = True
        app.state.startup_time = time.monotonic()
        logger.info("Vitreon Legal startup complete. Ready to serve requests.")

    except Exception as exc:
        logger.exception("Startup failed: %s", exc)
        app.state.ready = False
        # Re-raise so uvicorn exits with non-zero code on hard failure
        raise

    yield  # serve requests

    # --- SHUTDOWN ---
    logger.info("Vitreon Legal shutting down.")
    cleanup_task = getattr(app.state, "cleanup_task", None)
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
    corpus_deletion_task = getattr(app.state, "corpus_deletion_task", None)
    if corpus_deletion_task and not corpus_deletion_task.done():
        corpus_deletion_task.cancel()
    # Dispose the SQLAlchemy async engine to release all pooled connections
    from neolex.db.postgres import engine as pg_engine

    await pg_engine.dispose()
    logger.info("PostgreSQL engine disposed.")

    # Flush pending Langfuse spans before exit (no-op when disabled).
    from neolex.observability import shutdown_observability

    shutdown_observability()

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

# Initialize ready state before lifespan so tests that skip startup can read it.
app.state.ready = False


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
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)
# CSRF middleware: require X-Requested-With header on state-mutating requests.
# Must be added before CORS so it runs after CORS (Starlette processes in reverse order).
app.add_middleware(CSRFMiddleware)
# SessionMiddleware is required by authlib's starlette OAuth client
# to store the CSRF state between the redirect and the callback.
from starlette.middleware.sessions import SessionMiddleware

if not settings.jwt_secret_key:
    raise RuntimeError("JWT_SECRET_KEY environment variable must be set")
app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret_key)
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
app.include_router(feedback_router.router)
app.include_router(oauth_router.router)
app.include_router(email_auth_router.router)
app.include_router(stripe_router.router)
app.include_router(web_proxy_router.router)
app.include_router(templates_router.router)
app.include_router(drafting_router.router)
