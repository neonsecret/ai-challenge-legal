"""Billing helpers: effective plan resolution and promocode redemption."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from neolex.db.models import User

# Tier rank — higher rank = more privileged
_TIER_RANK: dict[str, int] = {
    "free": 0,
    "trial": 0,
    "starter": 1,
    "pro": 2,
    "enterprise": 3,
}


def effective_subscription_tier(user: "User") -> str:
    """Return the highest-ranked plan between paid tier and active promo.

    Clears expired promo fields on the user object (caller must commit).
    """
    paid = user.subscription_status or "free"
    paid_normalized = paid if paid in _TIER_RANK else "free"

    promo = user.promo_tier
    promo_exp = user.promo_expires_at

    if promo and promo_exp:
        now = datetime.now(UTC)
        # Ensure promo_exp is timezone-aware for comparison
        if promo_exp.tzinfo is None:
            promo_exp = promo_exp.replace(tzinfo=UTC)
        if promo_exp > now:
            promo_rank = _TIER_RANK.get(promo, 0)
            paid_rank = _TIER_RANK.get(paid_normalized, 0)
            if promo_rank > paid_rank:
                return promo
        else:
            # Expire lazily
            user.promo_tier = None
            user.promo_expires_at = None

    return paid_normalized


# ---------------------------------------------------------------------------
# Per-user redemption rate limiter (in-memory, 5 attempts / hour)
# ---------------------------------------------------------------------------

_promo_attempts: dict[str, list[float]] = defaultdict(list)
_promo_lock = Lock()
_PROMO_RATE_WINDOW = 3600  # 1 hour
_PROMO_RATE_LIMIT = 5


def _check_promo_rate_limit(user_id: str) -> None:
    """Raise 429 if user has exceeded 5 redemption attempts in the last hour."""
    now = time.monotonic()
    with _promo_lock:
        attempts = _promo_attempts[user_id]
        cutoff = now - _PROMO_RATE_WINDOW
        # Evict old entries
        _promo_attempts[user_id] = [t for t in attempts if t > cutoff]
        if len(_promo_attempts[user_id]) >= _PROMO_RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        _promo_attempts[user_id].append(now)


async def redeem_promocode(code: str, user: "User", db: "AsyncSession") -> dict:
    """Attempt to redeem a promocode for a user.

    Returns updated billing-status fields: promo_tier, promo_expires_at.
    Raises HTTPException on all failure modes with generic error messages.
    """
    from neolex.db.models import Promocode, PromocodeRedemption

    _check_promo_rate_limit(str(user.id))

    # Use the existing autobegin transaction — no nested db.begin()
    result = await db.execute(
        select(Promocode).where(Promocode.code == code, Promocode.active.is_(True)).with_for_update()
    )
    promo = result.scalar_one_or_none()

    now = datetime.now(UTC)

    # 404 for missing/inactive/expired code — generic message, no distinction
    if promo is None:
        raise HTTPException(status_code=404, detail="Invalid promocode")
    if promo.valid_until is not None:
        vu = promo.valid_until if promo.valid_until.tzinfo else promo.valid_until.replace(tzinfo=UTC)
        if vu < now:
            raise HTTPException(status_code=404, detail="Invalid promocode")

    # 409 exhausted
    if promo.max_redemptions is not None and promo.redemption_count >= promo.max_redemptions:
        raise HTTPException(status_code=409, detail="Promocode no longer available")

    # 409 already redeemed by this user
    existing = await db.execute(
        select(PromocodeRedemption).where(
            PromocodeRedemption.promocode_id == promo.id,
            PromocodeRedemption.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="You have already used this promocode")

    # 409 downgrade / same tier
    current_tier = effective_subscription_tier(user)
    promo_rank = _TIER_RANK.get(promo.tier, 0)
    current_rank = _TIER_RANK.get(current_tier, 0)
    if promo_rank <= current_rank:
        raise HTTPException(status_code=409, detail="This promocode would not upgrade your plan")

    # Apply
    expires_at = now + timedelta(days=promo.duration_days)
    db.add(
        PromocodeRedemption(
            promocode_id=promo.id,
            user_id=user.id,
            granted_tier=promo.tier,
            redeemed_at=now,
            expires_at=expires_at,
        )
    )
    promo.redemption_count += 1
    user.promo_tier = promo.tier
    user.promo_expires_at = expires_at
    await db.flush()

    return {
        "promo_tier": promo.tier,
        "promo_expires_at": expires_at.isoformat(),
    }
