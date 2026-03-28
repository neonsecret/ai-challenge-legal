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

MAX_HISTORY_TURNS = 6  # 3 Q&A pairs — caps token cost for rewriting


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
