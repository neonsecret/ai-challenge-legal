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
    laws: list[str] | None = Field(default=None, max_length=20)
    # Optional list of document IDs to restrict retrieval to specific uploaded documents.
    # Used when the user selects individual documents in a custom corpus instead of "All".
    doc_ids: list[str] | None = Field(default=None, max_length=50)
    # Optional custom corpus collection ID. Format: "{client_slug}:{collection_name}".
    # When set, the server resolves doc_ids from the collection's .meta files,
    # overriding any manually provided doc_ids.
    corpora_id: str | None = Field(default=None, max_length=128, pattern=r"^[a-zA-Z0-9_.@: -]{1,128}$")

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

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        pattern = re.compile(r"^[a-zA-Z0-9_.@-]{1,128}$")
        for doc_id in v:
            if not pattern.match(doc_id):
                raise ValueError(f"Invalid doc ID: {doc_id!r}")
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
    # Drafting mode: when set, the agent is told to draft a legal document using
    # this template.  The server fetches template metadata from DB and injects it
    # into the agent prompt.  Ignored when use_agent=False.
    template_slug: str | None = Field(
        default=None,
        max_length=128,
        pattern=r"^[a-z0-9_]*$",
        description="Template slug for drafting mode; activates document_draft tool",
    )


class SourceCitation(BaseModel):
    doc_id: str
    page_numbers: list[int]
    text: str | None = None  # source text for non-PDF corpora (Czech)
    url: str | None = None  # web source URL
    title: str | None = None  # web source title
    chunk_id: str | None = None
    # Court decision metadata — only present when source_type == "court_decision"
    source_type: str | None = None  # "statute" | "court_decision" | "txt"
    case_number: str | None = None  # e.g. "21 Cdo 1234/2023"
    decision_date: str | None = None  # ISO date e.g. "2023-06-15"
    court: str | None = None  # e.g. "Nejvyssi soud"
    category: str | None = None  # A-E
    ecli: str | None = None  # ECLI identifier
    legal_thesis: str | None = None  # pravni veta
    # TXT-source line range — only present when source_type == "txt"
    start_line: int | None = None
    end_line: int | None = None


class QueryResponse(BaseModel):
    answer: Any  # bool | int | float | str | list | None — do NOT coerce
    sources: list[SourceCitation]
    confidence: str  # "high" | "degraded" | "not_found"
    latency_ms: int
    model_name: str
    trace_id: str | None = None  # Langfuse trace ID; None when tracing is disabled


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
            chunk_id=cp.get("chunk_id"),
            source_type=cp.get("source_type"),
            case_number=cp.get("case_number"),
            decision_date=cp.get("decision_date"),
            court=cp.get("court"),
            category=cp.get("category"),
            ecli=cp.get("ecli"),
            legal_thesis=cp.get("legal_thesis"),
            start_line=cp.get("start_line"),
            end_line=cp.get("end_line"),
        )
        for cp in result.get("chunk_pages", [])
    ]
    raw_answer = result.get("answer")
    # Strip <analysis>...</analysis> and <answer>...</answer> XML wrappers
    # the LLM may produce. Keep only the content inside <answer> if present.
    answer = raw_answer
    if isinstance(raw_answer, str):
        # Extract <answer> content if present
        answer_match = re.search(r"<answer>(.*?)$", raw_answer, re.DOTALL)
        if answer_match:
            answer = answer_match.group(1)
            # Strip closing tag if present
            answer = re.sub(r"</answer>\s*$", "", answer)
        # Remove any remaining <analysis>...</analysis> blocks
        answer = re.sub(r"<analysis>.*?</analysis>", "", answer, flags=re.DOTALL)
        # Clean up leftover tags
        answer = re.sub(r"</?(?:analysis|answer)>", "", answer)
        answer = answer.strip() or raw_answer  # fallback to raw if stripping emptied it
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
        trace_id=result.get("trace_id") or None,
    )
