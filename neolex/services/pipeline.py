"""Adapter: wraps arlc.pipeline._process_question for single HTTP question.

This is the ONLY neolex/ file that imports from arlc/.
Do NOT import from arlc/ anywhere else in neolex/.
"""
from __future__ import annotations
import asyncio
import uuid
from typing import Any


async def run_single_question(
        question: str,
        answer_type: str,
        semaphore: asyncio.Semaphore,
        route_fn: Any,
        retrieve_fn: Any,
        answer_fn: Any,
        on_status: Any = None,
        on_token: Any = None,
        corpus: str = "difc",
        user_id: str | None = None,
        conversation_id: str | None = None,
) -> dict:
    """Route one HTTP question through the arlc pipeline.

    If user_id and conversation_id are provided, loads conversation history from
    PostgreSQL (scoped to that user) and rewrites follow-up questions as standalone
    queries before routing. This keeps arlc/ stateless.

    on_status: optional callable(stage: str) emitted at each pipeline stage.
    Called from the event loop (between awaits), so asyncio.Queue.put_nowait is safe.

    _process_question is already async def — await it directly.
    Do NOT wrap it in asyncio.to_thread() (it would create a nested event loop).
    Do NOT call asyncio.run() here (event loop is already running in FastAPI).
    """
    from arlc.pipeline import _process_question

    # Rewrite follow-up questions as standalone queries for correct routing
    effective_question = question
    if user_id and conversation_id:
        from neolex.services.conversation import load_history
        from neolex.services.context_rewriter import rewrite_for_retrieval
        history = await load_history(user_id, conversation_id)
        if history:
            effective_question = await rewrite_for_retrieval(question, history)

    question_data = {
        "id": str(uuid.uuid4()),
        "question": effective_question,
        "answer_type": answer_type,
    }
    return await _process_question(
        question_data, route_fn, retrieve_fn, answer_fn, semaphore,
        on_status=on_status,
        on_token=on_token,
        corpus=corpus,
        web_mode=True,  # enable markdown formatting in LLM answers
    )
