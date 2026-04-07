"""Integration test fixtures for session-based auth endpoints.

Uses a real PostgreSQL database — no DB mocking.
External services (Resend email, per-IP rate limiter) are mocked.

Event-loop isolation note
--------------------------
pytest-asyncio (auto mode) gives each test its own event loop. asyncpg
connections are bound to the loop that created them, so a pooled connection
from test N cannot be reused in test N+1's loop.

Fix: replace the global SQLAlchemy engine with a NullPool engine before any
test runs. NullPool never caches connections — each DB operation opens and
closes a fresh connection in the current loop. asyncio.run() calls (used by
session-scoped sync fixtures) are then safe because their short-lived
connections die before the next test loop starts.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.middleware.sessions import SessionMiddleware

from neolex.auth import email_auth, oauth
from neolex.config import settings
from neolex.db.models import User
from neolex.db.postgres import init_db

# ---------------------------------------------------------------------------
# NullPool engine — must be installed before any DB call
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def install_null_pool_engine():
    """Replace the global SQLAlchemy engine with a NullPool version.

    This fixture runs once per test session (sync, so it executes before any
    async test loop is created). NullPool prevents asyncpg connections from
    being reused across different event loops (one per test in auto mode).
    """
    import neolex.db.postgres as pg

    _db_url = pg._db_url
    test_engine = create_async_engine(_db_url, poolclass=NullPool)
    test_sessions = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    old_engine = pg.engine
    old_sessions = pg.AsyncSessionLocal

    pg.engine = test_engine
    pg.AsyncSessionLocal = test_sessions

    yield

    pg.engine = old_engine
    pg.AsyncSessionLocal = old_sessions


# ---------------------------------------------------------------------------
# One-time schema setup (runs after NullPool engine is installed)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def ensure_schema(install_null_pool_engine):  # noqa: ARG001 — depends on NullPool being installed first
    """Create all PostgreSQL tables once for the integration test session.

    Uses asyncio.run() which is safe with NullPool: connections are created
    and immediately closed inside the temporary loop, leaving no stale state.
    """
    asyncio.run(init_db())


# ---------------------------------------------------------------------------
# Minimal FastAPI test app (no pipeline, no CSRF middleware)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_app() -> FastAPI:
    """Auth-only FastAPI app — excludes pipeline startup and CSRF middleware."""
    app = FastAPI()
    # SessionMiddleware is required by authlib's OAuth client for CSRF state.
    app.add_middleware(SessionMiddleware, secret_key="integration-test-secret-key")
    app.include_router(email_auth.router)
    app.include_router(oauth.router)
    return app


# ---------------------------------------------------------------------------
# Per-test environment patches
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def dev_mode_on(monkeypatch):
    """Set dev_mode=True so cookies are NOT marked Secure.

    httpx uses http://test (not https), so Secure cookies would never be
    sent back to the server in subsequent requests, breaking session flows.
    """
    monkeypatch.setattr(settings, "dev_mode", True)


@pytest.fixture(autouse=True)
async def no_rate_limit():
    """Bypass per-IP rate limiting for all integration tests.

    Tests generate many requests from the same 'testclient' IP address.
    Rate limiting is tested separately by checking the auth code path.
    """
    with patch("neolex.auth.email_auth._auth_rate_check", new_callable=AsyncMock):
        yield


@pytest.fixture(autouse=True)
async def mock_email_services():
    """Mock outbound email calls (Resend). Captured by name in tests that need tokens."""
    with (
        patch("neolex.auth.email_auth.send_verification_email", new_callable=AsyncMock) as mv,
        patch("neolex.auth.email_auth.send_password_reset_email", new_callable=AsyncMock) as mr,
    ):
        yield mv, mr


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def unique_email() -> str:
    """Generate a unique email per test to avoid cross-test pollution."""
    return f"inttest_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
async def db():
    """Yield a live AsyncSession for direct DB assertions/setup."""
    import neolex.db.postgres as pg

    async with pg.AsyncSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
async def cleanup_test_users():
    """Delete all integration-test users after each test (cascade deletes sessions/tokens)."""
    yield
    import neolex.db.postgres as pg

    async with pg.AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.email.like("inttest_%@example.com")))
        await session.commit()


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(test_app) -> AsyncClient:
    """Async httpx client pointed at the auth-only test app.

    follow_redirects=False lets tests inspect redirect status codes and
    read the Set-Cookie headers on redirect responses (e.g. verify-email,
    logout) before the client would chase the Location header.
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
        follow_redirects=False,
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Compound auth-state fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def registered_user(client, mock_email_services, unique_email):
    """Register a new user and return (email, password, verify_token).

    The verification token is captured from the mocked send_verification_email call.
    """
    mock_verify, _ = mock_email_services
    email = unique_email
    password = "ValidPass123!"

    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Integration Tester"},
    )
    assert resp.status_code == 201, f"Register failed: {resp.text}"

    # Token is the second positional arg to send_verification_email(email, token)
    verify_token = mock_verify.call_args[0][1]
    return email, password, verify_token


@pytest.fixture
async def verified_user(client, registered_user):
    """Register + verify email. Returns (email, password) with a clean cookie jar."""
    email, password, token = registered_user
    resp = await client.get(f"/auth/verify-email?token={token}")
    # Endpoint redirects on success; 307 or 302 both indicate success
    assert resp.status_code in (302, 307), f"Email verification failed: {resp.status_code} {resp.text}"
    # Clear cookies set during email verification so each test starts without a pre-existing session
    client.cookies.clear()
    return email, password
