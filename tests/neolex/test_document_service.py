"""Unit tests for neolex.services.document_service.

Tests the internal document CRUD helpers used by the agent's _draft_document_fn
callback.  Uses an in-memory SQLite database (via aiosqlite) so no real
PostgreSQL or networking is required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_template(slug: str = "test_template", required: list | None = None) -> MagicMock:
    """Return a mock DocumentTemplate ORM object."""
    tmpl = MagicMock()
    tmpl.slug = slug
    tmpl.name = "Test Template"
    tmpl.jurisdiction = "CZ"
    tmpl.category = "civil"
    tmpl.required_fields = required or ["party_name", "claim_amount"]
    tmpl.field_descriptions = {"party_name": "Name of the plaintiff", "claim_amount": "Amount in CZK"}
    tmpl.description = "A test template"
    return tmpl


def _make_doc(
    doc_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    template_slug: str = "test_template",
    fields: dict | None = None,
    version: int = 1,
) -> MagicMock:
    """Return a mock ChatDocument ORM object."""
    doc = MagicMock()
    doc.id = doc_id or uuid.uuid4()
    doc.user_id = user_id or uuid.uuid4()
    doc.template_slug = template_slug
    doc.fields = fields or {"party_name": "Jan Novák", "claim_amount": "50000"}
    doc.version = version
    doc.created_at = MagicMock()
    doc.created_at.isoformat.return_value = "2026-04-10T10:00:00+00:00"
    return doc


async def _make_db(template=None, doc=None, doc_count: int = 0):
    """Return a mock AsyncSession with configurable query results."""
    db = AsyncMock()

    # Mock execute().scalar_one_or_none() chain for template lookup
    tmpl_result = MagicMock()
    tmpl_result.scalar_one_or_none.return_value = template

    # Mock execute().scalars().all() chain for document listing
    docs_result = MagicMock()
    docs_result.scalars.return_value.all.return_value = [doc] if doc else []

    # Mock execute().scalar_one() chain for count query
    count_result = MagicMock()
    count_result.scalar_one.return_value = doc_count

    # Sequence: first call = template lookup, second = doc lookup / count
    db.execute.side_effect = [tmpl_result, count_result]

    return db


# ---------------------------------------------------------------------------
# get_template_by_slug
# ---------------------------------------------------------------------------


class TestGetTemplateBySlug:
    @pytest.mark.asyncio
    async def test_returns_dict_for_existing_template(self):
        from neolex.services.document_service import get_template_by_slug

        tmpl = _make_template()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = tmpl
        db.execute.return_value = result

        out = await get_template_by_slug(db, "test_template")

        assert out is not None
        assert out["slug"] == "test_template"
        assert out["required_fields"] == ["party_name", "claim_amount"]
        assert "party_name" in out["field_descriptions"]

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_template(self):
        from neolex.services.document_service import get_template_by_slug

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        out = await get_template_by_slug(db, "nonexistent_slug")

        assert out is None


# ---------------------------------------------------------------------------
# create_draft_document
# ---------------------------------------------------------------------------


class TestCreateDraftDocument:
    @pytest.mark.asyncio
    async def test_returns_error_when_template_missing(self):
        from neolex.services.document_service import create_draft_document

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        out = await create_draft_document(
            db=db,
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            template_slug="ghost_template",
            fields={"party_name": "Jan"},
        )

        assert "error" in out
        assert "ghost_template" in out["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_required_fields_missing(self):
        from neolex.services.document_service import create_draft_document

        tmpl = _make_template(required=["party_name", "claim_amount"])
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = tmpl
        db.execute.return_value = result

        out = await create_draft_document(
            db=db,
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            template_slug="test_template",
            fields={"party_name": "Jan"},  # claim_amount missing
        )

        assert "error" in out
        assert "claim_amount" in out["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_cap_reached(self):
        from neolex.services.document_service import create_draft_document

        tmpl = _make_template(required=["party_name", "claim_amount"])
        db = AsyncMock()
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3  # already at max
        db.execute.side_effect = [tmpl_result, count_result]

        out = await create_draft_document(
            db=db,
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            template_slug="test_template",
            fields={"party_name": "Jan", "claim_amount": "5000"},
        )

        assert "error" in out
        assert "Maximum" in out["error"]

    @pytest.mark.asyncio
    async def test_creates_document_successfully(self):
        from neolex.services.document_service import create_draft_document

        tmpl = _make_template(required=["party_name", "claim_amount"])
        new_doc = _make_doc(version=1)
        new_doc_id = str(new_doc.id)

        db = AsyncMock()
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0  # under cap
        db.execute.side_effect = [tmpl_result, count_result]
        db.refresh = AsyncMock(side_effect=lambda doc: setattr(doc, "id", uuid.UUID(new_doc_id)))

        with patch("neolex.db.drafting_models.ChatDocument") as mock_cls:
            mock_cls.return_value = new_doc
            await create_draft_document(
                db=db,
                user_id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                template_slug="test_template",
                fields={"party_name": "Jan", "claim_amount": "5000"},
            )

        # Should call db.add, db.commit, db.refresh
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_draft_document
# ---------------------------------------------------------------------------


class TestUpdateDraftDocument:
    @pytest.mark.asyncio
    async def test_returns_error_when_document_not_found(self):
        from neolex.services.document_service import update_draft_document

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        out = await update_draft_document(
            db=db,
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            doc_id=uuid.uuid4(),
            fields={"claim_amount": "9999"},
        )

        assert "error" in out
        assert "not found" in out["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_wrong_owner(self):
        from neolex.services.document_service import update_draft_document

        doc = _make_doc(user_id=uuid.uuid4())  # owned by a different user
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        db.execute.return_value = result

        out = await update_draft_document(
            db=db,
            user_id=uuid.uuid4(),  # different user_id
            conversation_id=uuid.uuid4(),
            doc_id=doc.id,
            fields={"claim_amount": "9999"},
        )

        assert "error" in out

    @pytest.mark.asyncio
    async def test_merges_fields_and_increments_version(self):
        from neolex.services.document_service import update_draft_document

        user_id = uuid.uuid4()
        doc = _make_doc(user_id=user_id, fields={"party_name": "Jan", "claim_amount": "5000"}, version=1)

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        db.execute.return_value = result
        db.refresh = AsyncMock()

        with patch("neolex.services.pdf_generator.invalidate_cache"):
            await update_draft_document(
                db=db,
                user_id=user_id,
                conversation_id=uuid.uuid4(),
                doc_id=doc.id,
                fields={"claim_amount": "9999"},  # partial update
            )

        # Merged fields: party_name preserved, claim_amount updated
        assert doc.fields == {"party_name": "Jan", "claim_amount": "9999"}
        # Version incremented
        assert doc.version == 2
        db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Agent pipeline _make_draft_document_fn
# ---------------------------------------------------------------------------


class TestMakeDraftDocumentFn:
    def test_returns_callable(self):
        from neolex.services.agent_pipeline import _make_draft_document_fn

        fn = _make_draft_document_fn(uuid.uuid4(), uuid.uuid4())
        assert callable(fn)

    @pytest.mark.asyncio
    async def test_update_requires_document_id(self):
        from neolex.services.agent_pipeline import _make_draft_document_fn

        fn = _make_draft_document_fn(uuid.uuid4(), uuid.uuid4())

        with patch("neolex.db.postgres.AsyncSessionLocal") as mock_session_cls:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = ctx

            result = await fn(action="update", fields={"x": "y"}, document_id="", template_slug="t")

        assert "error" in result
        assert "document_id" in result["error"]

    @pytest.mark.asyncio
    async def test_update_rejects_invalid_uuid(self):
        from neolex.services.agent_pipeline import _make_draft_document_fn

        fn = _make_draft_document_fn(uuid.uuid4(), uuid.uuid4())

        with patch("neolex.db.postgres.AsyncSessionLocal") as mock_session_cls:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = ctx

            result = await fn(action="update", fields={"x": "y"}, document_id="not-a-uuid", template_slug="t")

        assert "error" in result
        assert "Invalid" in result["error"]

    @pytest.mark.asyncio
    async def test_create_requires_template_slug(self):
        from neolex.services.agent_pipeline import _make_draft_document_fn

        fn = _make_draft_document_fn(uuid.uuid4(), uuid.uuid4())

        with patch("neolex.db.postgres.AsyncSessionLocal") as mock_session_cls:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = ctx

            result = await fn(action="create", fields={"x": "y"}, document_id="", template_slug="")

        assert "error" in result
        assert "template_slug" in result["error"]
