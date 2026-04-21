"""Email/password auth routes: register, login, verify-email, forgot/reset password, data export, account deletion."""

import asyncio
import hashlib
import logging
import secrets
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from neolex.auth.email_service import send_password_reset_email, send_verification_email
from neolex.auth.session import _set_session_cookie, create_session, get_current_user
from neolex.config import settings
from neolex.db.models import (
    AuthToken,
    ConversationDocs,
    ConversationMessage,
    Invoice,
    Session,
    Subscription,
    User,
)
from neolex.db.postgres import get_db
from neolex.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _auth_rate_check(request: Request, action: str) -> None:
    """Per-IP rate limiter for auth endpoints (10 attempts / 5 min).

    Fails closed: rejects with 503 when the rate-limit DB is unavailable.
    A per-worker in-memory fallback would let attackers bypass limits by
    rotating across uvicorn workers (each worker has independent memory).
    """
    from neolex.db.audit import get_audit_db

    ip = getattr(request.client, "host", None) or "unknown"
    bucket = f"auth_{action}:{ip}"
    try:
        async with get_audit_db() as db:
            _, exceeded = await db.check_and_increment_rate(
                bucket=bucket,
                window_seconds=300.0,
                limit=10,
                now=time.time(),
            )
        if exceeded:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    except HTTPException:
        raise
    except Exception:
        logger.error("Rate limit DB unavailable for auth_%s; rejecting request for safety", action, exc_info=True)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again later.")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await _auth_rate_check(request, "register")
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        # Return same message to prevent email enumeration
        return {"message": "Check your email to verify your account."}

    now = datetime.now(UTC)
    user = User(
        email=body.email,
        password_hash=_hash_password(body.password),
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
    db.add(
        AuthToken(
            user_id=user.id,
            token_hash=_hash(raw_token),
            token_type="email_verify",
            expires_at=now + timedelta(hours=24),
        ),
    )
    await db.commit()

    await send_verification_email(body.email, raw_token)
    return {"message": "Check your email to verify your account."}


@router.get("/verify-email")
async def verify_email(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    now = datetime.now(UTC)
    # Atomic claim: UPDATE ... WHERE used_at IS NULL prevents concurrent reuse.
    result = await db.execute(
        sql_update(AuthToken)
        .where(
            AuthToken.token_hash == _hash(token),
            AuthToken.token_type == "email_verify",
            AuthToken.expires_at > now,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=now)
        .returning(AuthToken.user_id),
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    user_id = row[0]

    result2 = await db.execute(select(User).where(User.id == user_id))
    user = result2.scalar_one()
    user.email_verified = True
    user.last_login = now

    # Invalidate existing sessions to prevent session fixation
    await db.execute(sql_delete(Session).where(Session.user_id == user.id))

    # Commit before create_session so get_current_user can find both session and user.
    # See oauth.py for the same pattern.
    await db.commit()

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

    if not user or not user.password_hash or not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    user.last_login = datetime.now(UTC)

    # Commit last_login before create_session so get_current_user can find both
    # the session and the updated user row. See oauth.py for the same pattern.
    await db.commit()

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
        now = datetime.now(UTC)
        raw_token = secrets.token_urlsafe(32)
        db.add(
            AuthToken(
                user_id=user.id,
                token_hash=_hash(raw_token),
                token_type="password_reset",
                expires_at=now + timedelta(hours=1),
            ),
        )
        await db.commit()
        await send_password_reset_email(body.email, raw_token)

    return {"message": "If this email is registered, you will receive a reset link."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await _auth_rate_check(request, "reset")
    now = datetime.now(UTC)
    # Atomic claim: UPDATE ... WHERE used_at IS NULL prevents concurrent reuse.
    result = await db.execute(
        sql_update(AuthToken)
        .where(
            AuthToken.token_hash == _hash(body.token),
            AuthToken.token_type == "password_reset",
            AuthToken.expires_at > now,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=now)
        .returning(AuthToken.user_id),
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    user_id = row[0]

    result2 = await db.execute(select(User).where(User.id == user_id))
    user = result2.scalar_one()
    user.password_hash = _hash_password(body.new_password)

    # Invalidate all other unused reset tokens for this user
    await db.execute(
        sql_update(AuthToken)
        .where(
            AuthToken.user_id == user.id,
            AuthToken.token_type == "password_reset",
            AuthToken.used_at.is_(None),
        )
        .values(used_at=now),
    )

    # Invalidate all existing sessions
    from neolex.db.models import Session as DBSession

    sessions = (await db.execute(select(DBSession).where(DBSession.user_id == user.id))).scalars().all()
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
        select(Session).where(Session.user_id == user.id).order_by(Session.created_at.desc()),
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
        .order_by(ConversationMessage.created_at.asc()),
    )
    conversations: dict[str, list[dict]] = {}
    for m in msgs_result.scalars():
        conv_id = str(m.conversation_id)
        conversations.setdefault(conv_id, []).append(
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            },
        )

    # 4. Conversation docs (accumulated source references)
    docs_result = await db.execute(select(ConversationDocs).where(ConversationDocs.user_id == user.id))
    conversation_docs = {str(d.conversation_id): d.docs_json for d in docs_result.scalars()}

    # 5. Uploaded corpus metadata (GDPR Article 20 — portability; raw file bytes excluded)
    from neolex.services.document_manager import list_documents as _list_documents

    client_slug = str(user.id)
    raw_docs = await asyncio.to_thread(_list_documents, client_slug)
    corpora = [
        {
            "doc_id": d.get("doc_id"),
            "filename": d.get("filename"),
            "collection": d.get("collection"),
            "uploaded_at": d.get("uploaded_at"),
            "size_bytes": d.get("size_bytes"),
        }
        for d in raw_docs
    ]

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": profile,
        "sessions": sessions,
        "conversations": conversations,
        "conversation_docs": conversation_docs,
        "corpora": corpora,
    }


# ---------------------------------------------------------------------------
# Account deletion (GDPR Article 17 — right to erasure)
# ---------------------------------------------------------------------------


@router.delete("/delete-account", status_code=204)
async def delete_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Permanently delete the authenticated user's account and all associated data.

    This is irreversible. It cancels any active Stripe subscription, removes
    all conversations, documents, sessions, tokens, invoices, uploaded corpora
    files, audit records, and finally the user record itself.
    """
    user_id = user.id
    client_slug = str(user_id)

    # 1. Cancel active Stripe subscriptions
    await _cancel_stripe_subscriptions(user, db)

    # 2. Delete conversation messages
    await db.execute(sql_delete(ConversationMessage).where(ConversationMessage.user_id == user_id))

    # 3. Delete conversation docs
    await db.execute(sql_delete(ConversationDocs).where(ConversationDocs.user_id == user_id))

    # 4. Delete subscriptions (DB records)
    await db.execute(sql_delete(Subscription).where(Subscription.user_id == user_id))

    # 5. Delete invoices
    await db.execute(sql_delete(Invoice).where(Invoice.user_id == user_id))

    # 6. Delete sessions
    await db.execute(sql_delete(Session).where(Session.user_id == user_id))

    # 7. Delete auth tokens
    await db.execute(sql_delete(AuthToken).where(AuthToken.user_id == user_id))

    # 8. Delete uploaded corpus files and audit DB records
    await _delete_client_data(client_slug)

    # 8b. Delete audit log entries (queries, events) linked to this user's API keys
    await _delete_user_audit_logs(client_slug)

    # 9. Delete the user record
    await db.execute(sql_delete(User).where(User.id == user_id))

    await db.commit()
    logger.info("Account deleted: user_id=%s", user_id)

    # 10. Clear the session cookie
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not settings.dev_mode,
    )
    return response


async def _delete_user_audit_logs(client_slug: str) -> None:
    """Delete audit log entries (queries, events, api_keys) for a user.

    GDPR Article 17 requires full erasure — failures must propagate so the
    caller can rollback and surface an error instead of claiming success.
    """
    from sqlalchemy import delete as sa_delete
    from sqlalchemy import select as sa_select

    from neolex.db.audit import get_audit_db
    from neolex.db.operational_models import ApiKey, Event, Query

    async with get_audit_db() as audit_db:
        session = audit_db.get_session()

        result = await session.execute(sa_select(ApiKey.key_hash).where(ApiKey.client_slug == client_slug))
        key_hashes = [row[0] for row in result.all()]

        if key_hashes:
            del_queries = await session.execute(sa_delete(Query).where(Query.key_hash.in_(key_hashes)))
            del_events = await session.execute(sa_delete(Event).where(Event.key_hash.in_(key_hashes)))
            logger.info(
                "Deleted %d queries and %d events for client %s",
                del_queries.rowcount,
                del_events.rowcount,
                client_slug,
            )

        del_keys = await session.execute(sa_delete(ApiKey).where(ApiKey.client_slug == client_slug))
        logger.info("Deleted %d API keys for client %s", del_keys.rowcount, client_slug)


async def _cancel_stripe_subscriptions(user: User, db: AsyncSession) -> None:
    """Cancel all active Stripe subscriptions for the user."""
    if not user.stripe_customer_id:
        return

    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "trialing", "past_due"]),
        ),
    )
    active_subs = result.scalars().all()

    import stripe

    stripe.api_key = settings.stripe_secret_key

    for sub in active_subs:
        try:
            await asyncio.to_thread(stripe.Subscription.cancel, sub.stripe_subscription_id)
            logger.info(
                "Cancelled Stripe subscription %s for user %s",
                sub.stripe_subscription_id,
                user.id,
            )
        except Exception:
            logger.exception(
                "Failed to cancel Stripe subscription %s for user %s",
                sub.stripe_subscription_id,
                user.id,
            )


async def _delete_client_data(client_slug: str) -> None:
    """Delete uploaded corpus files from disk and audit DB records.

    CRITICAL: validates the path stays within data/clients/ to prevent
    directory traversal attacks. Never deletes built-in indexes (DIFC, Czech).
    """
    # Validate client_slug: must be a UUID-like string, no path separators
    if "/" in client_slug or "\\" in client_slug or ".." in client_slug:
        logger.error("Refusing to delete data for suspicious client_slug: %s", client_slug)
        return

    clients_root = Path(settings.data_dir).resolve() / "clients"
    client_dir = (clients_root / client_slug).resolve()

    # Path traversal guard: ensure resolved path is under data/clients/
    if not str(client_dir).startswith(str(clients_root)):
        logger.error(
            "Path traversal detected: client_dir=%s not under %s",
            client_dir,
            clients_root,
        )
        return

    # Delete audit DB records for this client — GDPR erasure must fail loudly
    # if cleanup fails so the caller can rollback and surface the error.
    from neolex.db.audit import get_audit_db

    async with get_audit_db() as audit_db:
        docs = await audit_db.list_documents(client_slug)
        for doc in docs:
            await audit_db.delete_document(doc["doc_id"], client_slug)

    # Delete the entire client directory (docs + index)
    if client_dir.exists():
        shutil.rmtree(str(client_dir))
        logger.info("Deleted client directory: %s", client_dir)
