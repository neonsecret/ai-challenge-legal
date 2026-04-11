"""Pydantic schemas for the legal document drafting feature.

Covers templates (public) and chat documents (user-scoped).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

# ---------------------------------------------------------------------------
# Template schemas (public read, admin write)
# ---------------------------------------------------------------------------


class TemplateListItem(BaseModel):
    """Compact template representation for list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    jurisdiction: str
    category: str
    description: str | None = None
    created_at: datetime


class TemplateDetail(TemplateListItem):
    """Full template with field metadata (no raw LaTeX — that stays server-side)."""

    required_fields: list[str]
    field_descriptions: dict[str, str] | None = None


class TemplateCreate(BaseModel):
    """Admin payload for creating a new template."""

    slug: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1, max_length=255)
    jurisdiction: str = Field(..., pattern=r"^(CZ|DIFC|UK|AU|general)$")
    category: str = Field(..., pattern=r"^(civil|labor|administrative|criminal|commercial|other)$")
    latex_template: str = Field(..., min_length=10)
    required_fields: list[str] = Field(default_factory=list)
    field_descriptions: dict[str, str] | None = None
    description: str | None = None

    @field_validator("required_fields")
    @classmethod
    def validate_field_names(cls, v: list[str]) -> list[str]:
        for name in v:
            if not name.replace("_", "").isalnum():
                raise ValueError(f"Invalid field name: {name!r} — only alphanumeric + underscore allowed")
        return v


class TemplateUpdate(BaseModel):
    """Admin payload for updating an existing template (all fields optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    jurisdiction: str | None = Field(default=None, pattern=r"^(CZ|DIFC|UK|AU|general)$")
    category: str | None = Field(default=None, pattern=r"^(civil|labor|administrative|criminal|commercial|other)$")
    latex_template: str | None = Field(default=None, min_length=10)
    required_fields: list[str] | None = None
    field_descriptions: dict[str, str] | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Chat document schemas (user-scoped)
# ---------------------------------------------------------------------------


class DocumentCreate(BaseModel):
    """Payload for creating a new chat document."""

    template_slug: str = Field(..., min_length=1, max_length=128)
    fields: dict[str, str] = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    """Payload for updating an existing chat document's fields."""

    fields: dict[str, str]

    @field_validator("fields")
    @classmethod
    def fields_must_not_be_empty(cls, v: dict[str, str]) -> dict[str, str]:
        """Reject empty-fields PATCH to prevent spurious cache invalidation."""
        if not v:
            raise ValueError("fields must not be empty — provide at least one field to update")
        return v


class DocumentResponse(BaseModel):
    """API response for a single chat document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    template_slug: str
    template_name: str | None = None
    fields: dict[str, str]
    version: int
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def doc_id(self) -> uuid.UUID:
        """Alias for id — frontend ChatDocument type uses doc_id."""
        return self.id
