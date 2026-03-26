"""NeoLex FastAPI application.

Entry point for the NeoLex legal QA API. The lifespan context manager pre-warms
all ML model singletons before serving requests — this prevents cross-encoder
deadlocks under concurrent cold-start load (see arlc/pipeline.py lines 1491-1493).
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from neolex.config import settings
from neolex.routers import health
from neolex.routers import query as query_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
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
        app.state.ready = True
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
    title="NeoLex",
    version="0.1.0",
    description="Legal QA API backed by the ARLC pipeline.",
    lifespan=lifespan,
)

# CORS: dev allows localhost:3000 (Next.js), production locks to Tailscale domain
# via ALLOWED_ORIGINS env var (NFR-07).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Routers
app.include_router(health.router)
app.include_router(query_router.router)
