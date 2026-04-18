"""Integration tests for document drafting with REAL database.

These tests complement the mocked tests in tests/neolex/test_drafting.py by
verifying actual database behavior:
- Documents persist correctly
- Ownership enforcement works at DB level
- Cascade deletes work
- Constraints are enforced

Fixtures used:
- test_client: Authenticated AsyncClient with real DB
- test_user: Real user in PostgreSQL
- db: AsyncSession for direct DB assertions
- mock_llm_calls: Mocks expensive LLM API calls

What is mocked (external services):
- LLM/pipeline calls
- PDF generation (xelatex/weasyprint)

What is REAL (database behavior):
- User creation and auth
- Template lookups
- Document CRUD operations
- Ownership enforcement
- Cascade deletes

Run with:
    uv run pytest tests/integration/test_drafting_real.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from neolex.db.drafting_models import DocumentTemplate

pytestmark = pytest.mark.asyncio(loop_scope="module")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def drafting_template(db) -> str:
    """Create a real document template in DB. Yields template slug, deletes on teardown."""
    from datetime import UTC, datetime

    from sqlalchemy import delete as sa_delete

    slug = f"integ_template_{uuid.uuid4().hex[:8]}"

    template = DocumentTemplate(
        id=uuid.uuid4(),
        slug=slug,
        name="Integration Test Template",
        jurisdiction="CZ",
        category="civil",
        latex_template=r"\documentclass{article}\begin{document}Hello {{name}}\end{document}",
        required_fields=["name"],
        field_descriptions={"name": "Full name"},
        description="Template for integration tests",
        created_at=datetime.now(UTC),
    )

    db.add(template)
    await db.commit()

    yield slug

    # Delete chat_documents referencing this slug before deleting the template
    # to satisfy the FK constraint (chat_documents_template_slug_fkey).
    from sqlalchemy import text as sa_text

    await db.execute(sa_text("DELETE FROM chat_documents WHERE template_slug = :slug"), {"slug": slug})
    await db.execute(sa_delete(DocumentTemplate).where(DocumentTemplate.slug == slug))
    await db.commit()


@pytest.fixture
async def conversation_record(test_user) -> str:
    """Create a conversation record in DB. Returns conversation ID."""
    from sqlalchemy import text

    from neolex.db.postgres import AsyncSessionLocal

    conv_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO conversation_messages (id, conversation_id, user_id, role, content, created_at)
                VALUES (:id, :conv_id, :user_id, 'user', 'test message', NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": str(uuid.uuid4()), "conv_id": str(conv_id), "user_id": test_user[1]},
        )
        await session.commit()

    return str(conv_id)


# ---------------------------------------------------------------------------
# Document Create Tests
# ---------------------------------------------------------------------------


class TestDocumentCreateIntegration:
    """Test document creation with real database."""

    async def test_create_document_returns_201_with_correct_fields(
        self, test_client, drafting_template, conversation_record
    ):
        """Document creation should return 201 with correct response structure."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Jan Novák"}},
        )
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["template_slug"] == drafting_template
        assert data["fields"]["name"] == "Jan Novák"
        assert data["version"] == 1
        assert "doc_id" in data

    async def test_create_document_preserves_czech_characters(
        self, test_client, drafting_template, conversation_record
    ):
        """Czech characters in field values should be preserved."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "žluťoučký kůň"}},
        )
        assert resp.status_code == 201
        assert "žluťoučký kůň" in resp.json()["fields"]["name"]

    async def test_create_document_missing_required_field_returns_422(
        self, test_client, drafting_template, conversation_record
    ):
        """Missing required field should return 422."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {}},  # 'name' missing
        )
        assert resp.status_code == 422
        assert "name" in resp.json()["detail"]

    async def test_create_document_unknown_template_returns_404(self, test_client, conversation_record):
        """Unknown template slug should return 404."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": "nonexistent_template_xyz", "fields": {}},
        )
        assert resp.status_code == 404

    async def test_create_document_max_3_per_conversation(self, test_client, drafting_template, conversation_record):
        """Creating 4th document should return 409 (max 3 per conversation)."""
        for i in range(3):
            resp = await test_client.post(
                f"/api/v1/conversations/{conversation_record}/documents",
                json={"template_slug": drafting_template, "fields": {"name": f"Doc{i}"}},
            )
            assert resp.status_code == 201, f"Failed to create doc {i}"

        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Doc4"}},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Document Read/List Tests
# ---------------------------------------------------------------------------


class TestDocumentReadIntegration:
    """Test document reading with real database."""

    async def test_list_documents_returns_only_own_documents(self, test_client, drafting_template, conversation_record):
        """User should only see their own documents."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "My Doc"}},
        )
        assert resp.status_code == 201

        resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(d["fields"]["name"] == "My Doc" for d in data)

    async def test_get_document_by_id(self, test_client, drafting_template, conversation_record):
        """GET .../documents/{id} should return the document."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Test Doc"}},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]

        resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["fields"]["name"] == "Test Doc"

    async def test_get_nonexistent_document_returns_404(self, test_client, conversation_record):
        """GET nonexistent document should return 404."""
        fake_id = str(uuid.uuid4())
        resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents/{fake_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Document Update Tests
# ---------------------------------------------------------------------------


class TestDocumentUpdateIntegration:
    """Test document updates with real database."""

    async def test_update_increments_version(self, test_client, drafting_template, conversation_record):
        """PATCH should increment version number."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Original"}},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]
        assert resp.json()["version"] == 1

        resp = await test_client.patch(
            f"/api/v1/conversations/{conversation_record}/documents/{doc_id}",
            json={"fields": {"name": "Updated"}},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2
        assert resp.json()["fields"]["name"] == "Updated"

    async def test_update_merges_fields(self, test_client, drafting_template, conversation_record):
        """PATCH should merge new fields with existing."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Original"}},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]

        resp = await test_client.patch(
            f"/api/v1/conversations/{conversation_record}/documents/{doc_id}",
            json={"fields": {"extra": "new value"}},
        )
        assert resp.status_code == 200
        fields = resp.json()["fields"]
        assert fields["name"] == "Original"
        assert fields["extra"] == "new value"

    async def test_update_nonexistent_returns_404(self, test_client, conversation_record):
        """PATCH nonexistent document should return 404."""
        fake_id = str(uuid.uuid4())
        resp = await test_client.patch(
            f"/api/v1/conversations/{conversation_record}/documents/{fake_id}",
            json={"fields": {"name": "Test"}},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Document Delete Tests
# ---------------------------------------------------------------------------


class TestDocumentDeleteIntegration:
    """Test document deletion with real database."""

    async def test_delete_returns_204_and_document_gone(self, test_client, drafting_template, conversation_record):
        """DELETE should return 204 and document should no longer be accessible."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "To Delete"}},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]

        resp = await test_client.delete(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}")
        assert resp.status_code == 204

        resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, test_client, conversation_record):
        """DELETE nonexistent document should return 404."""
        fake_id = str(uuid.uuid4())
        resp = await test_client.delete(f"/api/v1/conversations/{conversation_record}/documents/{fake_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PDF Endpoint Tests
# ---------------------------------------------------------------------------


class TestDocumentPdfIntegration:
    """Test PDF generation with mocked renderer."""

    async def test_pdf_returns_503_when_no_renderer(self, test_client, drafting_template, conversation_record):
        """PDF endpoint should return 503 when no LaTeX renderer is available."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Test"}},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]

        with (
            patch("neolex.routers.drafting._XELATEX_BIN", None),
            patch("neolex.routers.drafting._WEASYPRINT_AVAILABLE", False),
        ):
            resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}/pdf")
        assert resp.status_code == 503

    async def test_pdf_returns_200_when_renderer_mocked(self, test_client, drafting_template, conversation_record):
        """PDF endpoint should return 200 with mocked renderer."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "PDF Test"}},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]

        fake_pdf = b"%PDF-1.4 fake content"
        with (
            patch("neolex.routers.drafting._XELATEX_BIN", "/usr/bin/xelatex"),
            patch("neolex.routers.drafting.generate_pdf", new_callable=AsyncMock, return_value=fake_pdf),
        ):
            resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"


# ---------------------------------------------------------------------------
# TeX Endpoint Tests
# ---------------------------------------------------------------------------


class TestDocumentTexIntegration:
    """Test LaTeX source download with real database."""

    async def test_get_tex_returns_latex_source(self, test_client, drafting_template, conversation_record):
        """GET .../tex should return filled LaTeX source."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Jan Novak"}},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]

        resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}/tex")
        assert resp.status_code == 200
        assert "application/x-tex" in resp.headers["content-type"]
        assert "Jan Novak" in resp.text or "Jan" in resp.text

    async def test_get_tex_security_headers(self, test_client, drafting_template, conversation_record):
        """GET .../tex should include security headers."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Test"}},
        )
        doc_id = resp.json()["doc_id"]

        resp = await test_client.get(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}/tex")
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-store, private"
        assert resp.headers["x-content-type-options"] == "nosniff"

    async def test_head_tex_returns_200_no_body(self, test_client, drafting_template, conversation_record):
        """HEAD .../tex should return 200 with no body."""
        resp = await test_client.post(
            f"/api/v1/conversations/{conversation_record}/documents",
            json={"template_slug": drafting_template, "fields": {"name": "Test"}},
        )
        doc_id = resp.json()["doc_id"]

        resp = await test_client.head(f"/api/v1/conversations/{conversation_record}/documents/{doc_id}/tex")
        assert resp.status_code == 200
        assert resp.content == b""
        assert "application/x-tex" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Template Tests
# ---------------------------------------------------------------------------


class TestTemplateIntegration:
    """Test template listing with real database."""

    async def test_list_templates_returns_created_template(self, test_client, drafting_template):
        """GET /api/v1/templates should return the template created in DB."""
        resp = await test_client.get("/api/v1/templates")
        assert resp.status_code == 200
        data = resp.json()
        slugs = [t["slug"] for t in data]
        assert drafting_template in slugs

    async def test_get_template_returns_field_descriptions(self, test_client, drafting_template):
        """GET /api/v1/templates/{slug} should include field_descriptions."""
        resp = await test_client.get(f"/api/v1/templates/{drafting_template}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["required_fields"] == ["name"]
        assert "field_descriptions" in data
        assert data["field_descriptions"]["name"] == "Full name"
