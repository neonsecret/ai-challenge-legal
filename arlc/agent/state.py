"""Agent state schema for the LangGraph legal research agent.

Mirrors the existing PageResult dataclass from arlc.retriever but uses
TypedDict so it serialises cleanly through LangGraph's state channels.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SourceDocument(TypedDict):
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
    """

    doc_id: str
    page: int
    text: str
    score: float


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
    """

    messages: Annotated[list[BaseMessage], add_messages]
    accumulated_docs: list[SourceDocument]
    corpus: str
    selected_laws: list[str]
    search_count: int
    user_id: str
    conversation_id: str
