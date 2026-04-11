"""Agent state schema for the LangGraph legal research agent.

Mirrors the existing PageResult dataclass from arlc.retriever but uses
TypedDict so it serialises cleanly through LangGraph's state channels.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, NotRequired, Required, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SourceDocument(TypedDict, total=False):
    """A single retrieved legal document chunk.

    Kept intentionally flat (no nested objects) so it round-trips through
    JSON serialisation without custom encoders.

    Attributes
    ----------
    doc_id : str
        Canonical document identifier (e.g. "DIFC_LAW_001" or an ECLI).
    page : int
        1-indexed page number within the source PDF.
    text : str
        Raw chunk text (up to ~7500 chars per the project chunking strategy).
    score : float
        Relevance score from the reranker (higher is better).
    verified : bool
        Whether the source passed keyword-overlap relevance check against the
        answer.  Set by ``verify_source_relevance()`` — optional, absent until
        verification runs.
    source_type : str
        ``"statute"`` for statute corpus chunks (default, backward-compatible),
        ``"court_decision"`` for Czech Supreme Court decisions.
    case_number : str
        Case number for court decisions, e.g. "21 Cdo 1234/2023".
    decision_date : str
        ISO date string for court decisions, e.g. "2023-06-15".
    court : str
        Court name for court decisions, e.g. "Nejvyssi soud".
    category : str
        Decision category A-E for court decisions.
    legal_thesis : str
        Pravni veta (key legal principle) for court decisions.
    ecli : str
        ECLI identifier for court decisions.
    """

    doc_id: Required[str]
    page: Required[int]
    text: Required[str]
    score: Required[float]
    chunk_id: str
    verified: bool
    _corpus: str  # which corpus this doc came from (for cross-corpus filtering)
    # Court decision metadata — NotRequired for backward compatibility
    source_type: NotRequired[str]  # "statute" | "court_decision"
    case_number: NotRequired[str]  # "21 Cdo 1234/2023"
    decision_date: NotRequired[str]  # ISO date e.g. "2023-06-15"
    court: NotRequired[str]  # "Nejvyssi soud"
    category: NotRequired[str]  # "A" through "E"
    legal_thesis: NotRequired[str]  # pravni veta
    ecli: NotRequired[str]  # ECLI identifier


class AgentState(TypedDict):
    """Full state for the legal research agent.

    The ``messages`` field uses LangGraph's ``add_messages`` reducer so new
    messages are *appended* rather than replacing the list.  All other fields
    use last-write-wins semantics.

    Attributes
    ----------
    messages : list[BaseMessage]
        LangChain message objects (system, human, AI, tool).
    accumulated_docs : list[SourceDocument]
        Documents gathered across search iterations in this turn.
        Capped at 10 to fit comfortably in the context window.
    corpus : str
        Active corpus identifier: ``"difc"``, ``"czech"``, or a custom slug
        scoped to a PostgreSQL corpus partition.
    selected_laws : list[str]
        Optional law-filter prefixes (e.g. ``["DIFC_LAW_001"]``).
        Empty list means search the full corpus.
    search_count : int
        Number of search tool invocations in this agent turn.
        Hard-capped at 5 to prevent infinite loops.
    user_id : str
        For audit logging.
    conversation_id : str
        For conversation persistence / session tracking.
    cached_target_docs : list[str] | None
        Router-identified target document IDs from the first search call.
        Reserved for future use — currently NOT populated because the DIFC
        router is query-dependent (it extracts case IDs, law names, and
        article numbers from the search query text, which changes per LLM
        iteration).  If the router is ever refactored to use only the
        original user question, this field enables skipping redundant
        router calls on subsequent searches within the same agent turn.
    _on_status : Callable[[str], None] | None
        Per-request status callback.  Passed through state (not a graph
        channel) so the search_node can emit SSE status events.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    accumulated_docs: list[SourceDocument]
    corpus: str
    selected_laws: list[str]
    search_count: int
    user_id: str
    conversation_id: str
    web_sources: NotRequired[list[dict]]
    use_internet: NotRequired[bool]
    cached_target_docs: NotRequired[list[str] | None]
    doc_ids: NotRequired[list[str] | None]
    _on_status: NotRequired[Callable[[str], None] | None]
    _on_document: NotRequired[Callable[[dict], None] | None]
    # --- Drafting mode (injected when template_slug is present in the request) ---
    # When template_slug is set the agent operates in drafting mode: it searches
    # the corpus to ground legal content, then calls document_draft to persist the
    # filled-in document.  All drafting state is NotRequired so existing code
    # that builds AgentState without these fields continues to work unchanged.
    template_slug: NotRequired[str | None]  # e.g. "cz_zaloba_obecna"
    template_name: NotRequired[str]  # human-readable e.g. "Obecná žaloba"
    template_required_fields: NotRequired[list[str]]  # fields LLM must NOT invent
    template_field_descriptions: NotRequired[dict[str, str]]  # field hints for prompt
    chat_documents: NotRequired[list[dict]]  # existing docs [{id, template_slug, fields, version}]
    _draft_document_fn: NotRequired[Callable | None]  # async (action, fields, doc_id) -> dict
