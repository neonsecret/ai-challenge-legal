"""Integration tests for session-based auth endpoints.

Scope: all auth endpoints NOT covered by NEO-267 (OAuth callback + session creation).
Uses a real PostgreSQL database. External calls (email, rate limiter) are mocked.

Run with:
    uv run pytest tests/integration/test_auth_endpoints.py -v
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

import neolex.db.postgres as _pg
from neolex.auth.session import MAX_SESSIONS_PER_USER, hash_token
from neolex.db.models import AuthToken, User
from neolex.db.models import Session as DBSession

# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_success(self, client, unique_email):
        resp = await client.post(
            "/auth/register",
            json={"email": unique_email, "password": "StrongPass1!", "name": "Alice"},
        )
        assert resp.status_code == 201
        assert "message" in resp.json()

    async def test_register_duplicate_email_returns_same_message(self, client, unique_email):
        """Duplicate email must NOT return 409 — that would reveal whether an email is registered."""
        payload = {"email": unique_email, "password": "StrongPass1!"}
        r1 = await client.post("/auth/register", json=payload)
        r2 = await client.post("/auth/register", json=payload)
        # Both must return 201 with the same neutral message (email enumeration prevention)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["message"] == r2.json()["message"]

    async def test_register_invalid_email(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "StrongPass1!"},
        )
        assert resp.status_code == 422

    async def test_register_password_too_short(self, client, unique_email):
        resp = await client.post(
            "/auth/register",
            json={"email": unique_email, "password": "short"},
        )
        assert resp.status_code == 422

    async def test_register_missing_email(self, client):
        resp = await client.post("/auth/register", json={"password": "StrongPass1!"})
        assert resp.status_code == 422

    async def test_register_creates_auth_token_in_db(self, client, mock_email_services, unique_email):
        """Registration must insert an email_verify AuthToken into the DB."""
        mock_verify, _ = mock_email_services
        await client.post(
            "/auth/register",
            json={"email": unique_email, "password": "StrongPass1!"},
        )
        token_raw = mock_verify.call_args[0][1]
        # Verify the token exists in the DB by re-hashing it
        import hashlib

        token_hash_val = hashlib.sha256(token_raw.encode()).hexdigest()
        async with _pg.AsyncSessionLocal() as db:
            result = await db.execute(
                select(AuthToken).where(
                    AuthToken.token_hash == token_hash_val,
                    AuthToken.token_type == "email_verify",
                )
            )
            auth_token = result.scalar_one_or_none()
        assert auth_token is not None
        assert auth_token.used_at is None


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_success_sets_cookie(self, client, verified_user):
        email, password = verified_user
        resp = await client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Login successful"
        assert "vitreon_session" in resp.cookies

    async def test_login_wrong_password(self, client, verified_user):
        email, _ = verified_user
        resp = await client.post("/auth/login", json={"email": email, "password": "WrongPass999!"})
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "AnyPass123!"},
        )
        assert resp.status_code == 401

    async def test_login_unverified_account(self, client, registered_user):
        """Unverified email (no verify-email step taken) must be rejected with 403."""
        email, password, _ = registered_user
        resp = await client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 403
        assert "verify" in resp.json()["detail"].lower()

    async def test_login_creates_db_session(self, client, verified_user):
        email, password = verified_user
        await client.post("/auth/login", json={"email": email, "password": password})
        session_token = client.cookies.get("vitreon_session")
        assert session_token is not None
        token_hash = hash_token(session_token)
        async with _pg.AsyncSessionLocal() as db:
            result = await db.execute(select(DBSession).where(DBSession.token_hash == token_hash))
            db_session = result.scalar_one_or_none()
        assert db_session is not None
        assert db_session.expires_at > datetime.now(UTC)


# ---------------------------------------------------------------------------
# GET /auth/verify-email
# ---------------------------------------------------------------------------


class TestVerifyEmail:
    async def test_verify_email_success_redirects(self, client, registered_user):
        _, _, token = registered_user
        resp = await client.get(f"/auth/verify-email?token={token}")
        assert resp.status_code in (302, 307)
        assert "vitreon_session" in resp.cookies

    async def test_verify_email_marks_user_verified(self, client, registered_user):
        email, _, token = registered_user
        await client.get(f"/auth/verify-email?token={token}")
        async with _pg.AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()
        assert user.email_verified is True

    async def test_verify_email_marks_token_used(self, client, registered_user):
        """After verification the AuthToken.used_at must be set."""
        import hashlib

        _, _, token = registered_user
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await client.get(f"/auth/verify-email?token={token}")
        async with _pg.AsyncSessionLocal() as db:
            result = await db.execute(select(AuthToken).where(AuthToken.token_hash == token_hash))
            auth_token = result.scalar_one()
        assert auth_token.used_at is not None

    async def test_verify_email_session_fixation_prevention(self, client, registered_user, db):
        """Old sessions must be deleted before a new one is created (session fixation prevention)."""
        email, _, token = registered_user

        # Insert a stale pre-existing session for the user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        stale_session = DBSession(
            user_id=user.id,
            token_hash=hash_token("stale-token-value"),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.add(stale_session)
        await db.commit()
        stale_id = stale_session.id

        # Now verify the email
        await client.get(f"/auth/verify-email?token={token}")

        # The stale session must have been deleted
        async with _pg.AsyncSessionLocal() as fresh_db:
            result = await fresh_db.execute(select(DBSession).where(DBSession.id == stale_id))
            assert result.scalar_one_or_none() is None

    async def test_verify_email_expired_token(self, client, registered_user, db):
        """Expired token must be rejected with 400."""
        import hashlib

        email, _, token = registered_user
        # Backdate the token's expiry
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(select(AuthToken).where(AuthToken.token_hash == token_hash))
        auth_token = result.scalar_one()
        auth_token.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()

        resp = await client.get(f"/auth/verify-email?token={token}")
        assert resp.status_code == 400

    async def test_verify_email_invalid_token(self, client):
        resp = await client.get("/auth/verify-email?token=completelyfaketoken123")
        assert resp.status_code == 400

    async def test_verify_email_reuse_rejected(self, client, registered_user):
        """Using the same token twice must fail on the second attempt."""
        _, _, token = registered_user
        r1 = await client.get(f"/auth/verify-email?token={token}")
        assert r1.status_code in (302, 307)
        client.cookies.clear()
        r2 = await client.get(f"/auth/verify-email?token={token}")
        assert r2.status_code == 400


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    async def test_logout_deletes_session_and_clears_cookie(self, client, verified_user):
        email, password = verified_user
        # Login to get a session
        await client.post("/auth/login", json={"email": email, "password": password})
        session_token = client.cookies.get("vitreon_session")
        assert session_token is not None

        # Logout
        resp = await client.post("/auth/logout")
        assert resp.status_code in (302, 307)

        # Session must be gone from DB
        token_hash = hash_token(session_token)
        async with _pg.AsyncSessionLocal() as db:
            result = await db.execute(select(DBSession).where(DBSession.token_hash == token_hash))
            assert result.scalar_one_or_none() is None

    async def test_logout_without_session_is_safe(self, client):
        """Logout with no active session must not raise — should redirect cleanly."""
        resp = await client.post("/auth/logout")
        assert resp.status_code in (302, 307)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


class TestGetMe:
    async def test_get_me_authenticated_returns_profile(self, client, verified_user):
        email, password = verified_user
        await client.post("/auth/login", json={"email": email, "password": password})
        resp = await client.get("/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == email
        assert "subscription_status" in body
        assert "monthly_queries_used" in body

    async def test_get_me_unauthenticated_returns_401(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_get_me_expired_session_returns_401(self, client, verified_user, db):
        """Artificially expire a session — /auth/me must reject it with 401."""
        email, password = verified_user
        await client.post("/auth/login", json={"email": email, "password": password})
        session_token = client.cookies.get("vitreon_session")
        assert session_token is not None

        # Backdate the session's expiry in DB
        token_hash = hash_token(session_token)
        result = await db.execute(select(DBSession).where(DBSession.token_hash == token_hash))
        session = result.scalar_one()
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()

        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_get_me_normalizes_trial_to_free(self, client, verified_user, db):
        """Legacy 'trial' subscription_status must be exposed as 'free' to the frontend."""
        email, password = verified_user
        # Set user's subscription_status to 'trial'
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.subscription_status = "trial"
        await db.commit()

        await client.post("/auth/login", json={"email": email, "password": password})
        resp = await client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"


# ---------------------------------------------------------------------------
# POST /auth/forgot-password
# ---------------------------------------------------------------------------


class TestForgotPassword:
    async def test_forgot_password_known_email_returns_200(self, client, verified_user):
        """Known email must return 200 with a generic message."""
        email, _ = verified_user
        resp = await client.post("/auth/forgot-password", json={"email": email})
        assert resp.status_code == 200
        assert "If this email" in resp.json()["message"]

    async def test_forgot_password_unknown_email_still_200(self, client):
        """Unknown email must return the SAME 200 response — no email enumeration."""
        resp = await client.post(
            "/auth/forgot-password",
            json={"email": "nobody_real@example.com"},
        )
        assert resp.status_code == 200
        assert "If this email" in resp.json()["message"]

    async def test_forgot_password_sends_reset_token(self, client, verified_user, mock_email_services):
        """A password-reset AuthToken must be created and emailed for known accounts."""
        import hashlib

        _, mock_reset = mock_email_services
        email, _ = verified_user
        await client.post("/auth/forgot-password", json={"email": email})

        assert mock_reset.called
        raw_token = mock_reset.call_args[0][1]
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        async with _pg.AsyncSessionLocal() as db:
            result = await db.execute(
                select(AuthToken).where(
                    AuthToken.token_hash == token_hash,
                    AuthToken.token_type == "password_reset",
                )
            )
            assert result.scalar_one_or_none() is not None

    async def test_forgot_password_unknown_email_sends_no_email(self, client, mock_email_services):
        """No email must be sent for addresses that are not registered."""
        _, mock_reset = mock_email_services
        await client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
        assert not mock_reset.called


# ---------------------------------------------------------------------------
# POST /auth/reset-password
# ---------------------------------------------------------------------------


class TestResetPassword:
    async def _get_reset_token(self, client, email, mock_email_services):
        _, mock_reset = mock_email_services
        await client.post("/auth/forgot-password", json={"email": email})
        return mock_reset.call_args[0][1]

    async def test_reset_password_success(self, client, verified_user, mock_email_services):
        email, old_password = verified_user
        token = await self._get_reset_token(client, email, mock_email_services)
        new_password = "NewPass456!"

        resp = await client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": new_password},
        )
        assert resp.status_code == 200
        assert "reset" in resp.json()["message"].lower()

        # Can now login with new password
        client.cookies.clear()
        login_resp = await client.post("/auth/login", json={"email": email, "password": new_password})
        assert login_resp.status_code == 200

    async def test_reset_password_invalidates_all_sessions(self, client, verified_user, mock_email_services, db):
        """Password reset must delete all existing sessions for the user."""
        email, password = verified_user
        # Create a session
        await client.post("/auth/login", json={"email": email, "password": password})
        session_token = client.cookies.get("vitreon_session")
        token_hash = hash_token(session_token)

        # Reset the password
        reset_token = await self._get_reset_token(client, email, mock_email_services)
        await client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "BrandNew789!"},
        )

        # The previous session must no longer exist
        result = await db.execute(select(DBSession).where(DBSession.token_hash == token_hash))
        assert result.scalar_one_or_none() is None

    async def test_reset_password_invalid_token(self, client):
        resp = await client.post(
            "/auth/reset-password",
            json={"token": "totallyinvalidtoken", "new_password": "ValidPass1!"},
        )
        assert resp.status_code == 400

    async def test_reset_password_expired_token(self, client, verified_user, mock_email_services, db):
        import hashlib

        email, _ = verified_user
        raw_token = await self._get_reset_token(client, email, mock_email_services)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Backdate the token
        result = await db.execute(select(AuthToken).where(AuthToken.token_hash == token_hash))
        auth_token = result.scalar_one()
        auth_token.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()

        resp = await client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "ValidPass1!"},
        )
        assert resp.status_code == 400

    async def test_reset_password_token_cannot_be_reused(self, client, verified_user, mock_email_services):
        email, _ = verified_user
        token = await self._get_reset_token(client, email, mock_email_services)

        r1 = await client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "FirstReset1!"},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "SecondReset1!"},
        )
        assert r2.status_code == 400


# ---------------------------------------------------------------------------
# Session expiry enforcement
# ---------------------------------------------------------------------------


class TestSessionExpiry:
    async def test_expired_session_rejected_by_get_me(self, client, verified_user, db):
        """An expired DBSession (expires_at in the past) must be rejected with 401."""
        email, password = verified_user
        await client.post("/auth/login", json={"email": email, "password": password})
        session_token = client.cookies.get("vitreon_session")

        # Force expiry in DB
        token_hash = hash_token(session_token)
        result = await db.execute(select(DBSession).where(DBSession.token_hash == token_hash))
        session = result.scalar_one()
        session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()

        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_valid_session_accepted(self, client, verified_user):
        email, password = verified_user
        await client.post("/auth/login", json={"email": email, "password": password})
        resp = await client.get("/auth/me")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Per-user session cap (MAX_SESSIONS_PER_USER = 10)
# ---------------------------------------------------------------------------


class TestSessionCap:
    async def test_session_cap_evicts_oldest(self, client, verified_user, db):
        """When MAX_SESSIONS_PER_USER is exceeded, the oldest session is evicted."""
        email, password = verified_user

        # Resolve user id
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()

        # verified_user leaves 1 session in the DB (from email verification).
        # Delete it so we have full control over the count before filling the cap.
        from sqlalchemy import delete as sql_delete

        await db.execute(sql_delete(DBSession).where(DBSession.user_id == user.id))
        await db.commit()

        # Insert MAX_SESSIONS_PER_USER sessions directly (backdated so we know which is oldest)
        oldest_token_hash = hash_token("oldest-session-token-known")
        oldest_session = DBSession(
            user_id=user.id,
            token_hash=oldest_token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        db.add(oldest_session)
        # Fill remaining cap slots with filler sessions (all newer than oldest)
        for i in range(MAX_SESSIONS_PER_USER - 1):
            db.add(
                DBSession(
                    user_id=user.id,
                    token_hash=hash_token(f"filler-session-{i}"),
                    expires_at=datetime.now(UTC) + timedelta(days=30),
                    created_at=datetime.now(UTC) - timedelta(days=9 - i),
                )
            )
        await db.commit()

        # Confirm we're exactly at the cap
        result = await db.execute(select(DBSession).where(DBSession.user_id == user.id))
        assert len(result.scalars().all()) == MAX_SESSIONS_PER_USER

        # Login creates the (cap + 1)th session → oldest must be evicted
        resp = await client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200

        async with _pg.AsyncSessionLocal() as fresh_db:
            # Total sessions must not exceed the cap
            count_result = await fresh_db.execute(select(DBSession).where(DBSession.user_id == user.id))
            sessions_after = count_result.scalars().all()
        assert len(sessions_after) == MAX_SESSIONS_PER_USER

        # The oldest session must have been evicted
        async with _pg.AsyncSessionLocal() as fresh_db:
            evicted = await fresh_db.execute(select(DBSession).where(DBSession.token_hash == oldest_token_hash))
            assert evicted.scalar_one_or_none() is None

    async def test_session_cap_is_ten(self):
        """Confirm the constant is 10 — any change must be a deliberate decision."""
        assert MAX_SESSIONS_PER_USER == 10
