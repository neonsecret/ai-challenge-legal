"""Structural tools for the LangGraph legal research agent.

These tools give the agent direct database access to the corpus structure:
  - get_article: fetch a specific article/section/paragraph by number
  - list_laws: list all laws available in a given corpus
  - list_cases: list DIFC court cases matching a party name or case number

Unlike search_legal_corpus (semantic retrieval), these are deterministic
lookups — they find exact structural elements without embedding similarity.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arlc.agent.state import SourceDocument

logger = logging.getLogger(__name__)


def _escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcards so user input is treated as literal."""
    return value.replace("%", "\\%").replace("_", "\\_")


# Czech doc_id prefix → human-readable name (mirrors graph.py mapping)
_CZECH_LAW_NAMES: dict[str, str] = {
    "obcansky_zakonik": "Občanský zákoník (89/2012 Sb.)",
    "trestni_zakonik": "Trestní zákoník (40/2009 Sb.)",
    "zakonik_prace": "Zákoník práce (262/2006 Sb.)",
    "zakon_obch_korporace": "Zákon o obchodních korporacích (90/2012 Sb.)",
    "spravni_rad": "Správní řád (500/2004 Sb.)",
    "zivnostensky_zakon": "Živnostenský zákon (455/1991 Sb.)",
    "zakon_duchodove_pojisteni": "Zákon o důchodovém pojištění (155/1995 Sb.)",
    "zakon_dph": "Zákon o DPH (235/2004 Sb.)",
    "zakon_dane_prijmu": "Zákon o daních z příjmů (586/1992 Sb.)",
    "zakon_nemocenske_pojisteni": "Zákon o nemocenském pojištění (187/2006 Sb.)",
    "danovy_rad": "Daňový řád (280/2009 Sb.)",
}

# Article/section patterns per corpus family
_ARTICLE_RE_DIFC = re.compile(
    r"Article\s+(\d+)(?:\((\d+)\))?(?:\(([a-z])\))?",
    re.IGNORECASE,
)
_SECTION_RE_UK_AU = re.compile(
    r"(?:Section|s\.?)\s+(\d+[A-Z]?)(?:\((\d+)\))?",
    re.IGNORECASE,
)
_PARAGRAPH_RE_CZ = re.compile(
    r"§\s*(\d+[a-z]?)(?:\s+odst\.\s*(\d+))?",
)


async def execute_get_article(
    law_id: str,
    article: str,
    corpus: str,
) -> list[SourceDocument]:
    """Fetch chunks matching a specific article/section/paragraph.

    Uses POSIX regex against chunk text for Czech/DIFC, and metadata_extra
    section field for UK/AU (where section numbers live in structured metadata).

    Returns chunks as SourceDocument dicts, ordered by page number.
    """
    from sqlalchemy import or_, select

    from neolex.db.chunks import Chunk
    from neolex.db.postgres import AsyncSessionLocal as async_session

    base_law_id = re.sub(r"_\d{5}$", "", law_id)

    article_pattern = _build_article_pattern(article, corpus)
    if not article_pattern:
        logger.warning("[structural] could not build pattern for article=%r corpus=%s", article, corpus)
        return []

    async with async_session() as session:
        if corpus == "czech":
            doc_id_filter = Chunk.doc_id.like(f"{base_law_id}_%")
        else:
            doc_id_filter = Chunk.doc_id == base_law_id

        # Text-based regex match (works for Czech/DIFC)
        text_match = Chunk.text.op("~*")(article_pattern)

        # UK/AU: also match via metadata_extra['section'] field
        if corpus in ("uk", "au"):
            cleaned = article.strip().lstrip("Section ").lstrip("s. ").lstrip("s ")
            m = re.match(r"(\d+[A-Za-z]?)", cleaned)
            section_num = m.group(1) if m else cleaned
            meta_match = Chunk.metadata_extra["section"].astext.op("~*")(
                rf"^Section\s+{re.escape(section_num)}([^0-9A-Za-z]|$)"
            )
            content_filter = or_(text_match, meta_match)
        else:
            content_filter = text_match

        stmt = (
            select(Chunk)
            .where(
                Chunk.corpus == corpus,
                Chunk.tenant_id.is_(None),
                doc_id_filter,
                content_filter,
            )
            .order_by(Chunk.page)
            .limit(5)
        )
        result = await session.execute(stmt)
        chunks = result.scalars().all()

    if not chunks:
        logger.info(
            "[structural] get_article: no match for law=%s article=%s corpus=%s pattern=%s",
            law_id,
            article,
            corpus,
            article_pattern,
        )
        return []

    docs: list[SourceDocument] = []
    for c in chunks:
        from arlc.agent.state import SourceDocument as SD

        docs.append(
            SD(
                doc_id=c.doc_id,
                page=c.page,
                text=c.text,
                score=1.0,
                chunk_id=c.chunk_id,
                _corpus=corpus,
            )
        )

    logger.info(
        "[structural] get_article: law=%s article=%s → %d chunks",
        law_id,
        article,
        len(docs),
    )
    return docs


def _build_article_pattern(article: str, corpus: str) -> str | None:
    """Build a POSIX regex pattern for Postgres matching the section definition.

    Postgres uses POSIX extended regex — no \\b word boundary. We use newline
    anchors instead: ``(^|\\n)§ 52[^0-9a-z]`` matches the section header at the
    start of a line, avoiding cross-references embedded in running text.
    """
    cleaned = article.strip().lstrip("§ ")

    if corpus == "czech":
        # Czech chunks open with "[law_id] ...\n§ 52\n..."
        # Avoid matching cross-references like "viz § 521" or "§ 52a odst."
        m = re.match(r"(\d+)([a-z]?)", cleaned)
        if not m:
            return None
        num, suffix = m.group(1), m.group(2)
        if suffix:
            # Exact suffix match (e.g. § 52a): no trailing digit allowed
            return rf"(^|\n)§\s*{re.escape(num + suffix)}([^0-9a-z]|$)"
        # No suffix: must not be followed by a digit or lowercase letter
        return rf"(^|\n)§\s*{re.escape(num)}([^0-9a-z]|$)"

    if corpus == "difc":
        # DIFC chunks: "Article 14\n..." or numbered items "14. Title"
        m = re.match(r"(\d+)", cleaned)
        if not m:
            return None
        num = m.group(1)
        return rf"(^|\n)(Article\s+{re.escape(num)}[^0-9]|{re.escape(num)}\.\s)"

    if corpus in ("uk", "au"):
        # UK/AU: "Section 52\n..." or "52A.\n"
        m = re.match(r"(\d+[A-Za-z]?)", cleaned)
        if not m:
            return None
        num = m.group(1)
        return rf"(^|\n)(Section\s+{re.escape(num)}[^0-9A-Za-z]|{re.escape(num)}\.\s)"

    return None


async def execute_list_laws(corpus: str) -> list[dict[str, str]]:
    """List all distinct laws/statutes in a corpus with chunk counts.

    Queries the chunks table for distinct doc_ids, groups by base law name
    (stripping Czech chunk suffixes), and returns human-readable names.
    """
    from sqlalchemy import func, select

    from neolex.db.chunks import Chunk
    from neolex.db.postgres import AsyncSessionLocal as async_session

    async with async_session() as session:
        if corpus == "czech":
            # Group by base doc_id (strip _NNNNN suffix)
            base_expr = func.regexp_replace(Chunk.doc_id, r"_\d+$", "")
            stmt = (
                select(
                    base_expr.label("base_id"),
                    func.count().label("chunk_count"),
                )
                .where(
                    Chunk.corpus == corpus,
                    Chunk.tenant_id.is_(None),
                )
                .group_by(base_expr)
                .order_by(base_expr)
            )
        else:
            stmt = (
                select(
                    Chunk.doc_id.label("base_id"),
                    func.count().label("chunk_count"),
                )
                .where(
                    Chunk.corpus == corpus,
                    Chunk.tenant_id.is_(None),
                )
                .group_by(Chunk.doc_id)
                .order_by(Chunk.doc_id)
            )

        if corpus == "difc":
            # Only include laws, not judgments
            stmt = stmt.where(
                Chunk.metadata_extra["doc_type"].astext == "law",
            )

        result = await session.execute(stmt)
        rows = result.all()

    laws = []
    for row in rows:
        base_id = row.base_id
        human_name = _get_human_name(base_id, corpus)
        laws.append(
            {
                "id": base_id,
                "name": human_name,
                "chunk_count": row.chunk_count,
            }
        )

    logger.info("[structural] list_laws: corpus=%s → %d laws", corpus, len(laws))
    return laws


def _get_human_name(doc_id: str, corpus: str) -> str:
    """Convert a doc_id to a human-readable law name."""
    if corpus == "czech":
        return _CZECH_LAW_NAMES.get(doc_id, doc_id.replace("_", " ").title())

    if corpus == "difc":
        # DIFC law doc_ids: "employment_law_difc_law_no_2_of_2019"
        name = doc_id.replace("_", " ").title()
        # Capitalize common acronyms
        name = re.sub(r"\bDifc\b", "DIFC", name)
        name = re.sub(r"\bLlc\b", "LLC", name)
        return name

    # UK/AU: "companies_act_2006" → "Companies Act 2006"
    return doc_id.replace("_", " ").title()


async def execute_list_cases(
    corpus: str,
    party_name: str = "",
    case_number: str = "",
    limit: int = 20,
) -> list[dict[str, str]]:
    """List court cases in the corpus matching optional filters.

    For DIFC: queries chunks with doc_type='judgment', filters by party name
    in the doc_id (which contains party names in DIFC).

    For Czech: queries the court_decisions table with BM25 on party/case number.
    """
    if corpus == "czech":
        return await _list_czech_cases(party_name=party_name, case_number=case_number, limit=limit)
    if corpus == "difc":
        return await _list_difc_cases(party_name=party_name, case_number=case_number, limit=limit)

    # UK/AU don't have case law in the corpus
    return []


async def _list_difc_cases(
    party_name: str = "",
    case_number: str = "",
    limit: int = 20,
) -> list[dict[str, str]]:
    """List DIFC court judgments, optionally filtered by party name or case number."""
    from sqlalchemy import func, select

    from neolex.db.chunks import Chunk
    from neolex.db.postgres import AsyncSessionLocal as async_session

    async with async_session() as session:
        stmt = (
            select(
                Chunk.doc_id,
                func.count().label("chunk_count"),
                func.min(Chunk.page).label("first_page"),
            )
            .where(
                Chunk.corpus == "difc",
                Chunk.tenant_id.is_(None),
                Chunk.metadata_extra["doc_type"].astext == "judgment",
            )
            .group_by(Chunk.doc_id)
            .order_by(Chunk.doc_id)
            .limit(limit)
        )

        if party_name:
            # DIFC doc_ids contain party names separated by hyphens
            # Convert search term to lowercase hyphenated form
            normalized = _escape_like(party_name.lower().replace(" ", "-"))
            stmt = stmt.where(Chunk.doc_id.ilike(f"%{normalized}%"))

        if case_number:
            # Case numbers like "CFI-057-2025" or "CA-004-2021"
            normalized_cn = _escape_like(case_number.lower().replace("/", "-").replace(" ", "-"))
            stmt = stmt.where(Chunk.doc_id.ilike(f"%{normalized_cn}%"))

        result = await session.execute(stmt)
        rows = result.all()

    cases = []
    for row in rows:
        # Extract a readable case name from the doc_id
        readable = _difc_doc_id_to_name(row.doc_id)
        cases.append(
            {
                "doc_id": row.doc_id,
                "name": readable,
                "chunk_count": row.chunk_count,
            }
        )

    logger.info(
        "[structural] list_difc_cases: party=%r case_num=%r → %d results",
        party_name,
        case_number,
        len(cases),
    )
    return cases


def _difc_doc_id_to_name(doc_id: str) -> str:
    """Convert a DIFC judgment doc_id to a readable case name.

    Example: "1-al-ahli-bank-v-essar-global-2021-difc-cfi-001"
    → "Al Ahli Bank v Essar Global (2021 DIFC CFI 001)"
    """
    # Extract year and court reference at the end
    m = re.search(r"(\d{4})-difc-(cfi|ca|sct|arb)-(\d+)(?:-\d+)?$", doc_id)
    court_ref = ""
    name_part = doc_id
    if m:
        year, court, num = m.group(1), m.group(2).upper(), m.group(3)
        court_ref = f" ({year} DIFC {court} {num})"
        name_part = doc_id[: m.start()]

    # Strip leading number prefix (e.g., "1-")
    name_part = re.sub(r"^\d+-", "", name_part)

    # Convert hyphens to spaces, title-case
    words = name_part.replace("-", " ").split()
    titled = []
    skip_words = {"v", "vs", "and", "of", "the", "in", "for", "on", "a", "an"}
    for i, w in enumerate(words):
        if i == 0 or w.lower() not in skip_words:
            titled.append(w.capitalize())
        else:
            titled.append(w.lower())

    name = " ".join(titled)
    # Restore "v" as separator
    name = re.sub(r"\bV\b", "v", name)
    return name + court_ref


async def _list_czech_cases(
    party_name: str = "",
    case_number: str = "",
    limit: int = 20,
) -> list[dict[str, str]]:
    """List Czech Supreme Court decisions, optionally filtered."""
    from sqlalchemy import func, select

    from neolex.db.court_decisions import CourtDecision
    from neolex.db.postgres import AsyncSessionLocal as async_session

    async with async_session() as session:
        stmt = (
            select(
                CourtDecision.ecli,
                CourtDecision.case_number,
                CourtDecision.court,
                CourtDecision.decision_date,
                CourtDecision.decision_type,
                CourtDecision.category,
                func.left(CourtDecision.legal_thesis, 200).label("thesis_preview"),
            )
            .order_by(CourtDecision.decision_date.desc())
            .limit(limit)
        )

        if case_number:
            escaped_cn = _escape_like(case_number)
            stmt = stmt.where(CourtDecision.case_number.ilike(f"%{escaped_cn}%"))

        if party_name:
            # Search in full_text or legal_thesis for party name
            query_tsv = func.plainto_tsquery("simple", party_name)
            stmt = stmt.where(CourtDecision.search_vector.op("@@")(query_tsv))

        result = await session.execute(stmt)
        rows = result.all()

    cases = []
    for row in rows:
        cases.append(
            {
                "ecli": row.ecli,
                "case_number": row.case_number or "",
                "court": row.court or "",
                "date": str(row.decision_date) if row.decision_date else "",
                "type": row.decision_type or "",
                "category": row.category or "",
                "thesis_preview": row.thesis_preview or "",
            }
        )

    logger.info(
        "[structural] list_czech_cases: party=%r case_num=%r → %d results",
        party_name,
        case_number,
        len(cases),
    )
    return cases


def format_get_article_results(
    docs: list[SourceDocument],
    law_id: str,
    article: str,
    offset: int = 0,
) -> str:
    """Format get_article results for the LLM context."""
    if not docs:
        return f"Article/section {article} not found in {law_id}."

    parts = []
    for i, doc in enumerate(docs):
        idx = offset + i + 1
        header = f"[DOC-{idx}] {doc['doc_id']} (page {doc['page']})"
        text = re.sub(r"</document_content>", "&lt;/document_content&gt;", doc["text"], flags=re.IGNORECASE)
        parts.append(f"{header}\n<document_content>\n{text}\n</document_content>")
    return "\n---\n".join(parts)


def format_list_laws_results(laws: list[dict[str, str]], corpus: str) -> str:
    """Format list_laws results for the LLM context."""
    if not laws:
        return f"No laws found in the {corpus} corpus."

    lines = [f"Laws available in the {corpus.upper()} corpus ({len(laws)} total):\n"]
    for law in laws:
        count = law.get("chunk_count", "?")
        lines.append(f"- {law['id']}: {law['name']} ({count} chunks)")
    return "\n".join(lines)


def format_list_cases_results(cases: list[dict[str, str]], corpus: str) -> str:
    """Format list_cases results for the LLM context."""
    if not cases:
        return f"No cases found in the {corpus} corpus matching the criteria."

    if corpus == "czech":
        lines = [f"Czech Supreme Court decisions ({len(cases)} results):\n"]
        for c in cases:
            date_str = f" ({c['date']})" if c.get("date") else ""
            cat = f" [{c['category']}]" if c.get("category") else ""
            thesis = f" — {c['thesis_preview']}..." if c.get("thesis_preview") else ""
            lines.append(f"- {c['case_number']}{date_str}{cat}: ECLI {c['ecli']}{thesis}")
        return "\n".join(lines)

    # DIFC
    lines = [f"DIFC court cases ({len(cases)} results):\n"]
    for c in cases:
        lines.append(f"- {c['name']} (doc_id: {c['doc_id']}, {c.get('chunk_count', '?')} chunks)")
    return "\n".join(lines)
