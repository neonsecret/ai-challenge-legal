"""Internal document drafting service — callable from within the agent pipeline.

This module provides async helpers that the agent's _draft_document_fn callback
uses to create and update ChatDocuments without going through the HTTP layer.
It reuses the same validation logic as the drafting router but operates directly
on SQLAlchemy sessions, so it can be called from within neolex/services/.

The agent callback receives a db session (AsyncSession) and user context, then
delegates to these helpers.  Validation errors are returned as dicts with an
'error' key so the agent can relay them to the LLM as a ToolMessage without
raising exceptions that would abort the agent turn.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.constants import MAX_DOCS_PER_CONVERSATION

logger = logging.getLogger(__name__)


async def get_template_by_slug(db: AsyncSession, slug: str) -> dict | None:
    """Fetch a template by slug and return its metadata as a plain dict.

    Returns None if the template does not exist.
    """
    from neolex.db.drafting_models import DocumentTemplate

    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.slug == slug))
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        return None
    return {
        "slug": tmpl.slug,
        "name": tmpl.name,
        "jurisdiction": tmpl.jurisdiction,
        "category": tmpl.category,
        "required_fields": tmpl.required_fields or [],
        "field_descriptions": tmpl.field_descriptions or {},
        "description": tmpl.description or "",
    }


async def list_conversation_documents(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> list[dict]:
    """Return all draft documents for a conversation as plain dicts."""
    from neolex.db.drafting_models import ChatDocument

    result = await db.execute(
        select(ChatDocument)
        .where(
            ChatDocument.conversation_id == conversation_id,
            ChatDocument.user_id == user_id,
        )
        .order_by(ChatDocument.created_at.asc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(doc.id),
            "template_slug": doc.template_slug,
            "fields": dict(doc.fields),
            "version": doc.version,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in docs
    ]


async def create_draft_document(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    template_slug: str,
    fields: dict[str, str],
) -> dict:
    """Create a new draft document for a conversation.

    Returns a result dict with either:
    - {'id': ..., 'version': 1, 'ok': True} on success
    - {'error': str} on validation failure

    Enforces the 3-document-per-conversation cap with SELECT FOR UPDATE.
    Validates required fields against the template.
    """
    from neolex.db.drafting_models import ChatDocument, DocumentTemplate

    # Verify template exists
    tmpl_result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.slug == template_slug))
    template = tmpl_result.scalar_one_or_none()
    if template is None:
        return {"error": f"Template '{template_slug}' not found"}

    # Validate required fields
    required = template.required_fields or []
    missing = [f for f in required if f not in fields or not fields[f]]
    if missing:
        return {"error": f"Missing required field(s): {', '.join(missing)}. Please ask the user to provide these."}

    # Enforce max-3 cap with SELECT FOR UPDATE to prevent races.
    # PostgreSQL does not allow aggregates (COUNT) with FOR UPDATE — must fetch
    # rows with a lock and count them in Python.
    rows_result = await db.execute(
        select(ChatDocument.id)
        .where(
            ChatDocument.conversation_id == conversation_id,
            ChatDocument.user_id == user_id,
        )
        .with_for_update()
    )
    current_count = len(rows_result.scalars().all())
    if current_count >= MAX_DOCS_PER_CONVERSATION:
        return {
            "error": (
                f"Maximum of {MAX_DOCS_PER_CONVERSATION} documents per conversation reached. "
                "Ask the user to delete an existing document before creating a new one."
            )
        }

    doc = ChatDocument(
        conversation_id=conversation_id,
        user_id=user_id,
        template_slug=template_slug,
        fields=fields,
        version=1,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(
        "Agent created document: id=%s template=%s conversation=%s",
        doc.id,
        template_slug,
        conversation_id,
    )
    return {"id": str(doc.id), "version": doc.version, "template_slug": doc.template_slug, "ok": True}


async def update_draft_document(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    doc_id: uuid.UUID,
    fields: dict[str, str],
) -> dict:
    """Update fields on an existing draft document (PATCH semantics — merge over existing).

    Returns a result dict with either:
    - {'id': ..., 'version': N, 'ok': True} on success
    - {'error': str} on failure
    """
    from neolex.db.drafting_models import ChatDocument
    from neolex.services.pdf_generator import invalidate_cache

    result = await db.execute(
        select(ChatDocument).where(
            ChatDocument.id == doc_id,
            ChatDocument.conversation_id == conversation_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None or doc.user_id != user_id:
        return {"error": f"Document {doc_id} not found in this conversation"}

    # Merge incoming fields over existing (PATCH semantics)
    merged = {**doc.fields, **fields}
    doc.fields = merged
    doc.version = doc.version + 1

    await db.commit()
    await db.refresh(doc)

    # Invalidate cached PDF (version changed)
    invalidate_cache(doc.id)

    logger.info("Agent updated document: id=%s version=%d", doc.id, doc.version)
    return {"id": str(doc.id), "version": doc.version, "template_slug": doc.template_slug, "ok": True}
