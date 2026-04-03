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

Format helpers produce plain-numbered summaries (for search) and [DOC-N] document
blocks (for fetch) consistent with the existing citation mechanism.  Search
results deliberately avoid [CASE-N] bracket labels to prevent the LLM from
using them as citation tags in final answers.
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

    limit is clamped to [1, 30] to prevent excessive DB load from LLM-controlled params.

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

    limit = max(1, min(limit, 30))
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
    """Format case law search results as plain numbered summaries for the LLM.

    Deliberately avoids bracket labels (e.g. [CASE-N]) to prevent the LLM
    from treating search-result indices as citation tags.  Promoted documents
    are added as [DOC-N] blocks in the same tool response and should be cited
    via those labels only.

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

        # Plain "Case N:" prefix — not a citation tag, just a search result index
        header = f"Case {i}: {case_num}"
        if dec_date or category:
            meta = ", ".join(filter(None, [dec_date, f"kategorie {category}" if category else ""]))
            header += f" ({meta})"

        lines = [header]
        if thesis:
            # Truncate long thesis — 1000 chars to preserve critical caveats
            # and section references that often appear near the end
            thesis_preview = thesis[:1000] + ("..." if len(thesis) > 1000 else "")
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
    import re

    from neolex.db.court_decisions import get_decision_by_ecli, upsert_decision

    if not ecli or not re.match(r"^(ECLI:CZ:NS:|NSOUD:)[A-Za-z0-9.:_-]+$", ecli):
        logger.warning("[caselaw] invalid ECLI format: %s", ecli)
        return None

    record = await get_decision_by_ecli(ecli)
    if not record:
        logger.warning("[caselaw] ECLI not found: %s", ecli)
        return None

    # If full text not cached, fetch from nsoud.cz
    if not record.full_text_fetched and record.source_unid:
        try:
            import httpx

            from scripts.scrape_supreme_court import _HEADERS, fetch_decision

            _MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
            async with httpx.AsyncClient(
                headers=_HEADERS, timeout=30, follow_redirects=True, max_redirects=3
            ) as client:
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

    # CRITICAL: legal_thesis = "Právní věta" = the Supreme Court's authoritative holding.
    # full_text = "Anotace" = case summary that may include LOWER COURT reasoning
    # which the Supreme Court OVERTURNED.  The agent must see the legal_thesis as
    # the primary content, with Anotace as supplementary context only.
    thesis = record.legal_thesis or ""
    anotace = record.full_text or ""

    # Assemble text: thesis first (authoritative), then Anotace (supplementary).
    # The formatters (format_caselaw_full, _format_document_context) add their own
    # labels, but the raw text field should also be structured so any code path
    # that reads doc["text"] gets the thesis first.
    text_parts: list[str] = []
    if thesis:
        text_parts.append(thesis)
    if anotace and anotace != thesis:
        text_parts.append(anotace)
    combined_text = "\n\n---\n\n".join(text_parts) if text_parts else ""

    if len(combined_text) > _FULL_TEXT_MAX_CHARS:
        # Truncate the Anotace portion, never the thesis
        if thesis and anotace and anotace != thesis:
            remaining = _FULL_TEXT_MAX_CHARS - len(thesis) - len("\n\n---\n\n")
            if remaining > 200:
                combined_text = thesis + "\n\n---\n\n" + anotace[:remaining]
            else:
                # Not enough room for Anotace — thesis alone
                combined_text = thesis
        else:
            combined_text = combined_text[:_FULL_TEXT_MAX_CHARS]

    return SourceDocument(
        doc_id=record.ecli or f"NSOUD:{record.source_unid}",
        page=1,
        text=combined_text,
        score=1.0,
        chunk_id=record.source_unid or "",
        _corpus="czech",
        source_type="court_decision",
        case_number=record.case_number or "",
        decision_date=decision_date_str,
        court=record.court or "Nejvyssi soud",
        category=record.category or "",
        legal_thesis=thesis,
        ecli=record.ecli or "",
    )


def format_caselaw_full(doc: SourceDocument, doc_index: int) -> str:
    """Format a fetched court decision as a [DOC-N] document block for the LLM.

    Uses the same ``<document_content>`` tag wrapping as statute sources to
    maintain consistent citation mechanics and prevent prompt injection.

    Structure inside <document_content>:
    1. TYPE label ("ROZHODNUTÍ NEJVYŠŠÍHO SOUDU ČR") so the agent knows this
       is a court decision, not a statute.
    2. PRÁVNÍ VĚTA (legal thesis) — the Supreme Court's authoritative holding.
       This is the part the agent should cite and quote from.
    3. ANOTACE (case summary) — supplementary context that may describe lower
       court proceedings the Supreme Court reviewed or overturned.  The agent
       must NOT cite section numbers from this section as the court's holding.

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
    ecli = doc.get("ecli", doc.get("doc_id", ""))

    header_parts = [case_num, court]
    if dec_date:
        header_parts.append(dec_date)
    if category:
        header_parts.append(f"kat. {category}")
    header = " | ".join(filter(None, header_parts))

    # Escape closing tags to prevent prompt injection via tag boundary escape
    def _esc(s: str) -> str:
        return s.replace("</document_content>", "&lt;/document_content&gt;")

    # Build structured content: type label → legal thesis → full reasoning
    content_parts: list[str] = []
    content_parts.append(f"TYP: ROZHODNUTÍ NEJVYŠŠÍHO SOUDU ČR — {case_num}")
    if ecli and ecli.startswith("ECLI:"):
        content_parts.append(f"ECLI: {ecli}")

    thesis = doc.get("legal_thesis", "")
    raw_text = doc.get("text", "")

    # raw_text may contain "thesis\n\n---\n\nanotace" from execute_caselaw_fetch.
    # Extract the Anotace portion (everything after the separator) if present.
    anotace = ""
    if raw_text and thesis and "\n\n---\n\n" in raw_text:
        parts_split = raw_text.split("\n\n---\n\n", 1)
        anotace = parts_split[1] if len(parts_split) > 1 else ""
    elif raw_text and raw_text != thesis:
        anotace = raw_text

    if thesis:
        content_parts.append(f"\nPRÁVNÍ VĚTA (závazný právní závěr NS ČR — citujte z této části):\n{_esc(thesis)}")

    if anotace:
        content_parts.append(
            f"\nANOTACE (shrnutí případu — může obsahovat názory nižších soudů, "
            f"které NS zrušil; NECITUJTE § z této části jako závěr NS):\n{_esc(anotace)}"
        )
    elif raw_text and not thesis:
        content_parts.append(f"\nTEXT ROZHODNUTÍ:\n{_esc(raw_text)}")

    content = "\n".join(content_parts)

    return f"[DOC-{doc_index}] {header}\n<document_content>\n{content}\n</document_content>"
