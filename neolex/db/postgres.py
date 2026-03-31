"""PostgreSQL async engine — the single database backend for Vitreon Legal.

All tables live here: auth/billing (users, sessions, auth_tokens,
subscriptions, invoices) and operational (api_keys, queries, events,
rate_limits, documents, reindex_jobs).
"""
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


async def get_db():
    """FastAPI dependency: yields an async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables defined in models.py, operational_models.py, and chunks.py (idempotent)."""
    from neolex.db import (
        chunks,  # noqa: F401 — registers chunk/vector model
        models,  # noqa: F401 — registers auth/billing models
        operational_models,  # noqa: F401 — registers operational models
    )
    async with engine.begin() as conn:
        # Enable pgvector extension (must precede table creation)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Trigger to auto-populate text_search tsvector on INSERT/UPDATE
        # Uses 'simple' tokenizer: language-agnostic (Czech corpus),
        # preserves legal terms that stemmers would mangle.
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION chunks_text_search_trigger() RETURNS trigger AS $$
            BEGIN
                NEW.text_search := to_tsvector('simple', NEW.text);
                RETURN NEW;
            END
            $$ LANGUAGE plpgsql;
        """))
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TRIGGER chunks_text_search_update
                    BEFORE INSERT OR UPDATE OF text ON chunks
                    FOR EACH ROW EXECUTE FUNCTION chunks_text_search_trigger();
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
