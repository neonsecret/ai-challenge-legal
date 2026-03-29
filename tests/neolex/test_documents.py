"""Tests for document upload endpoint — Phase 3, Plan 1.

Covers DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07.
Uses tmp filesystem and tmp SQLite DB — never touches data/ or neolex.db.
"""
from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Minimal valid PDF header (just enough for magic byte check)
MINIMAL_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
# 1 byte over 50MB
OVERSIZED_CONTENT = b"%PDF-1.4\n" + b"x" * (50 * 1024 * 1024 + 1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_key_row():
    return {
        "id": 1,
        "name": "test-client",
        "key_hash": "mockhash",
        "key_prefix": "mockpref",
        "client_slug": "test-co",
        "scope": "query",
        "active": 1,
        "created_at": "2026-03-26T00:00:00",
        "last_used": None,
    }


@pytest.fixture
async def doc_client(tmp_path, monkeypatch, mock_key_row):
    """App client with auth mocked, tmp data dir, and tmp SQLite DB.

    Patches:
    - settings.data_dir -> tmp_path/data
    - settings.db_path  -> tmp_path/test.db
    - get_api_key       -> returns mock_key_row
    - run_reindex_job   -> no-op async function (don't actually index)
    """
    from neolex.main import app
    from neolex.auth.middleware import get_api_key
    from neolex.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))

    # Init schema in tmp DB
    from neolex.db.audit import get_audit_db

    async with get_audit_db(str(tmp_path / "test.db")) as db:
        await db.init_schema()

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)

    async def mock_get_api_key():
        return mock_key_row

    app.dependency_overrides[get_api_key] = mock_get_api_key

    # Patch reindex worker module to be instant (no-op) so tests don't spin real indexing
    async def fake_reindex_job(job_id, client_slug, db_path, app=None):
        from neolex.indexing.reindex_worker import update_job
        import datetime

        await update_job(
            job_id,
            db_path,
            status="complete",
            progress=1.0,
            completed_at=datetime.datetime.utcnow().isoformat(),
            doc_count=1,
        )

    with patch("neolex.indexing.reindex_worker.run_reindex_job", new=fake_reindex_job):
        async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    app.dependency_overrides.pop(get_api_key, None)


# ---------------------------------------------------------------------------
# Plan 1 tests: Upload endpoint
# ---------------------------------------------------------------------------


async def test_upload_valid_pdf(doc_client, tmp_path, monkeypatch):
    """DOC-01: Upload a valid PDF — returns 201 with doc_id and job_id."""
    response = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert "doc_id" in data
    assert "job_id" in data
    assert data["filename"] == "contract.pdf"
    assert data["size_bytes"] == len(MINIMAL_PDF)
    assert data["client_slug"] == "test-co"


async def test_upload_rejects_non_pdf_content_type(doc_client):
    """DOC-02: Non-PDF MIME type returns 415."""
    response = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("doc.docx", b"PK\x03\x04some docx content",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 415, response.text
    assert "Unsupported file type" in response.json()["detail"]


async def test_upload_rejects_non_pdf_magic_bytes(doc_client):
    """DOC-02: File with PDF MIME but non-PDF content returns 415."""
    response = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", b"This is not a PDF", "application/pdf")},
    )
    assert response.status_code == 415, response.text


async def test_upload_rejects_oversized_file(doc_client):
    """DOC-02: File exceeding 50MB returns 413."""
    response = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("big.pdf", OVERSIZED_CONTENT, "application/pdf")},
    )
    assert response.status_code == 413, response.text
    assert "too large" in response.json()["detail"].lower() or "50" in response.json()["detail"]


async def test_upload_triggers_reindex_job(doc_client):
    """DOC-04: Upload returns a valid job_id."""
    response = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]
    assert job_id  # non-empty UUID


async def test_upload_audit_logged(doc_client, tmp_path, monkeypatch):
    """AUDIT-02: Upload events are logged in the events table."""
    from neolex.config import settings
    from neolex.db.audit import get_audit_db

    await doc_client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
    )

    async with get_audit_db(settings.db_path) as db:
        events = await db.get_events(limit=10)

    upload_events = [e for e in events if e["event_type"] == "upload"]
    assert len(upload_events) >= 1
    detail = json.loads(upload_events[0]["detail_json"])
    assert detail.get("status") == "accepted"


async def test_upload_stores_in_client_dir(doc_client, tmp_path, monkeypatch):
    """DOC-03: File is saved in per-client directory."""
    from neolex.config import settings

    response = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 201
    doc_id = response.json()["doc_id"]

    client_dir = Path(settings.data_dir) / "clients" / "test-co" / "docs"
    assert client_dir.exists()

    pdf_files = list(client_dir.glob(f"{doc_id}_*.pdf"))
    assert len(pdf_files) == 1, f"Expected 1 PDF file for doc_id {doc_id}, found {pdf_files}"


async def test_upload_requires_auth():
    """AUTH-01: Upload endpoint requires Bearer token."""
    from neolex.main import app

    async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/documents",
            files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Plan 2 tests: Reindex job polling
# ---------------------------------------------------------------------------


async def test_reindex_job_status_polling(doc_client):
    """DOC-05: Can poll job status after upload."""
    upload_resp = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    job_id = upload_resp.json()["job_id"]

    # Poll status — give the background task a moment to complete
    await asyncio.sleep(0.1)

    status_resp = await doc_client.get(f"/api/v1/documents/reindex/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "running", "complete", "failed")


async def test_reindex_job_unknown_id_returns_404(doc_client):
    """DOC-05: Unknown job_id returns 404."""
    response = await doc_client.get("/api/v1/documents/reindex/nonexistent-job-id")
    assert response.status_code == 404


async def test_manual_reindex_trigger(doc_client):
    """Can manually trigger a reindex via POST."""
    response = await doc_client.post("/api/v1/documents/reindex")
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert data["client_slug"] == "test-co"


# ---------------------------------------------------------------------------
# Plan 2 tests: Document listing and deletion
# ---------------------------------------------------------------------------


async def test_list_documents_empty(doc_client):
    """DOC-06: Empty list returned for client with no documents."""
    response = await doc_client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["documents"] == []
    assert data["client_slug"] == "test-co"


async def test_list_documents_after_upload(doc_client):
    """DOC-06: Uploaded document appears in listing."""
    await doc_client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
    )
    response = await doc_client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["documents"][0]["filename"] == "contract.pdf"


async def test_delete_document(doc_client, tmp_path, monkeypatch):
    """DOC-07: Delete a document and verify it's removed."""
    from neolex.config import settings

    upload_resp = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["doc_id"]

    del_resp = await doc_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    data = del_resp.json()
    assert data["deleted"] is True
    assert data["doc_id"] == doc_id
    assert "job_id" in data

    # Verify it's gone from the listing
    list_resp = await doc_client.get("/api/v1/documents")
    assert list_resp.json()["total"] == 0


async def test_delete_nonexistent_document_returns_404(doc_client):
    """DOC-07: Deleting a non-existent document returns 404."""
    response = await doc_client.delete("/api/v1/documents/nonexistent-uuid")
    assert response.status_code == 404


async def test_client_isolation_delete(doc_client, tmp_path, monkeypatch):
    """DOC-03: Cannot delete another client's document (returns 404, not 403)."""
    from neolex.main import app
    from neolex.auth.middleware import get_api_key
    from neolex.config import settings

    # Upload document as test-co
    upload_resp = await doc_client.post(
        "/api/v1/documents",
        files={"file": ("private.pdf", MINIMAL_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["doc_id"]

    # Attempt deletion as different client (evil-corp)
    other_key_row = {
        "id": 2,
        "name": "evil",
        "key_hash": "evihash",
        "key_prefix": "evilpre",
        "client_slug": "evil-corp",
        "scope": "query",
        "active": 1,
        "created_at": "2026-03-26T00:00:00",
        "last_used": None,
    }

    async def evil_key():
        return other_key_row

    app.dependency_overrides[get_api_key] = evil_key

    async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
    ) as evil_client:
        response = await evil_client.delete(f"/api/v1/documents/{doc_id}")

    app.dependency_overrides[get_api_key] = lambda: mock_key_row
    assert response.status_code == 404
