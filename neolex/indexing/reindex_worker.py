"""Background reindex worker for per-client document indexing (Phase 3).

Architecture:
- Jobs are tracked in PostgreSQL (reindex_jobs table) via AuditDB.
- Reindex runs in a background asyncio Task (non-blocking for the API caller).
- On completion, the worker updates app.state to hot-swap the index (PIPE-06).
- The actual indexing is delegated to _run_indexing(), which wraps arlc/ tooling.

For v1 single-tenant, client_slug is always "default".
For multi-tenant readiness, all operations are scoped by client_slug.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from neolex.services.document_manager import client_docs_dir, client_index_dir, mark_indexed

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Startup dependency check
# ---------------------------------------------------------------------------

try:
    import pymupdf  # noqa: F401
except ImportError:
    logger.warning(
        "pymupdf is not installed — PDF corpus indexing jobs will be marked as failed. Run: uv pip install pymupdf"
    )


# ---------------------------------------------------------------------------
# Job store (PostgreSQL via AuditDB)
# ---------------------------------------------------------------------------


async def create_job(client_slug: str) -> str:
    """Insert a new reindex_jobs row and return the job_id."""
    from neolex.db.audit import get_audit_db

    job_id = str(uuid.uuid4())
    ts = datetime.datetime.utcnow().isoformat()

    async with get_audit_db() as db:
        await db.create_reindex_job(
            job_id=job_id,
            client_slug=client_slug,
            started_at=ts,
        )

    return job_id


async def get_job(job_id: str) -> dict | None:
    """Return job status dict or None if not found."""
    from neolex.db.audit import get_audit_db

    async with get_audit_db() as db:
        row = await db.get_reindex_job(job_id)

    if row is None:
        return None
    return row


async def update_job(
    job_id: str,
    *,
    status: str,
    progress: float = 0.0,
    completed_at: str | None = None,
    error: str | None = None,
    doc_count: int = 0,
) -> None:
    """Update job status in PostgreSQL."""
    from neolex.db.audit import get_audit_db

    async with get_audit_db() as db:
        await db.update_reindex_job(
            job_id=job_id,
            status=status,
            progress=progress,
            completed_at=completed_at,
            error=error,
            doc_count=doc_count,
        )


# ---------------------------------------------------------------------------
# Actual indexing logic
# ---------------------------------------------------------------------------


def _run_indexing_sync(client_slug: str, docs_dir: Path, index_dir: Path) -> tuple[int, int]:
    """Synchronous indexing implementation.

    Tries to use arlc/indexing/indexer.py if available.
    Falls back to a lightweight stub that tracks documents without embeddings.

    Returns (doc_count, chunks_skipped).
    """
    # Count indexed documents from meta files, supporting PDF and TXT formats.
    # Avoid double-counting UUID-prefixed file names by resolving via meta sidecars.
    meta_files = list(docs_dir.glob("*.meta"))
    doc_ids_with_docs = set()

    for meta_path in meta_files:
        try:
            meta = json.loads(meta_path.read_text())
            doc_id = meta.get("doc_id", "")
            # Accept any supported extension (.pdf or .txt).
            doc_path = next(
                (p for p in docs_dir.glob(f"{doc_id}_*") if p.suffix in {".pdf", ".txt"}),
                None,
            )
            if doc_path and doc_path.exists():
                doc_ids_with_docs.add(doc_id)
        except Exception:
            pass

    doc_count = len(doc_ids_with_docs)
    chunks_skipped = 0

    # Attempt real arlc indexing.
    # Only HTTP 400 from llama-server (bad chunk / context-window overflow) is
    # treated as a recoverable per-chunk failure — we stub that case and increment
    # chunks_skipped so the job completes with a warning.
    # All other exceptions (DB errors, ImportError, network failures, etc.) are
    # re-raised so run_reindex_job() can mark the job as "failed".
    try:
        _run_arlc_indexing(client_slug, docs_dir, index_dir, list(doc_ids_with_docs))
    except Exception as exc:
        # Detect HTTP 400 from llama-server specifically
        try:
            import requests

            if isinstance(exc, requests.exceptions.HTTPError):
                status_code = getattr(exc.response, "status_code", 0)
                if status_code == 400:
                    logger.error(
                        "llama-server returned 400 during indexing — chunk likely exceeds context window: %s",
                        exc,
                    )
                    chunks_skipped += 1
                    # Stub manifest for this HTTP-400 case only
                    manifest = {
                        "client_slug": client_slug,
                        "indexed_at": datetime.datetime.utcnow().isoformat(),
                        "doc_count": doc_count,
                        "docs": [str(p) for p in docs_dir.glob("*.meta")],
                        "stub": True,
                        "chunks_skipped": chunks_skipped,
                    }
                    manifest_path = index_dir / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest, indent=2))
                    return doc_count, chunks_skipped
                # Non-400 HTTP error: re-raise
                logger.error("llama-server HTTP %d during indexing: %s", status_code, exc)
                raise
        except ImportError:
            pass

        # Non-HTTP exception (ImportError for arlc, DB error, etc.): re-raise
        raise

    return doc_count, chunks_skipped


_reindex_lock = threading.Lock()


def _run_arlc_indexing(
    client_slug: str,
    docs_dir: Path,
    index_dir: Path,
    doc_ids: list[str],
) -> None:
    """Call arlc/indexing/indexer.py for real vector indexing into PostgreSQL.

    Temporarily overrides DOCUMENTS_DIR for the client's corpus, then calls
    build_index() with the client_slug as both corpus and tenant_id so chunks
    are scoped correctly in the PostgreSQL chunks table.

    If arlc dependencies are not available, raises ImportError (caller stubs).
    """
    import importlib

    indexer = importlib.import_module("arlc.indexing.indexer")

    # Serialize concurrent reindex operations to prevent monkey-patching races
    # on DOCUMENTS_DIR.
    with _reindex_lock:
        original_docs_dir = indexer.DOCUMENTS_DIR
        try:
            indexer.DOCUMENTS_DIR = str(docs_dir)
            indexer.build_index(corpus=client_slug, tenant_id=client_slug)
        finally:
            indexer.DOCUMENTS_DIR = original_docs_dir


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def run_reindex_job(
    job_id: str,
    client_slug: str,
    app: "FastAPI | None" = None,
) -> None:
    """Async background task: runs indexing and updates job status.

    Called via asyncio.create_task() — does not block the API caller.

    On completion, updates app.state index references if app is provided (PIPE-06 hot-swap).
    """
    docs_dir = client_docs_dir(client_slug)
    index_dir = client_index_dir(client_slug)

    logger.info("Reindex job %s starting for client %s", job_id, client_slug)

    await update_job(job_id, status="running", progress=0.1)

    try:
        # Run the CPU/IO-heavy indexing in a thread to avoid blocking the event loop
        doc_count, chunks_skipped = await asyncio.to_thread(_run_indexing_sync, client_slug, docs_dir, index_dir)

        status = "complete" if chunks_skipped == 0 else "complete_with_warnings"
        await update_job(
            job_id,
            status=status,
            progress=1.0,
            completed_at=datetime.datetime.utcnow().isoformat(),
            doc_count=doc_count,
            error=(f"{chunks_skipped} chunk(s) skipped during embedding" if chunks_skipped > 0 else None),
        )

        # Mark all documents as indexed in sidecar meta files + audit DB
        from neolex.db.audit import get_audit_db

        for meta_path in docs_dir.glob("*.meta"):
            try:
                meta = json.loads(meta_path.read_text())
                mark_indexed(client_slug, meta["doc_id"])
            except Exception:
                pass

        # Update indexed flag in audit database
        try:
            async with get_audit_db() as audit_db:
                for meta_path in docs_dir.glob("*.meta"):
                    try:
                        meta = json.loads(meta_path.read_text())
                        await audit_db.mark_document_indexed(meta["doc_id"], client_slug)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Failed to update indexed flags in audit DB: %s", e)

        logger.info(
            "Reindex job %s complete: %d docs indexed for client %s (chunks_skipped=%d)",
            job_id,
            doc_count,
            client_slug,
            chunks_skipped,
        )

        # Hot-swap index in app.state (PIPE-06) — optional, only if app provided
        if app is not None:
            _hot_swap_index(app, client_slug, index_dir)

    except Exception as exc:
        logger.exception("Reindex job %s failed: %s", job_id, exc)
        try:
            await update_job(
                job_id,
                status="failed",
                completed_at=datetime.datetime.utcnow().isoformat(),
                error="Indexing failed. Please try again or contact support.",
            )
        except Exception as update_exc:
            # DB may be down — log at CRITICAL so it surfaces even if the job
            # row stays stuck in "running". Do not re-raise: the background task
            # has already failed and there's nothing useful left to do.
            logger.critical(
                "Reindex job %s: FAILED to record failure in DB — job may appear stuck as 'running'. DB error: %s",
                job_id,
                update_exc,
            )


def _hot_swap_index(app: "FastAPI", client_slug: str, index_dir: Path) -> None:
    """Evict in-memory chunk caches so the retriever sees newly indexed documents."""
    try:
        from arlc.retriever import invalidate_corpus_cache

        invalidate_corpus_cache(client_slug)
        logger.info("Cache evicted for client %s after reindex", client_slug)
    except Exception as exc:
        logger.warning("Cache eviction failed (non-fatal): %s", exc)
