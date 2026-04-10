"""Template API — legal document LaTeX template management.

Public endpoints (no auth):
    GET /api/v1/templates                  — list templates, ?jurisdiction=CZ&category=civil
    GET /api/v1/templates/{slug}           — get template detail + field descriptions

Admin endpoints (require admin session):
    POST  /api/v1/admin/templates          — create template
    PATCH /api/v1/admin/templates/{slug}   — update template
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.db.drafting_models import DocumentTemplate
from neolex.db.postgres import get_db
from neolex.routers.admin import get_admin
from neolex.schemas.drafting import TemplateCreate, TemplateDetail, TemplateListItem, TemplateUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["templates"])


# ---------------------------------------------------------------------------
# Public: list templates
# ---------------------------------------------------------------------------


@router.get("/api/v1/templates", response_model=list[TemplateListItem])
async def list_templates(
    jurisdiction: str | None = Query(default=None, max_length=32),
    category: str | None = Query(default=None, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> list[TemplateListItem]:
    """List all available templates, optionally filtered by jurisdiction and/or category."""
    stmt = select(DocumentTemplate).order_by(DocumentTemplate.jurisdiction, DocumentTemplate.name)

    if jurisdiction:
        stmt = stmt.where(DocumentTemplate.jurisdiction == jurisdiction)
    if category:
        stmt = stmt.where(DocumentTemplate.category == category)

    result = await db.execute(stmt)
    templates = result.scalars().all()
    return [TemplateListItem.model_validate(t) for t in templates]


# ---------------------------------------------------------------------------
# Public: get single template
# ---------------------------------------------------------------------------


@router.get("/api/v1/templates/{slug}", response_model=TemplateDetail)
async def get_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> TemplateDetail:
    """Get a single template by slug, including field descriptions."""
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.slug == slug))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template '{slug}' not found")
    return TemplateDetail.model_validate(template)


# ---------------------------------------------------------------------------
# Admin: create template
# ---------------------------------------------------------------------------


@router.post("/api/v1/admin/templates", response_model=TemplateDetail, status_code=201)
async def create_template(
    payload: TemplateCreate,
    admin=Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> TemplateDetail:
    """Create a new document template (admin only)."""
    # Check slug uniqueness
    existing = await db.execute(select(DocumentTemplate).where(DocumentTemplate.slug == payload.slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Template slug '{payload.slug}' already exists")

    template = DocumentTemplate(
        slug=payload.slug,
        name=payload.name,
        jurisdiction=payload.jurisdiction,
        category=payload.category,
        latex_template=payload.latex_template,
        required_fields=payload.required_fields,
        field_descriptions=payload.field_descriptions,
        description=payload.description,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    logger.info("Template created: slug=%s by admin=%s", template.slug, admin.email)
    return TemplateDetail.model_validate(template)


# ---------------------------------------------------------------------------
# Admin: update template
# ---------------------------------------------------------------------------


@router.patch("/api/v1/admin/templates/{slug}", response_model=TemplateDetail)
async def update_template(
    slug: str,
    payload: TemplateUpdate,
    admin=Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> TemplateDetail:
    """Update an existing template (admin only). Only provided fields are updated."""
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.slug == slug))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template '{slug}' not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)

    logger.info("Template updated: slug=%s by admin=%s", slug, admin.email)
    return TemplateDetail.model_validate(template)
