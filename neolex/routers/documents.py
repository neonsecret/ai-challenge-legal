"""Document management endpoints — Phase 3.

Routes:
    POST   /api/v1/documents          — upload PDF (DOC-01, DOC-02, DOC-03, DOC-04)
    GET    /api/v1/documents           — list documents (DOC-06)
    DELETE /api/v1/documents/{doc_id}  — delete document + trigger reindex (DOC-07)
    POST   /api/v1/documents/reindex   — manually trigger reindex
    GET    /api/v1/documents/reindex/{job_id} — poll reindex status (DOC-05)
    GET    /api/v1/documents/{doc_id}/pdf      — serve raw PDF for source viewer
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from neolex.config import settings

from neolex.auth.middleware import get_api_key
from neolex.db.audit import get_audit_db
from neolex.schemas.documents import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentMeta,
    DocumentUploadResponse,
    ReindexJobResponse,
)
from neolex.services.document_manager import (
    MAX_UPLOAD_BYTES,
    client_docs_dir,
    delete_document,
    save_doc_meta,
    save_upload,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# POST /api/v1/documents  (DOC-01, DOC-02, DOC-03, DOC-04)
# ---------------------------------------------------------------------------


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
        request: Request,
        file: UploadFile = File(...),
        key_row: dict = Depends(get_api_key),
) -> DocumentUploadResponse:
    """Upload a PDF document into the client's private corpus.

    - Validates MIME type (PDF only) → 415 on mismatch
    - Validates file size (≤50MB) → 413 on oversize
    - Saves to data/clients/<slug>/docs/
    - Triggers background reindex and returns job_id
    """
    client_slug = key_row["client_slug"]

    # --- Validate content type ---
    ct = (file.content_type or "").lower()
    if ct not in ("application/pdf",):
        async with get_audit_db() as db:
            await db.log_event(
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

    # --- Read and validate ---
    content = await file.read()

    # Reject empty files
    if len(content) == 0:
        async with get_audit_db() as db:
            await db.log_event(
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
        async with get_audit_db() as db:
            await db.log_event(
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
        )
    except ValueError as exc:
        # Invalid PDF magic bytes or size guard
        status_code = 413 if "too large" in str(exc) else 415
        async with get_audit_db() as db:
            await db.log_event(
                key_hash=key_row["key_hash"],
                event_type="upload",
                detail={"filename": file.filename, "status": "rejected_invalid", "error": str(exc)},
                ip=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(status_code=status_code, detail=str(exc))

    # --- Persist to document registry (DB) ---
    async with get_audit_db() as db:
        await db.register_document(
            doc_id=meta["doc_id"],
            client_slug=client_slug,
            filename=meta["filename"],
            size_bytes=meta["size_bytes"],
            upload_ts=meta["upload_ts"],
        )

    # --- Write sidecar .meta file ---
    await asyncio.to_thread(save_doc_meta, client_slug, meta)

    # --- Trigger background reindex (non-blocking) ---
    from neolex.config import settings
    from neolex.indexing.reindex_worker import create_job, run_reindex_job

    job_id = await create_job(client_slug)
    asyncio.create_task(
        run_reindex_job(job_id, client_slug, app=request.app),
        name=f"reindex-{job_id[:8]}",
    )

    # --- Audit log ---
    async with get_audit_db() as db:
        await db.log_event(
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
# GET /api/v1/documents  (DOC-06)
# ---------------------------------------------------------------------------


@router.get("", response_model=DocumentListResponse)
async def list_documents(
        key_row: dict = Depends(get_api_key),
) -> DocumentListResponse:
    """List all documents uploaded by this client."""
    client_slug = key_row["client_slug"]

    async with get_audit_db() as db:
        rows = await db.list_documents(client_slug)

    docs = [
        DocumentMeta(
            doc_id=row["doc_id"],
            filename=row["filename"],
            size_bytes=row["size_bytes"],
            upload_ts=row["upload_ts"],
            indexed=bool(row["indexed"]),
        )
        for row in rows
    ]

    return DocumentListResponse(
        client_slug=client_slug,
        documents=docs,
        total=len(docs),
    )


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
    from neolex.config import settings
    from neolex.indexing.reindex_worker import create_job, run_reindex_job

    job_id = await create_job(client_slug)
    asyncio.create_task(
        run_reindex_job(job_id, client_slug, app=request.app),
        name=f"reindex-{job_id[:8]}",
    )

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

    from neolex.config import settings
    from neolex.indexing.reindex_worker import create_job, run_reindex_job

    job_id = await create_job(client_slug)
    asyncio.create_task(
        run_reindex_job(job_id, client_slug, app=request.app),
        name=f"reindex-{job_id[:8]}",
    )

    async with get_audit_db() as db:
        await db.log_event(
            key_hash=key_row["key_hash"],
            event_type="reindex",
            detail={"client_slug": client_slug, "job_id": job_id, "trigger": "manual"},
            ip=getattr(request.client, "host", None),
            user_agent=request.headers.get("user-agent"),
        )

    logger.info("Manual reindex triggered for client %s — job %s", client_slug, job_id)

    import datetime

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
