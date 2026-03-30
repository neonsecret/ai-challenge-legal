import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from neolex.auth.middleware import get_api_key
from neolex.config import settings
from neolex.db.audit import get_audit_db
from neolex.db.models import User
from neolex.db.postgres import get_db
from neolex.schemas.query import QueryRequest, QueryResponse, pipeline_dict_to_response
from neolex.services.pipeline import run_single_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _log_task_exception(task: asyncio.Task) -> None:
    """Log exceptions from fire-and-forget background tasks."""
    if not task.cancelled() and task.exception():
        logger.error("Background task failed: %s", task.exception())


# ---------------------------------------------------------------------------
# Corpus access control
# ---------------------------------------------------------------------------

_BUILTIN_CORPORA: frozenset[str] = frozenset({"difc", "czech"})

# ---------------------------------------------------------------------------
# Plan-based query rate limiting
# ---------------------------------------------------------------------------

# Daily query limits per paid plan. A value of 0 means unlimited (enterprise).
# This sentinel is checked explicitly in _enforce_query_limit() below.
UNLIMITED_DAILY_QUERIES = 0

_PLAN_DAILY_LIMITS: dict[str, int] = {
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
    now = datetime.now(timezone.utc)

    # Whitelist: reject any unknown/canceled status
    if status not in _ACTIVE_STATUSES:
        raise HTTPException(status_code=402, detail="Active subscription required.")

    # Free / legacy trial: monthly limit (atomic increment)
    if status in ("free", "trial"):
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Reset if needed
        if user.monthly_queries_reset_at is None or user.monthly_queries_reset_at < month_start:
            await db.execute(
                sql_update(User).where(User.id == user.id).values(
                    monthly_queries_used=0, monthly_queries_reset_at=month_start
                )
            )
            await db.commit()
            await db.refresh(user)

        # Atomic increment with limit check
        result = await db.execute(
            sql_update(User)
            .where(User.id == user.id, User.monthly_queries_used < settings.free_monthly_limit)
            .values(monthly_queries_used=User.monthly_queries_used + 1)
            .returning(User.monthly_queries_used)
        )
        new_count = result.scalar_one_or_none()
        if new_count is None:
            raise HTTPException(
                status_code=429,
                detail=f"Free tier limit reached ({settings.free_monthly_limit} queries/month). Upgrade to Starter for 50/day.",
            )
        await db.commit()
        return

    # Paid plans: daily limit (UNLIMITED_DAILY_QUERIES means no cap)
    daily_limit = _PLAN_DAILY_LIMITS.get(status, 0)

    # Reset daily counter if before today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if user.daily_queries_reset_at is None or user.daily_queries_reset_at < today_start:
        await db.execute(
            sql_update(User).where(User.id == user.id).values(
                daily_queries_used=0, daily_queries_reset_at=today_start
            )
        )
        await db.commit()
        await db.refresh(user)

    if daily_limit == UNLIMITED_DAILY_QUERIES:
        # Unlimited plan (enterprise) — increment for tracking, no cap enforced
        user.daily_queries_used += 1
        await db.commit()
    elif daily_limit > 0:
        result = await db.execute(
            sql_update(User)
            .where(User.id == user.id, User.daily_queries_used < daily_limit)
            .values(daily_queries_used=User.daily_queries_used + 1)
            .returning(User.daily_queries_used)
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
    except asyncio.TimeoutError:
        logger.error("Pipeline timeout for question: %.80s", body.question)
        raise HTTPException(
            status_code=504,
            detail={"error": "Pipeline timeout", "detail": "Query exceeded time limit."},
        )
    except Exception as exc:
        logger.exception("Pipeline error for question: %.80s", body.question)
        raise HTTPException(
            status_code=500,
            detail={"error": "Pipeline failed", "detail": "An internal error occurred. Please try again."},
        )

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
        create_pipeline_job,
        update_pipeline_job_status,
        complete_pipeline_job,
        fail_pipeline_job,
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
                    lambda f: logger.error("Background task failed: %s", f.exception())
                    if not f.cancelled() and f.exception() else None
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
            _schedule_coroutine(update_pipeline_job_status(
                pipeline_job_id, status=coarse, status_detail=stage,
            ))

        def on_status(stage: str):
            _enqueue(("status", stage))
            _update_job_status_detail(stage)

        def on_token(text: str):
            _enqueue(("token", text))

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
                    from neolex.services.agent_pipeline import run_agent_question
                    from arlc.agent.config import AGENT_TIMEOUT_SECONDS

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
                            use_internet=body.use_internet,
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
                event_type, data = await queue.get()
                if event_type == "status":
                    yield {"event": "status", "data": json.dumps({"status": data})}
                    await asyncio.sleep(0)
                elif event_type == "token":
                    yield {"event": "token", "data": json.dumps({"text": data})}
                    await asyncio.sleep(0)
                elif event_type == "done":
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
                t = asyncio.create_task(fail_pipeline_job(
                    pipeline_job_id, status="timeout",
                    detail="Query exceeded time limit. Please try a simpler question.",
                ))
                t.add_done_callback(_log_task_exception)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Pipeline timeout", "detail": "Query exceeded time limit. Please try a simpler question."}),
            }
            return
        if pipeline_error is not None:
            logger.exception("SSE pipeline error: %s", pipeline_error)
            # Persist failure status for frontend polling recovery
            if pipeline_job_id:
                t = asyncio.create_task(fail_pipeline_job(
                    pipeline_job_id, status="failed",
                    detail="An internal error occurred. Please try again.",
                ))
                t.add_done_callback(_log_task_exception)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Pipeline failed", "detail": "An internal error occurred. Please try again."}),
            }
            return

        # Emit answer + audit log + save conversation turn
        try:
            response = pipeline_dict_to_response(pipeline_result)
            sources_json = json.dumps([s.model_dump() for s in response.sources])
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
                task = asyncio.create_task(save_turn(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    question=body.question,
                    answer=str(response.answer),
                ))
                task.add_done_callback(_log_task_exception)

            # Persist completion to pipeline_jobs for frontend polling recovery
            if pipeline_job_id:
                t = asyncio.create_task(complete_pipeline_job(
                    pipeline_job_id,
                    answer=str(response.answer) if response.answer is not None else "",
                    sources_json=sources_json,
                    confidence=response.confidence,
                ))
                t.add_done_callback(_log_task_exception)

            yield {"event": "answer", "data": response.model_dump_json()}
        except Exception as exc:
            logger.exception("SSE post-processing error: %s", exc)
            if pipeline_job_id:
                t = asyncio.create_task(fail_pipeline_job(
                    pipeline_job_id, status="failed",
                    detail="An internal error occurred. Please try again.",
                ))
                t.add_done_callback(_log_task_exception)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Failed to format response", "detail": "An internal error occurred. Please try again."}),
            }
            return

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator(), ping=15)


@router.get("/corpora")
async def list_corpora(
    key_row: dict = Depends(get_api_key),
):
    """Return the list of searchable custom corpora for the authenticated user.

    Checks for FAISS indexes under data/clients/{client_slug}/index/.
    Returns {"corpora": [{"name": "My Documents", "corpus_id": "<client_slug>", "indexed": true}]}
    """
    from pathlib import Path

    client_slug = key_row["client_slug"]
    index_dir = Path(settings.data_dir) / "clients" / client_slug / "index"
    faiss_path = index_dir / "faiss_index.bin"

    logger.info("[corpora] client_slug=%s, checking %s (exists=%s)", client_slug, faiss_path, faiss_path.exists())
    corpora: list[dict] = []
    if faiss_path.exists():
        # Count documents for display
        docs_dir = Path(settings.data_dir) / "clients" / client_slug / "docs"
        doc_count = len(list(docs_dir.glob("*.pdf"))) if docs_dir.exists() else 0
        corpora.append({
            "name": "My Documents",
            "corpus_id": client_slug,
            "doc_count": doc_count,
            "indexed": True,
        })

    return {"corpora": corpora}


@router.get("/laws")
async def list_laws():
    """Return the available Czech law corpus entries for the law selector UI."""
    return {"laws": [
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
    ]}


@router.get("/conversations/{conversation_id}/last-answer")
async def get_last_answer(
    conversation_id: str = Path(pattern=r"^[a-zA-Z0-9_-]{1,64}$"),
    key_row: dict = Depends(get_api_key),
):
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
):
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
):
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
):
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
):
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
