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


@router.get("/query/stream")
async def query_stream(
    request: Request,
    question: Annotated[str, Query(min_length=5, max_length=2000)],
    answer_type: Annotated[str, Query(pattern=r"^(boolean|number|name|names|date|free_text)$")] = "free_text",
    key_row: dict = Depends(get_api_key),
):
    """Stream a legal query response as Server-Sent Events.

    Events emitted in real time as the pipeline progresses:
    1. status  {"status": "routing"}            -- document routing started
    2. status  {"status": "retrieving"}         -- hybrid retrieval started
    3. status  {"status": "answering:N"}        -- LLM generation started (N source pages)
    4. answer  {QueryResponse JSON}             -- pipeline completed
    5. done    {}                               -- signals end of stream

    Use with EventSource JS API:
        const es = new EventSource('/api/v1/query/stream?question=...')
        es.addEventListener('status', e => console.log(JSON.parse(e.data)))
        es.addEventListener('answer', e => console.log(JSON.parse(e.data)))
        es.addEventListener('done', () => es.close())
    """
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(
            status_code=503,
            detail={"error": "Service unavailable", "detail": "Pipeline is still warming up."},
        )

    state = request.app.state

    async def event_generator():
        # Queue-based real-time status: pipeline pushes stage transitions,
        # SSE generator yields them as they arrive.
        status_queue: asyncio.Queue = asyncio.Queue()

        def on_status(stage: str):
            """Called from the event loop between awaits in _process_question."""
            status_queue.put_nowait(("status", stage))

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
                    question=question,
                    answer_type=answer_type,
                    semaphore=state.semaphore,
                    route_fn=state.route_fn,
                    retrieve_fn=state.retrieve_fn,
                    answer_fn=state.answer_fn,
                    on_status=on_status,
                )
            except BaseException as exc:
                pipeline_error = exc
            finally:
                # Signal completion to the SSE loop
                status_queue.put_nowait(("done", None))

        task = asyncio.create_task(_run_pipeline())

        try:
            # Yield status events in real time as pipeline progresses
            while True:
                event_type, data = await status_queue.get()
                if event_type == "status":
                    yield {"event": "status", "data": json.dumps({"status": data})}
                    await asyncio.sleep(0)  # flush
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
                "data": json.dumps({"error": "Pipeline failed", "detail": str(pipeline_error)}),
            }
            return

        # Emit answer + audit log
        try:
            response = pipeline_dict_to_response(pipeline_result)
            sources_json = json.dumps([s.model_dump() for s in response.sources])
            async with get_audit_db() as db:
                await db.log_query(
                    key_hash=key_row["key_hash"],
                    question=question,
                    answer_text=response.answer,
                    sources_json=sources_json,
                    latency_ms=pipeline_result.get("total_time_ms", 0),
                    model_name=response.model_name,
                    ip=getattr(request.client, "host", None),
                    user_agent=request.headers.get("user-agent"),
                )
            yield {"event": "answer", "data": response.model_dump_json()}
        except Exception as exc:
            logger.exception("SSE post-processing error: %s", exc)
            yield {
                "event": "error",
                "data": json.dumps({"error": "Failed to format response", "detail": str(exc)}),
            }
            return

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator(), ping=15)


@router.get("/auth/verify")
async def verify_key(
    key_row: Annotated[dict, Depends(get_api_key)],
):
    """Lightweight key verification endpoint.

    Returns 200 if the key is valid, 401 if not.
    Use this to validate a key without triggering any pipeline or SSE logic.
    The key is passed via Authorization: Bearer header (not query param),
    so it never appears in URL logs.
    """
    return {"valid": True, "scope": key_row.get("scope"), "client": key_row.get("client_slug")}
