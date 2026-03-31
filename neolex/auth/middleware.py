"""FastAPI auth dependencies — session-based authentication.

All endpoints requiring authentication use:
  - get_current_user()  → returns User ORM object
  - get_auth()          → returns dict with client_slug/scope (for routers that expect key_row shape)
  - get_admin()         → requires active subscription
"""
from fastapi import Depends

from neolex.auth.session import get_current_user
from neolex.db.models import User


async def get_auth(user: User = Depends(get_current_user)) -> dict:
    """Auth dependency returning a dict for routers that use key_row["client_slug"] etc.

    client_slug is scoped to the user ID for corpus isolation — each user
    gets their own document namespace so they can't see/delete others' files.
    """
    return {
        "user_id": str(user.id),
        "email": user.email,
        "client_slug": str(user.id),
        "scope": "admin",
        "key_hash": f"session:{user.id}",
        "key_prefix": "session",
        "name": user.name or user.email,
    }


# Aliases for backward compat in routers
get_api_key = get_auth
get_admin_key = get_auth
