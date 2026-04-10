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

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.auth.middleware import get_api_key
from neolex.db.drafting_models import ChatDocument, DocumentTemplate
from neolex.db.postgres import get_db
from neolex.schemas.drafting import DocumentCreate, DocumentResponse, DocumentUpdate
from neolex.services.pdf_generator import _XELATEX_BIN, generate_pdf, invalidate_cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["drafting"])

# Maximum number of draft documents per conversation
_MAX_DOCS_PER_CONVERSATION = 3


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
    """Fetch a ChatDocument by (id, conversation_id, user_id) — all three in SQL WHERE.

    Pushing user_id into the WHERE clause means the DB never returns a row the
    caller isn't allowed to see (defense-in-depth; returns 404 on wrong owner).
    """
    result = await db.execute(
        select(ChatDocument).where(
            ChatDocument.id == doc_uuid,
            ChatDocument.conversation_id == conv_uuid,
            ChatDocument.user_id == user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


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

    # Acquire a transaction-level advisory lock on (conversation_id, user_id) before
    # counting so that concurrent first-insert requests don't all read count=0 and
    # race past the limit.  The lock is released automatically at transaction end.
    # Lock key: lower 63 bits of SHA-256(conv_uuid || user_id) — stable, collision-resistant.
    _lock_input = f"{conv_uuid}:{user_id}".encode()
    _lock_key = int.from_bytes(hashlib.sha256(_lock_input).digest()[:8], byteorder="big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _lock_key})

    # Fetch existing document IDs with FOR UPDATE to prevent concurrent races on
    # existing rows (SELECT COUNT(*) FOR UPDATE is invalid in PostgreSQL — only
    # row-returning queries may use FOR UPDATE).
    rows_result = await db.execute(
        select(ChatDocument.id)
        .where(
            ChatDocument.conversation_id == conv_uuid,
            ChatDocument.user_id == user_id,
        )
        .with_for_update()
    )
    current_count = len(rows_result.scalars().all())
    if current_count >= _MAX_DOCS_PER_CONVERSATION:
        raise HTTPException(
            status_code=409,
            detail=f"Conversation already has {_MAX_DOCS_PER_CONVERSATION} documents (the maximum). "
            "Delete an existing document to create a new one.",
        )

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
    return DocumentResponse.model_validate(doc)


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

    logger.info("Document updated: id=%s version=%d user=%s", doc.id, doc.version, user_id)
    return DocumentResponse.model_validate(doc)


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
    return [DocumentResponse.model_validate(d) for d in docs]


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
    return DocumentResponse.model_validate(doc)


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

    Returns 503 if xelatex is not installed.
    Returns cached PDF if already generated for this (doc_id, version).
    """
    if _XELATEX_BIN is None:
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
    except RuntimeError as exc:
        logger.error("PDF generation failed for doc_id=%s: %s", doc.id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="document_{doc.id}_v{doc.version}.pdf"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
        },
    )
