"""Document management endpoints — Phase 3.

Routes:
    POST   /api/v1/documents              — upload PDF (DOC-01, DOC-02, DOC-03, DOC-04)
    POST   /api/v1/documents/upload-zip   — upload ZIP of PDFs (batch upload)
    GET    /api/v1/documents              — list documents (DOC-06)
    DELETE /api/v1/documents/{doc_id}     — delete document + trigger reindex (DOC-07)
    POST   /api/v1/documents/reindex      — manually trigger reindex
    GET    /api/v1/documents/reindex/{job_id} — poll reindex status (DOC-05)
    GET    /api/v1/documents/{doc_id}/pdf — serve raw PDF for source viewer
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.auth.middleware import get_api_key
from neolex.config import settings
from neolex.db.audit import get_audit_db
from neolex.db.models import User
from neolex.db.postgres import get_db
from neolex.schemas.documents import (
    DocumentDeleteResponse,
    DocumentUploadResponse,
    ReindexJobResponse,
    ZipUploadResponse,
    ZipUploadResult,
)
from neolex.services.document_manager import (
    MAX_UPLOAD_BYTES,
    MAX_ZIP_BYTES,
    client_docs_dir,
    delete_document,
    extract_zip_safely,
    get_collection_names,
    save_doc_meta,
    save_upload,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _log_task_exception(task: asyncio.Task) -> None:
    """Log exceptions from fire-and-forget tasks."""
    if not task.cancelled() and task.exception():
        logger.error("Background task failed: %s", task.exception())


# ---------------------------------------------------------------------------
# Plan-based upload limits
# ---------------------------------------------------------------------------

_PLAN_MAX_CORPORA: dict[str, int] = {
    "free": 0,
    "trial": 0,
    "starter": settings.starter_max_corpora,
    "pro": settings.pro_max_corpora,
    "enterprise": settings.enterprise_max_corpora,
}

_PLAN_MAX_DOCS: dict[str, int] = {
    "free": 0,
    "trial": 0,
    "starter": settings.starter_max_docs_per_corpus,
    "pro": settings.pro_max_docs_per_corpus,
    "enterprise": settings.enterprise_max_docs_per_corpus,
}

_PLAN_MAX_SIZE_MB: dict[str, int] = {
    "free": 0,
    "trial": 0,
    "starter": settings.starter_max_corpus_size_mb,
    "pro": settings.pro_max_corpus_size_mb,
    "enterprise": settings.enterprise_max_corpus_size_mb,
}


async def _enforce_upload_limits(
    user: User,
    content_size: int,
    db_audit,
    collection: str,
) -> None:
    """Check subscription plan limits for document uploads.

    Raises 403 for free-tier users and 429 when paid-plan limits are exceeded.
    Checks (in order): plan tier, document count, corpus size, corpora count.
    """
    status = user.subscription_status

    # Free / trial users cannot upload at all
    if status in ("free", "trial"):
        raise HTTPException(
            status_code=403,
            detail="Document uploads require a paid plan. Please upgrade to Starter or higher.",
        )

    # Unknown / canceled plans
    max_docs = _PLAN_MAX_DOCS.get(status)
    if max_docs is None:
        raise HTTPException(
            status_code=403,
            detail="Active subscription required for document uploads.",
        )

    # Enforce per-corpus document count limit
    client_slug = str(user.id)
    rows = await db_audit.list_documents(client_slug)
    current_count = len(rows)

    if current_count >= max_docs:
        raise HTTPException(
            status_code=429,
            detail=f"Document limit reached ({max_docs} documents on {status.title()} plan). "
            f"Upgrade your plan for more capacity.",
        )

    # Enforce per-corpus total size limit
    max_size_bytes = _PLAN_MAX_SIZE_MB[status] * 1024 * 1024
    current_size = sum(r.get("size_bytes", 0) for r in rows)
    if current_size + content_size > max_size_bytes:
        max_mb = _PLAN_MAX_SIZE_MB[status]
        raise HTTPException(
            status_code=429,
            detail=f"Corpus size limit reached ({max_mb} MB on {status.title()} plan). "
            f"Delete existing documents or upgrade your plan.",
        )

    # Enforce corpora (collections) count limit
    max_corpora = _PLAN_MAX_CORPORA.get(status, 0)
    existing_collections = await asyncio.to_thread(get_collection_names, client_slug)

    if len(existing_collections) > max_corpora:
        # User is already over the limit — most likely due to a plan downgrade.
        # Block all new uploads until they delete collections to get under the limit.
        raise HTTPException(
            status_code=429,
            detail=(
                f"You have {len(existing_collections)} collections but your {status.title()} plan "
                f"allows {max_corpora}. Delete collections or upgrade to continue uploading."
            ),
        )

    if collection not in existing_collections and len(existing_collections) >= max_corpora:
        # This upload would create a new collection that exceeds the plan limit.
        raise HTTPException(
            status_code=429,
            detail=(
                f"Collection limit reached ({max_corpora} collections on {status.title()} plan). "
                f"Delete a collection or upgrade your plan to create new ones."
            ),
        )


# ---------------------------------------------------------------------------
# POST /api/v1/documents  (DOC-01, DOC-02, DOC-03, DOC-04)
# ---------------------------------------------------------------------------


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection: str = Form("My Documents"),
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a PDF document into the client's private corpus.

    - Checks subscription plan limits → 403 for free tier, 429 when exceeded
    - Validates MIME type (PDF only) → 415 on mismatch
    - Validates file size (≤50MB) → 413 on oversize
    - Saves to data/clients/<slug>/docs/
    - Triggers background reindex and returns job_id
    """
    client_slug = key_row["client_slug"]

    # --- Enforce subscription plan limits ---
    user_id = key_row.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # --- Validate content type ---
    ct = (file.content_type or "").lower()
    if ct not in ("application/pdf",):
        async with get_audit_db() as audit_db:
            await audit_db.log_event(
                key_hash=key_row["key_hash"],
                event_type="upload",
                detail={"filename": file.filename, "status": "rejected_type", "content_type": ct},
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ct}'. Only application/pdf is accepted.",
        )

    # --- Early Content-Length guard (reject before buffering) ---
    cl = request.headers.get("content-length")
    try:
        if cl and int(cl) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
    except (ValueError, TypeError):
        pass  # Malformed Content-Length header — let the actual size check handle it

    # --- Read and validate ---
    content = await file.read()

    # Check plan limits (needs content size for corpus size enforcement)
    async with get_audit_db() as audit_db:
        await _enforce_upload_limits(user, len(content), audit_db, collection)

    # Reject empty files
    if len(content) == 0:
        async with get_audit_db() as audit_db:
            await audit_db.log_event(
                key_hash=key_row["key_hash"],
                event_type="upload",
                detail={"filename": file.filename, "status": "rejected_empty"},
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(
            status_code=400,
            detail="File is empty (0 bytes). Upload a valid PDF document.",
        )

    if len(content) > MAX_UPLOAD_BYTES:
        async with get_audit_db() as audit_db:
            await audit_db.log_event(
                key_hash=key_row["key_hash"],
                event_type="upload",
                detail={
                    "filename": file.filename,
                    "status": "rejected_size",
                    "size_bytes": len(content),
                },
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content)} bytes). Maximum is {MAX_UPLOAD_BYTES} bytes (50MB).",
        )

    # --- Save file ---
    try:
        meta = await asyncio.to_thread(
            save_upload,
            client_slug,
            file.filename or "upload.pdf",
            content,
            collection,
        )
    except ValueError as exc:
        # Invalid PDF magic bytes or size guard
        status_code = 413 if "too large" in str(exc) else 415
        async with get_audit_db() as audit_db:
            await audit_db.log_event(
                key_hash=key_row["key_hash"],
                event_type="upload",
                detail={"filename": file.filename, "status": "rejected_invalid", "error": str(exc)},
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    # --- Persist to document registry (DB) ---
    async with get_audit_db() as audit_db:
        await audit_db.register_document(
            doc_id=meta["doc_id"],
            client_slug=client_slug,
            filename=meta["filename"],
            size_bytes=meta["size_bytes"],
            upload_ts=meta["upload_ts"],
        )

    # --- Write sidecar .meta file ---
    await asyncio.to_thread(save_doc_meta, client_slug, meta)

    # --- Trigger background reindex (non-blocking) ---
    from neolex.indexing.reindex_worker import create_job, run_reindex_job

    job_id = await create_job(client_slug)
    task = asyncio.create_task(
        run_reindex_job(job_id, client_slug, app=request.app),
        name=f"reindex-{job_id[:8]}",
    )
    task.add_done_callback(_log_task_exception)

    # --- Audit log ---
    async with get_audit_db() as audit_db:
        await audit_db.log_event(
            key_hash=key_row["key_hash"],
            event_type="upload",
            detail={
                "doc_id": meta["doc_id"],
                "filename": meta["filename"],
                "size_bytes": meta["size_bytes"],
                "status": "accepted",
                "job_id": job_id,
            },
            ip=getattr(request.client, "host", None),
            user_agent=request.headers.get("user-agent"),
        )

    logger.info(
        "Uploaded document %s (%d bytes) for client %s — reindex job %s started",
        meta["doc_id"],
        meta["size_bytes"],
        client_slug,
        job_id,
    )

    return DocumentUploadResponse(
        doc_id=meta["doc_id"],
        filename=meta["filename"],
        size_bytes=meta["size_bytes"],
        client_slug=client_slug,
        upload_ts=meta["upload_ts"],
        job_id=job_id,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/documents/upload-zip
# ---------------------------------------------------------------------------

_VALID_ZIP_CONTENT_TYPES = frozenset(
    {
        "application/zip",
        "application/x-zip-compressed",
        "application/x-zip",
    },
)


@router.post("/upload-zip", response_model=ZipUploadResponse, status_code=201)
async def upload_zip(
    request: Request,
    file: UploadFile = File(...),
    collection: str = Form("My Documents"),
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> ZipUploadResponse:
    """Upload a ZIP archive containing multiple PDFs.

    - Extracts PDFs safely (zip bomb protection, path traversal checks)
    - Registers each valid PDF into the client's corpus
    - Triggers a single background reindex job
    - Returns per-file results (uploaded / skipped / error)
    """
    client_slug = key_row["client_slug"]

    # --- Auth: resolve user ---
    user_id = key_row.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # --- Validate content type ---
    ct = (file.content_type or "").lower()
    fname = (file.filename or "").lower()
    if ct not in _VALID_ZIP_CONTENT_TYPES and not (ct == "application/octet-stream" and fname.endswith(".zip")):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ct}'. Expected a ZIP archive.",
        )

    # --- Early Content-Length guard (reject before buffering) ---
    cl = request.headers.get("content-length")
    try:
        if cl and int(cl) > MAX_ZIP_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
    except (ValueError, TypeError):
        pass  # Malformed Content-Length header — let the actual size check handle it

    # --- Read ZIP bytes ---
    zip_bytes = await file.read()
    if len(zip_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty (0 bytes).")
    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP file too large ({len(zip_bytes)} bytes). Maximum is {MAX_ZIP_BYTES // (1024 * 1024)} MB.",
        )

    # --- Extract safely (runs sync I/O in thread) ---
    try:
        valid_pdfs, skipped_files = await asyncio.to_thread(
            extract_zip_safely,
            zip_bytes,
        )
    except ValueError as exc:
        async with get_audit_db() as audit_db:
            await audit_db.log_event(
                key_hash=key_row["key_hash"],
                event_type="upload_zip",
                detail={
                    "filename": file.filename,
                    "status": "rejected_extraction",
                    "error": str(exc),
                },
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not valid_pdfs and not skipped_files:
        raise HTTPException(status_code=400, detail="ZIP archive is empty.")

    # --- Pre-check plan limits BEFORE saving any files ---
    total_new_size = sum(len(data) for _, data in valid_pdfs)
    new_count = len(valid_pdfs)

    status = user.subscription_status
    if status in ("free", "trial"):
        raise HTTPException(
            status_code=403,
            detail="Document uploads require a paid plan. Please upgrade to Starter or higher.",
        )

    max_docs = _PLAN_MAX_DOCS.get(status)
    if max_docs is None:
        raise HTTPException(
            status_code=403,
            detail="Active subscription required for document uploads.",
        )

    async with get_audit_db() as audit_db:
        existing_rows = await audit_db.list_documents(client_slug)
    existing_count = len(existing_rows)
    existing_size = sum(r.get("size_bytes", 0) for r in existing_rows)

    if existing_count + new_count > max_docs:
        raise HTTPException(
            status_code=429,
            detail=f"Would exceed document limit ({max_docs} on {status.title()} plan). "
            f"You have {existing_count} documents and are trying to add {new_count}.",
        )

    max_size_bytes = _PLAN_MAX_SIZE_MB[status] * 1024 * 1024
    if existing_size + total_new_size > max_size_bytes:
        max_mb = _PLAN_MAX_SIZE_MB[status]
        raise HTTPException(
            status_code=429,
            detail=f"Would exceed corpus size limit ({max_mb} MB on {status.title()} plan). "
            f"Delete existing documents or upgrade your plan.",
        )

    # Enforce corpora (collections) count limit
    max_corpora = _PLAN_MAX_CORPORA.get(status, 0)
    existing_collections = await asyncio.to_thread(get_collection_names, client_slug)

    if len(existing_collections) > max_corpora:
        # User is over the limit (likely due to a plan downgrade) — block all uploads.
        raise HTTPException(
            status_code=429,
            detail=(
                f"You have {len(existing_collections)} collections but your {status.title()} plan "
                f"allows {max_corpora}. Delete collections or upgrade to continue uploading."
            ),
        )

    if collection not in existing_collections and len(existing_collections) >= max_corpora:
        # This upload would create a new collection that exceeds the plan limit.
        raise HTTPException(
            status_code=429,
            detail=(
                f"Collection limit reached ({max_corpora} collections on {status.title()} plan). "
                f"Delete a collection or upgrade your plan to create new ones."
            ),
        )

    # --- Save each valid PDF ---
    file_results: list[ZipUploadResult] = []
    uploaded_doc_ids: list[str] = []
    total_uploaded_bytes = 0

    for pdf_name, pdf_bytes in valid_pdfs:
        try:
            meta = await asyncio.to_thread(
                save_upload,
                client_slug,
                pdf_name,
                pdf_bytes,
                collection,
            )
        except ValueError as exc:
            file_results.append(
                ZipUploadResult(
                    filename=pdf_name,
                    status="error",
                    size_bytes=len(pdf_bytes),
                    error=str(exc),
                ),
            )
            continue

        # Register in document DB
        async with get_audit_db() as audit_db:
            await audit_db.register_document(
                doc_id=meta["doc_id"],
                client_slug=client_slug,
                filename=meta["filename"],
                size_bytes=meta["size_bytes"],
                upload_ts=meta["upload_ts"],
            )

        # Write sidecar .meta
        await asyncio.to_thread(save_doc_meta, client_slug, meta)

        uploaded_doc_ids.append(meta["doc_id"])
        total_uploaded_bytes += meta["size_bytes"]
        file_results.append(
            ZipUploadResult(
                filename=meta["filename"],
                doc_id=meta["doc_id"],
                status="uploaded",
                size_bytes=meta["size_bytes"],
            ),
        )

    # --- Append skipped files to results ---
    for skipped_name, reason in skipped_files:
        file_results.append(
            ZipUploadResult(
                filename=skipped_name,
                status=reason,
            ),
        )

    # --- Trigger ONE reindex job (only if we uploaded at least 1 file) ---
    job_id: str | None = None
    if uploaded_doc_ids:
        from neolex.indexing.reindex_worker import create_job, run_reindex_job

        job_id = await create_job(client_slug)
        task = asyncio.create_task(
            run_reindex_job(job_id, client_slug, app=request.app),
            name=f"reindex-{job_id[:8]}",
        )
        task.add_done_callback(_log_task_exception)

    # --- Audit log ---
    async with get_audit_db() as audit_db:
        await audit_db.log_event(
            key_hash=key_row["key_hash"],
            event_type="upload_zip",
            detail={
                "zip_filename": file.filename,
                "uploaded_count": len(uploaded_doc_ids),
                "skipped_count": len(skipped_files),
                "total_size_bytes": total_uploaded_bytes,
                "doc_ids": uploaded_doc_ids,
                "job_id": job_id,
                "status": "accepted",
            },
            ip=getattr(request.client, "host", None),
            user_agent=request.headers.get("user-agent"),
        )

    uploaded_count = len(uploaded_doc_ids)
    skipped_count = len(file_results) - uploaded_count
    logger.info(
        "ZIP upload: %d uploaded, %d skipped for client %s — job %s",
        uploaded_count,
        skipped_count,
        client_slug,
        job_id,
    )

    return ZipUploadResponse(
        uploaded_count=uploaded_count,
        skipped_count=skipped_count,
        total_size_bytes=total_uploaded_bytes,
        files=file_results,
        job_id=job_id,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/documents  (DOC-06)
# ---------------------------------------------------------------------------


@router.get("")
async def list_documents(
    key_row: dict = Depends(get_api_key),
):
    """List all documents uploaded by this client, with collection info from .meta files."""
    client_slug = key_row["client_slug"]

    async with get_audit_db() as db:
        rows = await db.list_documents(client_slug)

    # Enrich with collection from .meta files
    docs_dir = client_docs_dir(client_slug)
    meta_collections: dict[str, str] = {}
    for meta_path in docs_dir.glob("*.meta"):
        try:
            meta = json.loads(meta_path.read_text())
            meta_collections[meta.get("doc_id", "")] = meta.get("collection", "My Documents")
        except Exception:  # nosec B110
            pass

    docs = []
    for row in rows:
        doc_id = row["doc_id"]
        docs.append(
            {
                "doc_id": doc_id,
                "filename": row["filename"],
                "size_bytes": row["size_bytes"],
                "upload_ts": row["upload_ts"],
                "indexed": bool(row["indexed"]),
                "collection": meta_collections.get(doc_id, "My Documents"),
            },
        )

    return {
        "client_slug": client_slug,
        "documents": docs,
        "total": len(docs),
    }


# ---------------------------------------------------------------------------
# DELETE /api/v1/documents/{doc_id}  (DOC-07)
# ---------------------------------------------------------------------------


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_doc(
    doc_id: str,
    request: Request,
    key_row: dict = Depends(get_api_key),
) -> DocumentDeleteResponse:
    """Delete a document from the client's corpus and trigger reindex."""
    # Validate doc_id format (same pattern as PDF endpoint)
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", doc_id):
        raise HTTPException(status_code=400, detail="Invalid doc_id format")

    client_slug = key_row["client_slug"]

    # Check document belongs to this client (cross-client isolation)
    async with get_audit_db() as db:
        row = await db.get_document(doc_id, client_slug)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found for client '{client_slug}'",
        )

    # Delete from filesystem
    deleted = await asyncio.to_thread(delete_document, client_slug, doc_id)

    # Delete from DB registry
    async with get_audit_db() as db:
        await db.delete_document(doc_id, client_slug)

    # Trigger reindex
    from neolex.indexing.reindex_worker import create_job, run_reindex_job

    job_id = await create_job(client_slug)
    task = asyncio.create_task(
        run_reindex_job(job_id, client_slug, app=request.app),
        name=f"reindex-{job_id[:8]}",
    )
    task.add_done_callback(_log_task_exception)

    # Audit log
    async with get_audit_db() as db:
        await db.log_event(
            key_hash=key_row["key_hash"],
            event_type="delete",
            detail={
                "doc_id": doc_id,
                "client_slug": client_slug,
                "deleted": deleted,
                "job_id": job_id,
            },
            ip=getattr(request.client, "host", None),
            user_agent=request.headers.get("user-agent"),
        )

    logger.info(
        "Deleted document %s for client %s — reindex job %s started",
        doc_id,
        client_slug,
        job_id,
    )

    return DocumentDeleteResponse(
        doc_id=doc_id,
        deleted=deleted,
        job_id=job_id,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/documents/reindex  — manual trigger
# ---------------------------------------------------------------------------


@router.post("/reindex", response_model=ReindexJobResponse, status_code=202)
async def trigger_reindex(
    request: Request,
    key_row: dict = Depends(get_api_key),
) -> ReindexJobResponse:
    """Manually trigger a reindex job for the client's corpus.

    Returns immediately with job_id. Poll GET /api/v1/documents/reindex/{job_id} for status.
    """
    client_slug = key_row["client_slug"]

    from neolex.indexing.reindex_worker import create_job, run_reindex_job

    job_id = await create_job(client_slug)
    task = asyncio.create_task(
        run_reindex_job(job_id, client_slug, app=request.app),
        name=f"reindex-{job_id[:8]}",
    )
    task.add_done_callback(_log_task_exception)

    async with get_audit_db() as db:
        await db.log_event(
            key_hash=key_row["key_hash"],
            event_type="reindex",
            detail={"client_slug": client_slug, "job_id": job_id, "trigger": "manual"},
            ip=getattr(request.client, "host", None),
            user_agent=request.headers.get("user-agent"),
        )

    logger.info("Manual reindex triggered for client %s — job %s", client_slug, job_id)

    return ReindexJobResponse(
        job_id=job_id,
        client_slug=client_slug,
        status="pending",
        progress=0.0,
        started_at=datetime.datetime.utcnow().isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/documents/reindex/{job_id}  (DOC-05)
# ---------------------------------------------------------------------------


@router.get("/reindex/{job_id}", response_model=ReindexJobResponse)
async def get_reindex_status(
    job_id: str,
    key_row: dict = Depends(get_api_key),
) -> ReindexJobResponse:
    """Poll reindex job status. Returns 404 if job_id not found."""
    client_slug = key_row["client_slug"]

    from neolex.indexing.reindex_worker import get_job

    job = await get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Reindex job '{job_id}' not found")

    # Enforce client isolation: job must belong to this client
    if job.get("client_slug") != client_slug:
        raise HTTPException(status_code=404, detail=f"Reindex job '{job_id}' not found")

    return ReindexJobResponse(
        job_id=job["job_id"],
        client_slug=job["client_slug"],
        status=job["status"],
        progress=job["progress"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error=job.get("error"),
        doc_count=job.get("doc_count", 0),
    )


# ---------------------------------------------------------------------------
# PATCH /api/v1/documents/collections/rename  — rename a collection
# ---------------------------------------------------------------------------


@router.patch("/collections/rename")
async def rename_collection(
    request: Request,
    key_row: dict = Depends(get_api_key),
):
    """Rename a collection by updating the 'collection' field in all matching .meta files."""
    body = await request.json()
    old_name = body.get("old_name", "").strip()
    new_name = body.get("new_name", "").strip()

    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Both old_name and new_name are required")
    if len(new_name) > 100:
        raise HTTPException(status_code=400, detail="Collection name too long (max 100 chars)")

    client_slug = key_row["client_slug"]
    docs_dir = client_docs_dir(client_slug)

    # Collect all files to update, then write atomically via temp file + os.replace
    updates: list[tuple[Path, dict]] = []
    for meta_path in docs_dir.glob("*.meta"):
        try:
            meta = json.loads(meta_path.read_text())
            current = meta.get("collection", "My Documents")
            if current == old_name:
                meta["collection"] = new_name
                updates.append((meta_path, meta))
        except Exception:  # nosec B110
            pass

    if not updates:
        raise HTTPException(status_code=404, detail=f"No documents found in collection '{old_name}'")

    for meta_path, meta in updates:
        tmp = meta_path.with_suffix(".meta.tmp")
        tmp.write_text(json.dumps(meta, indent=2))
        os.replace(str(tmp), str(meta_path))  # atomic on POSIX
    updated = len(updates)

    logger.info("Renamed collection '%s' → '%s' for client %s (%d docs)", old_name, new_name, client_slug, updated)
    return {"old_name": old_name, "new_name": new_name, "updated": updated}


# ---------------------------------------------------------------------------
# PATCH /api/v1/documents/{doc_id}/collection  — move doc to different collection
# ---------------------------------------------------------------------------


@router.patch("/{doc_id}/collection")
async def move_document_collection(
    doc_id: str,
    request: Request,
    key_row: dict = Depends(get_api_key),
):
    """Move a document to a different collection."""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", doc_id):
        raise HTTPException(status_code=400, detail="Invalid doc_id format")

    body = await request.json()
    collection = body.get("collection", "").strip()
    if not collection:
        raise HTTPException(status_code=400, detail="collection is required")
    if len(collection) > 100:
        raise HTTPException(status_code=400, detail="Collection name too long (max 100 chars)")

    client_slug = key_row["client_slug"]
    docs_dir = client_docs_dir(client_slug)
    meta_path = docs_dir / f"{doc_id}.meta"

    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    meta = json.loads(meta_path.read_text())
    old_collection = meta.get("collection", "My Documents")
    meta["collection"] = collection
    tmp = meta_path.with_suffix(".meta.tmp")
    tmp.write_text(json.dumps(meta, indent=2))
    os.replace(str(tmp), str(meta_path))

    logger.info("Moved doc %s from '%s' → '%s' for client %s", doc_id[:16], old_collection, collection, client_slug)
    return {"doc_id": doc_id, "old_collection": old_collection, "new_collection": collection}


# ---------------------------------------------------------------------------
# GET /api/v1/documents/chunk-context/{chunk_id}  — surrounding chunk context
# ---------------------------------------------------------------------------

_BUILTIN_CORPORA = frozenset({"difc", "czech", "uk", "au"})


class ChunkContextItem(BaseModel):
    chunk_id: str
    page: int
    text: str
    is_target: bool


class ChunkContextResponse(BaseModel):
    doc_id: str
    corpus: str
    pdf_available: bool
    chunks: list[ChunkContextItem]


@router.get("/chunk-context/{chunk_id}")
async def get_chunk_context(
    chunk_id: str,
    window: int = Query(default=1, ge=1, le=5),
    key_row: dict = Depends(get_api_key),
) -> ChunkContextResponse:
    """Return surrounding chunks for a given chunk_id.

    Finds the target chunk by its unique chunk_id, then returns `window`
    chunks before and after it within the same document, ordered by page.
    Works for all corpora (builtin and custom uploads).
    """
    from sqlalchemy import text as sa_text

    from neolex.db.postgres import AsyncSessionLocal

    if not re.fullmatch(r"[A-Za-z0-9_\-]+", chunk_id):
        raise HTTPException(status_code=400, detail="Invalid chunk_id format")

    client_slug = key_row["client_slug"]

    async with AsyncSessionLocal() as session:
        # 1. Find target chunk
        result = await session.execute(
            sa_text("""
            SELECT chunk_id, doc_id, corpus, page, text
            FROM chunks
            WHERE chunk_id = :chunk_id
        """),
            {"chunk_id": chunk_id},
        )
        row = result.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Chunk not found")

        target_doc_id = row.doc_id
        target_corpus = row.corpus

        # 2. Access control: builtin corpora accessible to all; custom must match client_slug
        #    Return 404 (not 403) to avoid leaking chunk existence to other tenants.
        if target_corpus not in _BUILTIN_CORPORA and target_corpus != client_slug:
            raise HTTPException(status_code=404, detail="Chunk not found")

        # 3. Fetch only the window of chunks around the target using SQL
        #    Uses ROW_NUMBER() with numeric sort on chunk suffix to avoid
        #    lexicographic mis-ordering (e.g. _10 before _2).
        context_rows = await session.execute(
            sa_text("""
            WITH ranked AS (
                SELECT chunk_id, page, text,
                       ROW_NUMBER() OVER (
                           ORDER BY page ASC,
                                    CAST(regexp_replace(chunk_id, '^.*_', '') AS INTEGER) ASC
                       ) AS rn
                FROM chunks
                WHERE doc_id = :doc_id AND corpus = :corpus
            ),
            target AS (
                SELECT rn FROM ranked WHERE chunk_id = :chunk_id
            )
            SELECT r.chunk_id, r.page, r.text,
                   (r.chunk_id = :chunk_id) AS is_target
            FROM ranked r
            CROSS JOIN target t
            WHERE r.rn BETWEEN t.rn - :window AND t.rn + :window
            ORDER BY r.rn ASC
        """),
            {
                "doc_id": target_doc_id,
                "corpus": target_corpus,
                "chunk_id": chunk_id,
                "window": window,
            },
        )
        window_chunks = context_rows.fetchall()

    # 4. Check PDF availability
    corpus_pdf = Path(settings.data_dir) / "documents" / f"{target_doc_id}.pdf"
    client_dir = client_docs_dir(client_slug)
    pdf_available = corpus_pdf.exists() or any(client_dir.glob(f"{target_doc_id}_*.pdf"))

    # Never expose tenant UUID — replace custom corpus with neutral label
    public_corpus = target_corpus if target_corpus in _BUILTIN_CORPORA else "custom"

    return ChunkContextResponse(
        doc_id=target_doc_id,
        corpus=public_corpus,
        pdf_available=pdf_available,
        chunks=[
            ChunkContextItem(
                chunk_id=s.chunk_id,
                page=s.page,
                text=s.text,
                is_target=bool(s.is_target),
            )
            for s in window_chunks
        ],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/documents/{doc_id}/pdf  — serve corpus PDF for source viewer
# ---------------------------------------------------------------------------


_PDF_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, private",
    "X-Content-Type-Options": "nosniff",
}


@router.get("/{doc_id}/pdf")
async def get_document_pdf(
    doc_id: str,
    key_row: dict = Depends(get_api_key),
) -> FileResponse:
    """Serve the raw PDF for a given doc_id.

    Corpus documents (shared DIFC laws/cases) are served to all authenticated
    users. Client-uploaded documents are scoped to the client's own corpus.
    """
    # Sanitise: doc_id must be hex hash or alphanumeric/dash/underscore only
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", doc_id):
        raise HTTPException(status_code=400, detail="Invalid doc_id format")

    client_slug = key_row["client_slug"]

    # 1. Corpus documents (shared public law texts — accessible to all tenants)
    corpus_path = Path(settings.data_dir) / "documents" / f"{doc_id}.pdf"
    if corpus_path.exists():
        logger.info("Serving shared corpus PDF %s to client %s", doc_id[:16], client_slug)
        return FileResponse(
            path=str(corpus_path),
            media_type="application/pdf",
            filename=f"{doc_id}.pdf",
            headers=_PDF_CACHE_HEADERS,
        )

    # 2. Client-uploaded documents (tenant-scoped)
    client_dir = client_docs_dir(client_slug)
    for f in client_dir.glob(f"{doc_id}_*.pdf"):
        return FileResponse(
            path=str(f),
            media_type="application/pdf",
            filename=f.name,
            headers=_PDF_CACHE_HEADERS,
        )

    raise HTTPException(status_code=404, detail="PDF not found")
