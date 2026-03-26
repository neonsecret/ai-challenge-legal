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

    Events emitted in order:
    1. status  {"status": "processing"}         -- immediately on connection
    2. answer  {QueryResponse JSON}              -- when pipeline completes
    3. done    {}                                -- signals end of stream

    Use with EventSource JS API:
        const es = new EventSource('/api/v1/query/stream?question=...')
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
        # Emit status immediately so the client knows the connection is open
        # and the server received the request. This prevents client-side timeout
        # during the 3-15 second pipeline execution.
        yield {"event": "status", "data": json.dumps({"status": "processing"})}

        # asyncio.sleep(0) is a cancellation checkpoint — yields control back to
        # the event loop so the SSE framework can flush the status event to the
        # client before we block on the pipeline call.
        await asyncio.sleep(0)

        try:
            result = await run_single_question(
                question=question,
                answer_type=answer_type,
                semaphore=state.semaphore,
                route_fn=state.route_fn,
                retrieve_fn=state.retrieve_fn,
                answer_fn=state.answer_fn,
            )
            response = pipeline_dict_to_response(result)
            sources_json = json.dumps([s.model_dump() for s in response.sources])
            async with get_audit_db() as db:
                await db.log_query(
                    key_hash=key_row["key_hash"],
                    question=question,
                    answer_text=response.answer,
                    sources_json=sources_json,
                    latency_ms=result.get("total_time_ms", 0),
                    model_name=response.model_name,
                    ip=getattr(request.client, "host", None),
                    user_agent=request.headers.get("user-agent"),
                )
            yield {"event": "answer", "data": response.model_dump_json()}
        except asyncio.CancelledError:
            # Client disconnected — generator is cancelled. Just return;
            # do not yield anything further. The pipeline coroutine is already
            # cancelled because run_single_question propagates cancellation.
            logger.info("SSE client disconnected during pipeline execution")
            return
        except Exception as exc:
            logger.exception("SSE pipeline error: %s", exc)
            yield {
                "event": "error",
                "data": json.dumps({"error": "Pipeline failed", "detail": str(exc)}),
            }
            return

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator(), ping=15)
