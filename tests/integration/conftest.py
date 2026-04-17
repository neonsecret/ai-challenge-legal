"""Integration test fixtures for session-based auth endpoints.

Uses a real PostgreSQL database — no DB mocking.
External services (Resend email, per-IP rate limiter) are mocked.

NullPool isolation is handled by the root conftest `_install_nullpool_engine`
session-scoped fixture. This conftest only adds integration-specific fixtures.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from starlette.middleware.sessions import SessionMiddleware

from neolex.auth import email_auth, oauth
from neolex.config import settings
from neolex.db.models import User
from neolex.db.postgres import init_db

# ---------------------------------------------------------------------------
# One-time schema setup (depends on root _install_nullpool_engine)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def ensure_schema(_install_nullpool_engine):  # noqa: ARG001 — NullPool must be installed first
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


# ---------------------------------------------------------------------------
# Drafting test fixtures (for document API integration tests)
# ---------------------------------------------------------------------------


async def _create_test_user(email: str, verified: bool = True) -> tuple[str, str]:
    """Create a user in the DB. Returns (email, user_id)."""
    import hashlib
    from datetime import UTC, datetime

    from neolex.db.models import User
    from neolex.db.postgres import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            name="Test User",
            password_hash=hashlib.sha256(b"test_password_placeholder").hexdigest(),
            email_verified=verified,
            created_at=datetime.now(UTC),
            subscription_status="starter",
            monthly_queries_used=0,
            daily_queries_used=0,
            max_corpora=1,
        )
        session.add(user)
        await session.flush()
        user_id = str(user.id)
        await session.commit()

    return email, user_id


@pytest.fixture
async def test_user(unique_email) -> tuple[str, str]:
    """Create a verified test user. Yields (email, user_id)."""
    email, user_id = await _create_test_user(unique_email, verified=True)
    yield email, user_id


@pytest.fixture(autouse=True)
async def mock_llm_calls():
    """Mock LLM calls to avoid expensive API calls in tests."""
    mock_result = {
        "answer": "This is a mocked LLM response for testing.",
        "chunk_pages": [],
        "ttft_ms": 100,
        "tpot_ms": 10.0,
        "total_time_ms": 500,
        "input_tokens": 100,
        "output_tokens": 50,
        "model_name": "claude-sonnet-4-6-test",
    }
    with (
        patch("neolex.routers.query.run_single_question", new_callable=AsyncMock, return_value=mock_result),
        patch("neolex.services.conversation.create_pipeline_job", new_callable=AsyncMock, return_value=uuid.uuid4()),
        patch("neolex.services.conversation.complete_pipeline_job", new_callable=AsyncMock),
        patch("neolex.services.conversation.fail_pipeline_job", new_callable=AsyncMock),
    ):
        yield mock_result


@pytest.fixture
async def test_client(test_user, mock_llm_calls) -> AsyncClient:
    """Authenticated AsyncClient with real DB for integration testing.

    - Auth is mocked via dependency override
    - DB is real (PostgreSQL via NullPool)
    - LLM/pipeline is mocked (avoid external API calls)
    """
    import asyncio as _asyncio

    from neolex.auth.middleware import get_api_key
    from neolex.db.postgres import AsyncSessionLocal, get_db
    from neolex.main import app

    email, user_id = test_user
    user_uuid = uuid.UUID(user_id)

    app.state.ready = True
    app.state.semaphore = _asyncio.Semaphore(5)
    app.state.workers = 5

    async def mock_get_api_key():
        return {
            "user_id": str(user_uuid),
            "email": email,
            "client_slug": user_id,
            "scope": "admin",
            "key_hash": f"session:{user_id}",
            "key_prefix": "session",
            "name": "Test User",
        }

    async def mock_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_api_key] = mock_get_api_key
    app.dependency_overrides[get_db] = mock_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        yield client

    app.dependency_overrides.pop(get_api_key, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def conversation_record(test_user) -> str:
    """Create a conversation record in DB. Returns conversation ID."""
    from sqlalchemy import text

    from neolex.db.postgres import AsyncSessionLocal

    conv_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO conversation_messages (id, conversation_id, user_id, role, content, created_at)
                VALUES (:id, :conv_id, :user_id, 'user', 'test message', NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": str(uuid.uuid4()), "conv_id": str(conv_id), "user_id": test_user[1]},
        )
        await session.commit()

    return str(conv_id)
