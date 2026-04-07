"""Stripe Checkout and webhook routes — tiered subscription system.

Plans: free, starter, pro, enterprise, business (custom).
Intervals: monthly, biweekly.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import stripe
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from neolex.auth.session import get_current_user
from neolex.config import settings
from neolex.db.models import Invoice, Subscription, User
from neolex.db.postgres import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["billing"])

stripe.api_key = settings.stripe_secret_key

# Webhook idempotency — simple in-memory set (OK for single-instance;
# use Redis for multi-instance).
from collections import OrderedDict

_processed_events: OrderedDict[str, None] = OrderedDict()
_MAX_PROCESSED = 10_000


# ---------------------------------------------------------------------------
# Price ID <-> plan name mapping
# ---------------------------------------------------------------------------

_PRICE_TO_PLAN: dict[str, str] = {}
_PLAN_INTERVAL_TO_PRICE: dict[tuple[str, str], str] = {}

# Plan limits for billing-status response
_PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "daily_limit": 3,
        "monthly_limit": None,
        "max_corpora": 0,
        "max_docs_per_corpus": 0,
        "max_corpus_size_mb": 0,
    },
    "starter": {
        "daily_limit": settings.starter_daily_limit,
        "monthly_limit": None,
        "max_corpora": settings.starter_max_corpora,
        "max_docs_per_corpus": settings.starter_max_docs_per_corpus,
        "max_corpus_size_mb": settings.starter_max_corpus_size_mb,
    },
    "pro": {
        "daily_limit": settings.pro_daily_limit,
        "monthly_limit": None,
        "max_corpora": settings.pro_max_corpora,
        "max_docs_per_corpus": settings.pro_max_docs_per_corpus,
        "max_corpus_size_mb": settings.pro_max_corpus_size_mb,
    },
    "enterprise": {
        "daily_limit": 0,  # 0 = unlimited
        "monthly_limit": None,
        "max_corpora": settings.enterprise_max_corpora,
        "max_docs_per_corpus": settings.enterprise_max_docs_per_corpus,
        "max_corpus_size_mb": settings.enterprise_max_corpus_size_mb,
    },
}


def _init_price_maps() -> None:
    """Build bidirectional price <-> plan mappings from settings."""
    pairs = [
        ("starter", "monthly", settings.stripe_price_starter_monthly),
        ("starter", "biweekly", settings.stripe_price_starter_biweekly),
        ("pro", "monthly", settings.stripe_price_pro_monthly),
        ("pro", "biweekly", settings.stripe_price_pro_biweekly),
        ("enterprise", "monthly", settings.stripe_price_enterprise_monthly),
        ("enterprise", "biweekly", settings.stripe_price_enterprise_biweekly),
    ]
    for plan, interval, price_id in pairs:
        if price_id:
            _PRICE_TO_PLAN[price_id] = plan
            _PLAN_INTERVAL_TO_PRICE[(plan, interval)] = price_id


_init_price_maps()


def _ensure_price_maps() -> None:
    """Re-initialise price maps if empty (guards against import-before-dotenv edge cases)."""
    if not _PLAN_INTERVAL_TO_PRICE:
        _init_price_maps()


def _plan_from_price(price_id: str) -> str:
    """Map a Stripe price ID back to a plan name. Falls back to 'free' (least privileged)."""
    plan = _PRICE_TO_PLAN.get(price_id)
    if plan is None:
        logger.warning("Unknown Stripe price ID: %s — defaulting to 'free'", price_id)
        return "free"
    return plan


def _max_corpora_for_plan(plan: str) -> int:
    """Return the max_corpora value for a plan name."""
    limits = _PLAN_LIMITS.get(plan, _PLAN_LIMITS["free"])
    return limits["max_corpora"]


# ---------------------------------------------------------------------------
# Corpus cleanup helper
# ---------------------------------------------------------------------------


async def _delete_user_corpora(user: User) -> None:
    """Delete all uploaded corpora for a user (called on cancel / account delete).

    This runs filesystem + DB cleanup in the background. Errors are logged but
    do not propagate — billing state updates must not fail because of cleanup.
    """
    try:
        import shutil

        from neolex.db.audit import get_audit_db
        from neolex.services.document_manager import client_docs_dir

        client_slug = str(user.id)  # user-scoped corpus isolation

        # Delete all documents from audit DB
        async with get_audit_db() as db:
            docs = await db.list_documents(client_slug)
            for doc in docs:
                await db.delete_document(doc["doc_id"], client_slug)

        # Remove the client docs directory
        docs_dir = client_docs_dir(client_slug)
        if docs_dir.exists():
            await asyncio.to_thread(shutil.rmtree, str(docs_dir), True)
            logger.info("Deleted corpus directory for user %s", user.id)

    except Exception:
        logger.exception("Failed to clean up corpora for user %s", user.id)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    plan: str  # starter | pro | enterprise
    interval: str = "monthly"  # monthly | biweekly


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for a specific plan and interval."""
    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Billing not enabled yet")

    _ensure_price_maps()

    if body.plan not in ("starter", "pro", "enterprise"):
        raise HTTPException(status_code=400, detail=f"Invalid plan: {body.plan}")
    if body.interval not in ("monthly", "biweekly"):
        raise HTTPException(status_code=400, detail=f"Invalid interval: {body.interval}")

    price_id = _PLAN_INTERVAL_TO_PRICE.get((body.plan, body.interval))
    logger.info(
        "Checkout requested: plan=%s interval=%s → price_id=%s (map_size=%d)",
        body.plan,
        body.interval,
        price_id,
        len(_PLAN_INTERVAL_TO_PRICE),
    )
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"No price configured for {body.plan}/{body.interval}",
        )

    if not user.stripe_customer_id:
        try:
            customer = await asyncio.to_thread(stripe.Customer.create, email=user.email, name=user.name or user.email)
        except stripe.StripeError as err:
            logger.exception("Failed to create Stripe customer for user %s", user.id)
            raise HTTPException(status_code=502, detail="Could not reach payment provider. Please try again.") from err
        user.stripe_customer_id = customer.id
        await db.commit()

    # Check for existing active subscription to handle upgrade/switch correctly.
    # Store old subscription ID in checkout metadata so _on_checkout_completed
    # can cancel it once the new subscription is active — prevents double billing.
    metadata: dict[str, str] = {"plan": body.plan, "interval": body.interval}
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
        .limit(1),
    )
    old_sub = result.scalar_one_or_none()
    if old_sub:
        metadata["previous_subscription_id"] = old_sub.stripe_subscription_id

    session = await asyncio.to_thread(
        stripe.checkout.Session.create,
        customer=user.stripe_customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/billing",
        metadata=metadata,
    )
    return JSONResponse({"url": session.url})


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except stripe.SignatureVerificationError as err:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid payload") from err

    # Idempotency guard — skip already-processed webhook events.
    event_id = event.id
    if event_id in _processed_events:
        logger.info("Duplicate webhook event %s, skipping", event_id)
        return JSONResponse({"status": "duplicate"})
    _processed_events[event_id] = None
    while len(_processed_events) > _MAX_PROCESSED:
        _processed_events.popitem(last=False)  # LRU eviction — removes oldest

    etype = event.type

    # Convert StripeObject to plain dict so handlers can use .get() safely.
    # Recursively convert via _serialize helper to handle Decimal values.
    def _serialize(obj):
        if hasattr(obj, "to_dict"):
            return {k: _serialize(v) for k, v in obj.to_dict().items()}
        if isinstance(obj, list):
            return [_serialize(i) for i in obj]
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        try:
            from decimal import Decimal

            if isinstance(obj, Decimal):
                return float(obj)
        except ImportError:
            pass
        return obj

    data = _serialize(event.data.object)

    if etype == "checkout.session.completed":
        await _on_checkout_completed(data, db)
    elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
        await _on_subscription_changed(data, db)
    elif etype == "invoice.payment_failed":
        await _on_payment_failed(data, db)
    elif etype == "invoice.paid":
        await _on_invoice_paid(data, db)

    return JSONResponse({"received": True})


@router.get("/customer-portal")
async def customer_portal(user: User = Depends(get_current_user)):
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account")

    portal = await asyncio.to_thread(
        stripe.billing_portal.Session.create,
        customer=user.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
    return JSONResponse({"url": portal.url})


@router.post("/sync-subscription")
async def sync_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync subscription status from Stripe — fallback when webhooks fail.

    Looks up the customer's active subscription directly via the Stripe API
    and updates the local DB accordingly.
    """
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account linked")

    try:
        subs = await asyncio.to_thread(
            stripe.Subscription.list, customer=user.stripe_customer_id, status="active", limit=1
        )
    except Exception as err:
        logger.exception("Failed to query Stripe subscriptions for user %s", user.id)
        raise HTTPException(status_code=502, detail="Could not reach Stripe") from err

    if not subs.data:
        # No active subscription on Stripe — ensure DB reflects that
        if user.subscription_status not in (None, "free", "canceled"):
            user.subscription_status = "free"
            user.max_corpora = 0
            await db.commit()
            logger.info("Sync: user %s has no active Stripe subscription, set to free", user.id)
        return JSONResponse({"synced": True, "plan": "free"})

    sub = subs.data[0]
    price_id = sub.items.data[0].price.id
    plan = _plan_from_price(price_id)

    if user.subscription_status != plan:
        user.subscription_status = plan
        user.max_corpora = _max_corpora_for_plan(plan)
        user.daily_queries_used = 0
        await db.commit()
        logger.info("Sync: user %s subscription updated to %s (price %s)", user.id, plan, price_id)

    return JSONResponse({"synced": True, "plan": plan})


@router.post("/cancel-subscription")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel the user's Stripe subscription at end of billing period.

    Does NOT revoke access immediately — the user keeps their plan until
    the current period ends, at which point the ``customer.subscription.deleted``
    webhook fires and the status is set to ``canceled``.
    """
    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Billing not enabled yet")

    # Look up the user's active Subscription record in the local DB
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
        .limit(1),
    )
    sub_record = result.scalar_one_or_none()

    if not sub_record:
        raise HTTPException(status_code=400, detail="No active subscription")

    # Tell Stripe to cancel at the end of the current billing period
    try:
        stripe_sub = await asyncio.to_thread(
            stripe.Subscription.modify,
            sub_record.stripe_subscription_id,
            cancel_at_period_end=True,
        )
    except Exception as err:
        logger.exception(
            "Failed to cancel Stripe subscription %s for user %s",
            sub_record.stripe_subscription_id,
            user.id,
        )
        raise HTTPException(status_code=502, detail="Could not reach Stripe") from err

    # Update local record to reflect pending cancellation
    sub_record.cancel_at_period_end = True
    sub_record.updated_at = datetime.now(UTC)

    # Sync period_end from Stripe response (item-level in API 2025+)
    items_data = stripe_sub.items.data
    if items_data:
        period_end_ts = getattr(items_data[0], "current_period_end", None)
        if period_end_ts:
            sub_record.current_period_end = datetime.fromtimestamp(period_end_ts, tz=UTC)

    await db.commit()
    logger.info(
        "User %s scheduled cancellation for subscription %s at period end",
        user.id,
        sub_record.stripe_subscription_id,
    )

    return JSONResponse(
        {
            "status": "canceled_at_period_end",
            "period_end": sub_record.current_period_end.isoformat() if sub_record.current_period_end else None,
        },
    )


@router.get("/billing-status")
async def billing_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return full plan info including usage counters and limits."""
    status = user.subscription_status

    # Normalize: 'trial', 'canceled', None, or any unrecognized value → 'free'
    _known_plans = ("free", "trial", "starter", "pro", "enterprise")
    effective_plan = status if status in _known_plans else "free"
    if effective_plan == "trial":
        effective_plan = "free"
    limits = _PLAN_LIMITS.get(effective_plan, _PLAN_LIMITS["free"])

    # Guard against None in usage counters (legacy rows or schema migrations)
    _monthly_used = user.monthly_queries_used or 0
    _daily_used = user.daily_queries_used or 0

    # Build usage info
    usage: dict = {}
    if effective_plan in ("free", "trial"):
        daily_limit = limits.get("daily_limit") or 3
        usage = {
            "daily_queries_used": _daily_used,
            "daily_limit": daily_limit,
            "remaining": max(0, daily_limit - _daily_used),
            "resets_at": (user.daily_queries_reset_at.isoformat() if user.daily_queries_reset_at else None),
        }
    elif effective_plan in ("starter", "pro"):
        daily_limit = limits["daily_limit"] or 0
        usage = {
            "daily_queries_used": _daily_used,
            "daily_limit": daily_limit,
            "remaining": max(0, daily_limit - _daily_used),
            "resets_at": (user.daily_queries_reset_at.isoformat() if user.daily_queries_reset_at else None),
        }
    elif effective_plan == "enterprise":
        usage = {
            "daily_queries_used": _daily_used,
            "daily_limit": "unlimited",
            "remaining": "unlimited",
        }

    # Available plans for upgrade prompts
    available_prices = {
        k[0] + "_" + k[1]: v
        for k, v in _PLAN_INTERVAL_TO_PRICE.items()
        if v  # only include configured prices
    }

    # Flatten usage fields for frontend compatibility — all plans use daily limits now
    is_monthly_limit = False
    daily_queries_used = usage.get("daily_queries_used", 0)
    daily_queries_limit = usage.get("daily_limit", 0) or limits.get("daily_limit", 0)
    # Enterprise unlimited → -1 sentinel
    if daily_queries_limit == "unlimited" or daily_queries_limit == 0:
        daily_queries_limit = -1 if effective_plan == "enterprise" else daily_queries_limit
    monthly_queries_used = 0
    monthly_queries_limit = 0

    # Corpus usage: count distinct collections from the user's .meta sidecar files
    from neolex.services.document_manager import get_collection_names

    client_slug = str(user.id)
    existing_collections = await asyncio.to_thread(get_collection_names, client_slug)
    corpora_used = len(existing_collections)
    corpora_limit = limits["max_corpora"]
    corpora_over_limit = corpora_used > corpora_limit

    # Look up active subscription for cancellation info
    cancel_at_period_end = False
    current_period_end: str | None = None
    if effective_plan != "free":
        sub_result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
            .limit(1),
        )
        active_sub = sub_result.scalar_one_or_none()
        if active_sub:
            cancel_at_period_end = active_sub.cancel_at_period_end
            current_period_end = active_sub.current_period_end.isoformat() if active_sub.current_period_end else None

    return JSONResponse(
        {
            "subscription_status": effective_plan,
            "plan": effective_plan,
            "has_stripe_customer": bool(user.stripe_customer_id),
            # Flat usage fields (frontend-compatible)
            "is_monthly_limit": is_monthly_limit,
            "daily_queries_used": daily_queries_used,
            "daily_queries_limit": daily_queries_limit,
            "monthly_queries_used": monthly_queries_used,
            "monthly_queries_limit": monthly_queries_limit,
            "corpora_used": corpora_used,
            "corpora_limit": corpora_limit,
            "corpora_over_limit": corpora_over_limit,
            # Payment warning: True while Stripe is retrying a failed payment
            "payment_warning": user.payment_warning,
            # Cancellation state
            "cancel_at_period_end": cancel_at_period_end,
            "current_period_end": current_period_end,
            # Nested for any future consumers
            "usage": usage,
            "limits": {
                "daily_limit": limits["daily_limit"],
                "monthly_limit": limits["monthly_limit"],
                "max_corpora": limits["max_corpora"],
                "max_docs_per_corpus": limits.get("max_docs_per_corpus", 0),
                "max_corpus_size_mb": limits.get("max_corpus_size_mb", 0),
            },
            "prices": available_prices,
        },
    )


# ---------------------------------------------------------------------------
# Webhook event handlers
# ---------------------------------------------------------------------------


async def _on_checkout_completed(session: dict, db: AsyncSession) -> None:
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    if not customer_id or not subscription_id:
        return

    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    try:
        sub = await asyncio.to_thread(stripe.Subscription.retrieve, subscription_id)
    except stripe.StripeError:
        logger.exception("Failed to retrieve subscription %s", subscription_id)
        return
    item = sub.items.data[0]
    price_id = item.price.id
    plan = _plan_from_price(price_id)

    # Cancel the previous subscription if this is an upgrade/switch.
    # The old subscription ID is stored in checkout metadata by create_checkout_session.
    metadata = session.get("metadata") or {}
    prev_sub_id = metadata.get("previous_subscription_id")
    if prev_sub_id:
        try:
            await asyncio.to_thread(stripe.Subscription.cancel, prev_sub_id)
            logger.info(
                "Canceled previous subscription %s for user %s (upgrade to %s)",
                prev_sub_id,
                user.id,
                plan,
            )
            # Mark the old DB record as canceled
            old_result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == prev_sub_id),
            )
            old_sub_record = old_result.scalar_one_or_none()
            if old_sub_record:
                old_sub_record.status = "canceled"
                old_sub_record.updated_at = datetime.now(UTC)
        except Exception:
            logger.error(
                "BILLING: Failed to cancel old subscription %s during upgrade for user %s. "
                "User may be double-billed. Manual intervention required.",
                prev_sub_id,
                user.id,
                exc_info=True,
            )
            # Don't block the new subscription activation — user paid for it

    # Update user to the new plan
    user.subscription_status = plan
    user.max_corpora = _max_corpora_for_plan(plan)
    # Cancel any pending corpus deletion — user just paid, restore full access.
    user.corpus_deletion_scheduled_at = None

    # Reset daily counters for the new plan
    user.daily_queries_used = 0
    user.daily_queries_reset_at = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Period fields live on the subscription item, not the top-level sub (Stripe API 2025+)
    period_start = getattr(item, "current_period_start", None) or sub.start_date
    period_end = getattr(item, "current_period_end", None) or getattr(sub, "current_period_end", None) or sub.start_date

    # Guard against duplicate Subscription rows (e.g. webhook replay after restart).
    existing_result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id),
    )
    existing_sub = existing_result.scalar_one_or_none()
    if existing_sub:
        # Update existing record instead of inserting a duplicate
        existing_sub.status = "active"
        existing_sub.stripe_price_id = price_id
        existing_sub.current_period_start = datetime.fromtimestamp(period_start, tz=UTC)
        existing_sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
        existing_sub.cancel_at_period_end = getattr(sub, "cancel_at_period_end", False)
        existing_sub.updated_at = datetime.now(UTC)
    else:
        db.add(
            Subscription(
                user_id=user.id,
                stripe_subscription_id=subscription_id,
                stripe_price_id=price_id,
                status="active",
                current_period_start=datetime.fromtimestamp(period_start, tz=UTC),
                current_period_end=datetime.fromtimestamp(period_end, tz=UTC),
                cancel_at_period_end=getattr(sub, "cancel_at_period_end", False),
            ),
        )

    await db.commit()
    logger.info("User %s subscribed to %s plan (price %s)", user.id, plan, price_id)


async def _on_subscription_changed(sub: dict, db: AsyncSession) -> None:
    customer_id = sub.get("customer")
    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    stripe_status = sub["status"]  # active | past_due | canceled | unpaid
    items_data = sub.get("items", {}).get("data", [])
    first_item = items_data[0] if items_data else {}
    price_id = first_item.get("price", {}).get("id") if first_item else None

    if stripe_status == "canceled":
        # Before revoking access, check if the user has another active subscription.
        # This happens during upgrades: old sub is canceled, but new one is already active.
        other_active = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
                Subscription.stripe_subscription_id != sub["id"],
            )
            .limit(1),
        )
        if other_active.scalar_one_or_none():
            logger.info(
                "User %s subscription %s canceled, but another active subscription exists — not revoking access",
                user.id,
                sub["id"],
            )
        else:
            # No other active subscription — revert to canceled.
            # Schedule corpus deletion 7 days out to give the user a grace period.
            user.subscription_status = "canceled"
            user.max_corpora = 0
            deletion_date = datetime.now(UTC) + timedelta(days=7)
            user.corpus_deletion_scheduled_at = deletion_date
            await db.commit()
            # Send warning email (fire-and-forget — billing state must not fail on email errors)
            deletion_date_str = deletion_date.strftime("%B %d, %Y")
            try:
                from neolex.auth.email_service import send_corpus_deletion_warning_email

                asyncio.create_task(send_corpus_deletion_warning_email(user.email, deletion_date_str))
            except Exception:
                logger.exception("Failed to send corpus deletion warning email to user %s", user.id)
            logger.info(
                "User %s subscription canceled, corpus deletion scheduled for %s",
                user.id,
                deletion_date_str,
            )
    elif stripe_status in ("active",):
        # Plan may have changed (upgrade/downgrade)
        plan = _plan_from_price(price_id) if price_id else user.subscription_status
        user.subscription_status = plan
        user.max_corpora = _max_corpora_for_plan(plan)
        user.payment_warning = False  # Clear warning if subscription recovered
        # Clear any pending corpus deletion — subscription is active again.
        user.corpus_deletion_scheduled_at = None
    elif stripe_status in ("past_due", "unpaid"):
        # Stripe retries for ~7 days before firing customer.subscription.deleted.
        # Preserve access during the retry window — only flag the warning.
        user.payment_warning = True

    # Update subscription record
    result2 = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == sub["id"]))
    existing = result2.scalar_one_or_none()
    if existing:
        existing.status = stripe_status
        existing.cancel_at_period_end = sub.get("cancel_at_period_end", False)
        # Period fields may be at item level (Stripe API 2025+) or top level (legacy)
        period_end = first_item.get("current_period_end") or sub.get("current_period_end")
        if period_end:
            existing.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
        existing.updated_at = datetime.now(UTC)
        if price_id:
            existing.stripe_price_id = price_id

    await db.commit()


async def _on_payment_failed(invoice: dict, db: AsyncSession) -> None:
    """Log payment failure but do NOT revoke access immediately.

    Stripe retries failed payments automatically. Access revocation is handled
    by ``customer.subscription.updated`` (status=past_due) and
    ``customer.subscription.deleted`` (status=canceled) webhooks, which fire
    after Stripe's retry cycle is exhausted. Revoking here would prematurely
    lock out users on the first transient payment failure.
    """
    customer_id = invoice.get("customer")
    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if user:
        logger.warning(
            "Payment failed for user %s (invoice %s) — access preserved pending Stripe retry cycle",
            user.id,
            invoice.get("id"),
        )


async def _on_invoice_paid(invoice: dict, db: AsyncSession) -> None:
    customer_id = invoice.get("customer")
    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    # Clear payment warning — invoice paid means the retry cycle succeeded.
    if user.payment_warning:
        user.payment_warning = False

    # Upsert check — prevent duplicate Invoice rows on webhook replay
    existing = (
        await db.execute(select(Invoice).where(Invoice.stripe_invoice_id == invoice["id"]))
    ).scalar_one_or_none()
    if existing:
        await db.commit()  # Persist payment_warning clear even on duplicate invoice
        return

    db.add(
        Invoice(
            user_id=user.id,
            stripe_invoice_id=invoice["id"],
            amount_cents=invoice.get("amount_paid", 0),
            currency=invoice.get("currency", "usd"),
            status="paid",
            invoice_pdf=invoice.get("invoice_pdf"),
        ),
    )
    await db.commit()
