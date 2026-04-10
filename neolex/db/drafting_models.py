"""SQLAlchemy ORM models for legal document drafting.

Tables:
  document_templates — LaTeX-based templates with {{field}} placeholders
  chat_documents     — user-created document instances tied to a conversation
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from neolex.db.postgres import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DocumentTemplate(Base):
    """A LaTeX template for generating legal documents.

    Templates are public (no auth required to list/get). Admin-only for create/update.
    Placeholders in latex_template use {{field_name}} syntax.
    required_fields lists which fields MUST be provided at document creation time.
    field_descriptions maps field names to human-readable labels/hints.
    """

    __tablename__ = "document_templates"
    __table_args__ = (
        Index("ix_doctemplate_jurisdiction", "jurisdiction"),
        Index("ix_doctemplate_category", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(32), nullable=False)  # CZ | DIFC | UK | general
    category: Mapped[str] = mapped_column(String(64), nullable=False)  # civil | labor | administrative | criminal
    latex_template: Mapped[str] = mapped_column(Text, nullable=False)
    required_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    field_descriptions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)


class ChatDocument(Base):
    """A legal document draft created by a user within a conversation.

    conversation_id is a UUID that identifies the chat session; there is NO
    foreign key to a 'chats' table because that table does not exist — conversations
    are tracked only via conversation_messages.

    Ownership is enforced via user_id FK so one user can never access another's drafts.
    The application enforces max 3 documents per conversation (not a DB constraint).
    """

    __tablename__ = "chat_documents"
    __table_args__ = (Index("ix_chatdoc_conv_user", "conversation_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_slug: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("document_templates.slug", ondelete="RESTRICT"),
        nullable=False,
    )
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
