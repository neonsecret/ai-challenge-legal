"""Conversation history service — user-scoped Q&A storage in PostgreSQL.

History is keyed by (user_id, conversation_id). The user_id comes from the
authenticated HttpOnly cookie session — never from the client request body.
Cross-user access is structurally impossible: every query filters by user_id.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from neolex.db.models import ConversationMessage
from neolex.db.postgres import AsyncSessionLocal

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10  # 5 Q&A pairs — worst-case context for agent cost control


def _to_conv_uuid(conversation_id: str) -> uuid.UUID:
    """Convert a conversation_id string to UUID.

    Frontend uses 'chat-{timestamp}' format. We deterministically map these
    to UUID5 so they fit the UUID column without losing identity.
    """
    try:
        return uuid.UUID(conversation_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_OID, conversation_id)


async def load_history(user_id: str, conversation_id: str) -> list[dict]:
    """Load the last MAX_HISTORY_TURNS messages for this user+conversation.

    Ownership is enforced by the WHERE user_id = ? clause — a user can only
    ever load their own conversation history.

    Returns [] on any error or if no history exists yet.
    """
    if not conversation_id:
        return []
    try:
        uid = uuid.UUID(str(user_id))
        cid = _to_conv_uuid(conversation_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConversationMessage.role, ConversationMessage.content)
                .where(
                    ConversationMessage.user_id == uid,
                    ConversationMessage.conversation_id == cid,
                )
                .order_by(ConversationMessage.created_at.asc())
                .limit(MAX_HISTORY_TURNS)
            )
            rows = result.all()
            return [{"role": row.role, "content": row.content} for row in rows]
    except Exception:
        logger.exception("Failed to load conversation history for conv=%s", conversation_id)
        return []


async def load_accumulated_docs(user_id: str, conversation_id: str) -> list[dict]:
    """Load accumulated source documents for an agent conversation.

    Returns [] on error or if no docs saved yet.
    """
    if not conversation_id:
        return []
    try:
        import json as _json
        uid = uuid.UUID(str(user_id))
        cid = _to_conv_uuid(conversation_id)
        async with AsyncSessionLocal() as session:
            from neolex.db.models import ConversationDocs
            from sqlalchemy import select as _select
            result = await session.execute(
                _select(ConversationDocs.docs_json).where(
                    ConversationDocs.conversation_id == cid,
                    ConversationDocs.user_id == uid,
                )
            )
            row = result.scalar_one_or_none()
            return _json.loads(row) if row else []
    except Exception:
        logger.exception("Failed to load accumulated docs for conv=%s", conversation_id)
        return []


async def save_accumulated_docs(
    user_id: str,
    conversation_id: str,
    docs: list[dict],
) -> None:
    """Persist accumulated source documents for multi-turn agent conversations.

    Upserts — creates or updates the single row per conversation.
    """
    if not conversation_id or not docs:
        return
    try:
        import json as _json
        uid = uuid.UUID(str(user_id))
        cid = _to_conv_uuid(conversation_id)
        docs_str = _json.dumps(docs, ensure_ascii=False)
        async with AsyncSessionLocal() as session:
            from neolex.db.models import ConversationDocs
            from sqlalchemy import select as _select
            result = await session.execute(
                _select(ConversationDocs).where(
                    ConversationDocs.conversation_id == cid,
                    ConversationDocs.user_id == uid,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.docs_json = docs_str
            else:
                session.add(ConversationDocs(
                    conversation_id=cid,
                    user_id=uid,
                    docs_json=docs_str,
                ))
            await session.commit()
    except Exception:
        logger.exception("Failed to save accumulated docs for conv=%s", conversation_id)


async def save_turn(
    user_id: str,
    conversation_id: str,
    question: str,
    answer: str,
) -> None:
    """Append a Q&A pair to the user's conversation history.

    Non-blocking in the caller — fire with asyncio.create_task().
    Silently swallows errors so a DB failure never breaks the SSE response.
    """
    if not conversation_id:
        return
    try:
        uid = uuid.UUID(str(user_id))
        cid = _to_conv_uuid(conversation_id)
        async with AsyncSessionLocal() as session:
            session.add(ConversationMessage(
                conversation_id=cid,
                user_id=uid,
                role="user",
                content=question[:2000],
            ))
            session.add(ConversationMessage(
                conversation_id=cid,
                user_id=uid,
                role="assistant",
                content=answer[:4000],
            ))
            await session.commit()
    except Exception:
        logger.exception("Failed to save conversation turn for conv=%s", conversation_id)
