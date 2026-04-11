import asyncio
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from neolex.auth.middleware import get_api_key
from neolex.config import settings
from neolex.constants import DRAFTING_CUSTOM_SLUG, DRAFTING_FREEFORM_SLUG, DRAFTING_MAX_DOCS_PER_CONVERSATION
from neolex.db.audit import get_audit_db
from neolex.db.models import User
from neolex.db.postgres import AsyncSessionLocal, get_db
from neolex.schemas.query import QueryRequest, QueryResponse, pipeline_dict_to_response
from neolex.services.pipeline import run_single_question

logger = logging.getLogger(__name__)

# Regex for extracting (current/total) progress from status strings
_PROGRESS_RE = re.compile(r"\((\d+)/(\d+)\)")
router = APIRouter(prefix="/api/v1")


def _log_task_exception(task: asyncio.Task) -> None:
    """Log exceptions from fire-and-forget background tasks."""
    if not task.cancelled() and task.exception():
        logger.error("Background task failed: %s", task.exception())


# ---------------------------------------------------------------------------
# Document drafting — pipeline integration
# ---------------------------------------------------------------------------


async def _create_pipeline_document(
    template_slug: str,
    conversation_id: str,
    user_id: str,
) -> dict | None:
    """Create a ChatDocument triggered by the query pipeline and return the SSE payload.

    Called after the answer event is yielded when the query body includes a
    template_slug.  Opens its own DB session so the call is independent of
    the request-scoped session used for rate-limiting.

    Returns a dict with doc_id / template_slug / template_name on success,
    or None when document creation is not possible (template missing, limit
    reached, bad IDs).  Errors are non-fatal — the caller logs and continues.
    """
    from neolex.db.drafting_models import ChatDocument, DocumentTemplate

    try:
        conv_uuid = uuid.UUID(conversation_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        logger.error(
            "Pipeline document creation skipped: invalid conversation_id=%r or user_id=%r",
            conversation_id,
            user_id,
        )
        return None

    effective_slug = DRAFTING_FREEFORM_SLUG if template_slug == DRAFTING_CUSTOM_SLUG else template_slug

    async with AsyncSessionLocal() as session:
        # Verify the template exists before creating the document.
        tmpl_result = await session.execute(select(DocumentTemplate).where(DocumentTemplate.slug == effective_slug))
        template = tmpl_result.scalar_one_or_none()
        if template is None:
            logger.warning(
                "Pipeline document creation skipped: template '%s' not found (has seed_templates.py been run?)",
                effective_slug,
            )
            return None

        # Capture template name before commit — expire_on_commit=True detaches the
        # object when the session exits, making post-commit attribute access raise
        # DetachedInstanceError.
        # For __custom__ slugs, always return the locale-neutral English label
        # regardless of what name the underlying DB template has (NEO-1021).
        template_name = "Custom Document" if template_slug == _PIPELINE_CUSTOM_SLUG else template.name

        # Serialize concurrent document creations for this conversation.
        # SELECT ... FOR UPDATE cannot lock rows that don't yet exist, so two
        # concurrent first-document requests would both read count=0 and both INSERT.
        # pg_advisory_xact_lock serialises them at the PostgreSQL level; the lock is
        # released automatically when the transaction commits or rolls back.
        _conv_lock_key = conv_uuid.int & 0x7FFFFFFFFFFFFFFF  # positive int64
        await session.execute(select(func.pg_advisory_xact_lock(_conv_lock_key)))

        # Respect the per-conversation document cap.
        count_result = await session.execute(
            select(ChatDocument.id).where(
                ChatDocument.conversation_id == conv_uuid,
                ChatDocument.user_id == user_uuid,
            )
        )
        if len(count_result.scalars().all()) >= DRAFTING_MAX_DOCS_PER_CONVERSATION:
            logger.info(
                "Pipeline document creation skipped: conversation %s already at limit",
                conv_uuid,
            )
            return None

        doc = ChatDocument(
            conversation_id=conv_uuid,
            user_id=user_uuid,
            template_slug=effective_slug,
            fields={},
            version=1,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

    logger.info(
        "Pipeline document created: id=%s template=%s conversation=%s",
        doc.id,
        effective_slug,
        conv_uuid,
    )
    return {
        "doc_id": str(doc.id),
        "template_slug": template_slug,  # Return the slug the client sent, not effective_slug
        "template_name": template_name,
    }


# ---------------------------------------------------------------------------
# Corpus access control
# ---------------------------------------------------------------------------

_BUILTIN_CORPORA: frozenset[str] = frozenset({"difc", "czech", "uk", "au"})

# ---------------------------------------------------------------------------
# Plan-based query rate limiting
# ---------------------------------------------------------------------------

# Daily query limits per paid plan. A value of 0 means unlimited (enterprise).
# This sentinel is checked explicitly in _enforce_query_limit() below.
UNLIMITED_DAILY_QUERIES = 0

_PLAN_DAILY_LIMITS: dict[str, int] = {
    "free": 3,
    "trial": 3,
    "starter": settings.starter_daily_limit,
    "pro": settings.pro_daily_limit,
    "enterprise": settings.enterprise_daily_limit,  # UNLIMITED_DAILY_QUERIES (0) = unlimited
}


_ACTIVE_STATUSES = {"free", "trial", "starter", "pro", "enterprise"}


async def _enforce_query_limit(user: User, db: AsyncSession) -> None:
    """Check and increment usage counters per plan. Raises 402/429 when exceeded.

    Uses atomic UPDATE ... WHERE to prevent race conditions on concurrent requests.
    """
    from sqlalchemy import update as sql_update

    status = user.subscription_status
    now = datetime.now(UTC)

    # Whitelist: reject any unknown/canceled status
    if status not in _ACTIVE_STATUSES:
        raise HTTPException(status_code=402, detail="Active subscription required.")

    # All plans use daily limits (free=3/day, starter=30/day, etc.)
    daily_limit = _PLAN_DAILY_LIMITS.get(status, 0)

    # Reset daily counter if before today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if user.daily_queries_reset_at is None or user.daily_queries_reset_at < today_start:
        await db.execute(
            sql_update(User).where(User.id == user.id).values(daily_queries_used=0, daily_queries_reset_at=today_start),
        )
        await db.commit()
        await db.refresh(user)

    if daily_limit == UNLIMITED_DAILY_QUERIES:
        # Unlimited plan (enterprise) — atomic increment for tracking, no cap enforced
        await db.execute(
            sql_update(User).where(User.id == user.id).values(daily_queries_used=User.daily_queries_used + 1),
        )
        await db.commit()
    elif daily_limit > 0:
        result = await db.execute(
            sql_update(User)
            .where(User.id == user.id, User.daily_queries_used < daily_limit)
            .values(daily_queries_used=User.daily_queries_used + 1)
            .returning(User.daily_queries_used),
        )
        new_count = result.scalar_one_or_none()
        if new_count is None:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit reached ({daily_limit}/day on {status.title()}). Resets at midnight UTC.",
            )
        await db.commit()


@router.post("/query", response_model=QueryResponse)
async def query(
    request: Request,
    body: QueryRequest,
    corpus: Annotated[str, Query(pattern=r"^[a-zA-Z0-9_-]{1,64}$")] = "difc",
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Submit a legal question and receive a grounded JSON answer with source citations.

    Returns 429 if the user's plan query limit is exceeded.
    Returns 503 if pipeline is not ready (still warming up).
    Returns 500 if pipeline raises an unexpected exception.
    Returns 422 if request body fails Pydantic validation.
    """
    # --- Enforce plan-based query limits ---
    user_id = key_row.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    await _enforce_query_limit(user, db)

    # Validate corpus access: built-in corpora are open, custom corpora must belong to the user
    if corpus not in _BUILTIN_CORPORA:
        if corpus != key_row["client_slug"]:
            raise HTTPException(status_code=403, detail="Access denied to this corpus")

    if not getattr(request.app.state, "ready", False):
        raise HTTPException(
            status_code=503,
            detail={"error": "Service unavailable", "detail": "Pipeline is still warming up."},
        )

    state = request.app.state
    try:
        result = await run_single_question(
            question=body.question,
            answer_type=body.answer_type,
            semaphore=state.semaphore,
            route_fn=state.route_fn,
            retrieve_fn=state.retrieve_fn,
            answer_fn=state.answer_fn,
            corpus=corpus,
            laws=body.laws,
        )
    except asyncio.TimeoutError as err:
        logger.error("Pipeline timeout for question: %.80s", body.question)
        raise HTTPException(
            status_code=504,
            detail={"error": "Pipeline timeout", "detail": "Query timed out. Please try again."},
        ) from err
    except Exception as err:
        logger.exception("Pipeline error for question: %.80s", body.question)
        raise HTTPException(
            status_code=500,
            detail={"error": "Pipeline failed", "detail": "An internal error occurred. Please try again."},
        ) from err

    response = pipeline_dict_to_response(result)
    latency_ms = result.get("total_time_ms", 0)
    sources_json = json.dumps([s.model_dump() for s in response.sources])
    async with get_audit_db() as db:
        await db.log_query(
            key_hash=key_row["key_hash"],
            question=body.question,
            answer_text=response.answer,
            sources_json=sources_json,
            latency_ms=latency_ms,
            model_name=response.model_name,
            ip=getattr(request.client, "host", None),
            user_agent=request.headers.get("user-agent"),
        )
    return response


@router.post("/query/stream")
async def query_stream(
    request: Request,
    body: QueryRequest,
    key_row: dict = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Stream a legal query response as Server-Sent Events.

    Accepts a JSON body with question, answer_type, corpus, and optional
    conversation_id. The conversation_id is an opaque key — conversation
    history is loaded server-side from PostgreSQL, scoped to the authenticated
    user. History content never travels in the request body.

    Events emitted in real time as the pipeline progresses:
    1. status  {"status": "routing"}            -- document routing started
    2. status  {"status": "retrieving"}         -- hybrid retrieval started
    3. status  {"status": "answering:N"}        -- LLM generation started (N source pages)
    4. answer  {QueryResponse JSON}             -- pipeline completed
    5. done    {}                               -- signals end of stream
    """
    # --- Enforce plan-based query limits ---
    user_id_str = key_row.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Authentication required")
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(User).where(User.id == user_id_str))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    await _enforce_query_limit(user, db)

    if not getattr(request.app.state, "ready", False):
        raise HTTPException(
            status_code=503,
            detail={"error": "Service unavailable", "detail": "Pipeline is still warming up."},
        )

    state = request.app.state
    user_id = key_row["user_id"]
    conversation_id = body.conversation_id
    corpus = body.corpus

    # Validate corpus access: built-in corpora are open, custom corpora must belong to the user
    if corpus not in _BUILTIN_CORPORA:
        if corpus != key_row["client_slug"]:
            raise HTTPException(status_code=403, detail="Access denied to this corpus")

    # Create pipeline job for persistent status tracking
    from neolex.services.conversation import (
        complete_pipeline_job,
        create_pipeline_job,
        fail_pipeline_job,
        update_pipeline_job_status,
    )

    pipeline_job_id = await create_pipeline_job(user_id, conversation_id or "", body.question)

    async def event_generator():
        # Unified queue for status, token, and done events.
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        # Callback wiring: both the deterministic pipeline and the LangGraph
        # agent may invoke callbacks from either the event-loop thread (async
        # code) or from worker threads (sync graph nodes, asyncio.to_thread).
        # A single pair of universal callbacks detects the execution context
        # and dispatches correctly — no caller needs to choose a flavour.

        def _in_event_loop() -> bool:
            """Return True if the current thread is running the event loop."""
            try:
                return asyncio.get_running_loop() is loop
            except RuntimeError:
                return False

        def _enqueue(item: tuple) -> None:
            """Put an item on the SSE queue from any thread."""
            if _in_event_loop():
                queue.put_nowait(item)
            else:
                loop.call_soon_threadsafe(queue.put_nowait, item)

        def _schedule_coroutine(coro) -> None:
            """Schedule a coroutine as a fire-and-forget task from any thread."""
            if _in_event_loop():
                t = asyncio.create_task(coro)
                t.add_done_callback(_log_task_exception)
            else:
                # From a worker thread: schedule task creation on the event loop.
                # Use asyncio.run_coroutine_threadsafe which is the proper API for
                # submitting coroutines from foreign threads.
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                future.add_done_callback(
                    lambda f: (
                        logger.error("Background task failed: %s", f.exception())
                        if not f.cancelled() and f.exception()
                        else None
                    ),
                )

        def _update_job_status_detail(stage: str):
            """Fire-and-forget: persist status to pipeline_jobs for SSE recovery."""
            if not pipeline_job_id:
                return
            coarse = "processing"
            lower = stage.lower()
            if "retriev" in lower or "search" in lower or "ranking" in lower:
                coarse = "searching"
            elif "answer" in lower or "writing" in lower:
                coarse = "answering"
            _schedule_coroutine(
                update_pipeline_job_status(
                    pipeline_job_id,
                    status=coarse,
                    status_detail=stage,
                ),
            )

        def on_status(stage: str):
            # Extract structured progress (current/total) from status strings
            # e.g. "retrieving:reranking passages (5/47)" → progress={current:5, total:47}
            m = _PROGRESS_RE.search(stage)
            if m:
                progress = {"current": int(m.group(1)), "total": int(m.group(2))}
                _enqueue(("status", stage, progress))
            else:
                _enqueue(("status", stage, None))
            _update_job_status_detail(stage)

        def on_token(text: str):
            _enqueue(("token", text))

        def on_document(payload: dict):
            _enqueue(("document", payload))

        # Emit initial connection status
        yield {"event": "status", "data": json.dumps({"status": "processing"})}
        await asyncio.sleep(0)

        # Run pipeline as a concurrent task so we can yield status events while it runs
        pipeline_result: dict = {}
        pipeline_error: BaseException | None = None

        async def _run_pipeline():
            nonlocal pipeline_result, pipeline_error
            try:
                if body.use_agent:
                    # ---- LangGraph agent path ----
                    from arlc.agent.config import AGENT_TIMEOUT_SECONDS
                    from neolex.services.agent_pipeline import run_agent_question

                    # Resolve drafting context when template_slug is set
                    template_name: str = ""
                    template_required_fields: list[str] | None = None
                    template_field_descriptions: dict[str, str] | None = None
                    chat_documents: list[dict] | None = None

                    if body.template_slug and conversation_id:
                        import uuid as _uuid

                        from neolex.services.document_service import (
                            get_template_by_slug,
                            list_conversation_documents,
                        )

                        tmpl = await get_template_by_slug(db, body.template_slug)
                        if tmpl:
                            template_name = tmpl["name"]
                            template_required_fields = tmpl["required_fields"]
                            template_field_descriptions = tmpl["field_descriptions"]

                        try:
                            chat_documents = await list_conversation_documents(
                                db,
                                user_id=_uuid.UUID(user_id),
                                conversation_id=_uuid.UUID(conversation_id),
                            )
                        except (ValueError, Exception):
                            chat_documents = []

                    pipeline_result = await asyncio.wait_for(
                        run_agent_question(
                            question=body.question,
                            answer_type=body.answer_type,
                            corpus=corpus,
                            user_id=user_id,
                            conversation_id=conversation_id,
                            selected_laws=body.laws,
                            on_status=on_status,
                            on_token=on_token,
                            on_document=on_document,
                            use_internet=body.use_internet,
                            doc_ids=body.doc_ids,
                            template_slug=body.template_slug,
                            template_name=template_name,
                            template_required_fields=template_required_fields,
                            template_field_descriptions=template_field_descriptions,
                            chat_documents=chat_documents,
                        ),
                        timeout=AGENT_TIMEOUT_SECONDS,
                    )
                else:
                    # ---- Deterministic pipeline path (unchanged) ----
                    pipeline_result = await run_single_question(
                        question=body.question,
                        answer_type=body.answer_type,
                        semaphore=state.semaphore,
                        route_fn=state.route_fn,
                        retrieve_fn=state.retrieve_fn,
                        answer_fn=state.answer_fn,
                        on_status=on_status,
                        on_token=on_token,
                        corpus=corpus,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        laws=body.laws,
                    )
            except asyncio.TimeoutError:
                logger.error("Agent pipeline timed out for question: %.80s", body.question)
                pipeline_error = asyncio.TimeoutError("Agent pipeline exceeded time limit")
            except BaseException as exc:
                pipeline_error = exc
            finally:
                # Signal completion to the SSE loop
                queue.put_nowait(("done", None))

        task = asyncio.create_task(_run_pipeline())

        try:
            while True:
                item = await queue.get()
                if item[0] == "status":
                    stage = item[1]
                    progress = item[2] if len(item) > 2 else None
                    payload: dict = {"status": stage}
                    if progress is not None:
                        payload["progress"] = progress
                    yield {"event": "status", "data": json.dumps(payload)}
                    await asyncio.sleep(0)
                elif item[0] == "token":
                    yield {"event": "token", "data": json.dumps({"text": item[1]})}
                    await asyncio.sleep(0)
                elif item[0] == "document":
                    doc_payload = item[1]
                    yield {
                        "event": "document_generated",
                        "data": json.dumps(
                            {
                                "doc_id": doc_payload.get("doc_id", ""),
                                "template_slug": doc_payload.get("template_slug", ""),
                                "template_name": doc_payload.get("template_name", ""),
                                "version": doc_payload.get("version", 1),
                            }
                        ),
                    }
                    await asyncio.sleep(0)
                elif item[0] == "done":
                    break
        except asyncio.CancelledError:
            # Client disconnected (page reload, network drop) — do NOT cancel the
            # pipeline task. Let it finish so the answer is saved to the DB.
            # The frontend will recover it via GET /conversations/{id}/status
            # polling on next page load.
            logger.info("SSE client disconnected — pipeline continues in background")
            return

        # Handle pipeline errors
        if isinstance(pipeline_error, asyncio.CancelledError):
            logger.info("SSE pipeline cancelled")
            return
        if isinstance(pipeline_error, (asyncio.TimeoutError, TimeoutError)):
            # Persist timeout status for frontend polling recovery
            if pipeline_job_id:
                t = asyncio.create_task(
                    fail_pipeline_job(
                        pipeline_job_id,
                        status="timeout",
                        detail="Query timed out — the pipeline took too long to process this request.",
                    ),
                )
                t.add_done_callback(_log_task_exception)
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": "Pipeline timeout",
                        "detail": "Query timed out. This may be due to heavy load or a complex search. Please try again.",
                    },
                ),
            }
            return
        if pipeline_error is not None:
            logger.exception("SSE pipeline error: %s", pipeline_error)
            # Persist failure status for frontend polling recovery
            if pipeline_job_id:
                t = asyncio.create_task(
                    fail_pipeline_job(
                        pipeline_job_id,
                        status="failed",
                        detail="An internal error occurred. Please try again.",
                    ),
                )
                t.add_done_callback(_log_task_exception)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Pipeline failed", "detail": "An internal error occurred. Please try again."},
                ),
            }
            return

        # Emit answer + audit log + save conversation turn
        try:
            response = pipeline_dict_to_response(pipeline_result)
            sources_json = json.dumps([s.model_dump() for s in response.sources])

            # Start follow-up generation concurrently with audit logging so the
            # two I/O-bound operations overlap and add minimal latency overall.
            from neolex.services.follow_ups import generate_follow_ups

            follow_ups_task = asyncio.create_task(
                generate_follow_ups(
                    question=body.question,
                    answer=str(response.answer) if response.answer is not None else "",
                    corpus=corpus,
                ),
            )
            follow_ups_task.add_done_callback(_log_task_exception)

            async with get_audit_db() as db:
                await db.log_query(
                    key_hash=key_row["key_hash"],
                    question=body.question,
                    answer_text=response.answer,
                    sources_json=sources_json,
                    latency_ms=pipeline_result.get("total_time_ms", 0),
                    model_name=response.model_name,
                    ip=getattr(request.client, "host", None),
                    user_agent=request.headers.get("user-agent"),
                )

            # Persist Q&A to conversation history (non-blocking, errors are swallowed)
            if user_id and conversation_id and response.answer is not None:
                from neolex.services.conversation import save_turn

                task = asyncio.create_task(
                    save_turn(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        question=body.question,
                        answer=str(response.answer),
                        sources_json=sources_json,
                        trace_id=pipeline_result.get("trace_id"),
                    ),
                )
                task.add_done_callback(_log_task_exception)

            # Persist completion to pipeline_jobs for frontend polling recovery
            if pipeline_job_id:
                t = asyncio.create_task(
                    complete_pipeline_job(
                        pipeline_job_id,
                        answer=str(response.answer) if response.answer is not None else "",
                        sources_json=sources_json,
                        confidence=response.confidence,
                    ),
                )
                t.add_done_callback(_log_task_exception)

            yield {"event": "answer", "data": response.model_dump_json()}

            # Fire RAGAS background evaluation after the answer is flushed.
            # The user never waits for this — scores land in Langfuse asynchronously.
            _ragas_trace_id = pipeline_result.get("trace_id")
            if _ragas_trace_id:
                from neolex.services.ragas_background import run_ragas_eval

                _ragas_contexts = [cp["text"] for cp in pipeline_result.get("chunk_pages", []) if cp.get("text")]
                _ragas_task = asyncio.create_task(
                    run_ragas_eval(
                        question=body.question,
                        answer=str(response.answer) if response.answer is not None else "",
                        contexts=_ragas_contexts,
                        trace_id=_ragas_trace_id,
                        corpus=corpus,
                        answer_type=body.answer_type,
                    )
                )
                _ragas_task.add_done_callback(_log_task_exception)

            # Collect follow-up questions (may already be ready since we started early)
            try:
                follow_up_questions = await asyncio.wait_for(asyncio.shield(follow_ups_task), timeout=10.0)
                if follow_up_questions:
                    yield {
                        "event": "follow_ups",
                        "data": json.dumps({"questions": follow_up_questions}),
                    }
            except (asyncio.TimeoutError, Exception):
                # Non-fatal — frontend falls back to static suggestions
                pass

            # Emit document_generated when the query included a template_slug.
            # The document is created as a stub (empty fields) that the user
            # fills via the DocumentCard UI.  Non-fatal if creation fails.
            if body.template_slug and conversation_id:
                try:
                    doc_payload = await _create_pipeline_document(
                        template_slug=body.template_slug,
                        conversation_id=conversation_id,
                        user_id=user_id,
                    )
                    if doc_payload is not None:
                        yield {
                            "event": "document_generated",
                            "data": json.dumps(doc_payload),
                        }
                except Exception:
                    logger.exception(
                        "Pipeline document creation failed for template_slug=%s conversation=%s",
                        body.template_slug,
                        conversation_id,
                    )

        except Exception as exc:
            logger.exception("SSE post-processing error: %s", exc)
            if pipeline_job_id:
                t = asyncio.create_task(
                    fail_pipeline_job(
                        pipeline_job_id,
                        status="failed",
                        detail="An internal error occurred. Please try again.",
                    ),
                )
                t.add_done_callback(_log_task_exception)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Failed to format response", "detail": "An internal error occurred. Please try again."},
                ),
            }
            return

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator(), ping=15)


@router.get("/corpora")
async def list_corpora(
    key_row: dict = Depends(get_api_key),
) -> dict[str, list]:
    """Return the list of searchable custom corpora for the authenticated user.

    Groups documents by collection name (stored in .meta files) so the frontend
    can show selectable pills per collection with their doc_ids for filtering.
    """
    from collections import defaultdict
    from pathlib import Path

    from arlc.retriever import get_chunk_count

    client_slug = key_row["client_slug"]
    chunk_count = get_chunk_count(corpus=client_slug)

    logger.info("[corpora] client_slug=%s, chunk_count=%d", client_slug, chunk_count)
    corpora: list[dict] = []
    if chunk_count > 0:
        docs_dir = Path(settings.data_dir) / "clients" / client_slug / "docs"
        if docs_dir.exists():
            # Group documents by collection name
            collections: dict[str, list[str]] = defaultdict(list)
            for meta_path in sorted(docs_dir.glob("*.meta")):
                try:
                    meta = json.loads(meta_path.read_text())
                    doc_id = meta.get("doc_id", "")
                    collection_name = meta.get("collection", "My Documents")
                    if doc_id:
                        collections[collection_name].append(doc_id)
                except Exception:
                    pass

            for name, doc_ids in collections.items():
                corpora.append(
                    {
                        "name": name,
                        "corpus_id": client_slug,
                        "doc_ids": doc_ids,
                        "doc_count": len(doc_ids),
                        "indexed": True,
                    },
                )

        # Fallback: no .meta files but chunks exist — show single entry
        if not corpora:
            corpora.append(
                {
                    "name": "My Documents",
                    "corpus_id": client_slug,
                    "indexed": True,
                },
            )

    return {"corpora": corpora}


_LAWS_BY_CORPUS: dict[str, list[dict[str, str]]] = {
    "czech": [
        {"id": "obcansky_zakonik", "name": "Občanský zákoník", "name_en": "Civil Code"},
        {"id": "trestni_zakonik", "name": "Trestní zákoník", "name_en": "Criminal Code"},
        {"id": "zakonik_prace", "name": "Zákoník práce", "name_en": "Labour Code"},
        {"id": "zakon_obch_korporace", "name": "Zákon o obch. korporacích", "name_en": "Business Corporations Act"},
        {"id": "spravni_rad", "name": "Správní řád", "name_en": "Administrative Procedure Code"},
        {"id": "zivnostensky_zakon", "name": "Živnostenský zákon", "name_en": "Trade Licensing Act"},
        {"id": "zakon_duchodove_pojisteni", "name": "Zákon o důch. pojištění", "name_en": "Pension Insurance Act"},
        {"id": "zakon_dph", "name": "Zákon o DPH", "name_en": "VAT Act"},
        {"id": "zakon_dane_prijmu", "name": "Zákon o daních z příjmů", "name_en": "Income Tax Act"},
        {"id": "zakon_nemocenske_pojisteni", "name": "Zákon o nem. pojištění", "name_en": "Sickness Insurance Act"},
        {"id": "danovy_rad", "name": "Daňový řád", "name_en": "Tax Procedure Code"},
    ],
    "uk": [
        {"id": "companies_act_2006", "name": "Companies Act 2006", "name_en": "Companies Act 2006"},
        {
            "id": "employment_rights_act_1996",
            "name": "Employment Rights Act 1996",
            "name_en": "Employment Rights Act 1996",
        },
        {"id": "consumer_rights_act_2015", "name": "Consumer Rights Act 2015", "name_en": "Consumer Rights Act 2015"},
        {"id": "equality_act_2010", "name": "Equality Act 2010", "name_en": "Equality Act 2010"},
        {"id": "data_protection_act_2018", "name": "Data Protection Act 2018", "name_en": "Data Protection Act 2018"},
        {"id": "insolvency_act_1986", "name": "Insolvency Act 1986", "name_en": "Insolvency Act 1986"},
        {
            "id": "financial_services_markets_act_2000",
            "name": "FSMA 2000",
            "name_en": "Financial Services and Markets Act 2000",
        },
        {"id": "limitation_act_1980", "name": "Limitation Act 1980", "name_en": "Limitation Act 1980"},
        {"id": "arbitration_act_1996", "name": "Arbitration Act 1996", "name_en": "Arbitration Act 1996"},
        {"id": "human_rights_act_1998", "name": "Human Rights Act 1998", "name_en": "Human Rights Act 1998"},
        {"id": "bribery_act_2010", "name": "Bribery Act 2010", "name_en": "Bribery Act 2010"},
        {"id": "modern_slavery_act_2015", "name": "Modern Slavery Act 2015", "name_en": "Modern Slavery Act 2015"},
        {"id": "competition_act_1998", "name": "Competition Act 1998", "name_en": "Competition Act 1998"},
        {"id": "partnership_act_1890", "name": "Partnership Act 1890", "name_en": "Partnership Act 1890"},
        {"id": "sale_of_goods_act_1979", "name": "Sale of Goods Act 1979", "name_en": "Sale of Goods Act 1979"},
    ],
    "au": [
        {"id": "corporations_act_2001", "name": "Corporations Act 2001", "name_en": "Corporations Act 2001"},
        {
            "id": "competition_consumer_act_2010",
            "name": "Competition and Consumer Act 2010",
            "name_en": "Competition and Consumer Act 2010",
        },
        {"id": "fair_work_act_2009", "name": "Fair Work Act 2009", "name_en": "Fair Work Act 2009"},
        {"id": "privacy_act_1988", "name": "Privacy Act 1988", "name_en": "Privacy Act 1988"},
        {"id": "bankruptcy_act_1966", "name": "Bankruptcy Act 1966", "name_en": "Bankruptcy Act 1966"},
        {
            "id": "insurance_contracts_act_1984",
            "name": "Insurance Contracts Act 1984",
            "name_en": "Insurance Contracts Act 1984",
        },
        {
            "id": "asic_act_2001",
            "name": "ASIC Act 2001",
            "name_en": "Australian Securities and Investments Commission Act 2001",
        },
        {
            "id": "superannuation_supervision_act_1993",
            "name": "Superannuation (SIS) Act 1993",
            "name_en": "Superannuation Industry (Supervision) Act 1993",
        },
        {
            "id": "telecommunications_act_1997",
            "name": "Telecommunications Act 1997",
            "name_en": "Telecommunications Act 1997",
        },
        {
            "id": "epbc_act_1999",
            "name": "EPBC Act 1999",
            "name_en": "Environment Protection and Biodiversity Conservation Act 1999",
        },
        {"id": "migration_act_1958", "name": "Migration Act 1958", "name_en": "Migration Act 1958"},
        {
            "id": "income_tax_assessment_act_1997",
            "name": "Income Tax Assessment Act 1997",
            "name_en": "Income Tax Assessment Act 1997",
        },
        {
            "id": "aml_ctf_act_2006",
            "name": "AML/CTF Act 2006",
            "name_en": "Anti-Money Laundering and Counter-Terrorism Financing Act 2006",
        },
        {"id": "whs_act_2011", "name": "Work Health and Safety Act 2011", "name_en": "Work Health and Safety Act 2011"},
        {
            "id": "consumer_credit_act_2009",
            "name": "Consumer Credit Act 2009",
            "name_en": "National Consumer Credit Protection Act 2009",
        },
    ],
}


@router.get("/laws")
async def list_laws(corpus: str = "czech") -> dict[str, list]:
    """Return the available law corpus entries for the law selector UI."""
    laws = _LAWS_BY_CORPUS.get(corpus, [])
    return {"laws": laws}


@router.get("/conversations/{conversation_id}/last-answer")
async def get_last_answer(
    conversation_id: str = Path(pattern=r"^[a-zA-Z0-9_-]{1,64}$"),
    key_row: dict = Depends(get_api_key),
) -> dict[str, str]:
    """Return the last assistant message for a conversation, if it exists.

    Used by the frontend to recover answers after SSE connection drops.
    The backend saves completed answers to PostgreSQL even when SSE breaks.
    """
    from neolex.services.conversation import load_history

    user_id = key_row["user_id"]
    history = await load_history(user_id, conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail="No history found")
    # Find last assistant message
    last_assistant = None
    for msg in reversed(history):
        if msg["role"] == "assistant":
            last_assistant = msg
            break
    if not last_assistant:
        raise HTTPException(status_code=404, detail="No answer found")
    return {"answer": last_assistant["content"]}


@router.get("/conversations/{conversation_id}/status")
async def get_pipeline_status(
    conversation_id: str = Path(pattern=r"^[a-zA-Z0-9_-]{1,64}$"),
    key_row: dict = Depends(get_api_key),
) -> dict:
    """Return the latest pipeline job status for a conversation.

    Used by the frontend to poll for pipeline progress after SSE connection
    drops (page reload, chat switch, network interruption). The pipeline
    continues in the background and updates status in the pipeline_jobs table.

    Returns:
    - 200 with status object (processing/searching/answering/complete/failed/timeout)
    - 404 if no pipeline job found for this conversation
    """
    from neolex.services.conversation import get_pipeline_job_status

    user_id = key_row["user_id"]
    result = await get_pipeline_job_status(user_id, conversation_id)
    if not result:
        raise HTTPException(status_code=404, detail="No pipeline job found")
    return result


@router.get("/conversations")
async def list_conversations(
    key_row: dict = Depends(get_api_key),
) -> dict[str, list]:
    """Return the authenticated user's recent conversations.

    Each entry contains:
    - id: the conversation UUID (string)
    - title: first user message, truncated to 80 chars
    - last_message_at: ISO timestamp of the most recent message
    - message_count: total messages in the conversation
    """
    from neolex.services.conversation import list_user_conversations

    user_id = key_row["user_id"]
    return {"conversations": await list_user_conversations(user_id)}


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str = Path(pattern=r"^[a-zA-Z0-9_-]{1,64}$"),
    key_row: dict = Depends(get_api_key),
) -> None:
    """Delete all messages and docs for a conversation owned by the authenticated user."""
    from neolex.services.conversation import delete_conversation as do_delete

    user_id = key_row["user_id"]
    deleted = await do_delete(user_id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str = Path(pattern=r"^[a-zA-Z0-9_-]{1,64}$"),
    key_row: dict = Depends(get_api_key),
) -> dict[str, list]:
    """Return all messages for a specific conversation.

    Used by the frontend to hydrate a conversation that exists in the backend
    but is missing from localStorage (e.g. after logout/login or TTL expiry).
    """
    from neolex.services.conversation import load_full_conversation

    user_id = key_row["user_id"]
    messages = await load_full_conversation(user_id, conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found")
    return {"messages": messages}
