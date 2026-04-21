"""SQLAlchemy ORM models for auth and billing tables.

Tables: users, sessions, auth_tokens, subscriptions, invoices, feedback.
Operational tables (api_keys, queries, etc.) are in operational_models.py.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from neolex.db.postgres import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)

    # Email/password auth (NULL if Google-only)
    password_hash: Mapped[str | None] = mapped_column(String)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Google OAuth (NULL if email/password only)
    google_id: Mapped[str | None] = mapped_column(String, unique=True)

    # Subscription state
    subscription_status: Mapped[str] = mapped_column(
        String,
        default="free",
        nullable=False,
    )  # free | starter | pro | enterprise | canceled  (legacy: trial treated as free)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, unique=True)

    # Usage tracking — free tier monthly, paid tiers daily
    monthly_queries_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_queries_reset_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    daily_queries_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_queries_reset_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    max_corpora: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # True while Stripe is retrying a failed payment — access is preserved during the retry window.
    # Cleared when the subscription recovers (active) or when the invoice is paid.
    payment_warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Set on subscription cancellation — corpus is deleted at this datetime (7-day grace period).
    # NULL means no deletion is pending. Cleared after the nightly job executes the deletion.
    corpus_deletion_scheduled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    auth_tokens: Mapped[list["AuthToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ip: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)

    user: Mapped["User"] = relationship(back_populates="sessions")


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    token_type: Mapped[str] = mapped_column(String, nullable=False)  # email_verify | password_reset
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="auth_tokens")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    stripe_subscription_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # active | past_due | canceled | trialing
    current_period_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="subscriptions")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="usd", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # paid | open | void | uncollectible
    invoice_pdf: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="invoices")


class ConversationMessage(Base):
    """Per-user conversation history for multi-turn query context.

    Ownership is enforced via user_id FK — one user can never read
    another user's conversation history.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(String, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(String)  # JSON-serialised list[Source]
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        # Fast lookup: load history for a user+conversation ordered by time
        Index("ix_convmsg_user_conv_time", "user_id", "conversation_id", "created_at"),
        # Idempotency guard: prevent duplicate rows when save_turn() fires twice
        # (retry / SSE reconnect). Partial so NULL trace_id rows are not affected.
        Index(
            "ix_convmsg_user_conv_trace_uq",
            "user_id",
            "conversation_id",
            "trace_id",
            unique=True,
            postgresql_where=text("trace_id IS NOT NULL"),
        ),
    )


class ConversationDocs(Base):
    """Accumulated source documents for agent multi-turn conversations.

    Stores the agent's accumulated_docs as JSON so follow-up questions
    can reference prior sources without re-retrieval. One row per conversation.
    """

    __tablename__ = "conversation_docs"

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    docs_json: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class PipelineJob(Base):
    """Tracks in-flight pipeline jobs so the frontend can poll status after SSE drops.

    One row per query submission. Updated as the pipeline progresses through
    stages: processing -> searching -> answering -> complete/failed/timeout.
    Frontend polls GET /conversations/{id}/status to recover state after reload.
    """

    __tablename__ = "pipeline_jobs"
    __table_args__ = (Index("ix_pipeline_job_user_conv", "user_id", "conversation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="processing",
    )  # processing | searching | answering | complete | failed | timeout
    status_detail: Mapped[str | None] = mapped_column(String)
    answer: Mapped[str | None] = mapped_column(String)
    sources_json: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class Feedback(Base):
    """Per-message user feedback (thumbs up/down) on query responses.

    One row per (message_id, user_id) — upserted on repeat submissions.
    The unique index enforces at most one rating per user per message.
    """

    __tablename__ = "feedback"
    __table_args__ = (
        Index("feedback_message_user_uq", "message_id", "user_id", unique=True),
        CheckConstraint("rating IN ('positive', 'negative')", name="feedback_rating_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[str] = mapped_column(String, nullable=False)  # 'positive' | 'negative'
    comment: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)
