"""Chunk storage model — pgvector + tsvector for hybrid search."""
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from neolex.db.postgres import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    corpus: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    doc_id: Mapped[str] = mapped_column(String, nullable=False)
    pdf_id: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(4096))
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)
    # Pre-computed tsvector column for full-text search
    text_search = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(
        default=_utcnow, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # No HNSW/IVFFlat index: pgvector limits HNSW to 2000 dims, our
        # embeddings are 4096-dim (Qwen3-8B).  At ~18k rows exact sequential
        # scan is sub-millisecond, so an ANN index is unnecessary.
        # GIN index for full-text search on pre-computed tsvector
        Index("chunks_text_fts", "text_search", postgresql_using="gin"),
        # Composite index for corpus + tenant filtering
        Index("chunks_corpus_tenant", "corpus", "tenant_id"),
        # For doc-level lookups
        Index("chunks_doc_id", "corpus", "doc_id"),
    )
