"""PostgreSQL async engine — the single database backend for Vitreon Legal.

All tables live here: auth/billing (users, sessions, auth_tokens,
subscriptions, invoices) and operational (api_keys, queries, events,
rate_limits, documents, reindex_jobs).
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
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
    """Create all tables defined in models.py and operational_models.py (idempotent)."""
    from neolex.db import models  # noqa: F401 — registers auth/billing models
    from neolex.db import operational_models  # noqa: F401 — registers operational models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
