"""Email/password auth routes: register, login, verify-email, forgot/reset password, data export."""
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from neolex.auth.email_service import send_password_reset_email, send_verification_email
from neolex.auth.session import create_session, get_current_user, _set_session_cookie
from neolex.config import settings
from neolex.db.models import AuthToken, ConversationDocs, ConversationMessage, Session, User
from neolex.db.postgres import get_db
from neolex.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _auth_rate_check(request: Request, action: str) -> None:
    """Per-IP rate limiter for auth endpoints (10 attempts / 5 min)."""
    from neolex.db.audit import get_audit_db
    ip = getattr(request.client, "host", None) or "unknown"
    bucket = f"auth_{action}:{ip}"
    try:
        async with get_audit_db() as db:
            _, exceeded = await db.check_and_increment_rate(
                bucket=bucket, window_seconds=300.0, limit=10, now=time.time(),
            )
        if exceeded:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    except HTTPException:
        raise
    except Exception:
        pass  # Non-fatal — don't block auth if rate DB is unavailable


_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await _auth_rate_check(request, "register")
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        # Return same message to prevent email enumeration
        return {"message": "Check your email to verify your account."}

    now = datetime.now(timezone.utc)
    user = User(
        email=body.email,
        password_hash=_pwd.hash(body.password),
        name=body.name,
        email_verified=False,
        subscription_status="free",
        monthly_queries_used=0,
        daily_queries_used=0,
        max_corpora=0,
    )
    db.add(user)
    await db.flush()  # get user.id

    raw_token = secrets.token_urlsafe(32)
    db.add(AuthToken(
        user_id=user.id,
        token_hash=_hash(raw_token),
        token_type="email_verify",
        expires_at=now + timedelta(hours=24),
    ))
    await db.commit()

    await send_verification_email(body.email, raw_token)
    return {"message": "Check your email to verify your account."}


@router.get("/verify-email")
async def verify_email(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == _hash(token),
            AuthToken.token_type == "email_verify",
            AuthToken.expires_at > now,
            AuthToken.used_at == None,  # noqa: E711
        )
    )
    auth_token = result.scalar_one_or_none()
    if not auth_token:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    auth_token.used_at = now
    result2 = await db.execute(select(User).where(User.id == auth_token.user_id))
    user = result2.scalar_one()
    user.email_verified = True
    user.last_login = now

    ip = getattr(request.client, "host", None)
    raw_session = await create_session(user, db, ip=ip, user_agent=request.headers.get("user-agent"))

    response = RedirectResponse(url=f"{settings.frontend_url}/chat")
    _set_session_cookie(response, raw_session)
    return response


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await _auth_rate_check(request, "login")
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not _pwd.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    user.last_login = datetime.now(timezone.utc)
    ip = getattr(request.client, "host", None)
    raw_session = await create_session(user, db, ip=ip, user_agent=request.headers.get("user-agent"))

    response = JSONResponse({"message": "Login successful"})
    _set_session_cookie(response, raw_session)
    return response


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await _auth_rate_check(request, "forgot")
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Always 200 — never reveal whether an email is registered
    if user:
        now = datetime.now(timezone.utc)
        raw_token = secrets.token_urlsafe(32)
        db.add(AuthToken(
            user_id=user.id,
            token_hash=_hash(raw_token),
            token_type="password_reset",
            expires_at=now + timedelta(hours=1),
        ))
        await db.commit()
        await send_password_reset_email(body.email, raw_token)

    return {"message": "If this email is registered, you will receive a reset link."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == _hash(body.token),
            AuthToken.token_type == "password_reset",
            AuthToken.expires_at > now,
            AuthToken.used_at == None,  # noqa: E711
        )
    )
    auth_token = result.scalar_one_or_none()
    if not auth_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    auth_token.used_at = now
    result2 = await db.execute(select(User).where(User.id == auth_token.user_id))
    user = result2.scalar_one()
    user.password_hash = _pwd.hash(body.new_password)

    # Invalidate all other unused reset tokens for this user
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.token_type == "password_reset",
            AuthToken.used_at == None,  # noqa: E711
        ).values(used_at=now)
    )

    # Invalidate all existing sessions
    from neolex.db.models import Session as DBSession
    sessions = (await db.execute(select(DBSession).where(DBSession.user_id == user.id))).scalars()
    for s in sessions:
        await db.delete(s)

    await db.commit()
    return {"message": "Password reset successful. Please log in."}


@router.get("/my-data")
async def export_my_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all personal data (GDPR Article 20 — right to data portability).

    Returns the authenticated user's profile, conversation history, and
    accumulated document references as a structured JSON object.
    """
    # 1. User profile (exclude internal fields like password_hash)
    profile = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "email_verified": user.email_verified,
        "subscription_status": user.subscription_status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }

    # 2. Active sessions (metadata only — not the token hashes)
    sessions_result = await db.execute(
        select(Session).where(Session.user_id == user.id).order_by(Session.created_at.desc())
    )
    sessions = [
        {
            "created_at": s.created_at.isoformat(),
            "expires_at": s.expires_at.isoformat(),
            "ip": s.ip,
            "user_agent": s.user_agent,
        }
        for s in sessions_result.scalars()
    ]

    # 3. Conversation messages
    msgs_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.user_id == user.id)
        .order_by(ConversationMessage.created_at.asc())
    )
    conversations: dict[str, list[dict]] = {}
    for m in msgs_result.scalars():
        conv_id = str(m.conversation_id)
        conversations.setdefault(conv_id, []).append({
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        })

    # 4. Conversation docs (accumulated source references)
    docs_result = await db.execute(
        select(ConversationDocs).where(ConversationDocs.user_id == user.id)
    )
    conversation_docs = {
        str(d.conversation_id): d.docs_json
        for d in docs_result.scalars()
    }

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "sessions": sessions,
        "conversations": conversations,
        "conversation_docs": conversation_docs,
    }
