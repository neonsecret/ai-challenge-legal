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
        Canonical document identifier (e.g. "DIFC_LAW_001").
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
    """

    doc_id: Required[str]
    page: Required[int]
    text: Required[str]
    score: Required[float]
    verified: bool
    _corpus: str  # which corpus this doc came from (for cross-corpus filtering)


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
        matching a ``data/faiss_{corpus}.bin`` index.
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
    _on_status: NotRequired[Callable[[str], None] | None]
