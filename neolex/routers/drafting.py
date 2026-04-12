"""Document drafting API — user-scoped legal document creation within conversations.

All endpoints require authentication via get_api_key (session cookie).
Every endpoint verifies that chat_document.user_id == current_user.id —
cross-user access returns 404 (not 403) to avoid leaking existence.

Routes:
    POST   /api/v1/conversations/{conversation_id}/documents             — create document
    PATCH  /api/v1/conversations/{conversation_id}/documents/{doc_id}   — update fields
    DELETE /api/v1/conversations/{conversation_id}/documents/{doc_id}   — delete document
    GET    /api/v1/conversations/{conversation_id}/documents             — list documents
    GET    /api/v1/conversations/{conversation_id}/documents/{doc_id}   — get document
    GET    /api/v1/conversations/{conversation_id}/documents/{doc_id}/pdf — generate PDF
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.auth.middleware import get_api_key
from neolex.constants import DRAFTING_MAX_DOCS_PER_CONVERSATION
from neolex.db.drafting_models import ChatDocument, DocumentTemplate
from neolex.db.postgres import conversation_doc_lock_key, get_db
from neolex.schemas.drafting import DocumentCreate, DocumentResponse, DocumentUpdate
from neolex.services.pdf_generator import (
    _WEASYPRINT_AVAILABLE,
    _XELATEX_BIN,
    PDFTimeoutError,
    generate_pdf,
    invalidate_cache,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["drafting"])


def _parse_conversation_id(conversation_id: str) -> uuid.UUID:
    """Parse conversation_id path param, returning 400 on malformed input."""
    try:
        return uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id — must be a UUID")


def _parse_doc_id(doc_id: str) -> uuid.UUID:
    """Parse doc_id path param, returning 400 on malformed input."""
    try:
        return uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid doc_id — must be a UUID")


async def _get_owned_document(
    doc_uuid: uuid.UUID,
    conv_uuid: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> ChatDocument:
    """Fetch a ChatDocument by (id, conversation_id) and verify user ownership.

    Returns 404 for both non-existence and wrong-owner (avoids existence leak).
    """
    result = await db.execute(
        select(ChatDocument).where(
            ChatDocument.id == doc_uuid,
            ChatDocument.conversation_id == conv_uuid,
            ChatDocument.user_id == user_id,  # SQL-level defence-in-depth
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ---------------------------------------------------------------------------
# Helpers: template name lookup and response construction
# ---------------------------------------------------------------------------


async def _get_template_name(db: AsyncSession, slug: str) -> str | None:
    """Return the display name for a template slug, or None if not found."""
    result = await db.execute(select(DocumentTemplate.name).where(DocumentTemplate.slug == slug))
    return result.scalar_one_or_none()


async def _get_template_names(db: AsyncSession, slugs: set[str]) -> dict[str, str]:
    """Batch-fetch display names for a set of template slugs."""
    if not slugs:
        return {}
    result = await db.execute(
        select(DocumentTemplate.slug, DocumentTemplate.name).where(DocumentTemplate.slug.in_(slugs))
    )
    return {row[0]: row[1] for row in result.all()}


def _build_doc_response(doc: ChatDocument, template_name: str | None) -> DocumentResponse:
    """Construct a DocumentResponse with template_name populated."""
    return DocumentResponse(
        id=doc.id,
        conversation_id=doc.conversation_id,
        template_slug=doc.template_slug,
        template_name=template_name,
        fields=doc.fields,
        version=doc.version,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/conversations/{conversation_id}/documents
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/conversations/{conversation_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def create_document(
    conversation_id: str,
    payload: DocumentCreate,
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Create a new draft document within a conversation.

    Validates:
    - Template exists
    - All required_fields are present in payload.fields
    - Conversation has fewer than 3 documents (with SELECT FOR UPDATE to prevent races)
    """
    conv_uuid = _parse_conversation_id(conversation_id)
    user_id = uuid.UUID(key_row["user_id"])

    # Resolve template
    tmpl_result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.slug == payload.template_slug))
    template = tmpl_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template '{payload.template_slug}' not found")

    # Validate required fields
    required = template.required_fields or []
    missing = [f for f in required if f not in payload.fields]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required field(s): {', '.join(missing)}",
        )

    # Serialize concurrent document creations for this conversation using an
    # advisory lock so both the REST path and the pipeline path (_create_pipeline_document
    # in query.py) coordinate on the same mutex.  pg_advisory_xact_lock blocks
    # until no other session holds the same key, then holds it for the duration
    # of this transaction (released automatically at commit/rollback).
    # SELECT ... FOR UPDATE alone cannot prevent races when there are zero
    # existing rows to lock — the advisory lock closes that gap.
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": conversation_doc_lock_key(conv_uuid)})

    # Enforce max 3 documents per conversation with SELECT FOR UPDATE to prevent races.
    # NOTE: SELECT COUNT(*) FOR UPDATE is invalid in PostgreSQL — only row-returning
    # queries can use FOR UPDATE. We fetch the IDs instead and count in Python.
    rows_result = await db.execute(
        select(ChatDocument.id)
        .where(
            ChatDocument.conversation_id == conv_uuid,
            ChatDocument.user_id == user_id,
        )
        .with_for_update()
    )
    current_count = len(rows_result.scalars().all())
    if current_count >= DRAFTING_MAX_DOCS_PER_CONVERSATION:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum of {DRAFTING_MAX_DOCS_PER_CONVERSATION} documents per conversation reached. "
            "Delete an existing document to create a new one.",
        )

    # Capture before commit: SQLAlchemy expires ORM objects on commit (expire_on_commit=True),
    # so accessing template.name after commit raises DetachedInstanceError in production.
    template_name = template.name

    doc = ChatDocument(
        conversation_id=conv_uuid,
        user_id=user_id,
        template_slug=payload.template_slug,
        fields=payload.fields,
        version=1,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(
        "Document created: id=%s template=%s conversation=%s user=%s",
        doc.id,
        doc.template_slug,
        conv_uuid,
        user_id,
    )
    return _build_doc_response(doc, template_name)


# ---------------------------------------------------------------------------
# PATCH /api/v1/conversations/{conversation_id}/documents/{doc_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/api/v1/conversations/{conversation_id}/documents/{doc_id}",
    response_model=DocumentResponse,
)
async def update_document(
    conversation_id: str,
    doc_id: str,
    payload: DocumentUpdate,
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Update an existing document's fields and increment its version counter."""
    conv_uuid = _parse_conversation_id(conversation_id)
    doc_uuid = _parse_doc_id(doc_id)
    user_id = uuid.UUID(key_row["user_id"])

    doc = await _get_owned_document(doc_uuid, conv_uuid, user_id, db)

    # Merge incoming fields over existing ones (PATCH semantics)
    merged_fields = {**doc.fields, **payload.fields}
    doc.fields = merged_fields
    doc.version = doc.version + 1

    await db.commit()
    await db.refresh(doc)

    # Invalidate cached PDF for this document (version changed)
    invalidate_cache(doc.id)

    tmpl_name = await _get_template_name(db, doc.template_slug)
    logger.info("Document updated: id=%s version=%d user=%s", doc.id, doc.version, user_id)
    return _build_doc_response(doc, tmpl_name)


# ---------------------------------------------------------------------------
# DELETE /api/v1/conversations/{conversation_id}/documents/{doc_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/api/v1/conversations/{conversation_id}/documents/{doc_id}",
    status_code=204,
)
async def delete_document(
    conversation_id: str,
    doc_id: str,
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a draft document and invalidate its cached PDF.

    Returns 404 if the document does not exist or belongs to a different user.
    """
    conv_uuid = _parse_conversation_id(conversation_id)
    doc_uuid = _parse_doc_id(doc_id)
    user_id = uuid.UUID(key_row["user_id"])

    doc = await _get_owned_document(doc_uuid, conv_uuid, user_id, db)
    doc_id_for_cache = doc.id

    await db.delete(doc)
    await db.commit()

    invalidate_cache(doc_id_for_cache)

    logger.info("Document deleted: id=%s conversation=%s user=%s", doc_id_for_cache, conv_uuid, user_id)


# ---------------------------------------------------------------------------
# GET /api/v1/conversations/{conversation_id}/documents
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/conversations/{conversation_id}/documents",
    response_model=list[DocumentResponse],
)
async def list_documents(
    conversation_id: str,
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List all draft documents for a conversation owned by the authenticated user."""
    conv_uuid = _parse_conversation_id(conversation_id)
    user_id = uuid.UUID(key_row["user_id"])

    result = await db.execute(
        select(ChatDocument)
        .where(
            ChatDocument.conversation_id == conv_uuid,
            ChatDocument.user_id == user_id,
        )
        .order_by(ChatDocument.created_at.asc())
    )
    docs = result.scalars().all()
    slugs = {d.template_slug for d in docs}
    name_map = await _get_template_names(db, slugs)
    return [_build_doc_response(d, name_map.get(d.template_slug)) for d in docs]


# ---------------------------------------------------------------------------
# GET /api/v1/conversations/{conversation_id}/documents/{doc_id}
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/conversations/{conversation_id}/documents/{doc_id}",
    response_model=DocumentResponse,
)
async def get_document(
    conversation_id: str,
    doc_id: str,
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get a single draft document by ID."""
    conv_uuid = _parse_conversation_id(conversation_id)
    doc_uuid = _parse_doc_id(doc_id)
    user_id = uuid.UUID(key_row["user_id"])

    doc = await _get_owned_document(doc_uuid, conv_uuid, user_id, db)
    tmpl_name = await _get_template_name(db, doc.template_slug)
    return _build_doc_response(doc, tmpl_name)


# ---------------------------------------------------------------------------
# GET /api/v1/conversations/{conversation_id}/documents/{doc_id}/pdf
# ---------------------------------------------------------------------------


@router.get("/api/v1/conversations/{conversation_id}/documents/{doc_id}/pdf")
async def get_document_pdf(
    conversation_id: str,
    doc_id: str,
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate and return a PDF for the specified draft document.

    Returns 503 if no PDF renderer is available (xelatex or weasyprint).
    Returns cached PDF if already generated for this (doc_id, version).
    """
    if _XELATEX_BIN is None and not _WEASYPRINT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation is not available on this server. Contact support.",
        )

    conv_uuid = _parse_conversation_id(conversation_id)
    doc_uuid = _parse_doc_id(doc_id)
    user_id = uuid.UUID(key_row["user_id"])

    doc = await _get_owned_document(doc_uuid, conv_uuid, user_id, db)

    # Fetch the template (needed for its LaTeX source)
    tmpl_result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.slug == doc.template_slug))
    template = tmpl_result.scalar_one_or_none()
    if template is None:
        # Template was deleted after doc was created — shouldn't happen but handle gracefully
        raise HTTPException(status_code=500, detail="Template not found for this document.")

    try:
        pdf_bytes = await generate_pdf(
            doc_id=doc.id,
            version=doc.version,
            template=template.latex_template,
            fields=doc.fields,
        )
    except PDFTimeoutError as exc:
        logger.error("PDF generation timed out for doc_id=%s", doc.id)
        raise HTTPException(
            status_code=503,
            detail="PDF generation failed.",
        ) from exc
    except RuntimeError as exc:
        logger.error("PDF generation failed for doc_id=%s: %s", doc.id, exc)
        raise HTTPException(
            status_code=500,
            detail="PDF generation failed. Contact support if this persists.",
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="document_{doc.id}_v{doc.version}.pdf"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
        },
    )
