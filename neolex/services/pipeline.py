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

    Multi-turn support (when user_id + conversation_id are provided):
    - Loads conversation history from PostgreSQL scoped to this user
    - Enriches the query with condensed previous answers for the router + embedder
      (previous answers contain law names/article numbers that help routing)
    - Wraps answer_fn so Claude receives proper multi-turn messages (original
      question + history), not the enriched query string

    on_status: optional callable(stage: str) emitted at each pipeline stage.
    _process_question is already async def — await it directly.
    """
    from arlc.pipeline import _process_question

    effective_question = question
    answer_fn_to_use = answer_fn

    if user_id and conversation_id:
        from neolex.services.conversation import load_history
        history = await load_history(user_id, conversation_id)
        if history:
            # Enrich query for routing + retrieval: append condensed previous answers
            # so the regex router and FAISS embedder find document references from
            # prior turns (e.g. "DIFC Law No. 5", "Article 118").
            prev_answers = [t["content"][:300] for t in history if t["role"] == "assistant"][-2:]
            if prev_answers:
                effective_question = f"{question}\n\n[Previous discussion: {' | '.join(prev_answers)}]"

            # Wrap answer_fn to pass (a) the original question for the LLM prompt
            # and (b) history as proper multi-turn messages — Claude handles context naturally.
            _orig_question = question
            _history = history
            _orig_answer_fn = answer_fn

            async def _answer_with_context(
                enriched_q, at, pages, qid="",
                metadata_answer=None, on_token=None, web_mode=False,
            ):
                return await _orig_answer_fn(
                    _orig_question, at, pages, qid,
                    metadata_answer=metadata_answer, on_token=on_token, web_mode=web_mode,
                    conversation_history=_history,
                )

            answer_fn_to_use = _answer_with_context

    question_data = {
        "id": str(uuid.uuid4()),
        "question": effective_question,
        "answer_type": answer_type,
    }
    return await _process_question(
        question_data, route_fn, retrieve_fn, answer_fn_to_use, semaphore,
        on_status=on_status,
        on_token=on_token,
        corpus=corpus,
        web_mode=True,  # enable markdown formatting in LLM answers
    )
