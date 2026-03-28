from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(..., min_length=5, max_length=2000)
    answer_type: str = Field(
        default="free_text",
        pattern=r"^(boolean|number|name|names|date|free_text)$",
    )
    corpus: str = Field(default="difc", pattern=r"^(difc|czech)$")
    # Opaque session pointer — server loads history from DB using user_id+conversation_id.
    # Client never sends history content; only this UUID-like key.
    conversation_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_-]{1,64}$",
    )


class SourceCitation(BaseModel):
    doc_id: str
    page_numbers: list[int]
    text: str | None = None  # source text for non-PDF corpora (Czech)


class QueryResponse(BaseModel):
    answer: Any  # bool | int | float | str | list | None — do NOT coerce
    sources: list[SourceCitation]
    confidence: str  # "high" | "degraded" | "not_found"
    latency_ms: int
    model_name: str


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    request_id: str = ""


def pipeline_dict_to_response(result: dict) -> QueryResponse:
    """Convert _process_question output dict to QueryResponse.

    Confidence logic:
    - "not_found": answer is None (pipeline found no relevant info)
    - "degraded": model_name is "error" or "timeout" (pipeline fallback path)
    - "high": everything else
    """
    sources = [
        SourceCitation(
            doc_id=cp["doc_id"],
            page_numbers=cp.get("page_numbers", []),
            text=cp.get("text"),
        )
        for cp in result.get("chunk_pages", [])
    ]
    answer = result.get("answer")
    model_name = result.get("model_name", "unknown")
    if answer is None:
        confidence = "not_found"
    elif model_name in ("error", "timeout"):
        confidence = "degraded"
    else:
        confidence = "high"

    return QueryResponse(
        answer=answer,
        sources=sources,
        confidence=confidence,
        latency_ms=int(result.get("total_time_ms", 0)),
        model_name=model_name,
    )
