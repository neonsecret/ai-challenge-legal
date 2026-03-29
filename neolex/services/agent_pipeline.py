"""Agent pipeline adapter — connects LangGraph agent to the SSE endpoint.

Drop-in replacement for run_single_question() when use_agent=True.
The existing SSE protocol (status/token/answer/done events) is preserved,
so the frontend needs zero changes.

This is the ONLY neolex/ file (besides pipeline.py) that imports from arlc/.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


def _log_task_exception(task: asyncio.Task) -> None:
    """Log exceptions from fire-and-forget background tasks."""
    if not task.cancelled() and task.exception():
        logger.error("Background task failed: %s", task.exception())


async def run_agent_question(
    question: str,
    answer_type: str,  # noqa: ARG001 — kept for API compatibility with the SSE endpoint
    corpus: str = "difc",
    user_id: str | None = None,
    conversation_id: str | None = None,
    selected_laws: list[str] | None = None,
    on_status: Callable[[str], None] | None = None,
    on_token: Callable[[str], None] | None = None,
) -> dict:
    """Run a question through the LangGraph agent.

    Multi-turn support: loads accumulated docs from prior turns so the agent
    can answer follow-ups without re-searching. Saves updated docs after.
    """
    t_start = time.monotonic()

    if on_status:
        on_status("processing")

    # Load conversation history + accumulated docs in parallel
    conversation_history: list[dict] = []
    accumulated_docs: list[dict] = []

    if user_id and conversation_id:
        from neolex.services.conversation import load_history, load_accumulated_docs

        conversation_history, accumulated_docs = await asyncio.gather(
            load_history(user_id, conversation_id),
            load_accumulated_docs(user_id, conversation_id),
        )

        if accumulated_docs:
            logger.info("Loaded %d accumulated docs from prior turns", len(accumulated_docs))

    # Run the agent
    from arlc.agent.graph import run_agent_turn

    result = await run_agent_turn(
        question=question,
        corpus=corpus,
        selected_laws=selected_laws or [],
        accumulated_docs=accumulated_docs,
        conversation_history=conversation_history,
        user_id=user_id or "",
        conversation_id=conversation_id or "",
        on_status=on_status,
        on_token=on_token,
    )

    # Persist accumulated docs for future turns (non-blocking)
    new_docs = result.get("accumulated_docs", [])
    if user_id and conversation_id and new_docs:
        from neolex.services.conversation import save_accumulated_docs

        task = asyncio.create_task(save_accumulated_docs(user_id, conversation_id, new_docs))
        task.add_done_callback(_log_task_exception)

    elapsed_ms = (time.monotonic() - t_start) * 1000

    return {
        "answer": result.get("answer", ""),
        "chunk_pages": result.get("sources", []),
        "total_time_ms": elapsed_ms,
        "model_name": "vitreon-legal",
    }
