"""Search tool for the LangGraph legal research agent.

Thin wrapper around the competition-proven ``retrieve_pages()`` pipeline.
All retrieval logic (BM25, FAISS, HyDE, RRF fusion, cross-encoder reranking,
article-to-page mapping, cross-reference boosting) lives in ``arlc.retriever``
— this module just adapts it for the agent's needs:

  1. Runs the router to identify target documents (DIFC only).
  2. Calls ``retrieve_pages()`` with exclusion of already-seen docs.
  3. Converts ``PageResult`` objects to ``SourceDocument`` dicts.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from arlc.agent.config import SEARCH_ANSWER_TYPE, SEARCH_MAX_PER_DOC, SEARCH_TOP_K
from arlc.agent.state import SourceDocument

logger = logging.getLogger(__name__)


def execute_search(
    query: str,
    corpus: str,
    law_filters: list[str] | None,
    exclude_doc_pages: set[tuple[str, int]],
    target_new: int = SEARCH_TOP_K,
    on_status: Callable[[str], None] | None = None,
) -> list[SourceDocument]:
    """Search the legal corpus, always returning fresh results.

    Delegates to the full competition pipeline (``retrieve_pages``) which
    handles BM25 + FAISS + HyDE fusion, cross-encoder reranking, article
    mapping, and cross-reference boosting.  Already-seen documents are
    excluded at the retrieval level so every call is guaranteed to return
    new sources (unless the corpus is exhausted).

    For DIFC, the router is run first to identify target documents.
    For other corpora (Czech, custom), retrieval is corpus-wide.
    """
    from arlc.retriever import retrieve_pages, PageResult

    # DIFC: run the deterministic router for targeted retrieval
    target_docs = None
    if corpus == "difc":
        try:
            from arlc.router import route
            route_result = route(query, SEARCH_ANSWER_TYPE)
            target_docs = getattr(route_result, "target_doc_ids", None) or None
            if target_docs:
                logger.info("[search] router found %d target docs: %s",
                           len(target_docs), target_docs[:3])
        except Exception:
            logger.warning("[search] router failed, falling back to corpus-wide search")

    # Request more than we need to account for exclusions
    fetch_total = target_new + len(exclude_doc_pages)

    pages: list[PageResult] = retrieve_pages(
        question=query,
        target_doc_ids=target_docs,
        max_per_doc=SEARCH_MAX_PER_DOC,
        max_total=fetch_total,
        answer_type=SEARCH_ANSWER_TYPE,
        corpus=corpus,
        on_status=on_status,
        laws=law_filters,
    )

    # Filter out already-seen docs and take top_k new
    new_pages = [
        p for p in pages
        if (p.doc_id, p.page_number) not in exclude_doc_pages
    ][:target_new]

    logger.info("[search] query=\"%s\" corpus=%s → %d/%d pages (excluded %d seen)",
               query[:60], corpus, len(new_pages), len(pages),
               len(pages) - len(new_pages))

    return [
        SourceDocument(
            doc_id=p.doc_id,
            page=p.page_number,
            text=p.text or "",
            score=p.score,
        )
        for p in new_pages
    ]


def format_search_results(docs: list[SourceDocument], offset: int = 0) -> str:
    """Format search results as numbered document blocks for the LLM."""
    if not docs:
        return "No new documents found for this query."
    parts = []
    for i, doc in enumerate(docs):
        idx = offset + i + 1
        parts.append(f"[DOC-{idx}] {doc['doc_id']} (page {doc['page']})\n{doc['text']}")
    return "\n---\n".join(parts)


def verify_source_relevance(
    answer: str, docs: list[SourceDocument]
) -> list[SourceDocument]:
    """Flag sources with low keyword overlap against the answer.

    Informational only — does not remove sources, just adds a 'verified'
    field.  Helps the frontend indicate source quality.
    """
    answer_words = set(answer.lower().split())
    for doc in docs:
        doc_words = set(doc.get("text", "").lower().split())
        overlap = len(answer_words & doc_words) / max(len(answer_words), 1)
        doc["verified"] = overlap > 0.05
    return docs
