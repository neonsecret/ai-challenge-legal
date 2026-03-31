"""Pydantic models for document management endpoints (Phase 3).

DOC-01 through DOC-07 request/response contracts.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class DocumentUploadResponse(BaseModel):
    """Returned by POST /api/v1/documents."""

    doc_id: str = Field(..., description="UUID assigned to this document")
    filename: str
    size_bytes: int
    client_slug: str
    upload_ts: str = Field(..., description="ISO-8601 UTC timestamp")
    job_id: str = Field(..., description="Reindex job ID — poll via GET /api/v1/documents/reindex/{job_id}")


# ---------------------------------------------------------------------------
# Document listing
# ---------------------------------------------------------------------------


class DocumentMeta(BaseModel):
    """Metadata for a single uploaded document (DOC-06)."""

    doc_id: str
    filename: str
    size_bytes: int
    upload_ts: str
    indexed: bool


class DocumentListResponse(BaseModel):
    """Returned by GET /api/v1/documents."""

    client_slug: str
    documents: list[DocumentMeta]
    total: int


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class DocumentDeleteResponse(BaseModel):
    """Returned by DELETE /api/v1/documents/{doc_id}."""

    doc_id: str
    deleted: bool
    job_id: str = Field(..., description="Reindex job triggered after deletion")


# ---------------------------------------------------------------------------
# ZIP upload
# ---------------------------------------------------------------------------


class ZipUploadResult(BaseModel):
    """Result for a single file extracted from a ZIP."""

    filename: str
    doc_id: str | None = None
    status: str  # "uploaded", "skipped_not_pdf", "skipped_too_large", "skipped_invalid", "error"
    size_bytes: int = 0
    error: str | None = None


class ZipUploadResponse(BaseModel):
    """Returned by POST /api/v1/documents/upload-zip."""

    uploaded_count: int
    skipped_count: int
    total_size_bytes: int
    files: list[ZipUploadResult]
    job_id: str | None = Field(None, description="Reindex job ID — only set if at least 1 file uploaded")


# ---------------------------------------------------------------------------
# Reindex job
# ---------------------------------------------------------------------------

ReindexStatus = Literal["pending", "running", "complete", "complete_with_warnings", "failed"]


class ReindexJobResponse(BaseModel):
    """Returned by POST /api/v1/documents/reindex and GET /api/v1/documents/reindex/{job_id}."""

    job_id: str
    client_slug: str
    status: ReindexStatus
    progress: float = Field(0.0, ge=0.0, le=1.0, description="0.0–1.0 fraction complete")
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    doc_count: int = Field(0, description="Number of documents indexed")
    chunks_skipped: int = Field(0, description="Number of chunks skipped during embedding")
