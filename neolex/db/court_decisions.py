"""Court decisions model — BM25 + vector hybrid search for Czech judikatura.

Stores Czech Supreme Court (Nejvyssi soud) decisions scraped from
rozhodnuti.nsoud.cz.  Full text is fetched on demand and cached.

Retrieval modes:
- BM25 only: ``search_decisions()`` — keyword match on legal_thesis, case_number, keywords
- Vector only: ``search_decisions_vector()`` — Qwen3-8B semantic similarity on legal_thesis
- Hybrid: ``search_decisions_hybrid()`` — RRF fusion of BM25 + vector (recommended)

The ``embedding`` column is nullable — rows without embeddings are excluded from
the vector leg but remain searchable via BM25.  This enables a clean migration:
add the column, backfill asynchronously, hybrid search improves as more rows gain
embeddings with no code change required.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta

import numpy as np
from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, Date, Index, String, Text, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.expression import bindparam

from neolex.db.postgres import AsyncSessionLocal, Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CourtDecision(Base):
    """Czech Supreme Court decision record.

    Attributes
    ----------
    id : UUID
        Primary key.
    ecli : str
        European Case Law Identifier, unique.
        E.g. "ECLI:CZ:NS:2023:21.CDO.1234.2023.1"
    case_number : str
        Formatted case number.  E.g. "21 Cdo 1234/2023"
    court : str
        Court name, defaults to "Nejvyssi soud".
    decision_date : date
        Date the decision was issued.
    decision_type : str
        "rozsudek" (judgment) or "usneseni" (resolution).
    category : str
        A–E, where A = landmark decision, E = routine.
    legal_thesis : str
        Pravni veta — the key legal principle established by the decision.
    judges : str
        Names of the presiding judges.
    full_text : str | None
        Full reasoning text, fetched on demand and cached.
    full_text_fetched : bool
        Whether full_text has been fetched from nsoud.cz.
    source_url : str
        Direct URL to the decision on nsoud.cz.
    source_unid : str
        IBM Domino UNID for targeted full-text fetching.
    regulations : list[dict]
        Statute references extracted from legal_thesis.
        Schema: ``[{"paragraph": "52", "law_number": 262, "law_year": 2006}]``
    keywords : list[str]
        Keywords / classification tags from nsoud.cz.
    search_vector : tsvector
        GIN-indexed, auto-populated by DB trigger from
        ``legal_thesis || case_number || keywords``.
    embedding : Vector(4096) | None
        Qwen3-8B embedding of legal_thesis for semantic search.
        Nullable — rows without embeddings are excluded from the vector search
        leg but remain fully searchable via BM25.
        No HNSW index: 4096 dims exceeds pgvector's 2000-dim HNSW limit;
        exact scan at ~50K rows ≈ 150ms (acceptable for this corpus size).
    created_at, updated_at : datetime
        Audit timestamps.
    """

    __tablename__ = "court_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ecli: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    case_number: Mapped[str] = mapped_column(Text, nullable=False)
    court: Mapped[str] = mapped_column(Text, nullable=False, default="Nejvyssi soud", server_default="Nejvyssi soud")
    decision_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    decision_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(4), nullable=True)
    legal_thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    judges: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_fetched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_unid: Mapped[str | None] = mapped_column(Text, nullable=True)
    regulations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    search_vector = mapped_column(TSVECTOR, nullable=True)
    embedding = mapped_column(Vector(4096), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index("court_decisions_search_fts", "search_vector", postgresql_using="gin"),
        Index("court_decisions_regulations", "regulations", postgresql_using="gin"),
        # Descending BTree index for date-ordered queries (most recent first)
        Index("court_decisions_date_desc", text("decision_date DESC")),
        Index("court_decisions_category", "category"),
        # No HNSW on embedding: pgvector HNSW max is 2000 dims, our embeddings are
        # 4096-dim.  Exact scan at ~50K rows ≈ 150ms — no index needed.
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _recency_cutoff() -> date:
    """Date object for the 3-year recency cutoff."""
    return (datetime.now(UTC) - timedelta(days=3 * 365)).date()


def _normalize(vec: list[float]) -> list[float]:
    """L2-normalize a float vector in place, return normalized list."""
    arr = np.array(vec, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def _build_prefix_tsquery(query: str) -> str:
    """Build a PostgreSQL tsquery string with prefix matching for Czech morphology.

    Czech has rich declension/conjugation, so exact token matching misses valid
    results (e.g., "nadbytečnost" won't match "nadbytečným" in the tsvector).

    Strategy:
    1. Split query into words, keep only Czech/Latin alphabetic tokens
    2. For each word ≥ 5 chars, truncate to approximate stem (remove last 3 chars)
       to capture Czech inflected forms (e.g., "nadbytečn" matches both
       "nadbytečnost" and "nadbytečným")
    3. Shorter words get plain prefix matching (word:*)
    4. Terms joined with OR (|) so partial matches are returned — ts_rank
       naturally scores multi-term matches higher than single-term ones

    Returns a tsquery string like ``'nadbytečn:* | výpov:*'``.
    Falls back to the raw query if no valid terms can be extracted.
    """
    # Extract Czech/Latin words and numbers (diacritics included)
    words = re.findall(r"[a-záčďéěíňóřšťúůýžA-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9]+", query)
    if not words:
        return query

    terms: list[str] = []
    for word in words:
        w = word.lower()
        if len(w) < 2:
            continue
        # Numbers (section references like "52", "588") — exact match, no truncation
        if w.isdigit():
            terms.append(w)
            continue
        if len(w) < 3:
            continue
        if len(w) >= 5:
            # Truncate to approximate Czech stem: remove last 3 chars
            # "nadbytečnost" (13) → "nadbytečno" → but we need "nadbytečn" to match "nadbytečným"
            # Use aggressive truncation: remove ceil(30%) of chars, min stem = 4
            stem_len = max(4, len(w) - 3)
            terms.append(f"{w[:stem_len]}:*")
        else:
            terms.append(f"{w}:*")

    if not terms:
        return query

    return " | ".join(terms)


def _statute_ref_filter(stmt, statute_ref: tuple[int, int] | None):
    """Apply JSONB statute reference filter to a SQLAlchemy select statement."""
    if statute_ref is None:
        return stmt
    law_number, law_year = statute_ref
    return stmt.where(CourtDecision.regulations.contains([{"law_number": law_number, "law_year": law_year}]))


def _date_filters(stmt, date_from: date | None, date_to: date | None):
    """Apply optional date range filters to a SQLAlchemy select statement."""
    if date_from is not None:
        stmt = stmt.where(CourtDecision.decision_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(CourtDecision.decision_date <= date_to)
    return stmt


# ---------------------------------------------------------------------------
# BM25 search
# ---------------------------------------------------------------------------


async def search_decisions(
    query: str,
    statute_ref: tuple[int, int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 10,
) -> list[CourtDecision]:
    """BM25 search on court decisions with optional statute + date filters.

    Scoring combines ts_rank relevance (60%) and recency bonus (40%):
    - ts_rank: standard tsvector relevance score
    - recency: 1.0 if decision_date within last 3 years, else 0.4

    Parameters
    ----------
    query : str
        Czech language search terms.
    statute_ref : (law_number, law_year) | None
        Filter to decisions citing this statute.
        E.g. ``(262, 2006)`` for the Labour Code.
    date_from, date_to : date | None
        Optional date range filters (inclusive).
    limit : int
        Maximum number of results to return.

    Returns
    -------
    list[CourtDecision]
        Ordered by combined relevance + recency score descending.
    """
    if not query or not query.strip():
        return []

    cutoff = _recency_cutoff()

    # Build prefix-matched tsquery for Czech morphology.
    # Uses OR between terms so partial matches are returned; ts_rank
    # naturally scores multi-term matches higher.
    tsq_str = _build_prefix_tsquery(query)

    order_expr = text(
        "ts_rank(search_vector, to_tsquery('simple', :q)) * 0.6 "
        "+ CASE WHEN decision_date >= :cutoff THEN 1.0 ELSE 0.4 END * 0.4 "
        "DESC"
    )
    ts_query_fn = func.to_tsquery("simple", bindparam("q"))

    stmt = (
        select(CourtDecision).where(CourtDecision.search_vector.op("@@")(ts_query_fn)).order_by(order_expr).limit(limit)
    )
    stmt = _statute_ref_filter(stmt, statute_ref)
    stmt = _date_filters(stmt, date_from, date_to)

    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt, {"q": tsq_str, "cutoff": cutoff})
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------


async def search_decisions_vector(
    query_embedding: list[float],
    statute_ref: tuple[int, int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
) -> list[CourtDecision]:
    """Semantic vector search on court decisions using Qwen3-8B embeddings.

    Only searches decisions that have ``embedding IS NOT NULL`` — rows without
    embeddings are skipped (graceful degradation during backfill).

    Uses pgvector inner product (``<#>``) which returns a negative similarity
    (more negative = more similar for normalized vectors).

    Parameters
    ----------
    query_embedding : list[float]
        4096-dim Qwen3-8B embedding of the query, from ``embed_query()``.
    statute_ref : (law_number, law_year) | None
        Optional JSONB containment filter.
    date_from, date_to : date | None
        Optional date range filters.
    limit : int
        Maximum number of results.

    Returns
    -------
    list[CourtDecision]
        Ordered by inner product similarity (most similar first).
    """
    normalized = _normalize(query_embedding)
    vec_literal = "[" + ",".join(str(x) for x in normalized) + "]"

    # Build statement: filter to rows with embeddings, order by inner product
    stmt = (
        select(CourtDecision)
        .where(CourtDecision.embedding.is_not(None))
        .order_by(text("embedding <#> cast(:vec as vector)"))
        .limit(limit)
    )
    stmt = _statute_ref_filter(stmt, statute_ref)
    stmt = _date_filters(stmt, date_from, date_to)

    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt, {"vec": vec_literal})
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Hybrid BM25 + vector search with RRF
# ---------------------------------------------------------------------------

_RRF_K = 60  # standard RRF constant (Cormack et al. 2009)
_RRF_BM25_WEIGHT = 0.4
_RRF_VECTOR_WEIGHT = 0.6


def _rrf_fuse(
    bm25_results: list[CourtDecision],
    vector_results: list[CourtDecision],
    *,
    bm25_weight: float = _RRF_BM25_WEIGHT,
    vector_weight: float = _RRF_VECTOR_WEIGHT,
    k: int = _RRF_K,
    limit: int = 10,
) -> list[CourtDecision]:
    """Reciprocal Rank Fusion of BM25 and vector result lists.

    Score for each document: sum(weight_i / (k + rank_i)) across both legs.
    Vector gets 0.6 weight (better for semantic/factual queries), BM25 gets 0.4
    (better for exact legal term matches like statute names and article numbers).

    Documents appearing in only one leg still contribute their single-leg score —
    this is important when embeddings are sparse (not all rows have embeddings yet).
    """
    scores: dict[str, float] = {}

    for rank, doc in enumerate(bm25_results):
        eid = doc.ecli
        scores[eid] = scores.get(eid, 0.0) + bm25_weight / (k + rank + 1)

    for rank, doc in enumerate(vector_results):
        eid = doc.ecli
        scores[eid] = scores.get(eid, 0.0) + vector_weight / (k + rank + 1)

    # Collect unique docs, preserving CourtDecision objects
    all_docs: dict[str, CourtDecision] = {}
    for doc in bm25_results + vector_results:
        all_docs.setdefault(doc.ecli, doc)

    fused = sorted(all_docs.values(), key=lambda d: scores.get(d.ecli, 0.0), reverse=True)
    return fused[:limit]


async def search_decisions_hybrid(
    query: str,
    query_embedding: list[float],
    statute_ref: tuple[int, int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 10,
) -> list[CourtDecision]:
    """Hybrid BM25 + vector search with RRF fusion.

    Runs both search legs concurrently, then fuses results using Reciprocal
    Rank Fusion.  Falls back gracefully when the BM25 or vector leg returns
    empty results (e.g., empty query → BM25 skipped; no embeddings → vector
    leg returns nothing).

    Parameters
    ----------
    query : str
        Czech language search terms for the BM25 leg.
    query_embedding : list[float]
        4096-dim Qwen3-8B embedding for the vector leg.
    statute_ref, date_from, date_to :
        Filters applied to both legs independently.
    limit : int
        Maximum results after fusion.

    Returns
    -------
    list[CourtDecision]
        RRF-fused results, most relevant first.
    """
    import asyncio

    # Fetch more candidates per leg so fusion has a rich pool to draw from
    leg_limit = min(limit * 3, 30)

    bm25_coro = search_decisions(query, statute_ref=statute_ref, date_from=date_from, date_to=date_to, limit=leg_limit)
    vector_coro = search_decisions_vector(
        query_embedding, statute_ref=statute_ref, date_from=date_from, date_to=date_to, limit=leg_limit
    )

    bm25_results, vector_results = await asyncio.gather(bm25_coro, vector_coro)

    # If one leg is empty, return the other directly (no fusion needed)
    if not bm25_results:
        return vector_results[:limit]
    if not vector_results:
        return bm25_results[:limit]

    return _rrf_fuse(bm25_results, vector_results, limit=limit)


# ---------------------------------------------------------------------------
# Standard CRUD helpers
# ---------------------------------------------------------------------------


async def get_decision_by_ecli(ecli: str) -> CourtDecision | None:
    """Fetch a single decision by ECLI identifier."""
    stmt = select(CourtDecision).where(CourtDecision.ecli == ecli)
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def upsert_decision(data: dict) -> CourtDecision:
    """Insert a new decision or update on ECLI conflict.

    The ``ecli`` key in ``data`` is used as the upsert key.  All other
    keys are mapped to CourtDecision columns.  Unknown keys are silently
    ignored so the scraper can pass raw parsed dicts.

    The ``embedding`` field is accepted if provided by the caller — this lets
    the batch embedding script or scraper pass pre-computed embeddings directly.

    Parameters
    ----------
    data : dict
        Must include ``ecli`` and ``case_number``.

    Raises
    ------
    ValueError
        If ``ecli`` or ``case_number`` is missing.
    """
    ecli = (data.get("ecli") or "").strip()
    case_number = (data.get("case_number") or "").strip()
    if not ecli:
        raise ValueError("upsert_decision requires 'ecli'")
    if not case_number:
        raise ValueError("upsert_decision requires 'case_number'")

    _allowed = {
        "ecli",
        "case_number",
        "court",
        "decision_date",
        "decision_type",
        "category",
        "legal_thesis",
        "judges",
        "full_text",
        "full_text_fetched",
        "source_url",
        "source_unid",
        "regulations",
        "keywords",
        "embedding",  # accepted when pre-computed by caller
    }
    fields = {k: v for k, v in data.items() if k in _allowed}

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourtDecision).where(CourtDecision.ecli == ecli))
        existing = result.scalar_one_or_none()

        if existing is None:
            record = CourtDecision(**fields)
            session.add(record)
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.updated_at = _utcnow()
            record = existing

        await session.commit()
        await session.refresh(record)
        return record


async def get_decisions_count() -> int:
    """Return total number of court decisions in the database."""
    stmt = select(func.count()).select_from(CourtDecision)
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return result.scalar_one()


async def get_unembedded_decisions(limit: int = 500) -> list[CourtDecision]:
    """Return decisions that have legal_thesis but no embedding yet.

    Used by the batch embedding script to find rows that need to be processed.
    Ordered by updated_at DESC so recently-scraped decisions are embedded first.
    """
    stmt = (
        select(CourtDecision)
        .where(
            CourtDecision.legal_thesis.is_not(None),
            CourtDecision.embedding.is_(None),
        )
        .order_by(CourtDecision.updated_at.desc())
        .limit(limit)
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return list(result.scalars().all())
