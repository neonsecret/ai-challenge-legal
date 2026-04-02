"""Agent tool implementations for Czech Supreme Court case law search.

Provides two tools for the LangGraph agent:
- ``execute_caselaw_search``: hybrid BM25 + vector search over court_decisions table
- ``execute_caselaw_fetch``: fetch full Anotace text for a specific ECLI

Search strategy:
- Primary: hybrid RRF(BM25=0.4, vector=0.6) when embeddings are available
- Graceful fallback: BM25-only when llama-server is unavailable or embeddings absent
- The vector leg is skipped if ``embed_query`` raises (offline llama-server),
  so the agent always gets results even without the embedding service.

These are the *execution* functions; the @tool schema-only wrappers live in
graph.py alongside the existing ``search_legal_corpus`` schema.

Format helpers produce [CASE-N] summaries (for search) and [DOC-N] document
blocks (for fetch) consistent with the existing citation mechanism.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from arlc.agent.state import SourceDocument

logger = logging.getLogger(__name__)

# Maximum characters of full text to include when fetch returns a document
_FULL_TEXT_MAX_CHARS = 12_000


def _parse_statute_ref(statute_reference: str) -> tuple[int, int] | None:
    """Parse 'law_number/law_year' or 'law_number/law_year § paragraph' into tuple.

    Parameters
    ----------
    statute_reference : str
        E.g. ``"262/2006"`` or ``"262/2006 § 52"``

    Returns
    -------
    (law_number, law_year) | None
    """
    if not statute_reference:
        return None
    m = re.match(r"(\d{1,4})/(\d{4})", statute_reference.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _parse_date_arg(value: str) -> date | None:
    """Parse ISO date string '2023-01-01' → date, or return None."""
    if not value:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value.strip())
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


async def execute_caselaw_search(
    query: str,
    statute_reference: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 10,
) -> list[SourceDocument]:
    """Search court_decisions with hybrid BM25 + vector (RRF) and return SourceDocuments.

    Search strategy:
    1. Try to embed the query with Qwen3-8B (via llama-server)
    2. If embedding succeeds: run hybrid search (BM25 + vector RRF)
    3. If embedding fails (llama-server offline): fall back to BM25-only

    Parameters
    ----------
    query : str
        Czech language search terms.
    statute_reference : str
        Optional statute filter, e.g. ``"262/2006"`` for the Labour Code.
    date_from, date_to : str
        Optional ISO date range, e.g. ``"2020-01-01"``.
    limit : int
        Max results.

    Returns
    -------
    list[SourceDocument]
        Each entry has ``source_type="court_decision"`` plus case metadata fields.
    """
    import asyncio

    from neolex.db.court_decisions import search_decisions, search_decisions_hybrid

    statute_ref = _parse_statute_ref(statute_reference)
    df = _parse_date_arg(date_from)
    dt = _parse_date_arg(date_to)

    try:
        # Attempt to get query embedding for the vector leg (runs in thread pool
        # since embed_query is synchronous HTTP to llama-server).
        query_emb = None
        if query and query.strip():
            try:
                from arlc.retriever import embed_query

                query_emb = await asyncio.to_thread(embed_query, query)
            except Exception as emb_exc:
                logger.info("[caselaw] embed_query unavailable, falling back to BM25: %s", emb_exc)

        if query_emb is not None:
            decisions = await search_decisions_hybrid(
                query=query,
                query_embedding=query_emb,
                statute_ref=statute_ref,
                date_from=df,
                date_to=dt,
                limit=limit,
            )
            logger.info("[caselaw] hybrid search query=%r → %d results", query[:60], len(decisions))
        else:
            decisions = await search_decisions(
                query=query,
                statute_ref=statute_ref,
                date_from=df,
                date_to=dt,
                limit=limit,
            )
            logger.info("[caselaw] bm25-only search query=%r → %d results", query[:60], len(decisions))
    except Exception as exc:
        logger.error("[caselaw] search failed: %s", exc)
        return []

    results: list[SourceDocument] = []
    for d in decisions:
        decision_date_str = d.decision_date.isoformat() if d.decision_date else ""
        results.append(
            SourceDocument(
                doc_id=d.ecli or f"NSOUD:{d.source_unid}",
                page=1,
                text=d.legal_thesis or "",
                score=float(d.score) if hasattr(d, "score") else 0.0,
                chunk_id=d.source_unid or "",
                _corpus="czech",
                source_type="court_decision",
                case_number=d.case_number or "",
                decision_date=decision_date_str,
                court=d.court or "Nejvyssi soud",
                category=d.category or "",
                legal_thesis=d.legal_thesis or "",
                ecli=d.ecli or "",
            )
        )

    return results


def format_caselaw_search_results(docs: list[SourceDocument]) -> str:
    """Format case law search results as [CASE-N] summaries for the LLM.

    Parameters
    ----------
    docs : list[SourceDocument]
        Court decision source documents from ``execute_caselaw_search``.

    Returns
    -------
    str
        Formatted text block with case summaries.
    """
    if not docs:
        return "No case law found for this query."

    parts = []
    for i, doc in enumerate(docs, start=1):
        case_num = doc.get("case_number", doc.get("doc_id", ""))
        dec_date = doc.get("decision_date", "")
        category = doc.get("category", "")
        thesis = doc.get("legal_thesis", doc.get("text", ""))
        ecli = doc.get("ecli", doc.get("doc_id", ""))

        # Format regulations citation if available — extract from text
        header = f"[CASE-{i}] {case_num}"
        if dec_date or category:
            meta = ", ".join(filter(None, [dec_date, f"kategorie {category}" if category else ""]))
            header += f" ({meta})"

        lines = [header]
        if thesis:
            # Truncate long thesis to keep context manageable
            thesis_preview = thesis[:500] + ("..." if len(thesis) > 500 else "")
            lines.append(f"Pravni veta: {thesis_preview}")
        if ecli and ecli.startswith("ECLI:"):
            lines.append(f"ECLI: {ecli}")

        parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


async def execute_caselaw_fetch(ecli: str) -> SourceDocument | None:
    """Fetch a specific court decision by ECLI, caching full text if needed.

    If the decision has ``full_text_fetched=False``, fetches from nsoud.cz,
    caches in DB, and returns the result.  Already-cached decisions are served
    directly from DB.

    Parameters
    ----------
    ecli : str
        ECLI identifier from search results.

    Returns
    -------
    SourceDocument | None
    """
    from neolex.db.court_decisions import get_decision_by_ecli, upsert_decision

    record = await get_decision_by_ecli(ecli)
    if not record:
        logger.warning("[caselaw] ECLI not found: %s", ecli)
        return None

    # If full text not cached, fetch from nsoud.cz
    if not record.full_text_fetched and record.source_unid:
        try:
            import httpx

            from scripts.scrape_supreme_court import _HEADERS, fetch_decision

            async with httpx.AsyncClient(headers=_HEADERS, timeout=30, follow_redirects=True) as client:
                enrichment = await fetch_decision(record.source_unid, client)

            if enrichment.get("full_text"):
                await upsert_decision(
                    {
                        "ecli": ecli,
                        "case_number": record.case_number,
                        "full_text": enrichment["full_text"],
                        "full_text_fetched": True,
                    }
                )
                # Reload from DB with updated full text
                record = await get_decision_by_ecli(ecli)
        except Exception as exc:
            logger.warning("[caselaw] fetch failed for %s: %s", ecli, exc)

    if not record:
        return None

    decision_date_str = record.decision_date.isoformat() if record.decision_date else ""
    full_text = record.full_text or record.legal_thesis or ""
    if len(full_text) > _FULL_TEXT_MAX_CHARS:
        full_text = full_text[:_FULL_TEXT_MAX_CHARS]

    return SourceDocument(
        doc_id=record.ecli or f"NSOUD:{record.source_unid}",
        page=1,
        text=full_text,
        score=1.0,
        chunk_id=record.source_unid or "",
        _corpus="czech",
        source_type="court_decision",
        case_number=record.case_number or "",
        decision_date=decision_date_str,
        court=record.court or "Nejvyssi soud",
        category=record.category or "",
        legal_thesis=record.legal_thesis or "",
        ecli=record.ecli or "",
    )


def format_caselaw_full(doc: SourceDocument, doc_index: int) -> str:
    """Format a fetched court decision as a [DOC-N] document block for the LLM.

    Uses the same ``<document_content>`` tag wrapping as statute sources to
    maintain consistent citation mechanics and prevent prompt injection.

    Parameters
    ----------
    doc : SourceDocument
        Court decision with full text in ``doc["text"]``.
    doc_index : int
        1-based document index (the N in [DOC-N]).

    Returns
    -------
    str
        Formatted document block.
    """
    case_num = doc.get("case_number", doc.get("doc_id", ""))
    court = doc.get("court", "Nejvyssi soud")
    dec_date = doc.get("decision_date", "")
    category = doc.get("category", "")

    header_parts = [case_num, court]
    if dec_date:
        header_parts.append(dec_date)
    if category:
        header_parts.append(f"kat. {category}")
    header = " | ".join(filter(None, header_parts))

    text = doc.get("text", "")
    # Escape closing tags to prevent prompt injection via tag boundary escape
    text = text.replace("</document_content>", "&lt;/document_content&gt;")

    return f"[DOC-{doc_index}] {header}\n<document_content>\n{text}\n</document_content>"
