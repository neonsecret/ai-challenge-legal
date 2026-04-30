"""Promocode service — effective subscription tier resolution.

Determines the user's effective subscription tier by combining their
paid subscription status with any active promo code upgrade.
"""

from datetime import datetime, timezone

# Tier rank: higher number = higher tier. Used to decide if a promo
# would upgrade the user (promo rank > current rank).
TIER_RANK = {
    "free": 0,
    "starter": 1,
    "pro": 2,
    "enterprise": 3,
}


def effective_subscription_tier(user) -> str:
    """Return the effective subscription tier for a user.

    Rules:
    1. Paid tier is the base: user.subscription_status or "free".
    2. If user has an active promo (promo_tier set, promo_expires_at > now UTC),
       and the promo tier outranks the paid tier, return the promo tier.
    3. Otherwise return the paid tier.

    Expired promos are ignored (no lazy cleanup — they just stop taking effect).
    """
    paid_tier = user.subscription_status or "free"
    # No promo tier set → return paid tier
    if not user.promo_tier or not user.promo_expires_at:
        return paid_tier
    # Promo expired → return paid tier
    now = datetime.now(timezone.utc)
    if user.promo_expires_at < now:
        return paid_tier
    # Promo active — check if it outranks paid tier
    promo_rank = TIER_RANK.get(user.promo_tier, 0)
    paid_rank = TIER_RANK.get(paid_tier, 0)
    if promo_rank > paid_rank:
        return user.promo_tier
    return paid_tier
