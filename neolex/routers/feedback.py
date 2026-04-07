"""Feedback endpoint — collect user ratings on query responses.

POST /api/feedback
  Auth: session cookie required
  Body: { trace_id, message_id, conversation_id, rating, comment? }
  Rate limit: 60 feedback submissions per hour per user (audit DB, fail-open)
  Ownership: conversation_id must belong to the requesting user
"""

import asyncio
import logging
import time
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.auth.session import get_current_user
from neolex.db.audit import get_audit_db
from neolex.db.models import Feedback, PipelineJob, User
from neolex.db.postgres import get_db
from neolex.observability import get_langfuse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=256)
    message_id: str = Field(..., min_length=1, max_length=256)
    conversation_id: str = Field(..., min_length=1, max_length=256)
    rating: Literal["positive", "negative"]
    comment: str | None = Field(None, max_length=2000)


def _push_score_sync(trace_id: str, rating: str, comment: str | None) -> None:
    """Synchronous Langfuse score push — runs in a thread pool to stay non-blocking."""
    client = get_langfuse()
    if client is None:
        return
    try:
        client.create_score(
            trace_id=trace_id,
            name="user-feedback",
            value=1.0 if rating == "positive" else 0.0,
            comment=comment,
        )
    except Exception:
        logger.debug("Langfuse score push failed", exc_info=True)


async def _push_score_bg(trace_id: str, rating: str, comment: str | None) -> None:
    """Async wrapper for fire-and-forget Langfuse score push.

    Catches all exceptions so a Langfuse outage never surfaces in the
    background task runner or causes a 500 on a future request.
    """
    try:
        await asyncio.to_thread(_push_score_sync, trace_id, rating, comment)
    except Exception:
        logger.debug("Langfuse background push failed", exc_info=True)


@router.post("/feedback", status_code=200)
async def submit_feedback(
    body: FeedbackRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record user feedback for a query response.

    Uses upsert so repeated feedback on the same message updates in place
    rather than duplicating rows (1 feedback per message per user).
    """
    # --- Rate limit: 60 submissions per hour per user (fail-open) ---
    bucket = f"feedback:{user.id}"
    try:
        async with get_audit_db() as audit:
            _, exceeded = await audit.check_and_increment_rate(
                bucket=bucket,
                window_seconds=3600.0,
                limit=60,
                now=time.time(),
            )
        if exceeded:
            raise HTTPException(status_code=429, detail="Too many feedback submissions. Try again later.")
    except HTTPException:
        raise
    except Exception:
        logger.debug("Feedback rate limit DB unavailable, skipping", exc_info=True)
        # Fail open — do NOT block the user if the audit DB is down

    # --- Ownership check: conversation_id must belong to requesting user ---
    conversation_owned = await db.scalar(
        select(
            exists().where(
                PipelineJob.conversation_id == body.conversation_id,
                PipelineJob.user_id == user.id,
            )
        )
    )
    if not conversation_owned:
        raise HTTPException(status_code=403, detail="Forbidden")

    stmt = (
        pg_insert(Feedback)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            trace_id=body.trace_id,
            message_id=body.message_id,
            conversation_id=body.conversation_id,
            rating=body.rating,
            comment=body.comment,
        )
        .on_conflict_do_update(
            index_elements=["message_id", "user_id"],
            set_={
                "trace_id": body.trace_id,
                "conversation_id": body.conversation_id,
                "rating": body.rating,
                "comment": body.comment,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()

    # Fire-and-forget: push score to Langfuse without blocking the response.
    # Fails silently if Langfuse is down or LANGFUSE_ENABLED=False.
    background_tasks.add_task(_push_score_bg, body.trace_id, body.rating, body.comment)

    return {"status": "ok"}
