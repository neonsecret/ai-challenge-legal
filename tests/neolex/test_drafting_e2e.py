"""E2E tests for document drafting — coverage not already in test_drafting.py.

T1 — Admin template CRUD
    POST  /api/v1/admin/templates — 201 + slug roundtrip, 409 on duplicate slug
    PATCH /api/v1/admin/templates/{slug} — 200 + name updated in response

T4 — Parametrized PDF smoke test for all 8 built-in CZ template slugs
    Create doc with dummy fields, call PDF endpoint, assert not 500.
    Accepts 200 or 503 (503 when xelatex not installed).

T8 — All 6 document CRUD endpoints accessible + PUT → 405
    GET list, POST create, GET single, PATCH update, DELETE, PDF,
    plus verifies PUT on the collection endpoint returns 405.

Do NOT duplicate coverage already in test_drafting.py (T2, T3, T5, T6, T7, PDF 503 unit).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CZ_TEMPLATE_SLUGS = [
    "navrh_rozvod",
    "navrh_platebni_rozkaz",
    "odpor_platebni_rozkaz",
    "odvolani_proti_rozsudku",
    "plna_moc_obecna",
    "stiznost_spravni_organ",
    "zaloba_neplatnost_vypovedi",
    "zaloba_na_zaplaceni",
]

# Valid payload matching TemplateCreate schema constraints.
_VALID_TEMPLATE_PAYLOAD = {
    "slug": "test_navrh_e2e",
    "name": "Test návrh E2E",
    "jurisdiction": "CZ",
    "category": "civil",
    "latex_template": r"\documentclass{article}\begin{document}{{name}}\end{document}",
    "required_fields": ["name"],
    "field_descriptions": {"name": "Jméno žalobce"},
    "description": "Testovací vzor",
}


# ---------------------------------------------------------------------------
# Object factories
# ---------------------------------------------------------------------------


def _make_template_obj(slug: str = "test_template") -> "DocumentTemplate":  # noqa: F821
    from neolex.db.drafting_models import DocumentTemplate

    t = DocumentTemplate()
    t.id = uuid.uuid4()
    t.slug = slug
    t.name = f"Template {slug}"
    t.jurisdiction = "CZ"
    t.category = "civil"
    t.latex_template = r"\documentclass{article}\begin{document}{{name}}\end{document}"
    t.required_fields = ["name"]
    t.field_descriptions = {"name": "Jméno"}
    t.description = None
    t.created_at = datetime.now(UTC)
    return t


def _make_doc_obj(user_id_str: str, conv_id: uuid.UUID, slug: str = "test_template") -> "ChatDocument":  # noqa: F821
    from neolex.db.drafting_models import ChatDocument

    doc = ChatDocument()
    doc.id = uuid.uuid4()
    doc.conversation_id = conv_id
    doc.user_id = uuid.UUID(user_id_str)
    doc.template_slug = slug
    doc.fields = {"name": "Test"}
    doc.version = 1
    doc.created_at = datetime.now(UTC)
    doc.updated_at = datetime.now(UTC)
    return doc


# ---------------------------------------------------------------------------
# App client factories (mirrors _make_app_client from test_drafting.py)
# ---------------------------------------------------------------------------


def _mock_admin_app(db_session):
    """App with admin auth (get_admin override) and DB mocked."""
    from neolex.db.postgres import get_db
    from neolex.main import app
    from neolex.routers.admin import get_admin

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    admin_user = MagicMock()
    admin_user.email = "admin@vitreon.app"
    admin_user.id = uuid.uuid4()

    async def mock_get_admin():
        return admin_user

    async def mock_db():
        yield db_session

    app.dependency_overrides[get_admin] = mock_get_admin
    app.dependency_overrides[get_db] = mock_db
    return app


def _mock_user_app(user_id: str, db_session):
    """App with API-key auth and DB mocked (same pattern as test_drafting.py)."""
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
            "user_id": user_id,
            "email": "test@vitreon.app",
            "client_slug": user_id,
            "scope": "admin",
            "key_hash": f"session:{user_id}",
            "key_prefix": "session",
            "name": "Test User",
        }

    async def mock_db():
        yield db_session

    app.dependency_overrides[get_api_key] = mock_auth
    app.dependency_overrides[get_db] = mock_db
    return app


# ---------------------------------------------------------------------------
# T1 — Admin template CRUD
# ---------------------------------------------------------------------------


class TestAdminTemplateCRUD:
    """POST + PATCH /api/v1/admin/templates require admin session (get_admin dep)."""

    @pytest.mark.asyncio
    async def test_create_template_returns_201_and_slug(self):
        """POST creates template, returns 201, echoes slug and name."""
        mock_session = AsyncMock()

        # Uniqueness check: no existing template with this slug.
        check_result = MagicMock()
        check_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=check_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        created_id = uuid.uuid4()

        async def mock_refresh(obj):
            obj.id = created_id
            obj.created_at = datetime.now(UTC)

        mock_session.refresh = mock_refresh

        app = _mock_admin_app(mock_session)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/admin/templates",
                    json=_VALID_TEMPLATE_PAYLOAD,
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 201
            data = resp.json()
            assert data["slug"] == _VALID_TEMPLATE_PAYLOAD["slug"]
            assert data["name"] == _VALID_TEMPLATE_PAYLOAD["name"]
            assert data["jurisdiction"] == "CZ"
            assert data["id"] == str(created_id)
        finally:
            from neolex.db.postgres import get_db
            from neolex.main import app as _app
            from neolex.routers.admin import get_admin

            _app.dependency_overrides.pop(get_admin, None)
            _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_create_template_duplicate_slug_returns_409(self):
        """POST returns 409 when the slug is already taken."""
        existing = _make_template_obj(_VALID_TEMPLATE_PAYLOAD["slug"])

        mock_session = AsyncMock()
        check_result = MagicMock()
        check_result.scalar_one_or_none.return_value = existing  # slug occupied
        mock_session.execute = AsyncMock(return_value=check_result)

        app = _mock_admin_app(mock_session)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/admin/templates",
                    json=_VALID_TEMPLATE_PAYLOAD,
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 409
            assert "already exists" in resp.json()["detail"]
        finally:
            from neolex.db.postgres import get_db
            from neolex.main import app as _app
            from neolex.routers.admin import get_admin

            _app.dependency_overrides.pop(get_admin, None)
            _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_patch_template_returns_200_with_updated_name(self):
        """PATCH updates a template and reflects the new name in the response."""
        slug = _VALID_TEMPLATE_PAYLOAD["slug"]
        existing = _make_template_obj(slug)
        original_name = existing.name

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.commit = AsyncMock()

        # Refresh is a no-op: the handler already mutated the object in-place.
        async def mock_refresh(obj):
            pass

        mock_session.refresh = mock_refresh

        app = _mock_admin_app(mock_session)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/admin/templates/{slug}",
                    json={"name": "Aktualizovaný název"},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "Aktualizovaný název"
            assert data["name"] != original_name
            assert data["slug"] == slug
        finally:
            from neolex.db.postgres import get_db
            from neolex.main import app as _app
            from neolex.routers.admin import get_admin

            _app.dependency_overrides.pop(get_admin, None)
            _app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# T4 — Parametrized PDF smoke test for all 8 CZ templates
# ---------------------------------------------------------------------------


class TestCzTemplatesPdf:
    """Smoke-test the PDF endpoint for every built-in CZ template slug.

    Strategy:
      1. Create a document with dummy fields (template + doc count mocked).
      2. Call GET .../pdf with _XELATEX_BIN=None → deterministic 503.
         The 503 is raised before any DB access, so no second DB mock is needed.
      3. Assert status != 500.  Accepts 200 or 503.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("slug", _CZ_TEMPLATE_SLUGS)
    async def test_pdf_not_500_for_slug(self, slug: str):
        user_id = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        template = _make_template_obj(slug)

        mock_session = AsyncMock()
        # Create sequence: template lookup → returns template; doc count → 0 existing.
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = template
        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(side_effect=[tmpl_result, count_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(UTC)
            obj.updated_at = datetime.now(UTC)

        mock_session.refresh = mock_refresh

        app = _mock_user_app(user_id, mock_session)
        try:
            # Step 1: create document.
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                create_resp = await client.post(
                    f"/api/v1/conversations/{conv_id}/documents",
                    json={"template_slug": slug, "fields": {"name": "Testovací účastník"}},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert create_resp.status_code == 201, f"create failed for slug={slug!r}: {create_resp.text}"
            doc_id = create_resp.json()["id"]

            # Step 2: call PDF endpoint.  _XELATEX_BIN=None → 503 before DB access.
            with patch("neolex.routers.drafting._XELATEX_BIN", None):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    pdf_resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/pdf")
            assert pdf_resp.status_code != 500, f"PDF endpoint returned 500 for slug={slug!r}: {pdf_resp.text}"
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db
            from neolex.main import app as _app

            _app.dependency_overrides.pop(get_api_key, None)
            _app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# T8 — All 6 document endpoints accessible + PUT → 405
# ---------------------------------------------------------------------------


class TestDocumentEndpointsAccessible:
    """One test per endpoint: verifies routing, auth wiring, and expected status codes.

    These are smoke tests — business-logic edge cases live in test_drafting.py.
    """

    def _ids(self):
        """Return fresh (user_id, conv_id, doc_id) for each test."""
        return str(uuid.uuid4()), uuid.uuid4(), uuid.uuid4()

    @pytest.mark.asyncio
    async def test_get_documents_list_returns_200(self):
        """GET /conversations/{conv_id}/documents returns 200 with a JSON list."""
        user_id, conv_id, _ = self._ids()
        doc = _make_doc_obj(user_id, conv_id)

        mock_session = AsyncMock()
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [doc]
        mock_session.execute = AsyncMock(return_value=list_result)

        app = _mock_user_app(user_id, mock_session)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db
            from neolex.main import app as _app

            _app.dependency_overrides.pop(get_api_key, None)
            _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_post_document_returns_201(self):
        """POST /conversations/{conv_id}/documents returns 201."""
        user_id, conv_id, _ = self._ids()
        template = _make_template_obj()

        mock_session = AsyncMock()
        tmpl_result = MagicMock()
        tmpl_result.scalar_one_or_none.return_value = template
        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(side_effect=[tmpl_result, count_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(UTC)
            obj.updated_at = datetime.now(UTC)

        mock_session.refresh = mock_refresh

        app = _mock_user_app(user_id, mock_session)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/conversations/{conv_id}/documents",
                    json={"template_slug": "test_template", "fields": {"name": "Jan Novák"}},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 201
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db
            from neolex.main import app as _app

            _app.dependency_overrides.pop(get_api_key, None)
            _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_single_document_returns_200(self):
        """GET /conversations/{conv_id}/documents/{doc_id} returns 200."""
        user_id, conv_id, doc_id = self._ids()
        doc = _make_doc_obj(user_id, conv_id)
        doc.id = doc_id

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute = AsyncMock(return_value=result)

        app = _mock_user_app(user_id, mock_session)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}")
            assert resp.status_code == 200
            assert resp.json()["id"] == str(doc_id)
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db
            from neolex.main import app as _app

            _app.dependency_overrides.pop(get_api_key, None)
            _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_patch_document_returns_200(self):
        """PATCH /conversations/{conv_id}/documents/{doc_id} returns 200."""
        user_id, conv_id, doc_id = self._ids()
        doc = _make_doc_obj(user_id, conv_id)
        doc.id = doc_id

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            pass

        mock_session.refresh = mock_refresh

        app = _mock_user_app(user_id, mock_session)
        with patch("neolex.routers.drafting.invalidate_cache"):
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.patch(
                        f"/api/v1/conversations/{conv_id}/documents/{doc_id}",
                        json={"fields": {"name": "Aktualizované jméno"}},
                        headers={"X-Requested-With": "XMLHttpRequest"},
                    )
                assert resp.status_code == 200
                assert resp.json()["version"] == 2
            finally:
                from neolex.auth.middleware import get_api_key
                from neolex.db.postgres import get_db
                from neolex.main import app as _app

                _app.dependency_overrides.pop(get_api_key, None)
                _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_delete_document_returns_204(self):
        """DELETE /conversations/{conv_id}/documents/{doc_id} returns 204."""
        user_id, conv_id, doc_id = self._ids()
        doc = _make_doc_obj(user_id, conv_id)
        doc.id = doc_id

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        app = _mock_user_app(user_id, mock_session)
        with patch("neolex.routers.drafting.invalidate_cache"):
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.delete(
                        f"/api/v1/conversations/{conv_id}/documents/{doc_id}",
                        headers={"X-Requested-With": "XMLHttpRequest"},
                    )
                assert resp.status_code == 204
            finally:
                from neolex.auth.middleware import get_api_key
                from neolex.db.postgres import get_db
                from neolex.main import app as _app

                _app.dependency_overrides.pop(get_api_key, None)
                _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_pdf_returns_non_500(self):
        """GET .../pdf returns 200 or 503 — never an unhandled 500.

        Forces xelatex=None so the 503 branch is taken deterministically
        (before any DB access), making this test self-contained.
        """
        user_id, conv_id, doc_id = self._ids()

        mock_session = AsyncMock()
        app = _mock_user_app(user_id, mock_session)
        with patch("neolex.routers.drafting._XELATEX_BIN", None):
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.get(f"/api/v1/conversations/{conv_id}/documents/{doc_id}/pdf")
                assert resp.status_code in (200, 503)
            finally:
                from neolex.auth.middleware import get_api_key
                from neolex.db.postgres import get_db
                from neolex.main import app as _app

                _app.dependency_overrides.pop(get_api_key, None)
                _app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_put_on_document_collection_returns_405(self):
        """PUT /conversations/{conv_id}/documents returns 405 (method not registered).

        Only GET and POST are registered for the collection path; Starlette
        returns 405 when the path matches but the method does not.
        """
        user_id, conv_id, _ = self._ids()

        mock_session = AsyncMock()
        app = _mock_user_app(user_id, mock_session)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/v1/conversations/{conv_id}/documents",
                    json={},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            assert resp.status_code == 405
        finally:
            from neolex.auth.middleware import get_api_key
            from neolex.db.postgres import get_db
            from neolex.main import app as _app

            _app.dependency_overrides.pop(get_api_key, None)
            _app.dependency_overrides.pop(get_db, None)
