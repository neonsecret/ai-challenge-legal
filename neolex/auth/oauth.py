"""Google OAuth 2.0 routes via authlib + starlette.

Requires SessionMiddleware to be registered in main.py (for OAuth state CSRF).
"""

from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from neolex.auth.session import _set_session_cookie, create_session, get_current_user
from neolex.config import settings
from neolex.db.models import User
from neolex.db.postgres import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

_oauth = OAuth()
_oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/google")
async def google_login(request: Request):
    """Redirect user to Google's OAuth consent screen."""
    redirect_uri = request.url_for("google_callback")
    return await _oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback — upsert user, set session cookie."""
    token = await _oauth.google.authorize_access_token(request)
    userinfo = token["userinfo"]

    email: str = userinfo["email"]
    google_id: str = userinfo["sub"]
    name: str | None = userinfo.get("name")
    avatar_url: str | None = userinfo.get("picture")
    now = datetime.now(timezone.utc)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # New user — create with Google identity (free tier, 5 queries/month)
        user = User(
            email=email,
            google_id=google_id,
            name=name,
            avatar_url=avatar_url,
            email_verified=True,
            subscription_status="free",
            monthly_queries_used=0,
            daily_queries_used=0,
            max_corpora=0,
            last_login=now,
        )
        db.add(user)
        await db.flush()  # populate user.id before creating session
    elif user.google_id and user.google_id == google_id:
        # Returning Google user — update profile
        user.name = name or user.name
        user.avatar_url = avatar_url or user.avatar_url
        user.last_login = now
    elif not user.google_id:
        # Existing email/password user linking Google for the first time.
        # Only allow if the email is already verified (prevents takeover of
        # unverified accounts) AND Google confirms the email is verified.
        if not user.email_verified:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=403,
                content={"detail": "Please verify your email before linking Google."},
            )
        if not userinfo.get("email_verified", False):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=403,
                content={"detail": "Google email is not verified."},
            )
        user.google_id = google_id
        user.name = name or user.name
        user.avatar_url = avatar_url or user.avatar_url
        user.last_login = now
    else:
        # google_id mismatch — different Google account for same email
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content={"detail": "This email is already linked to a different Google account."},
        )

    ip = getattr(request.client, "host", None)
    user_agent = request.headers.get("user-agent")
    token_str = await create_session(user, db, ip=ip, user_agent=user_agent)

    response = RedirectResponse(url=f"{settings.frontend_url}/chat")
    _set_session_cookie(response, token_str)
    return response


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Delete server-side session and clear cookie."""
    from neolex.auth.session import hash_token
    from neolex.db.models import Session as DBSession

    token = request.cookies.get(settings.session_cookie_name)
    if token:
        result = await db.execute(select(DBSession).where(DBSession.token_hash == hash_token(token)))
        session = result.scalar_one_or_none()
        if session:
            await db.delete(session)
            await db.commit()

    response = RedirectResponse(url=settings.frontend_url)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not settings.dev_mode,
    )
    return response


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Return current user profile (used by frontend to check auth state)."""
    # Normalize legacy 'trial' to 'free' for the frontend
    effective_plan = "free" if user.subscription_status in ("free", "trial") else user.subscription_status
    return JSONResponse(
        {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "subscription_status": effective_plan,
            "plan": effective_plan,
            "monthly_queries_used": user.monthly_queries_used,
            "max_corpora": user.max_corpora,
        }
    )
