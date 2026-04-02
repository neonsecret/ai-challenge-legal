"""Server-side session management via PostgreSQL + HttpOnly cookie.

The cookie stores an opaque random token. The DB stores its SHA-256 hash.
This means even if someone reads the DB, they cannot forge sessions.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.config import settings
from neolex.db.models import Session as DBSession
from neolex.db.models import User
from neolex.db.postgres import get_db


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


MAX_SESSIONS_PER_USER = 10


async def create_session(
    user: User,
    db: AsyncSession,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Insert a session row and return the raw token (goes into the cookie).

    Evicts the oldest sessions when the per-user cap is reached.
    Commits the transaction — caller must NOT commit again after this.
    """
    # Evict oldest sessions if at or above the per-user cap.
    # FOR UPDATE serializes concurrent login requests for the same user.
    result = await db.execute(
        select(DBSession).where(DBSession.user_id == user.id).order_by(DBSession.created_at.asc()).with_for_update(),
    )
    existing = result.scalars().all()
    if len(existing) >= MAX_SESSIONS_PER_USER:
        for s in existing[: len(existing) - MAX_SESSIONS_PER_USER + 1]:
            await db.delete(s)
        await db.flush()

    token = generate_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.session_ttl_days)
    session = DBSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=expires_at,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(session)
    await db.commit()
    return token


def _set_session_cookie(response, token: str) -> None:
    """Attach the vitreon_session cookie to *response* in place."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.dev_mode,
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — returns the authenticated User or raises 401."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    now = datetime.now(UTC)
    result = await db.execute(
        select(DBSession).where(
            DBSession.token_hash == hash_token(token),
            DBSession.expires_at > now,
        ),
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    result2 = await db.execute(select(User).where(User.id == session.user_id))
    user = result2.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
