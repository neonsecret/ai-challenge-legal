"""Conversation history service — user-scoped Q&A storage in PostgreSQL.

History is keyed by (user_id, conversation_id). The user_id comes from the
authenticated HttpOnly cookie session — never from the client request body.
Cross-user access is structurally impossible: every query filters by user_id.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select, func, case

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


async def list_user_conversations(user_id: str, limit: int = 50) -> list[dict]:
    """Return the user's most recent conversations with metadata.

    Each dict contains: id, title, last_message_at, message_count.
    Ordered by most recent message first. Title is the first user message
    truncated to 80 characters.
    """
    try:
        uid = uuid.UUID(str(user_id))
        async with AsyncSessionLocal() as session:
            # Subquery: per-conversation aggregates
            stmt = (
                select(
                    ConversationMessage.conversation_id,
                    func.count().label("message_count"),
                    func.max(ConversationMessage.created_at).label("last_message_at"),
                    # First user message as title (MIN created_at among user messages)
                    func.min(
                        case(
                            (ConversationMessage.role == "user", ConversationMessage.content),
                            else_=None,
                        )
                    ).label("first_user_content"),
                )
                .where(ConversationMessage.user_id == uid)
                .group_by(ConversationMessage.conversation_id)
                .order_by(func.max(ConversationMessage.created_at).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.all()

            conversations = []
            for row in rows:
                title = row.first_user_content or "New chat"
                if len(title) > 80:
                    title = title[:80] + "..."
                conversations.append({
                    "id": str(row.conversation_id),
                    "title": title,
                    "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None,
                    "message_count": row.message_count,
                })
            return conversations
    except Exception:
        logger.exception("Failed to list conversations for user=%s", user_id)
        return []


async def load_full_conversation(user_id: str, conversation_id: str) -> list[dict]:
    """Load ALL messages for a user+conversation (no limit).

    Returns messages as dicts with: role, content, created_at.
    Used by the frontend to hydrate a conversation from the backend.
    """
    if not conversation_id:
        return []
    try:
        uid = uuid.UUID(str(user_id))
        cid = _to_conv_uuid(conversation_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(
                    ConversationMessage.role,
                    ConversationMessage.content,
                    ConversationMessage.created_at,
                )
                .where(
                    ConversationMessage.user_id == uid,
                    ConversationMessage.conversation_id == cid,
                )
                .order_by(ConversationMessage.created_at.asc())
                .limit(500)
            )
            rows = result.all()
            return [
                {
                    "role": row.role,
                    "content": row.content,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
    except Exception:
        logger.exception("Failed to load full conversation for conv=%s", conversation_id)
        return []


async def delete_conversation(user_id: str, conversation_id: str) -> bool:
    """Delete all messages and accumulated docs for a user's conversation.

    Returns True if anything was deleted, False otherwise.
    """
    if not conversation_id:
        return False
    try:
        uid = uuid.UUID(str(user_id))
        cid = _to_conv_uuid(conversation_id)
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete as sql_delete
            from neolex.db.models import ConversationDocs

            # Delete messages
            msg_result = await session.execute(
                sql_delete(ConversationMessage).where(
                    ConversationMessage.user_id == uid,
                    ConversationMessage.conversation_id == cid,
                )
            )
            # Delete accumulated docs
            await session.execute(
                sql_delete(ConversationDocs).where(
                    ConversationDocs.user_id == uid,
                    ConversationDocs.conversation_id == cid,
                )
            )
            await session.commit()
            return msg_result.rowcount > 0
    except Exception:
        logger.exception("Failed to delete conversation conv=%s", conversation_id)
        return False


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
                content=answer[:8000],
            ))
            await session.commit()
    except Exception:
        logger.exception("Failed to save conversation turn for conv=%s", conversation_id)
