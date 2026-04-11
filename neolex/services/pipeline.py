"""Adapter: wraps arlc.pipeline._process_question for single HTTP question.

This is the ONLY neolex/ file that imports from arlc/.
Do NOT import from arlc/ anywhere else in neolex/.
"""

from __future__ import annotations

import asyncio
import time
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
    laws: list[str] | None = None,
    user_email: str | None = None,
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

    Returns the pipeline result dict, extended with an optional ``trace_id`` key
    (str | None) when Langfuse tracing is enabled.
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
                enriched_q,
                at,
                pages,
                qid="",
                metadata_answer=None,
                on_token=None,
                web_mode=False,
            ):
                return await _orig_answer_fn(
                    _orig_question,
                    at,
                    pages,
                    qid,
                    metadata_answer=metadata_answer,
                    on_token=on_token,
                    web_mode=web_mode,
                    conversation_history=_history,
                )

            answer_fn_to_use = _answer_with_context

    # --- Langfuse tracing setup ---
    # All Langfuse calls are CPU-cheap and non-blocking: the SDK queues spans in
    # memory and a background OTEL exporter flushes them without touching the
    # event loop.  This adds zero latency to the query path.
    from neolex.observability import (
        add_generation_span,
        create_query_trace,
        finalize_trace,
        get_trace_id,
        is_enabled,
        reset_current_trace,
        set_current_trace,
    )

    trace = None
    _trace_token = None
    _stage_times: dict[str, float] = {}

    if is_enabled():
        trace = create_query_trace(
            query=question,
            corpus=corpus,
            answer_type=answer_type,
            user_id=user_id,
            session_id=conversation_id,
            user_email=user_email,
        )
        if trace is not None:
            _trace_token = set_current_trace(trace)

    # Wrap on_status to record the wall-clock start of each pipeline stage so
    # we can compute span durations after the pipeline completes.
    _original_on_status = on_status

    def _traced_on_status(stage: str) -> None:
        _stage_times[stage] = time.monotonic()
        if _original_on_status is not None:
            _original_on_status(stage)

    effective_on_status = _traced_on_status if trace is not None else on_status

    question_data = {
        "id": str(uuid.uuid4()),
        "question": effective_question,
        "answer_type": answer_type,
    }
    if laws:
        question_data["laws"] = laws

    try:
        result = await _process_question(
            question_data,
            route_fn,
            retrieve_fn,
            answer_fn_to_use,
            semaphore,
            on_status=effective_on_status,
            on_token=on_token,
            corpus=corpus,
            web_mode=True,  # enable markdown formatting in LLM answers
        )
    except Exception:
        if trace is not None:
            finalize_trace(trace, level="ERROR")
        if _trace_token is not None:
            reset_current_trace(_trace_token)
        raise

    # --- Post-pipeline: record spans and finalise the trace ---
    if trace is not None:
        _record_retrieval_span(trace, question, _stage_times)
        answer_str = str(result.get("answer", "")) if result.get("answer") is not None else ""
        add_generation_span(
            trace,
            model=result.get("model_name", "unknown"),
            input_text=effective_question,
            output_text=answer_str,
            duration_ms=float(result.get("total_time_ms", 0)),
            usage={
                "input": result.get("input_tokens", 0),
                "output": result.get("output_tokens", 0),
            },
            cache_read_tokens=result.get("cache_read_tokens", 0),
            cache_write_tokens=result.get("cache_write_tokens", 0),
        )
        finalize_trace(trace, output=answer_str)
        result["trace_id"] = get_trace_id(trace)

    if _trace_token is not None:
        reset_current_trace(_trace_token)

    return result


def _record_retrieval_span(trace: Any, question: str, stage_times: dict[str, float]) -> None:
    """Create a retrieval span using timestamps collected during pipeline execution.

    Span covers the full retrieve+rerank phase: from ``retrieving`` to the first
    ``answering:N`` stage.  Skipped silently when timestamps are unavailable
    (oracle / rule-based fast paths that bypass retrieval entirely).
    """
    from neolex.observability import add_retrieval_span

    t_retrieve = stage_times.get("retrieving")
    t_answer: float | None = None
    n_pages = 0
    for stage, ts in stage_times.items():
        if stage.startswith("answering:"):
            t_answer = ts
            try:
                n_pages = int(stage.split(":", 1)[1])
            except (IndexError, ValueError):
                pass
            break

    if t_retrieve is not None and t_answer is not None:
        add_retrieval_span(
            trace,
            query=question,
            num_results=n_pages,
            duration_ms=(t_answer - t_retrieve) * 1000,
        )
