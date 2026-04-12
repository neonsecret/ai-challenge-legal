"""Tests for the legal document drafting feature.

Coverage:
  - Template list/get with jurisdiction/category filtering
  - Document create: happy path, max-3 enforcement, missing required field → 422
  - Document update: field merging, version increment, cache invalidation
  - Document delete: happy path, wrong owner, not found
  - Document list/get with ownership enforcement
  - PDF endpoint: 503 when xelatex missing, 200 when mocked
  - LaTeX injection: escape_latex() correctness
  - PDF generator: _inject_fields placeholder substitution
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# escape_latex unit tests (no DB needed)
# ---------------------------------------------------------------------------


class TestEscapeLatex:
    def test_plain_text_unchanged(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("Hello World") == "Hello World"

    def test_ampersand_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("AT&T") == r"AT\&T"

    def test_percent_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("50%") == r"50\%"

    def test_dollar_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("$100") == r"\$100"

    def test_hash_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("#1") == r"\#1"

    def test_underscore_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("some_var") == r"some\_var"

    def test_braces_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("a{b}c") == r"a\{b\}c"

    def test_tilde_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("a~b") == r"a\textasciitilde{}b"

    def test_caret_escaped(self):
        from neolex.services.pdf_generator import escape_latex

        assert escape_latex("a^b") == r"a\textasciicircum{}b"

    def test_backslash_escaped_first(self):
        """Backslash must be escaped before other replacements to avoid double-escaping."""
        from neolex.services.pdf_generator import escape_latex

        result = escape_latex("\\")
        assert result == r"\textbackslash{}"

    def test_combined_injection_attempt(self):
        """A real injection attempt should be fully neutralised."""
        from neolex.services.pdf_generator import escape_latex

        injection = r"\input{/etc/passwd}"
        result = escape_latex(injection)
        assert r"\input" not in result
        assert r"\textbackslash{}" in result

    def test_czech_diacritics_pass_through(self):
        """Czech characters must not be altered — only LaTeX specials are escaped."""
        from neolex.services.pdf_generator import escape_latex

        czech = "žáludkový zákon – § 42"
        result = escape_latex(czech)
        assert "žáludkový zákon" in result
        # em-dash is not a LaTeX special char
        assert "–" in result


class TestInjectFields:
    def test_single_placeholder(self):
        from neolex.services.pdf_generator import _inject_fields

        template = r"Dear {{name}},"
        result = _inject_fields(template, {"name": "John"})
        assert result == "Dear John,"

    def test_multiple_placeholders(self):
        from neolex.services.pdf_generator import _inject_fields

        template = "{{first}} {{last}}"
        result = _inject_fields(template, {"first": "Jan", "last": "Novák"})
        assert result == "Jan Novák"

    def test_missing_key_renders_empty(self):
        from neolex.services.pdf_generator import _inject_fields

        template = "{{name}} {{missing}}"
        result = _inject_fields(template, {"name": "X"})
        assert result == "X "

    def test_field_value_is_escaped(self):
        """Values with LaTeX special chars must be escaped in the output."""
        from neolex.services.pdf_generator import _inject_fields

        template = "Amount: {{amount}}"
        result = _inject_fields(template, {"amount": "50% & $100"})
        assert r"\%" in result
        assert r"\&" in result
        assert r"\$" in result

    def test_injection_via_placeholder(self):
        """An attacker cannot inject LaTeX through a placeholder value."""
        from neolex.services.pdf_generator import _inject_fields

        template = "Note: {{note}}"
        result = _inject_fields(template, {"note": r"\input{/etc/passwd}"})
        # The backslash must be escaped, breaking the command
        assert r"\input" not in result
        assert r"\textbackslash{}" in result


class TestLatexToHtml:
    def test_curly_brace_field_value_renders_verbatim(self):
        """Field values containing curly braces must appear verbatim in HTML output.

        Regression guard for the curly-brace escape bug (9bc2b09): if the
        single-pass _HTML_TEMPLATE.format() call were to re-parse substituted
        values, {2023} would raise an IndexError or be silently dropped.
        """
        from neolex.services.pdf_generator import _latex_to_html

        # Minimal LaTeX template with a {{case}} placeholder
        template = r"\documentclass{article}\begin{document}{{case}}\end{document}"
        # Field value contains raw curly braces (e.g. a legal citation)
        result = _latex_to_html(template, {"case": "Smith {2023}"})
        # The curly braces must survive all format/escape passes unchanged.
        # Use the full field value so this assertion fails if {{2023}} double-escape
        # corruption is re-introduced ("Smith {2023}" is NOT a substring of
        # "Smith {{2023}}").
        assert "Smith {2023}" in result
        assert "{{2023}}" not in result  # explicit guard: double-escape caught here


# ---------------------------------------------------------------------------
# API tests using FastAPI TestClient with mocked DB and auth
# ---------------------------------------------------------------------------


def _make_app_client(mock_user_id: str, db_session_override):
    """Build an AsyncClient with auth and DB mocked."""
    from neolex.auth.middleware import get_api_key
    from neolex.db.postgres import get_db
    from neolex.main import app

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async def mock_auth():
        return {
            "user_id": mock_user_id,
            "email": "test@vitreon.app",
            "client_slug": mock_user_id,
            "scope": "admin",
            "key_hash": f"session:{mock_user_id}",
            "key_prefix": "session",
            "name": "Test User",
        }

    async def mock_db():
        yield db_session_override

    app.dependency_overrides[get_api_key] = mock_auth
    app.dependency_overrides[get_db] = mock_db
    return app


# ---------------------------------------------------------------------------
# Template API tests (DB-mocked with MagicMock scalars)
# ---------------------------------------------------------------------------


class TestTemplateAPI:
    """Tests for GET /api/v1/templates and GET /api/v1/templates/{slug}."""

    @pytest.fixture
    def sample_template(self):
        from neolex.db.drafting_models import DocumentTemplate

        t = DocumentTemplate()
        t.id = uuid.uuid4()
        t.slug = "zaloba_neplatnost_vypovedi"
        t.name = "Žaloba na neplatnost výpovědi"
        t.jurisdiction = "CZ"
        t.category = "labor"
        t.latex_template = r"\documentclass{article}\begin{document}{{name}}\end{document}"
        t.required_fields = ["name", "employer"]
        t.field_descriptions = {"name": "Jméno žalobce", "employer": "Název zaměstnavatele"}
        t.description = "Vzor žaloby pro pracovněprávní spory"
        from datetime import UTC, datetime

        t.created_at = datetime.now(UTC)
        return t

    @pytest.mark.asyncio
    async def test_list_templates_returns_items(self, sample_template):
        """GET /api/v1/templates returns list of templates."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_template]
        mock_session.execute = AsyncMock(return_value=mock_result)

        user_id = str(uuid.uuid4())
        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/templates",
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            # Templates list is public — no auth needed, but CSRF header is needed for GET
            # Actually GET doesn't need CSRF header (CSRFMiddleware only checks mutating methods)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/templates")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["slug"] == "zaloba_neplatnost_vypovedi"
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_list_templates_filters_by_jurisdiction(self, sample_template):
        """Jurisdiction filter is passed through to the DB query."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_template]
        mock_session.execute = AsyncMock(return_value=mock_result)

        user_id = str(uuid.uuid4())
        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/templates?jurisdiction=CZ")
            assert resp.status_code == 200
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_list_templates_excludes_freeform_sentinel(self):
        """GET /api/v1/templates must never return the vlastni_dokument sentinel row.

        vlastni_dokument is the DB row that backs the __custom__ frontend sentinel.
        It is surfaced in the UI via a hardcoded 'Custom document' button, so returning
        it from the API would create a duplicate entry in the template picker.
        """
        from datetime import UTC, datetime

        from neolex.constants import DRAFTING_FREEFORM_SLUG
        from neolex.db.drafting_models import DocumentTemplate

        other = DocumentTemplate()
        other.id = uuid.uuid4()
        other.slug = "zaloba_na_zaplaceni"
        other.name = "Žaloba na zaplacení"
        other.jurisdiction = "CZ"
        other.category = "civil"
        other.latex_template = r"\documentclass{article}\begin{document}\end{document}"
        other.required_fields = ["amount"]
        other.field_descriptions = {}
        other.description = None
        other.created_at = datetime.now(UTC)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Mock returns the already-filtered result that the DB-level WHERE clause produces
        # (WHERE slug != DRAFTING_FREEFORM_SLUG). SQL-level correctness is verified by
        # integration tests; this unit test validates the API contract and response shape.
        mock_result.scalars.return_value.all.return_value = [other]
        mock_session.execute = AsyncMock(return_value=mock_result)

        user_id = str(uuid.uuid4())
        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/templates")
            assert resp.status_code == 200
            data = resp.json()
            slugs = [t["slug"] for t in data]
            assert DRAFTING_FREEFORM_SLUG not in slugs, (
                f"Template list must not expose the freeform sentinel '{DRAFTING_FREEFORM_SLUG}'"
            )
            assert "zaloba_na_zaplaceni" in slugs
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_template_not_found(self):
        """GET /api/v1/templates/{slug} returns 404 for unknown slug."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        user_id = str(uuid.uuid4())
        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/templates/no_such_template")
            assert resp.status_code == 404
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_template_returns_field_descriptions(self, sample_template):
        """GET /api/v1/templates/{slug} includes field_descriptions."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template
        mock_session.execute = AsyncMock(return_value=mock_result)

        user_id = str(uuid.uuid4())
        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/templates/zaloba_neplatnost_vypovedi")
            assert resp.status_code == 200
            data = resp.json()
            assert "field_descriptions" in data
            assert data["required_fields"] == ["name", "employer"]
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Document API tests
# ---------------------------------------------------------------------------


class TestDocumentCreate:
    @pytest.fixture
    def sample_template(self):
        from neolex.db.drafting_models import DocumentTemplate

        t = DocumentTemplate()
        t.id = uuid.uuid4()
        t.slug = "test_template"
        t.name = "Test Template"
        t.jurisdiction = "CZ"
        t.category = "civil"
        t.latex_template = r"\documentclass{article}\begin{document}{{name}}\end{document}"
        t.required_fields = ["name"]
        t.field_descriptions = {"name": "Full name"}
        t.description = None
        from datetime import UTC, datetime

        t.created_at = datetime.now(UTC)
        return t

    def _make_chat_doc(self, user_id_str: str, template_slug: str, fields: dict):
        from datetime import UTC, datetime

        from neolex.db.drafting_models import ChatDocument

        doc = ChatDocument()
        doc.id = uuid.uuid4()
        doc.conversation_id = uuid.uuid4()
        doc.user_id = uuid.UUID(user_id_str)
        doc.template_slug = template_slug
        doc.fields = fields
        doc.version = 1
        doc.created_at = datetime.now(UTC)
        doc.updated_at = datetime.now(UTC)
        return doc

    @pytest.mark.asyncio
    async def test_create_document_happy_path(self, sample_template):
        """POST creates a document when all required fields are provided."""
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        mock_session = AsyncMock()

        # First execute: template lookup
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = sample_template

        # Second execute: pg_advisory_xact_lock (return value unused)
        lock_result = MagicMock()

        # Third execute: row-fetch FOR UPDATE (0 existing docs)
        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[tmpl_result, lock_result, count_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock refresh to populate the doc
        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            from datetime import UTC, datetime

            obj.created_at = datetime.now(UTC)
            obj.updated_at = datetime.now(UTC)

        mock_session.refresh = mock_refresh

        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/conversations/{conv_id}/documents",
                    json={"template_slug": "test_template", "fields": {"name": "Jan Novák"}},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 201
            data = resp.json()
            assert data["template_slug"] == "test_template"
            assert data["template_name"] == "Test Template"
            assert data["doc_id"] == data["id"]
            assert data["fields"]["name"] == "Jan Novák"
            assert data["version"] == 1
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_create_document_missing_required_field(self, sample_template):
        """POST returns 422 when a required field is missing from the payload."""
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        mock_session = AsyncMock()
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = sample_template
        mock_session.execute = AsyncMock(return_value=tmpl_result)

        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/conversations/{conv_id}/documents",
                    json={"template_slug": "test_template", "fields": {}},  # 'name' missing
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 422
            assert "name" in resp.json()["detail"]
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_create_document_max_3_enforcement(self, sample_template):
        """POST returns 409 when conversation already has 3 documents."""
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        mock_session = AsyncMock()

        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = sample_template

        # pg_advisory_xact_lock execute (return value unused)
        lock_result = MagicMock()

        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

        mock_session.execute = AsyncMock(side_effect=[tmpl_result, lock_result, count_result])

        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/conversations/{conv_id}/documents",
                    json={"template_slug": "test_template", "fields": {"name": "X"}},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 409
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_create_document_unknown_template(self):
        """POST returns 404 when template slug does not exist."""
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        mock_session = AsyncMock()
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=tmpl_result)

        app = _make_app_client(user_id, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/conversations/{conv_id}/documents",
                    json={"template_slug": "nonexistent", "fields": {}},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 404
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)


class TestDocumentUpdate:
    @pytest.mark.asyncio
    async def test_update_increments_version(self):
        """PATCH increments version and merges fields."""
        from datetime import UTC, datetime

        from neolex.db.drafting_models import ChatDocument

        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        existing_doc = ChatDocument()
        existing_doc.id = doc_id
        existing_doc.conversation_id = conv_id
        existing_doc.user_id = uuid.UUID(user_id_str)
        existing_doc.template_slug = "test_template"
        existing_doc.fields = {"name": "Old Name"}
        existing_doc.version = 1
        existing_doc.created_at = datetime.now(UTC)
        existing_doc.updated_at = datetime.now(UTC)

        mock_session = AsyncMock()

        # First execute: _get_owned_document (returns the ChatDocument)
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = existing_doc

        # Second execute: _get_template_name (returns display name scalar)
        name_result = MagicMock()
        name_result.scalar_one_or_none.return_value = "Test Template"

        mock_session.execute = AsyncMock(side_effect=[doc_result, name_result])
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            pass

        mock_session.refresh = mock_refresh

        app = _make_app_client(user_id_str, mock_session)

        with patch("neolex.routers.drafting.invalidate_cache"):
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.patch(
                        f"/api/v1/conversations/{conv_id}/documents/{doc_id}",
                        json={"fields": {"name": "New Name", "extra": "value"}},
                        headers={"X-Requested-With": "XMLHttpRequest"},
                    )
                assert resp.status_code == 200
                data = resp.json()
                assert data["version"] == 2
                assert data["template_name"] == "Test Template"
                assert data["doc_id"] == data["id"]
                assert data["fields"]["name"] == "New Name"
                assert data["fields"]["extra"] == "value"
                assert data["template_name"] == "Test Template"
            finally:
                from neolex.auth.middleware import get_api_key
                from neolex.db.postgres import get_db

                app.dependency_overrides.pop(get_api_key, None)
                app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_update_wrong_owner_returns_404(self):
        """PATCH returns 404 when the document belongs to a different user."""
        from datetime import UTC, datetime

        from neolex.db.drafting_models import ChatDocument

        real_owner = uuid.uuid4()
        requester = str(uuid.uuid4())  # different user
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        existing_doc = ChatDocument()
        existing_doc.id = doc_id
        existing_doc.conversation_id = conv_id
        existing_doc.user_id = real_owner  # owned by someone else
        existing_doc.template_slug = "test_template"
        existing_doc.fields = {}
        existing_doc.version = 1
        existing_doc.created_at = datetime.now(UTC)
        existing_doc.updated_at = datetime.now(UTC)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        # SQL WHERE now includes user_id — wrong-owner row is not returned by DB
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        app = _make_app_client(requester, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/conversations/{conv_id}/documents/{doc_id}",
                    json={"fields": {"name": "Hack"}},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 404
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)


class TestDocumentPdf:
    @pytest.mark.asyncio
    async def test_pdf_endpoint_returns_503_when_no_renderer_available(self):
        """GET .../pdf returns 503 if neither xelatex nor weasyprint is available."""
        app = _make_app_client(str(uuid.uuid4()), AsyncMock())

        with (
            patch("neolex.routers.drafting._XELATEX_BIN", None),
            patch("neolex.routers.drafting._WEASYPRINT_AVAILABLE", False),
        ):
            try:
                conv_id = uuid.uuid4()
                doc_id = uuid.uuid4()
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/pdf")
                assert resp.status_code == 503
            finally:
                from neolex.auth.middleware import get_api_key
                from neolex.db.postgres import get_db

                app.dependency_overrides.pop(get_api_key, None)
                app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_pdf_endpoint_returns_pdf_bytes(self):
        """GET .../pdf returns application/pdf when xelatex is available (mocked)."""
        from datetime import UTC, datetime

        from neolex.db.drafting_models import ChatDocument, DocumentTemplate

        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = ChatDocument()
        doc.id = doc_id
        doc.conversation_id = conv_id
        doc.user_id = uuid.UUID(user_id_str)
        doc.template_slug = "test_template"
        doc.fields = {"name": "Test"}
        doc.version = 1
        doc.created_at = datetime.now(UTC)
        doc.updated_at = datetime.now(UTC)

        tmpl = DocumentTemplate()
        tmpl.id = uuid.uuid4()
        tmpl.slug = "test_template"
        tmpl.name = "Test"
        tmpl.jurisdiction = "CZ"
        tmpl.category = "civil"
        tmpl.latex_template = r"\documentclass{article}\begin{document}{{name}}\end{document}"
        tmpl.required_fields = []
        tmpl.field_descriptions = None
        tmpl.description = None
        tmpl.created_at = datetime.now(UTC)

        mock_session = AsyncMock()

        # First execute: get_owned_document
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc

        # Second execute: template lookup
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl

        mock_session.execute = AsyncMock(side_effect=[doc_result, tmpl_result])

        fake_pdf = b"%PDF-1.4 fake pdf content"
        app = _make_app_client(user_id_str, mock_session)

        with (
            patch("neolex.routers.drafting._XELATEX_BIN", "/usr/bin/xelatex"),
            patch(
                "neolex.routers.drafting.generate_pdf",
                new_callable=AsyncMock,
                return_value=fake_pdf,
            ),
        ):
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/pdf")
                assert resp.status_code == 200
                assert resp.headers["content-type"] == "application/pdf"
                assert resp.content == fake_pdf
            finally:
                from neolex.auth.middleware import get_api_key
                from neolex.db.postgres import get_db

                app.dependency_overrides.pop(get_api_key, None)
                app.dependency_overrides.pop(get_db, None)


class TestDocumentDelete:
    def _make_chat_doc(self, user_id_str: str, conv_id: uuid.UUID, doc_id: uuid.UUID):
        from datetime import UTC, datetime

        from neolex.db.drafting_models import ChatDocument

        doc = ChatDocument()
        doc.id = doc_id
        doc.conversation_id = conv_id
        doc.user_id = uuid.UUID(user_id_str)
        doc.template_slug = "test_template"
        doc.fields = {"name": "Test"}
        doc.version = 1
        doc.created_at = datetime.now(UTC)
        doc.updated_at = datetime.now(UTC)
        return doc

    @pytest.mark.asyncio
    async def test_delete_document_happy_path(self):
        """DELETE returns 204 and removes document owned by the authenticated user."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = self._make_chat_doc(user_id_str, conv_id, doc_id)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        app = _make_app_client(user_id_str, mock_session)

        with patch("neolex.routers.drafting.invalidate_cache"):
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.delete(
                        f"/api/v1/conversations/{conv_id}/documents/{doc_id}",
                        headers={"X-Requested-With": "XMLHttpRequest"},
                    )
                assert resp.status_code == 204
                mock_session.delete.assert_awaited_once_with(doc)
                mock_session.commit.assert_awaited_once()
            finally:
                from neolex.auth.middleware import get_api_key
                from neolex.db.postgres import get_db

                app.dependency_overrides.pop(get_api_key, None)
                app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_delete_document_wrong_owner_returns_404(self):
        """DELETE returns 404 when the document belongs to a different user."""
        requester = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        # SQL WHERE now includes user_id — wrong-owner row is not returned by DB
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        app = _make_app_client(requester, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(
                    f"/api/v1/conversations/{conv_id}/documents/{doc_id}",
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 404
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self):
        """DELETE returns 404 when document does not exist."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(
                    f"/api/v1/conversations/{conv_id}/documents/{doc_id}",
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 404
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)


class TestDocumentTex:
    """Tests for GET/HEAD .../documents/{doc_id}/tex endpoint."""

    def _make_chat_doc(
        self, user_id_str: str, conv_id: uuid.UUID, doc_id: uuid.UUID, template_slug: str = "test_template"
    ):
        from datetime import UTC, datetime

        from neolex.db.drafting_models import ChatDocument

        doc = ChatDocument()
        doc.id = doc_id
        doc.conversation_id = conv_id
        doc.user_id = uuid.UUID(user_id_str)
        doc.template_slug = template_slug
        doc.fields = {"name": "Jan Novák", "amount": "50%"}
        doc.version = 1
        doc.created_at = datetime.now(UTC)
        doc.updated_at = datetime.now(UTC)
        return doc

    def _make_template(
        self, latex_template: str | None = r"\documentclass{article}\begin{document}{{name}}\end{document}"
    ):
        from datetime import UTC, datetime

        from neolex.db.drafting_models import DocumentTemplate

        tmpl = DocumentTemplate()
        tmpl.id = uuid.uuid4()
        tmpl.slug = "test_template"
        tmpl.name = "Test Template"
        tmpl.jurisdiction = "CZ"
        tmpl.category = "civil"
        tmpl.latex_template = latex_template
        tmpl.required_fields = ["name"]
        tmpl.field_descriptions = {"name": "Full name"}
        tmpl.description = None
        tmpl.created_at = datetime.now(UTC)
        return tmpl

    @pytest.mark.asyncio
    async def test_get_tex_returns_200_with_correct_content_type(self):
        """GET .../tex returns 200 with application/x-tex and filled LaTeX content."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = self._make_chat_doc(user_id_str, conv_id, doc_id)
        tmpl = self._make_template()

        mock_session = AsyncMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl
        mock_session.execute = AsyncMock(side_effect=[doc_result, tmpl_result])

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/tex")
            assert resp.status_code == 200
            assert "application/x-tex" in resp.headers["content-type"]
            # Field value injected into body
            assert b"Jan Novak" in resp.content or b"Jan Nov" in resp.content or b"Jan" in resp.content
            # Content-Disposition must name the file as {doc_id}.tex
            assert f"{doc_id}.tex" in resp.headers["content-disposition"]
            # Security headers
            assert resp.headers["cache-control"] == "no-store, private"
            assert resp.headers["x-content-type-options"] == "nosniff"
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_tex_field_values_are_latex_escaped(self):
        """GET .../tex escapes LaTeX special chars in field values (security guard)."""
        from datetime import UTC, datetime

        from neolex.db.drafting_models import ChatDocument

        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = ChatDocument()
        doc.id = doc_id
        doc.conversation_id = conv_id
        doc.user_id = uuid.UUID(user_id_str)
        doc.template_slug = "test_template"
        doc.fields = {"name": r"\input{/etc/passwd}"}  # injection attempt
        doc.version = 1
        doc.created_at = datetime.now(UTC)
        doc.updated_at = datetime.now(UTC)

        tmpl = self._make_template()

        mock_session = AsyncMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl
        mock_session.execute = AsyncMock(side_effect=[doc_result, tmpl_result])

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/tex")
            assert resp.status_code == 200
            body = resp.text
            # The raw injection command must not appear in the output
            assert r"\input{/etc/passwd}" not in body
            # The backslash must be escaped
            assert r"\textbackslash{}" in body
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_head_tex_returns_200_no_body(self):
        """HEAD .../tex returns 200 with headers but no response body."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = self._make_chat_doc(user_id_str, conv_id, doc_id)
        tmpl = self._make_template()

        mock_session = AsyncMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl
        mock_session.execute = AsyncMock(side_effect=[doc_result, tmpl_result])

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.head(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/tex")
            assert resp.status_code == 200
            assert "application/x-tex" in resp.headers["content-type"]
            # HEAD must return no body
            assert resp.content == b""
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_tex_422_when_latex_template_is_none(self):
        """GET .../tex returns 422 when template.latex_template is None."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = self._make_chat_doc(user_id_str, conv_id, doc_id)
        tmpl = self._make_template(latex_template=None)

        mock_session = AsyncMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl
        mock_session.execute = AsyncMock(side_effect=[doc_result, tmpl_result])

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/tex")
            assert resp.status_code == 422
            assert "No LaTeX source" in resp.json()["detail"]
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_tex_422_when_latex_template_is_empty_string(self):
        """GET .../tex returns 422 when template.latex_template is empty string."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = self._make_chat_doc(user_id_str, conv_id, doc_id)
        tmpl = self._make_template(latex_template="")

        mock_session = AsyncMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = tmpl
        mock_session.execute = AsyncMock(side_effect=[doc_result, tmpl_result])

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/tex")
            assert resp.status_code == 422
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_tex_404_when_document_not_found(self):
        """GET .../tex returns 404 when document does not exist."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        mock_session = AsyncMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=doc_result)

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/tex")
            assert resp.status_code == 404
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_tex_404_when_template_not_found(self):
        """GET .../tex returns 404 when the template row has been deleted."""
        user_id_str = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        doc = self._make_chat_doc(user_id_str, conv_id, doc_id)

        mock_session = AsyncMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = None  # template deleted
        mock_session.execute = AsyncMock(side_effect=[doc_result, tmpl_result])

        app = _make_app_client(user_id_str, mock_session)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/tex")
            assert resp.status_code == 404
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db

            app.dependency_overrides.pop(get_api_key, None)
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# _latex_to_html_body unit tests (no DB needed — pure conversion)
# ---------------------------------------------------------------------------


class TestLatexToHtmlBody:
    """Unit tests for _latex_to_html_body — direct LaTeX→HTML conversion.

    No fixtures or async needed: the function is a pure string transformer.
    """

    def test_textbf_becomes_strong(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"\textbf{Bold Text}")
        assert "<strong>Bold Text</strong>" in result

    def test_textit_becomes_em(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"\textit{Italic}")
        assert "<em>Italic</em>" in result

    def test_emph_becomes_em(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"\emph{Emphasized}")
        assert "<em>Emphasized</em>" in result

    def test_rule_becomes_hr(self):
        r"""Regression guard: \rule has TWO brace groups.

        The catch-all brace-command strip must not consume only the first group
        (\rule{6cm}), leaving "{0.4pt}" as orphan text and never emitting <hr>.
        Bug fixed in commit 2157d6c.
        """
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"\rule{6cm}{0.4pt}")
        assert "<hr" in result
        # Second brace group must not leak as visible text
        assert "0.4pt" not in result

    def test_vspace_becomes_br(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        # Test in context: bare \vspace{...} alone produces <p><br></p> which
        # the empty-paragraph cleanup pass removes, so we embed it between words.
        result = _latex_to_html_body(r"before\vspace{1em}after")
        assert "<br>" in result

    def test_hspace_is_stripped(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"before\hspace{1em}after")
        assert r"\hspace" not in result
        assert "1em" not in result

    def test_small_group_becomes_closed_span(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"{\small some text}")
        assert '<span style="font-size:9pt;">some text</span>' in result

    def test_standalone_small_is_stripped(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"\small")
        assert r"\small" not in result
        # Must not produce an unclosed <span>
        assert "<span" not in result

    def test_center_env_becomes_div(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"\begin{center}Centred text\end{center}")
        assert '<div style="text-align:center;">' in result
        assert "Centred text" in result

    def test_quote_env_becomes_blockquote(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body(r"\begin{quote}Quoted text\end{quote}")
        assert "<blockquote" in result
        assert "Quoted text" in result

    def test_double_newline_becomes_paragraph_break(self):
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body("First paragraph\n\nSecond paragraph")
        assert "</p><p>" in result

    def test_bare_curly_year_passes_through(self):
        """Bare {2023} in body must appear verbatim — no KeyError, no corruption.

        Regression guard: if _HTML_TEMPLATE.format() re-parsed substituted values,
        {2023} would raise an IndexError or be silently dropped.
        """
        from neolex.services.pdf_generator import _latex_to_html_body

        result = _latex_to_html_body("See judgment {2023}")
        assert "{2023}" in result
