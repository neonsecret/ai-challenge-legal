import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException

from neolex.schemas.query import QueryRequest, QueryResponse, pipeline_dict_to_response
from neolex.services.pipeline import run_single_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest) -> QueryResponse:
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

    return pipeline_dict_to_response(result)
