"""Root conftest.py — adds project root to sys.path so tests can import the arlc package."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env before any neolex module imports so DATABASE_URL and other env vars
# are available when SQLAlchemy engine is created at import time.
# Fall back to a dummy URL so test collection still works in CI without .env.
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
# ADMIN_EMAILS: required by neolex.routers.admin for admin-gate logic.
# In CI without .env this must be set before any neolex import so that
# admin-scoped tests can run. The value matches .env.example.
os.environ.setdefault("ADMIN_EMAILS", "admin@vitreon.app")
# JWT_SECRET_KEY: required by neolex.main at module-import time (SessionMiddleware).
# Without it `import neolex.main` raises RuntimeError, breaking the entire test
# suite in CI environments where no .env is present.
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-only-secret-key-not-for-production")

# These test files reference modules (agent_tools, agent_v2) that were removed
# during the arlc refactor. Exclude them from collection to prevent ImportError.
collect_ignore = [
    "test_agent_tools.py",
    "test_agent_v2.py",
]


# ---------------------------------------------------------------------------
# Asyncpg pool isolation — prevent cross-module event-loop contamination
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _install_nullpool_engine():
    """Replace the global SQLAlchemy engine with a NullPool version for the
    entire test session.

    asyncpg connections are bound to the event loop that created them.
    pytest-asyncio (auto mode) creates a new loop per test, so pooled
    connections from test N become invalid in test N+1's loop. NullPool
    opens a fresh connection per operation, avoiding cross-loop reuse.
    """
    try:
        import neolex.db.postgres as pg
    except Exception:
        yield
        return

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    test_engine = create_async_engine(pg._db_url, poolclass=NullPool)
    test_sessions = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    old_engine = pg.engine
    old_sessions = pg.AsyncSessionLocal

    pg.engine = test_engine
    pg.AsyncSessionLocal = test_sessions

    yield

    pg.engine = old_engine
    pg.AsyncSessionLocal = old_sessions
