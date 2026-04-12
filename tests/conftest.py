"""Root conftest.py — adds project root to sys.path so tests can import the arlc package."""

import os
import sys
from pathlib import Path

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
