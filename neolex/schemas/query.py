from __future__ import annotations
import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(..., min_length=5, max_length=2000)
    answer_type: str = Field(
        default="free_text",
        pattern=r"^(boolean|number|name|names|date|free_text)$",
    )
    corpus: str = Field(default="difc", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    # Optional list of Czech law prefixes to restrict retrieval to specific laws.
    # E.g. ["zakonik_prace", "obcansky_zakonik"]. Empty or None = all laws.
    laws: list[str] | None = Field(default=None)

    @field_validator("laws")
    @classmethod
    def validate_law_ids(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        pattern = re.compile(r"^[a-z0-9_]{1,64}$")
        for law_id in v:
            if not pattern.match(law_id):
                raise ValueError(f"Invalid law ID: {law_id!r}")
        return v
    # Opaque session pointer — server loads history from DB using user_id+conversation_id.
    # Client never sends history content; only this UUID-like key.
    conversation_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_-]{1,64}$",
    )
    # When True, route the question through the LangGraph agent instead of the
    # deterministic pipeline.  The SSE event protocol is identical — the frontend
    # does not need to know which path is active.
    use_agent: bool = Field(default=False)
    # When False, the agent will not use the web search tool.
    # The tool is still bound to the LLM (graph is a singleton), but the
    # search_node returns a "disabled" message instead of executing the search.
    use_internet: bool = Field(default=True, description="Enable web search tool for the LLM")


class SourceCitation(BaseModel):
    doc_id: str
    page_numbers: list[int]
    text: str | None = None  # source text for non-PDF corpora (Czech)
    url: str | None = None  # web source URL
    title: str | None = None  # web source title


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
            url=cp.get("url"),
            title=cp.get("title"),
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

    # Don't leak the real LLM model name to the frontend.
    # Use the internal model_name only for confidence logic above.
    public_model_name = "vitreon-legal"

    return QueryResponse(
        answer=answer,
        sources=sources,
        confidence=confidence,
        latency_ms=int(result.get("total_time_ms", 0)),
        model_name=public_model_name,
    )
