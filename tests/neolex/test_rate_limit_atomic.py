"""Tests for atomic rate-limit operations (NEO-2244).

Bug A: _enforce_query_limit reset race — reset+increment must be one SQL statement.
Bug B: check_and_increment_rate TOCTOU — must use INSERT...ON CONFLICT upsert.
Bug C: _auth_rate_check per-worker fallback — must fail closed when DB is unavailable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bug A: _enforce_query_limit atomic reset+increment
# ---------------------------------------------------------------------------


class TestEnforceQueryLimitAtomic:
    """_enforce_query_limit must combine reset and increment into one SQL statement."""

    def _make_user(self, status="starter", used=0, reset_at=None):
        u = MagicMock()
        u.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        u.subscription_status = status
        u.daily_queries_used = used
        u.daily_queries_reset_at = reset_at
        u.promo_tier = None
        u.promo_expires_at = None
        return u

    def _make_db(self, scalar_return):
        """Return a mock AsyncSession whose execute().scalar_one_or_none() returns scalar_return."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = scalar_return
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.commit = AsyncMock()
        return db

    async def test_limited_plan_within_limit_allowed(self):
        """When DB returns a count, the request is allowed through."""
        from neolex.routers.query import _enforce_query_limit

        user = self._make_user(status="starter", used=5)
        db = self._make_db(scalar_return=6)  # DB says new count = 6

        await _enforce_query_limit(user, db)  # must not raise

        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    async def test_limited_plan_at_limit_raises_429(self):
        """When DB returns None (no rows updated = at cap), must raise 429."""
        from fastapi import HTTPException

        from neolex.routers.query import _enforce_query_limit

        user = self._make_user(status="starter", used=30)
        db = self._make_db(scalar_return=None)  # no rows updated = limit hit

        with pytest.raises(HTTPException) as exc:
            await _enforce_query_limit(user, db)

        assert exc.value.status_code == 429
        assert "Daily limit reached" in exc.value.detail

    async def test_reset_and_increment_is_single_execute(self):
        """A single db.execute call means reset+increment are atomic — not two transactions."""
        from neolex.routers.query import _enforce_query_limit

        yesterday = datetime.now(UTC) - timedelta(days=1)
        user = self._make_user(status="starter", used=25, reset_at=yesterday)
        db = self._make_db(scalar_return=1)  # reset → count starts at 1

        await _enforce_query_limit(user, db)

        # Exactly one execute call: reset + increment are one atomic statement.
        # Old code issued two: one for reset, one for increment.
        assert db.execute.await_count == 1
        assert db.commit.await_count == 1

    async def test_unlimited_plan_single_execute(self):
        """Enterprise plan also uses a single execute call (no cap check needed)."""
        from neolex.routers.query import _enforce_query_limit

        user = self._make_user(status="enterprise", used=199)
        db = self._make_db(scalar_return=None)  # RETURNING not used for unlimited

        await _enforce_query_limit(user, db)

        assert db.execute.await_count == 1
        assert db.commit.await_count == 1

    async def test_inactive_status_raises_402(self):
        """Unknown/canceled subscription must raise 402 before touching the DB."""
        from fastapi import HTTPException

        from neolex.routers.query import _enforce_query_limit

        user = self._make_user(status="canceled")
        db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await _enforce_query_limit(user, db)

        assert exc.value.status_code == 402
        db.execute.assert_not_awaited()

    async def test_free_plan_at_limit_raises_429(self):
        """Free plan (limit=10) at limit must be blocked."""
        from fastapi import HTTPException

        from neolex.routers.query import _enforce_query_limit

        user = self._make_user(status="free", used=10)
        db = self._make_db(scalar_return=None)

        with pytest.raises(HTTPException) as exc:
            await _enforce_query_limit(user, db)

        assert exc.value.status_code == 429

    async def test_sql_contains_returning(self):
        """The SQL must use RETURNING so the caller knows the new count without a second query."""

        from neolex.routers.query import _enforce_query_limit

        user = self._make_user(status="starter", used=5)

        captured_sql: list[str] = []

        async def capture_execute(stmt, params=None):
            if hasattr(stmt, "text"):
                captured_sql.append(stmt.text)
            elif isinstance(stmt, str):
                captured_sql.append(stmt)
            result = MagicMock()
            result.scalar_one_or_none.return_value = 6
            return result

        db = AsyncMock()
        db.execute = capture_execute
        db.commit = AsyncMock()

        await _enforce_query_limit(user, db)

        assert any("RETURNING" in s.upper() for s in captured_sql), (
            "Expected RETURNING in atomic UPDATE statement; found: " + repr(captured_sql)
        )


# ---------------------------------------------------------------------------
# Bug B: check_and_increment_rate atomic upsert
# ---------------------------------------------------------------------------


class TestCheckAndIncrementRateAtomic:
    """check_and_increment_rate must use a single atomic upsert, not SELECT then INSERT/UPDATE."""

    def _make_session(self, count: int):
        result = MagicMock()
        result.scalar_one.return_value = count
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        return session

    async def test_first_request_returns_1_not_exceeded(self):
        """First hit in a window: count=1, below any reasonable limit."""
        from neolex.db.audit import AuditDB

        session = self._make_session(count=1)
        db = AuditDB(session)

        count, exceeded = await db.check_and_increment_rate("b1", 300.0, 10, 1000.0)

        assert count == 1
        assert exceeded is False
        session.execute.assert_awaited_once()

    async def test_returns_exceeded_when_count_over_limit(self):
        """When DB returns count > limit, exceeded must be True."""
        from neolex.db.audit import AuditDB

        session = self._make_session(count=11)
        db = AuditDB(session)

        count, exceeded = await db.check_and_increment_rate("b2", 300.0, 10, 1000.0)

        assert count == 11
        assert exceeded is True

    async def test_exactly_at_limit_is_not_exceeded(self):
        """count == limit: the limit-th request is still allowed (exceeded uses strict >)."""
        from neolex.db.audit import AuditDB

        session = self._make_session(count=10)
        db = AuditDB(session)

        count, exceeded = await db.check_and_increment_rate("b3", 300.0, 10, 1000.0)

        assert count == 10
        assert exceeded is False  # 10 > 10 is False; 11th request would be exceeded

    async def test_exactly_one_db_call(self):
        """Must issue exactly one execute() — no separate SELECT before INSERT."""
        from neolex.db.audit import AuditDB

        session = self._make_session(count=3)
        db = AuditDB(session)

        await db.check_and_increment_rate("b4", 300.0, 10, 1000.0)

        assert session.execute.await_count == 1

    async def test_sql_uses_on_conflict(self):
        """The SQL must contain ON CONFLICT to be a real upsert."""
        from neolex.db.audit import AuditDB

        captured_sql: list[str] = []

        async def capture_execute(stmt, params=None):
            if hasattr(stmt, "text"):
                captured_sql.append(stmt.text)
            result = MagicMock()
            result.scalar_one.return_value = 1
            return result

        session = AsyncMock()
        session.execute = capture_execute
        db = AuditDB(session)

        await db.check_and_increment_rate("bucket", 300.0, 10, 1000.0)

        assert any("ON CONFLICT" in s.upper() for s in captured_sql), (
            "check_and_increment_rate must use ON CONFLICT upsert; found: " + repr(captured_sql)
        )


# ---------------------------------------------------------------------------
# Bug C: _auth_rate_check fail-closed on DB unavailability
# ---------------------------------------------------------------------------


class TestAuthRateCheckFailClosed:
    """_auth_rate_check must raise 503 (not pass through) when DB is unavailable."""

    def _make_request(self, ip="1.2.3.4"):
        req = MagicMock()
        req.client = MagicMock()
        req.client.host = ip
        return req

    async def test_db_unavailable_raises_503(self):
        """Simulate DB failure: must reject the request with 503, not allow it through."""
        from contextlib import asynccontextmanager

        from fastapi import HTTPException

        from neolex.auth.email_auth import _auth_rate_check

        @asynccontextmanager
        async def failing_audit_db():
            raise RuntimeError("connection refused")
            yield  # noqa: RET504

        with patch("neolex.db.audit.get_audit_db", failing_audit_db):
            with pytest.raises(HTTPException) as exc:
                await _auth_rate_check(self._make_request(), "login")

        assert exc.value.status_code == 503
        assert "unavailable" in exc.value.detail.lower()

    async def test_db_available_not_exceeded_passes(self):
        """Happy path: DB responds, count below limit, request is allowed."""
        from contextlib import asynccontextmanager

        from neolex.auth.email_auth import _auth_rate_check

        mock_audit = AsyncMock()
        mock_audit.check_and_increment_rate = AsyncMock(return_value=(1, False))

        @asynccontextmanager
        async def ok_audit_db():
            yield mock_audit

        with patch("neolex.db.audit.get_audit_db", ok_audit_db):
            await _auth_rate_check(self._make_request(), "login")  # must not raise

    async def test_db_available_exceeded_raises_429(self):
        """When DB says limit exceeded, must raise 429."""
        from contextlib import asynccontextmanager

        from fastapi import HTTPException

        from neolex.auth.email_auth import _auth_rate_check

        mock_audit = AsyncMock()
        mock_audit.check_and_increment_rate = AsyncMock(return_value=(11, True))

        @asynccontextmanager
        async def ok_audit_db():
            yield mock_audit

        with patch("neolex.db.audit.get_audit_db", ok_audit_db):
            with pytest.raises(HTTPException) as exc:
                await _auth_rate_check(self._make_request(), "login")

        assert exc.value.status_code == 429

    async def test_no_fallback_dict_in_module(self):
        """Verify the per-worker fallback dict has been removed from the module."""
        import neolex.auth.email_auth as m

        assert not hasattr(m, "_fallback_rates"), (
            "_fallback_rates per-worker dict must be removed; it lets attackers bypass rate limits by rotating workers"
        )
