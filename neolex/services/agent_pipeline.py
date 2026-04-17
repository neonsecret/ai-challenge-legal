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
import uuid
from typing import Callable

logger = logging.getLogger(__name__)


def _log_task_exception(task: asyncio.Task) -> None:
    """Log exceptions from fire-and-forget background tasks."""
    if not task.cancelled() and task.exception():
        logger.error("Background task failed: %s", task.exception())


def _make_draft_document_fn(
    user_uuid: uuid.UUID,
    conversation_uuid: uuid.UUID,
) -> Callable:
    """Build the async callable that the agent uses to create/update documents.

    Returns a closure that accepts (action, fields, document_id, template_slug)
    and delegates to the internal document service.  Acquires its own DB session
    per call so it can be awaited safely from within the agent's search_node.
    """

    async def _draft_fn(
        action: str,
        fields: dict[str, str],
        document_id: str = "",
        template_slug: str = "",
    ) -> dict:
        from neolex.db.postgres import AsyncSessionLocal
        from neolex.services.document_service import create_draft_document, update_draft_document

        async with AsyncSessionLocal() as db:
            if action == "update":
                if not document_id:
                    return {"error": "document_id is required for action=update"}
                try:
                    doc_uuid = uuid.UUID(document_id)
                except ValueError:
                    return {"error": f"Invalid document_id: {document_id!r} — must be a UUID"}
                return await update_draft_document(
                    db=db,
                    user_id=user_uuid,
                    conversation_id=conversation_uuid,
                    doc_id=doc_uuid,
                    fields=fields,
                )
            else:
                # Default: create
                if not template_slug:
                    return {"error": "template_slug is required"}
                return await create_draft_document(
                    db=db,
                    user_id=user_uuid,
                    conversation_id=conversation_uuid,
                    template_slug=template_slug,
                    fields=fields,
                )

    return _draft_fn


async def run_agent_question(
    question: str,
    answer_type: str,  # noqa: ARG001 — kept for API compatibility with the SSE endpoint
    corpus: str = "difc",
    user_id: str | None = None,
    conversation_id: str | None = None,
    selected_laws: list[str] | None = None,
    on_status: Callable[[str], None] | None = None,
    on_token: Callable[[str], None] | None = None,
    on_document: Callable[[dict], None] | None = None,
    use_internet: bool = True,
    doc_ids: list[str] | None = None,
    # --- Drafting mode (all optional) ---
    template_slug: str | None = None,
    template_name: str = "",
    template_required_fields: list[str] | None = None,
    template_field_descriptions: dict[str, str] | None = None,
    chat_documents: list[dict] | None = None,
    # --- Observability ---
    user_email: str | None = None,
    subscription_plan: str | None = None,
    # --- Hybrid search: builtin corpus + custom corpus collection ---
    custom_corpus: str | None = None,
    custom_doc_ids: list[str] | None = None,
    # --- Routing experiment override (NEO-2322, benchmark / debug only) ---
    routing_mode_override: str | None = None,
) -> dict:
    """Run a question through the LangGraph agent.

    Multi-turn support: loads accumulated docs from prior turns so the agent
    can answer follow-ups without re-searching. Saves updated docs after.

    When template_slug is set the agent operates in drafting mode: it searches
    the corpus, fills template fields, and calls document_draft to persist.
    """
    t_start = time.monotonic()

    if on_status:
        on_status("processing")

    # --- Langfuse trace lifecycle ---
    from neolex.observability import (
        create_query_trace,
        finalize_trace,
        get_trace_id,
        is_enabled,
        reset_current_trace,
        set_current_trace,
    )

    trace = None
    _trace_token = None
    if is_enabled():
        trace = create_query_trace(
            query=question,
            corpus=corpus,
            answer_type=answer_type,
            user_id=user_id,
            session_id=conversation_id,
            user_email=user_email,
            subscription_plan=subscription_plan,
            use_agent=True,
        )
        if trace is not None:
            _trace_token = set_current_trace(trace)

    # Load conversation history + accumulated docs in parallel
    conversation_history: list[dict] = []
    accumulated_docs: list[dict] = []

    if user_id and conversation_id:
        from neolex.services.conversation import load_accumulated_docs, load_history

        conversation_history, accumulated_docs = await asyncio.gather(
            load_history(user_id, conversation_id),
            load_accumulated_docs(user_id, conversation_id),
        )

        # Drop docs from a different corpus — they're irrelevant after a jurisdiction switch
        if accumulated_docs:
            same_corpus = [d for d in accumulated_docs if d.get("_corpus", corpus) == corpus]
            if len(same_corpus) < len(accumulated_docs):
                logger.info(
                    "Dropped %d docs from different corpus (kept %d for %s)",
                    len(accumulated_docs) - len(same_corpus),
                    len(same_corpus),
                    corpus,
                )
            accumulated_docs = same_corpus

    # Build the draft_document_fn callback when in drafting mode OR when
    # existing documents are present in the conversation (so the agent can
    # call document_draft with action="update" on turn 2+ even without a
    # template_slug being set in the current request).
    draft_document_fn = None
    if (template_slug or chat_documents) and user_id and conversation_id:
        try:
            from neolex.services.conversation import _to_conv_uuid

            user_uuid = uuid.UUID(user_id)
            conv_uuid = _to_conv_uuid(conversation_id)
            draft_document_fn = _make_draft_document_fn(user_uuid, conv_uuid)
        except ValueError:
            logger.warning(
                "[agent-pipeline] could not build draft_document_fn: invalid UUIDs user=%s conv=%s",
                user_id,
                conversation_id,
            )

    # Run the agent
    from arlc.agent.graph import run_agent_turn

    try:
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
            on_document=on_document,
            use_internet=use_internet,
            doc_ids=doc_ids,
            template_slug=template_slug,
            template_name=template_name,
            template_required_fields=template_required_fields,
            template_field_descriptions=template_field_descriptions,
            chat_documents=chat_documents,
            draft_document_fn=draft_document_fn,
            custom_corpus=custom_corpus,
            custom_doc_ids=custom_doc_ids,
            routing_mode_override=routing_mode_override,
        )
    except Exception:
        if trace is not None:
            finalize_trace(trace, level="ERROR")
        if _trace_token is not None:
            reset_current_trace(_trace_token)
        raise

    # Persist accumulated docs for future turns (non-blocking)
    new_docs = result.get("accumulated_docs", [])
    if user_id and conversation_id and new_docs:
        from neolex.services.conversation import save_accumulated_docs

        task = asyncio.create_task(save_accumulated_docs(user_id, conversation_id, new_docs))
        task.add_done_callback(_log_task_exception)

    elapsed_ms = (time.monotonic() - t_start) * 1000

    answer_str = result.get("answer", "")
    if trace is not None:
        finalize_trace(trace, output=answer_str)
    if _trace_token is not None:
        reset_current_trace(_trace_token)

    return {
        "answer": answer_str,
        "chunk_pages": result.get("sources", []),
        "total_time_ms": elapsed_ms,
        "model_name": "vitreon-legal",
        "trace_id": get_trace_id(trace),
    }
