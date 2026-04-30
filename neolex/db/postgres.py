"""PostgreSQL async engine — the single database backend for Vitreon Legal.

All tables live here: auth/billing (users, sessions, auth_tokens,
subscriptions, invoices) and operational (api_keys, queries, events,
rate_limits, documents, reindex_jobs).
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from neolex.config import settings

_db_url = settings.database_url
if not _db_url:
    raise RuntimeError("DATABASE_URL must be set for PostgreSQL connection")

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def conversation_doc_lock_key(conv_uuid: uuid.UUID) -> int:
    """Derive a pg_advisory_xact_lock key for a conversation's document cap check.

    XORs the high and low 64-bit halves of the UUID to produce a unique,
    positive int64 that fits in a PostgreSQL bigint.  Two distinct UUIDs may
    theoretically produce the same key (false contention), but never produce
    different keys for the same UUID (no missed contention).
    """
    hi = conv_uuid.int >> 64
    lo = conv_uuid.int & 0xFFFFFFFFFFFFFFFF
    return (hi ^ lo) & 0x7FFFFFFFFFFFFFFF


async def get_db():
    """FastAPI dependency: yields an async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables defined in models.py, operational_models.py, chunks.py, and court_decisions.py (idempotent)."""
    from neolex.db import (
        chunks,  # noqa: F401 — registers chunk/vector model
        court_decisions,  # noqa: F401 — registers court decisions model
        drafting_models,  # noqa: F401 — registers document_templates, chat_documents
        models,  # noqa: F401 — registers auth/billing models
        operational_models,  # noqa: F401 — registers operational models
    )

    async with engine.begin() as conn:
        # Enable pgvector extension (must precede table creation)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Idempotent schema migrations — add columns that may not exist on older instances.
        await conn.execute(
            text("ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS sources_json TEXT;"),
        )
        # Ensure feedback unique index exists on older instances (created by create_all on new ones).
        await conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS feedback_message_user_uq ON feedback(message_id, user_id);"),
        )
        # Add embedding column to court_decisions if it doesn't exist (idempotent migration).
        # Vector(4096) — no HNSW index (4096-dim exceeds pgvector's 2000-dim limit).
        await conn.execute(
            text("ALTER TABLE court_decisions ADD COLUMN IF NOT EXISTS embedding vector(4096);"),
        )
        # corpus_deletion_scheduled_at: set on cancellation; corpus deleted at this timestamp.
        # 7-day grace period lets users export data before permanent deletion.
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS corpus_deletion_scheduled_at TIMESTAMPTZ;"),
        )
        # file_type: 'pdf' | 'txt' — explicit format tag so the indexer can dispatch
        # without guessing from the filename extension. Existing rows default to 'pdf'.
        await conn.execute(
            text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_type TEXT NOT NULL DEFAULT 'pdf';"),
        )
        # trace_id: Langfuse trace ID stored on assistant messages for feedback linkage.
        await conn.execute(
            text("ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS trace_id TEXT;"),
        )
        # chunks.id DEFAULT: ensure gen_random_uuid() is set so INSERTs that
        # omit id never fail with NotNullViolation (idempotent).
        await conn.execute(
            text("ALTER TABLE chunks ALTER COLUMN id SET DEFAULT gen_random_uuid();"),
        )
        # Promo tier columns on users (NEO-2874).
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS promo_tier TEXT;"),
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS promo_expires_at TIMESTAMPTZ;"),
        )
        # Promocodes table (NEO-2874)
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    code TEXT UNIQUE NOT NULL,
                    tier TEXT NOT NULL,
                    duration_days INTEGER NOT NULL,
                    max_redemptions INTEGER,
                    redemption_count INTEGER NOT NULL DEFAULT 0,
                    valid_until TIMESTAMPTZ,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """),
        )
        # Promocode redemptions table (NEO-2874)
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS promocode_redemptions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    promocode_id UUID NOT NULL REFERENCES promocodes(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    granted_tier TEXT NOT NULL,
                    redeemed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (promocode_id, user_id)
                );
            """),
        )
        # Index for promocode redemptions lookups
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_promocode_redemptions_user ON promocode_redemptions(user_id);"),
        )
        # Trigger to auto-populate text_search tsvector on INSERT/UPDATE
        # Uses 'simple' tokenizer: language-agnostic (Czech corpus),
        # preserves legal terms that stemmers would mangle.
        await conn.execute(
            text("""
            CREATE OR REPLACE FUNCTION chunks_text_search_trigger() RETURNS trigger AS $$
            BEGIN
                NEW.text_search := to_tsvector('simple', NEW.text);
                RETURN NEW;
            END
            $$ LANGUAGE plpgsql;
        """),
        )
        await conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TRIGGER chunks_text_search_update
                    BEFORE INSERT OR UPDATE OF text ON chunks
                    FOR EACH ROW EXECUTE FUNCTION chunks_text_search_trigger();
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """),
        )
        # Trigger to auto-populate search_vector tsvector on court_decisions INSERT/UPDATE.
        # Indexes legal_thesis, case_number, and keywords array for BM25 search.
        # Uses 'simple' tokenizer: language-agnostic, preserves Czech legal terms.
        await conn.execute(
            text("""
            CREATE OR REPLACE FUNCTION court_decisions_search_trigger() RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := to_tsvector(
                    'simple',
                    coalesce(NEW.legal_thesis, '') || ' ' ||
                    coalesce(NEW.case_number, '') || ' ' ||
                    coalesce(array_to_string(NEW.keywords, ' '), '')
                );
                RETURN NEW;
            END
            $$ LANGUAGE plpgsql;
        """),
        )
        await conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TRIGGER court_decisions_search_update
                    BEFORE INSERT OR UPDATE OF legal_thesis, case_number, keywords
                    ON court_decisions
                    FOR EACH ROW EXECUTE FUNCTION court_decisions_search_trigger();
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """),
        )
