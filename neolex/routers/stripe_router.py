"""Stripe Checkout and webhook routes — tiered subscription system.

Plans: free, starter, pro, enterprise, business (custom).
Intervals: monthly, biweekly.
"""
import asyncio
import logging
from datetime import datetime, timezone

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
_processed_events: set[str] = set()
_MAX_PROCESSED = 10_000


# ---------------------------------------------------------------------------
# Price ID <-> plan name mapping
# ---------------------------------------------------------------------------

_PRICE_TO_PLAN: dict[str, str] = {}
_PLAN_INTERVAL_TO_PRICE: dict[tuple[str, str], str] = {}

# Plan limits for billing-status response
_PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "daily_limit": None,
        "monthly_limit": settings.free_monthly_limit,
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
        from neolex.services.document_manager import client_docs_dir
        from neolex.db.audit import get_audit_db
        import shutil

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
        body.plan, body.interval, price_id, len(_PLAN_INTERVAL_TO_PRICE),
    )
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"No price configured for {body.plan}/{body.interval}",
        )

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email, name=user.name or user.email)
        user.stripe_customer_id = customer.id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/billing",
        metadata={"plan": body.plan, "interval": body.interval},
    )
    return JSONResponse({"url": session.url})


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    # Idempotency guard — skip already-processed webhook events.
    event_id = event.get("id", "")
    if event_id in _processed_events:
        logger.info("Duplicate webhook event %s, skipping", event_id)
        return JSONResponse({"status": "duplicate"})
    _processed_events.add(event_id)
    if len(_processed_events) > _MAX_PROCESSED:
        _processed_events.clear()  # Simple eviction

    etype = event["type"]
    data = event["data"]["object"]

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

    portal = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
    return JSONResponse({"url": portal.url})


@router.get("/billing-status")
async def billing_status(user: User = Depends(get_current_user)):
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
    if effective_plan == "free":
        monthly_limit = limits["monthly_limit"] or 0
        usage = {
            "monthly_queries_used": _monthly_used,
            "monthly_limit": monthly_limit,
            "remaining": max(0, monthly_limit - _monthly_used),
            "resets_at": (
                user.monthly_queries_reset_at.isoformat()
                if user.monthly_queries_reset_at
                else None
            ),
        }
    elif effective_plan in ("starter", "pro"):
        daily_limit = limits["daily_limit"] or 0
        usage = {
            "daily_queries_used": _daily_used,
            "daily_limit": daily_limit,
            "remaining": max(0, daily_limit - _daily_used),
            "resets_at": (
                user.daily_queries_reset_at.isoformat()
                if user.daily_queries_reset_at
                else None
            ),
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

    # Flatten usage fields for frontend compatibility
    is_monthly_limit = effective_plan == "free"
    daily_queries_used = usage.get("daily_queries_used", 0) if not is_monthly_limit else 0
    daily_queries_limit = usage.get("daily_limit", 0) if not is_monthly_limit else 0
    # Enterprise unlimited → -1 sentinel
    if usage.get("daily_limit") == "unlimited":
        daily_queries_limit = -1
    monthly_queries_used = usage.get("monthly_queries_used", 0) if is_monthly_limit else 0
    monthly_queries_limit = usage.get("monthly_limit", 0) if is_monthly_limit else 0

    # Corpus usage: corpora_count not yet tracked per-user; default to 0
    corpora_used = 0
    corpora_limit = limits["max_corpora"]

    return JSONResponse({
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
    })


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

    sub = stripe.Subscription.retrieve(subscription_id)
    price_id = sub["items"]["data"][0]["price"]["id"]
    plan = _plan_from_price(price_id)

    # Update user to the new plan
    user.subscription_status = plan
    user.max_corpora = _max_corpora_for_plan(plan)

    # Reset daily counters for the new plan
    user.daily_queries_used = 0
    user.daily_queries_reset_at = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    db.add(Subscription(
        user_id=user.id,
        stripe_subscription_id=subscription_id,
        stripe_price_id=price_id,
        status="active",
        current_period_start=datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc),
        current_period_end=datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc),
        cancel_at_period_end=sub.get("cancel_at_period_end", False),
    ))
    await db.commit()
    logger.info("User %s subscribed to %s plan (price %s)", user.id, plan, price_id)


async def _on_subscription_changed(sub: dict, db: AsyncSession) -> None:
    customer_id = sub.get("customer")
    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    stripe_status = sub["status"]  # active | past_due | canceled | unpaid
    price_id = sub["items"]["data"][0]["price"]["id"] if sub.get("items", {}).get("data") else None

    if stripe_status == "canceled":
        # Subscription deleted — revert to canceled, clean up corpora
        user.subscription_status = "canceled"
        user.max_corpora = 0
        await db.commit()
        # Fire-and-forget corpus cleanup (with error logging)
        task = asyncio.create_task(_delete_user_corpora(user))
        task.add_done_callback(lambda t: logger.error("Corpus cleanup failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)
        logger.info("User %s subscription canceled, corpora cleanup scheduled", user.id)
    elif stripe_status in ("active",):
        # Plan may have changed (upgrade/downgrade)
        plan = _plan_from_price(price_id) if price_id else user.subscription_status
        user.subscription_status = plan
        user.max_corpora = _max_corpora_for_plan(plan)
    elif stripe_status in ("past_due", "unpaid"):
        user.subscription_status = "canceled"
        user.max_corpora = 0

    # Update subscription record
    result2 = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == sub["id"])
    )
    existing = result2.scalar_one_or_none()
    if existing:
        existing.status = stripe_status
        existing.cancel_at_period_end = sub.get("cancel_at_period_end", False)
        existing.current_period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        if price_id:
            existing.stripe_price_id = price_id

    await db.commit()


async def _on_payment_failed(invoice: dict, db: AsyncSession) -> None:
    customer_id = invoice.get("customer")
    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if user:
        user.subscription_status = "canceled"
        user.max_corpora = 0
        await db.commit()
        logger.warning("Payment failed for user %s, set to canceled", user.id)


async def _on_invoice_paid(invoice: dict, db: AsyncSession) -> None:
    customer_id = invoice.get("customer")
    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    db.add(Invoice(
        user_id=user.id,
        stripe_invoice_id=invoice["id"],
        amount_cents=invoice.get("amount_paid", 0),
        currency=invoice.get("currency", "usd"),
        status="paid",
        invoice_pdf=invoice.get("invoice_pdf"),
    ))
    await db.commit()
