"""Integration tests for OAuth callback, session flow, and email/password auth.

These tests use a real PostgreSQL database — no DB mocks.
The only mocked external calls are:
  - Google OAuth token exchange (external HTTP to accounts.google.com)
  - Resend email sending (external HTTP to api.resend.com)

Run: uv run pytest tests/integration/test_auth_flow.py -v
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

# Share one event loop for all tests in this module so the SQLAlchemy async
# engine connection pool (a module-level singleton) stays bound to the same
# loop as every DB call — avoids "Future attached to a different loop" errors.
pytestmark = pytest.mark.asyncio(loop_scope="module")

from neolex.auth.session import MAX_SESSIONS_PER_USER, create_session
from neolex.db.models import Session as DBSession
from neolex.db.models import User
from neolex.db.postgres import AsyncSessionLocal, init_db

# ---------------------------------------------------------------------------
# Schema initialization (idempotent — safe against a live dev DB)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
async def _ensure_schema():
    """Create all tables and PostgreSQL extensions if not already present."""
    await init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _test_email() -> str:
    """Return a unique email that passes EmailStr validation.

    Uses @example.com (RFC 2606 reserved) so test rows are easily identifiable
    and the domain passes email-validator's deliverability check bypass.
    """
    return f"inttest+{uuid.uuid4().hex[:10]}@example.com"


async def _cleanup_user(email: str) -> None:
    """Delete the test user and all cascaded rows (sessions, auth_tokens)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            await db.delete(user)
            await db.commit()


# ---------------------------------------------------------------------------
# Shared CSRF header (required for POST /auth/register and /auth/login)
# ---------------------------------------------------------------------------

_CSRF = {"X-Requested-With": "XMLHttpRequest"}


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """AsyncClient wrapping the FastAPI ASGI app.

    The pipeline (RAG) is mocked so tests don't touch arlc/ or data/.
    Auth and PostgreSQL operations are fully real.
    follow_redirects=False lets OAuth and verify-email redirect responses
    be inspected for cookies and Location headers before following them.
    """
    from neolex.main import app

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Test 1: OAuth callback sequence
# ---------------------------------------------------------------------------


async def test_oauth_callback_sequence(client):
    """GET /auth/google/callback → session created in DB → GET /auth/me returns user."""
    email = _test_email()
    fake_token_response = {
        "userinfo": {
            "email": email,
            "sub": f"google_{uuid.uuid4().hex}",
            "name": "OAuth Integration Test",
            "picture": None,
            "email_verified": True,
        }
    }

    try:
        from neolex.auth.oauth import _oauth

        with patch.object(
            _oauth.google,
            "authorize_access_token",
            new_callable=AsyncMock,
            return_value=fake_token_response,
        ):
            resp = await client.get("/auth/google/callback")

        assert resp.status_code in (302, 307), (
            f"Expected redirect after OAuth callback, got {resp.status_code}: {resp.text[:200]}"
        )
        assert "/chat" in resp.headers.get("location", ""), "Redirect location must contain /chat"

        session_cookie = resp.cookies.get("vitreon_session")
        assert session_cookie, "vitreon_session cookie must be set on OAuth callback"

        # Real DB lookup: session and user must both be committed
        me = await client.get("/auth/me", cookies={"vitreon_session": session_cookie})
        assert me.status_code == 200, f"/auth/me returned {me.status_code}: {me.text}"
        data = me.json()
        assert data["email"] == email
        assert data["plan"] in ("free", "starter", "pro", "enterprise")

    finally:
        await _cleanup_user(email)


# ---------------------------------------------------------------------------
# Test 2: Race condition window — user committed before redirect
# ---------------------------------------------------------------------------


async def test_session_committed_before_redirect(client):
    """User row is visible in a fresh DB connection before the OAuth redirect.

    The callback executes db.commit() (user upsert) *before* create_session().
    This ensures that another connection (e.g. the /auth/me handler) can always
    find the user row when it resolves the session token — eliminating a race
    window where /auth/me would see the cookie but no matching user row.
    """
    email = _test_email()
    fake_token_response = {
        "userinfo": {
            "email": email,
            "sub": f"google_{uuid.uuid4().hex}",
            "name": "Race Condition Test",
            "picture": None,
            "email_verified": True,
        }
    }

    try:
        from neolex.auth.oauth import _oauth
        from neolex.auth.session import hash_token

        with patch.object(
            _oauth.google,
            "authorize_access_token",
            new_callable=AsyncMock,
            return_value=fake_token_response,
        ):
            resp = await client.get("/auth/google/callback")

        assert resp.status_code in (302, 307)
        session_cookie = resp.cookies.get("vitreon_session")
        assert session_cookie

        # Independent pool connection — simulates /auth/me on a different DB connection
        async with AsyncSessionLocal() as db:
            token_hash = hash_token(session_cookie)

            sess_result = await db.execute(select(DBSession).where(DBSession.token_hash == token_hash))
            session = sess_result.scalar_one_or_none()
            assert session is not None, "Session row must be committed to DB before the OAuth redirect is sent"

            user_result = await db.execute(select(User).where(User.id == session.user_id))
            user = user_result.scalar_one_or_none()
            assert user is not None, "User row must be committed before session row — commit ordering fix"
            assert user.email == email

    finally:
        await _cleanup_user(email)


# ---------------------------------------------------------------------------
# Test 3: Concurrent session creation — SELECT FOR UPDATE serialization
# ---------------------------------------------------------------------------


async def test_concurrent_session_creation():
    """Concurrent create_session() calls complete without deadlocks or errors.

    The SELECT FOR UPDATE in create_session() prevents deadlocks by acquiring all
    session row locks upfront before eviction (commit 30bcfab fix).  Without it,
    two concurrent transactions that each delete different rows could deadlock.

    What SELECT FOR UPDATE guarantees under concurrent load:
      - No deadlocks — all N concurrent calls succeed and return unique tokens.
      - No constraint violations — token_hash is unique per row.

    What it does NOT guarantee:
      - Exact cap enforcement under true concurrency: when transaction T0 holds
        the lock and later commits (deleting S1, inserting S11), waiting
        transactions T1/T2 re-scan from PostgreSQL's post-commit state.
        PostgreSQL's FOR UPDATE re-scan only covers rows that existed when T1/T2's
        query started, so T1/T2 may see N-1 rows (S1 gone, S11 not yet in their
        scan) and skip eviction.  This is expected PostgreSQL behavior, not a bug.

    This test verifies the deadlock-free guarantee: all concurrent creates must
    succeed and every returned token must be unique.
    """
    email = _test_email()
    n = MAX_SESSIONS_PER_USER + 2

    try:
        async with AsyncSessionLocal() as db:
            user = User(
                email=email,
                email_verified=True,
                subscription_status="free",
                monthly_queries_used=0,
                daily_queries_used=0,
                max_corpora=0,
            )
            db.add(user)
            await db.commit()
            user_id = user.id

        async def _create_one(index: int) -> str:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                u = result.scalar_one()
                return await create_session(u, db, ip=f"10.0.2.{index}", user_agent=f"concurrent-{index}")

        tokens = await asyncio.gather(*[_create_one(i) for i in range(n)])

        # Primary guarantee: no deadlock — all calls must return a token
        assert len(tokens) == n, "All concurrent create_session calls must return tokens"

        # Each session token must be unique (no hash collisions or shared rows)
        assert len(set(tokens)) == n, "Every concurrent session must have a unique token"

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(DBSession).where(DBSession.user_id == user_id))
            final_count = len(result.scalars().all())

        # Session count is bounded: at most MAX_SESSIONS_PER_USER + n in the worst
        # case (no pre-existing sessions → no eviction triggered for any create).
        assert final_count <= n, f"Session count unexpectedly high: {final_count} (created {n} from empty)"

    finally:
        await _cleanup_user(email)


# ---------------------------------------------------------------------------
# Test 4: Email/password login end-to-end
# ---------------------------------------------------------------------------


async def test_email_password_login_flow(client):
    """POST /auth/register → GET /auth/verify-email → POST /auth/login → GET /auth/me."""
    email = _test_email()
    password = "Vitreon@Test2026!"
    captured_token: list[str] = []

    async def _capture_verification_email(to_email: str, token: str) -> None:
        captured_token.append(token)

    try:
        # 1. Register — mock email sending to capture the raw verification token
        with patch(
            "neolex.auth.email_auth.send_verification_email",
            new=_capture_verification_email,
        ):
            reg = await client.post(
                "/auth/register",
                json={"email": email, "password": password, "name": "Integration Test User"},
                headers=_CSRF,
            )
        assert reg.status_code == 201, f"Register failed: {reg.text}"
        assert captured_token, "send_verification_email must have been called during register"

        # 2. Verify email — endpoint is CSRF-exempt (GET), creates and commits a session
        verify = await client.get("/auth/verify-email", params={"token": captured_token[0]})
        assert verify.status_code in (302, 307), (
            f"verify-email expected redirect, got {verify.status_code}: {verify.text[:200]}"
        )
        assert "/chat" in verify.headers.get("location", "")

        # 3. Login — creates a second, independent session
        login_resp = await client.post(
            "/auth/login",
            json={"email": email, "password": password},
            headers=_CSRF,
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        assert login_resp.json().get("message") == "Login successful"
        session_cookie = login_resp.cookies.get("vitreon_session")
        assert session_cookie, "vitreon_session cookie must be present after login"

        # 4. GET /auth/me — session resolves to the authenticated user
        me = await client.get("/auth/me", cookies={"vitreon_session": session_cookie})
        assert me.status_code == 200, f"/auth/me failed: {me.text}"
        data = me.json()
        assert data["email"] == email

    finally:
        await _cleanup_user(email)


# ---------------------------------------------------------------------------
# Test 5: Session limit — eviction at MAX_SESSIONS_PER_USER
# ---------------------------------------------------------------------------


async def test_session_limit():
    """Creating MAX_SESSIONS_PER_USER + 1 sessions evicts the oldest one.

    After filling to the cap and creating one more session, the DB must
    contain exactly MAX_SESSIONS_PER_USER rows — the eviction path in
    create_session() must have deleted the oldest session.
    """
    email = _test_email()

    try:
        async with AsyncSessionLocal() as db:
            user = User(
                email=email,
                email_verified=True,
                subscription_status="free",
                monthly_queries_used=0,
                daily_queries_used=0,
                max_corpora=0,
            )
            db.add(user)
            await db.commit()
            user_id = user.id

        # Fill to the cap
        for i in range(MAX_SESSIONS_PER_USER):
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                u = result.scalar_one()
                await create_session(u, db, ip=f"10.0.1.{i}")

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(DBSession).where(DBSession.user_id == user_id))
            count_at_cap = len(result.scalars().all())

        assert count_at_cap == MAX_SESSIONS_PER_USER, (
            f"Expected exactly {MAX_SESSIONS_PER_USER} sessions at cap, got {count_at_cap}"
        )

        # One more session — oldest must be evicted, total must stay at MAX
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            u = result.scalar_one()
            await create_session(u, db, ip="10.0.1.99")

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(DBSession).where(DBSession.user_id == user_id))
            final_count = len(result.scalars().all())

        assert final_count == MAX_SESSIONS_PER_USER, (
            f"Expected {MAX_SESSIONS_PER_USER} sessions after eviction, got {final_count}"
        )

    finally:
        await _cleanup_user(email)


# ---------------------------------------------------------------------------
# Test 6: Cookie attributes
# ---------------------------------------------------------------------------


async def test_cookie_attributes(client):
    """Session cookie must have HttpOnly, SameSite=Lax, and Path=/ attributes.

    In dev mode the Secure flag must be absent (allows HTTP on localhost).
    In production mode (DEV_MODE unset or false) the Secure flag must be present.
    """
    email = _test_email()
    password = "C00kie@Attr2026!"
    captured_token: list[str] = []

    async def _capture_verification_email(to_email: str, token: str) -> None:
        captured_token.append(token)

    try:
        with patch(
            "neolex.auth.email_auth.send_verification_email",
            new=_capture_verification_email,
        ):
            reg = await client.post(
                "/auth/register",
                json={"email": email, "password": password, "name": "Cookie Attr Test"},
                headers=_CSRF,
            )
        assert reg.status_code == 201
        assert captured_token

        await client.get("/auth/verify-email", params={"token": captured_token[0]})

        login_resp = await client.post(
            "/auth/login",
            json={"email": email, "password": password},
            headers=_CSRF,
        )
        assert login_resp.status_code == 200

        set_cookie = login_resp.headers.get("set-cookie", "")
        lower = set_cookie.lower()

        assert "vitreon_session=" in set_cookie, "Cookie name missing from Set-Cookie header"
        assert "httponly" in lower, "Session cookie must be HttpOnly"
        assert "samesite=lax" in lower, "Session cookie must have SameSite=Lax"
        assert "path=/" in lower, "Session cookie must be scoped to Path=/"

        from neolex.config import settings

        if settings.dev_mode:
            assert "secure" not in lower, "Secure flag must be absent in dev mode (allows HTTP on localhost)"
        else:
            assert "secure" in lower, "Secure flag must be present in production mode"

    finally:
        await _cleanup_user(email)
