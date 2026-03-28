import asyncio
import json
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from neolex.auth.middleware import get_api_key
from neolex.db.audit import get_audit_db
from neolex.schemas.query import QueryRequest, QueryResponse, pipeline_dict_to_response
from neolex.services.pipeline import run_single_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.post("/query", response_model=QueryResponse)
async def query(
        request: Request,
        body: QueryRequest,
        corpus: Annotated[str, Query(pattern=r"^(difc|czech)$")] = "difc",
        key_row: dict = Depends(get_api_key),
) -> QueryResponse:
    """Submit a legal question and receive a grounded JSON answer with source citations.

    Returns 503 if pipeline is not ready (still warming up).
    Returns 500 if pipeline raises an unexpected exception.
    Returns 422 if request body fails Pydantic validation.
    """
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
            detail={"error": "Pipeline failed", "detail": str(exc)},
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
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(
            status_code=503,
            detail={"error": "Service unavailable", "detail": "Pipeline is still warming up."},
        )

    state = request.app.state
    user_id = key_row["user_id"]
    conversation_id = body.conversation_id
    corpus = body.corpus

    async def event_generator():
        # Unified queue for status, token, and done events.
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def on_status(stage: str):
            queue.put_nowait(("status", stage))

        def on_token(text: str):
            # Called from asyncio.to_thread — must be thread-safe.
            loop.call_soon_threadsafe(queue.put_nowait, ("token", text))

        # Emit initial connection status
        yield {"event": "status", "data": json.dumps({"status": "processing"})}
        await asyncio.sleep(0)

        # Run pipeline as a concurrent task so we can yield status events while it runs
        pipeline_result: dict = {}
        pipeline_error: BaseException | None = None

        async def _run_pipeline():
            nonlocal pipeline_result, pipeline_error
            try:
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
                )
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
            task.cancel()
            logger.info("SSE client disconnected during pipeline execution")
            return

        # Handle pipeline errors
        if isinstance(pipeline_error, asyncio.CancelledError):
            logger.info("SSE pipeline cancelled")
            return
        if pipeline_error is not None:
            logger.exception("SSE pipeline error: %s", pipeline_error)
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
                asyncio.create_task(save_turn(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    question=body.question,
                    answer=str(response.answer),
                ))

            yield {"event": "answer", "data": response.model_dump_json()}
        except Exception as exc:
            logger.exception("SSE post-processing error: %s", exc)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Failed to format response", "detail": "An internal error occurred. Please try again."}),
            }
            return

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator(), ping=15)
