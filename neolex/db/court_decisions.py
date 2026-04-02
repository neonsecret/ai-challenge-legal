"""Court decisions model — BM25 + JSONB regulation index for Czech judikatura.

Stores Czech Supreme Court (Nejvyssi soud) decisions scraped from
rozhodnuti.nsoud.cz.  Full text is fetched on demand and cached.

Key differences from the ``chunks`` table:
- No vector embeddings — retrieval is BM25 (tsvector) only
- Rich case metadata: case number, category, judges, decision type
- Legal thesis (pravni veta) as a distinct indexed field
- Statute citation graph via JSONB (regulations field)
- On-demand full text fetching pattern (full_text_fetched flag)
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

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
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _recency_cutoff() -> date:
    """Date object for the 3-year recency cutoff."""
    return (datetime.now(UTC) - timedelta(days=3 * 365)).date()


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

    cutoff = _recency_cutoff()  # date object for asyncpg

    # Combined score: 60% BM25 ts_rank + 40% recency
    # Using text() for the ORDER BY expression to keep the SQL straightforward.
    # Both :q (str) and :cutoff (date) are bound at execute time.
    order_expr = text(
        "ts_rank(search_vector, plainto_tsquery('simple', :q)) * 0.6 "
        "+ CASE WHEN decision_date >= :cutoff THEN 1.0 ELSE 0.4 END * 0.4 DESC"
    )

    ts_query_fn = func.plainto_tsquery("simple", bindparam("q"))

    stmt = (
        select(CourtDecision).where(CourtDecision.search_vector.op("@@")(ts_query_fn)).order_by(order_expr).limit(limit)
    )

    if statute_ref is not None:
        law_number, law_year = statute_ref
        # JSONB containment: regulations array must contain an element with
        # matching law_number and law_year fields.
        # Using .contains() which maps to the @> operator via SQLAlchemy JSONB API.
        stmt = stmt.where(CourtDecision.regulations.contains([{"law_number": law_number, "law_year": law_year}]))

    if date_from is not None:
        stmt = stmt.where(CourtDecision.decision_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(CourtDecision.decision_date <= date_to)

    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt, {"q": query, "cutoff": cutoff})
        return list(result.scalars().all())


async def get_decision_by_ecli(ecli: str) -> CourtDecision | None:
    """Fetch a single decision by ECLI identifier.

    Parameters
    ----------
    ecli : str
        Full ECLI string, e.g. "ECLI:CZ:NS:2023:21.CDO.1234.2023.1"

    Returns
    -------
    CourtDecision | None
    """
    stmt = select(CourtDecision).where(CourtDecision.ecli == ecli)
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def upsert_decision(data: dict) -> CourtDecision:
    """Insert a new decision or update on ECLI conflict.

    The ``ecli`` key in ``data`` is used as the upsert key.  All other
    keys are mapped to CourtDecision columns.  Unknown keys are silently
    ignored so the scraper can pass raw parsed dicts.

    Parameters
    ----------
    data : dict
        Must include ``ecli`` and ``case_number``.

    Returns
    -------
    CourtDecision
        The inserted or updated record (refreshed from DB).

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
