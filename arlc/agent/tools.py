"""Search tool for the LangGraph legal research agent.

Thin wrapper around the competition-proven ``retrieve_pages()`` pipeline.
All retrieval logic (tsvector full-text, pgvector ANN, HyDE, RRF fusion,
cross-encoder reranking, article-to-page mapping, cross-reference boosting)
lives in ``arlc.retriever`` — this module just adapts it for the agent:

  1. Runs the router to identify target documents (DIFC only).
  2. Calls ``retrieve_pages()`` with exclusion of already-seen docs.
  3. Converts ``PageResult`` objects to ``SourceDocument`` dicts.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from arlc.agent.config import SEARCH_ANSWER_TYPE, SEARCH_MAX_PER_DOC, SEARCH_TOP_K, WEB_SEARCH_MAX_RESULTS
from arlc.agent.state import SourceDocument

logger = logging.getLogger(__name__)


def execute_search(
    query: str,
    corpus: str,
    law_filters: list[str] | None,
    exclude_doc_pages: set[tuple[str, int]],
    target_new: int = SEARCH_TOP_K,
    on_status: Callable[[str], None] | None = None,
    cached_target_docs: list[str] | None = None,
    doc_ids: list[str] | None = None,
) -> list[SourceDocument]:
    """Search the legal corpus, always returning fresh results.

    Delegates to the full competition pipeline (``retrieve_pages``) which
    handles tsvector + pgvector + HyDE fusion, cross-encoder reranking,
    article mapping, and cross-reference boosting.  Already-seen documents are
    excluded at the retrieval level so every call is guaranteed to return
    new sources (unless the corpus is exhausted).

    For DIFC, the router is run first to identify target documents.
    For other corpora (Czech, custom), retrieval is corpus-wide.

    Parameters
    ----------
    cached_target_docs:
        If provided, skip the router call and use these target doc IDs
        directly.  **Not currently used by the graph** — the DIFC router
        extracts case IDs, law names, and article references from the
        ``query`` text via regex, and the query changes per agent iteration
        (the LLM rewrites search queries).  Caching the first router
        result would miss entities referenced only in later queries,
        producing incorrect routing.  This parameter is reserved for future
        use if the router is ever refactored to separate entity extraction
        from the query string (e.g., routing based on the original user
        question only).
    """
    from arlc.retriever import PageResult, retrieve_pages

    # DIFC: run the deterministic router for targeted retrieval.
    # NOTE on caching: the router uses regex extraction on the query string
    # to find case IDs (e.g. "CFI 057/2025"), law names ("Employment Law"),
    # and article references ("Article 14").  Since the LLM generates
    # different query strings per search iteration, different queries will
    # match different entities — caching the first result would miss
    # entities mentioned only in later queries.  We therefore always run
    # the router fresh.  If cached_target_docs is provided, it is used
    # as-is (the caller is responsible for correctness).
    target_docs = cached_target_docs
    if target_docs is None and corpus == "difc":
        try:
            from arlc.router import route
            route_result = route(query, SEARCH_ANSWER_TYPE)
            target_docs = getattr(route_result, "target_doc_ids", None) or None
            if target_docs:
                logger.info("[search] router found %d target docs: %s",
                           len(target_docs), target_docs[:3])
        except Exception:
            logger.warning("[search] router failed, falling back to corpus-wide search")

    # UK/AU: extract citations for logging (retrieval is corpus-wide via pgvector)
    if corpus in ("uk", "au"):
        try:
            if corpus == "uk":
                from arlc.router import extract_uk_citations
                cites = extract_uk_citations(query)
            else:
                from arlc.router import extract_au_citations
                cites = extract_au_citations(query)
            if cites:
                logger.info("[search] %s citations extracted: %s", corpus.upper(), cites[:5])
        except Exception:
            pass  # citation extraction is best-effort

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
        doc_ids=doc_ids,
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
            _corpus=corpus,
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


_BLOCKED_DOMAINS = {
    "instagram.com", "facebook.com", "twitter.com", "x.com", "tiktok.com",
    "linkedin.com", "youtube.com", "reddit.com", "pinterest.com",
    "t.me", "telegram.org", "vk.com", "ok.ru",
}


def _is_useful_result(r: dict) -> bool:
    """Return False for social media, empty results, or clearly irrelevant pages."""
    url = r.get("href", "") or r.get("url", "")
    snippet = r.get("body", "") or r.get("snippet", "")

    if not url or not snippet:
        return False

    from urllib.parse import urlparse
    try:
        domain = urlparse(url).netloc.lstrip("www.")
    except Exception:
        return False

    # Block social media
    if any(domain == bd or domain.endswith("." + bd) for bd in _BLOCKED_DOMAINS):
        return False

    # Require at least 50 chars of snippet content
    if len(snippet.strip()) < 50:
        return False

    return True


def execute_web_search(query: str, max_results: int = WEB_SEARCH_MAX_RESULTS) -> list[dict]:
    """Search the web via DuckDuckGo. Returns list of {title, url, snippet}.

    Uses the ``ddgs`` package (successor to ``duckduckgo_search``).
    Filters out social media profiles, empty results, and other noise.
    """
    try:
        from ddgs import DDGS
        # Fetch more than needed to account for filtered-out results
        fetch_count = max_results * 3
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=fetch_count))
        useful = [r for r in raw if _is_useful_result(r)]
        results = useful[:max_results]
        logger.info("[web-search] fetched %d, kept %d after filtering", len(raw), len(results))
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in results
        ]
    except Exception as e:
        logger.warning("[web-search] failed: %s", e)
        return []


_WEB_SNIPPET_MAX_CHARS = 500


def format_web_results(results: list[dict]) -> str:
    """Format web search results for the LLM context.

    Snippets are truncated to 500 chars to limit context usage and wrapped
    in <web_content> tags to prevent prompt injection from web sources.
    """
    if not results:
        return "No web results found."

    def _esc(s: str) -> str:
        return s.replace("</web_content>", "&lt;/web_content&gt;")

    parts = []
    for r in results:
        snippet = (r['snippet'] or "")[:_WEB_SNIPPET_MAX_CHARS]
        # Escape closing tags in ALL fields to prevent prompt injection
        title = _esc(r.get('title', '') or '')
        url = _esc(r.get('url', '') or '')
        snippet = _esc(snippet)
        parts.append(f"[WEB: \"{title}\"]({url})\n{snippet}")
    return "<web_content>\n" + "\n---\n".join(parts) + "\n</web_content>"


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
