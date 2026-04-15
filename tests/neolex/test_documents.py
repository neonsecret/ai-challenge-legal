"""Tests for document management — DOC-01 through DOC-07.

Section A: AuditDB document registry (real PostgreSQL, NullPool)
    Tests register_document, get_document, list_documents,
    mark_document_indexed, and delete_document directly against the DB.

Section B: HTTP endpoint tests (real PostgreSQL + minimal FastAPI app)
    Tests auth enforcement and upload validation via the documents router.

Run:
    uv run pytest tests/neolex/test_documents.py -v
"""

from __future__ import annotations

import asyncio
import datetime
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import neolex.db.postgres as _pg
from neolex.auth.session import get_current_user
from neolex.db.audit import AuditDB
from neolex.db.models import User
from neolex.db.operational_models import Document
from neolex.db.postgres import get_db, init_db

# Minimal valid PDF bytes (magic bytes only — sufficient for upload validation tests).
_PDF_STUB = b"%PDF-1.4\n%%EOF\n"

# Minimal valid UTF-8 text content for TXT upload tests.
_TXT_STUB = b"This is a sample legal text document.\n"

# Binary content that masquerades as text (contains null byte — should be rejected).
_BINARY_STUB = b"Not text\x00binary garbage\x01\x02"


# ---------------------------------------------------------------------------
# NullPool engine — prevents cross-loop connection reuse (pytest-asyncio auto mode)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def install_null_pool_docs_engine():
    """Replace the global SQLAlchemy engine with NullPool for document tests.

    NullPool never caches connections, so each test's event loop gets a fresh
    connection that it owns — avoids asyncpg "bound to a different loop" errors.
    """
    _db_url = _pg._db_url
    test_engine = create_async_engine(_db_url, poolclass=NullPool)
    test_sessions = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    old_engine = _pg.engine
    old_sessions = _pg.AsyncSessionLocal

    _pg.engine = test_engine
    _pg.AsyncSessionLocal = test_sessions

    yield

    _pg.engine = old_engine
    _pg.AsyncSessionLocal = old_sessions


@pytest.fixture(scope="session", autouse=True)
def ensure_docs_schema(install_null_pool_docs_engine):  # noqa: ARG001
    """Create all PostgreSQL tables once for this test session."""
    asyncio.run(init_db())


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_slug() -> str:
    """Unique client slug per test — prevents cross-test data pollution."""
    return f"doctest_{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
async def cleanup_test_docs():
    """Delete all document rows created by this test suite after each test."""
    yield
    async with _pg.AsyncSessionLocal() as session:
        await session.execute(delete(Document).where(Document.client_slug.like("doctest_%")))
        await session.commit()


@pytest.fixture
def unique_email() -> str:
    return f"doctest_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def enterprise_user(unique_email: str) -> User:
    """Enterprise-tier test user persisted in PostgreSQL."""
    from neolex.config import settings

    user = User(
        email=unique_email,
        email_verified=True,
        subscription_status="enterprise",
        max_corpora=settings.enterprise_max_corpora,
    )
    async with _pg.AsyncSessionLocal() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest.fixture(autouse=True)
async def cleanup_test_users():
    """Delete all document-test users after each test (cascade-deletes sessions/tokens)."""
    yield
    async with _pg.AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.email.like("doctest_%@example.com")))
        await session.commit()


# ---------------------------------------------------------------------------
# Mock helpers for HTTP tests
# ---------------------------------------------------------------------------


def _make_mock_audit() -> AsyncMock:
    """Return an AuditDB-shaped AsyncMock for endpoint tests."""
    mock = AsyncMock()
    mock.list_documents = AsyncMock(return_value=[])
    mock.log_event = AsyncMock()
    mock.register_document = AsyncMock()
    mock.get_document = AsyncMock(return_value=None)
    mock.delete_document = AsyncMock(return_value=1)
    return mock


@asynccontextmanager
async def _mock_get_audit_db():
    yield _make_mock_audit()


# ---------------------------------------------------------------------------
# Minimal FastAPI test app (documents router only, no pipeline startup)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def docs_app() -> FastAPI:
    """FastAPI app containing only the documents router."""
    from neolex.routers.documents import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def authed_docs_client(docs_app: FastAPI, enterprise_user: User) -> AsyncClient:
    """Authenticated HTTP client: injects enterprise_user via get_current_user override.

    get_audit_db is replaced with a lightweight mock to avoid hitting the
    audit table from HTTP-level validation tests.
    """
    user_id = enterprise_user.id

    async def _auth(db: AsyncSession = Depends(get_db)) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    docs_app.dependency_overrides[get_current_user] = _auth

    with patch("neolex.routers.documents.get_audit_db", _mock_get_audit_db):
        async with AsyncClient(
            transport=ASGITransport(app=docs_app),
            base_url="http://test",
        ) as c:
            yield c

    docs_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def unauthed_docs_client(docs_app: FastAPI) -> AsyncClient:
    """Unauthenticated client — no session cookie, expects 401 responses."""
    docs_app.dependency_overrides.pop(get_current_user, None)
    async with AsyncClient(
        transport=ASGITransport(app=docs_app),
        base_url="http://test",
    ) as c:
        yield c


# ===========================================================================
# A. AuditDB document registry — real PostgreSQL, no mocks
# ===========================================================================


class TestAuditDBRegisterDocument:
    """register_document() stores correct data in the documents table (DOC-01)."""

    async def test_stores_row_with_correct_fields(self, client_slug: str):
        doc_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            await audit.register_document(
                doc_id=doc_id,
                client_slug=client_slug,
                filename="contract.pdf",
                size_bytes=1024,
                upload_ts=ts,
            )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(Document).where(Document.doc_id == doc_id))
            row = result.scalar_one_or_none()

        assert row is not None
        assert row.doc_id == doc_id
        assert row.client_slug == client_slug
        assert row.filename == "contract.pdf"
        assert row.size_bytes == 1024
        assert row.indexed is False

    async def test_is_idempotent_on_duplicate_doc_id(self, client_slug: str):
        """Registering the same doc_id twice must not create a second row."""
        doc_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            for _ in range(2):
                await audit.register_document(
                    doc_id=doc_id,
                    client_slug=client_slug,
                    filename="a.pdf",
                    size_bytes=512,
                    upload_ts=ts,
                )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(
                select(Document).where(Document.doc_id == doc_id, Document.client_slug == client_slug)
            )
            rows = result.scalars().all()

        assert len(rows) == 1


class TestAuditDBGetDocument:
    """get_document() retrieves by (doc_id, client_slug) with tenant isolation (DOC-07)."""

    async def test_returns_correct_row(self, client_slug: str):
        doc_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            await audit.register_document(
                doc_id=doc_id,
                client_slug=client_slug,
                filename="lease.pdf",
                size_bytes=2048,
                upload_ts=ts,
            )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            row = await audit.get_document(doc_id, client_slug)

        assert row is not None
        assert row["doc_id"] == doc_id
        assert row["filename"] == "lease.pdf"
        assert row["size_bytes"] == 2048
        assert row["indexed"] is False

    async def test_client_isolation_returns_none_for_other_tenant(self, client_slug: str):
        """get_document() must not return a document owned by a different client."""
        doc_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            await audit.register_document(
                doc_id=doc_id,
                client_slug=client_slug,
                filename="private.pdf",
                size_bytes=100,
                upload_ts=ts,
            )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            row = await audit.get_document(doc_id, "other_tenant")

        assert row is None


class TestAuditDBListDocuments:
    """list_documents() returns the correct set for each client (DOC-06)."""

    async def test_returns_all_documents_for_client(self, client_slug: str):
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            for i in range(3):
                await audit.register_document(
                    doc_id=str(uuid.uuid4()),
                    client_slug=client_slug,
                    filename=f"doc{i}.pdf",
                    size_bytes=100 * (i + 1),
                    upload_ts=ts,
                )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            rows = await audit.list_documents(client_slug)

        assert len(rows) == 3
        assert {r["filename"] for r in rows} == {"doc0.pdf", "doc1.pdf", "doc2.pdf"}

    async def test_client_isolation_hides_other_tenants_documents(self, client_slug: str):
        """list_documents() must not return rows belonging to other clients (AUDIT-04)."""
        other_slug = f"doctest_{uuid.uuid4().hex}"
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            await audit.register_document(
                doc_id=str(uuid.uuid4()),
                client_slug=other_slug,
                filename="other_tenant.pdf",
                size_bytes=500,
                upload_ts=ts,
            )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            rows = await audit.list_documents(client_slug)

        assert len(rows) == 0

    async def test_empty_result_for_client_with_no_documents(self, client_slug: str):
        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            rows = await audit.list_documents(client_slug)

        assert rows == []


class TestAuditDBMarkIndexed:
    """mark_document_indexed() transitions indexed from False → True."""

    async def test_sets_indexed_flag(self, client_slug: str):
        doc_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            await audit.register_document(
                doc_id=doc_id,
                client_slug=client_slug,
                filename="indexed.pdf",
                size_bytes=300,
                upload_ts=ts,
            )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            await audit.mark_document_indexed(doc_id, client_slug)
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(Document).where(Document.doc_id == doc_id))
            row = result.scalar_one_or_none()

        assert row is not None
        assert row.indexed is True


class TestAuditDBDeleteDocument:
    """delete_document() removes the row and returns the correct count (DOC-07)."""

    async def test_removes_row_and_returns_one(self, client_slug: str):
        doc_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            await audit.register_document(
                doc_id=doc_id,
                client_slug=client_slug,
                filename="todelete.pdf",
                size_bytes=200,
                upload_ts=ts,
            )
            await session.commit()

        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            deleted = await audit.delete_document(doc_id, client_slug)
            await session.commit()

        assert deleted == 1

        async with _pg.AsyncSessionLocal() as session:
            result = await session.execute(select(Document).where(Document.doc_id == doc_id))
            row = result.scalar_one_or_none()

        assert row is None

    async def test_returns_zero_when_document_not_found(self, client_slug: str):
        async with _pg.AsyncSessionLocal() as session:
            audit = AuditDB(session)
            deleted = await audit.delete_document("nonexistent_doc_id", client_slug)
            await session.commit()

        assert deleted == 0


# ===========================================================================
# B. HTTP endpoint tests — auth enforcement and upload validation
# ===========================================================================


class TestDocumentEndpointAuth:
    """Auth enforcement: all document endpoints return 401 without a session (DOC-01, DOC-06, DOC-07)."""

    async def test_upload_without_auth_returns_401(self, unauthed_docs_client: AsyncClient):
        resp = await unauthed_docs_client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", _PDF_STUB, "application/pdf")},
            data={"collection": "My Docs"},
        )
        assert resp.status_code == 401

    async def test_list_without_auth_returns_401(self, unauthed_docs_client: AsyncClient):
        resp = await unauthed_docs_client.get("/api/v1/documents")
        assert resp.status_code == 401

    async def test_delete_without_auth_returns_401(self, unauthed_docs_client: AsyncClient):
        resp = await unauthed_docs_client.delete("/api/v1/documents/some_doc_id")
        assert resp.status_code == 401


class TestDocumentUploadValidation:
    """Upload input validation: MIME type, file size, empty file (DOC-02, DOC-03, DOC-04)."""

    async def test_unsupported_mime_type_returns_415(self, authed_docs_client: AsyncClient):
        """POST with an unsupported MIME type must be rejected with 415."""
        resp = await authed_docs_client.post(
            "/api/v1/documents",
            files={"file": ("doc.docx", b"PK\x03\x04", "application/msword")},
            data={"collection": "My Docs"},
        )
        assert resp.status_code == 415
        assert "application/pdf" in resp.json()["detail"]
        assert "text/plain" in resp.json()["detail"]

    async def test_oversized_content_length_returns_413(self, authed_docs_client: AsyncClient):
        """POST with Content-Length > 50 MB must be rejected with 413 before reading (DOC-02)."""
        over_limit = 50 * 1024 * 1024 + 1
        resp = await authed_docs_client.post(
            "/api/v1/documents",
            files={"file": ("big.pdf", _PDF_STUB, "application/pdf")},
            data={"collection": "My Docs"},
            headers={"Content-Length": str(over_limit)},
        )
        assert resp.status_code == 413

    async def test_empty_pdf_returns_400(self, authed_docs_client: AsyncClient):
        """POST with 0-byte body must be rejected with 400 (DOC-04)."""
        resp = await authed_docs_client.post(
            "/api/v1/documents",
            files={"file": ("empty.pdf", b"", "application/pdf")},
            data={"collection": "My Docs"},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    async def test_delete_invalid_doc_id_format_returns_400(self, authed_docs_client: AsyncClient):
        """DELETE with a doc_id containing invalid characters must return 400."""
        resp = await authed_docs_client.delete("/api/v1/documents/invalid!doc@id")
        assert resp.status_code == 400

    async def test_text_plain_charset_mime_is_accepted(self, authed_docs_client: AsyncClient):
        """POST with 'text/plain; charset=utf-8' MIME must not be rejected at the MIME guard."""
        # charset-qualified MIME reaches save_upload (binary content triggers 415 there)
        resp = await authed_docs_client.post(
            "/api/v1/documents",
            files={"file": ("note.txt", _BINARY_STUB, "text/plain; charset=utf-8")},
            data={"collection": "My Docs"},
        )
        # 415 from content check (binary), NOT from MIME guard (which now accepts text/plain)
        assert resp.status_code == 415
        assert "null bytes" in resp.json()["detail"] or "UTF-8" in resp.json()["detail"]

    async def test_binary_content_as_txt_returns_415(self, authed_docs_client: AsyncClient):
        """POST with text/plain MIME but binary content (null bytes) must return 415 (AC-2)."""
        resp = await authed_docs_client.post(
            "/api/v1/documents",
            files={"file": ("malicious.txt", _BINARY_STUB, "text/plain")},
            data={"collection": "My Docs"},
        )
        assert resp.status_code == 415
        assert "null bytes" in resp.json()["detail"] or "UTF-8" in resp.json()["detail"]

    async def test_oversized_txt_content_length_returns_413(self, authed_docs_client: AsyncClient):
        """POST with Content-Length > 50 MB for a .txt file must be rejected with 413 (AC-3)."""
        over_limit = 50 * 1024 * 1024 + 1
        resp = await authed_docs_client.post(
            "/api/v1/documents",
            files={"file": ("big.txt", _TXT_STUB, "text/plain")},
            data={"collection": "My Docs"},
            headers={"Content-Length": str(over_limit)},
        )
        assert resp.status_code == 413


class TestDocumentListEndpoint:
    """GET /api/v1/documents returns correct structure (DOC-06)."""

    async def test_authenticated_request_returns_200_with_list(self, authed_docs_client: AsyncClient):
        resp = await authed_docs_client.get("/api/v1/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert "documents" in body
        assert "total" in body
        assert isinstance(body["documents"], list)


class TestDocumentDeleteEndpoint:
    """DELETE /api/v1/documents/{doc_id} (DOC-07)."""

    async def test_nonexistent_doc_returns_404(self, authed_docs_client: AsyncClient):
        """Deleting a doc not in the registry must return 404."""
        # Mock audit db returns None for get_document (already set in _make_mock_audit)
        resp = await authed_docs_client.delete("/api/v1/documents/nonexistent_doc")
        assert resp.status_code == 404
