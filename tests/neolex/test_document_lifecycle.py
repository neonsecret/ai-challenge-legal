"""Document lifecycle state-transition tests (real PostgreSQL, NullPool).

Covers the three lifecycle states a document row goes through:
  1. Registered (indexed=False)  — immediately after upload
  2. Indexed  (indexed=True)     — after the reindex worker completes
  3. Deleted  (row absent)       — after explicit client delete

These tests verify the AuditDB state-machine methods directly against
the PostgreSQL `documents` table, not through HTTP mocking.

Run:
    uv run pytest tests/neolex/test_document_lifecycle.py -v
"""

from __future__ import annotations

import asyncio
import datetime
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import neolex.db.postgres as _pg
from neolex.db.audit import AuditDB
from neolex.db.operational_models import Document
from neolex.db.postgres import init_db

# ---------------------------------------------------------------------------
# NullPool engine setup — same pattern as test_billing.py and test_documents.py
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def install_null_pool_lifecycle_engine():
    """Replace the global engine with NullPool to prevent cross-loop connection reuse."""
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
def ensure_lifecycle_schema(install_null_pool_lifecycle_engine):  # noqa: ARG001
    """Create all PostgreSQL tables once for the lifecycle test session."""
    asyncio.run(init_db())


# ---------------------------------------------------------------------------
# Per-test helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def client_slug() -> str:
    """Unique client slug per test to avoid cross-test pollution."""
    return f"lifecycle_{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
async def cleanup_lifecycle_docs():
    """Remove all lifecycle-test document rows after each test."""
    yield
    async with _pg.AsyncSessionLocal() as session:
        await session.execute(delete(Document).where(Document.client_slug.like("lifecycle_%")))
        await session.commit()


def _ts() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


async def test_document_registered_as_not_indexed(client_slug: str):
    """After register_document() the row must have indexed=False (upload state)."""
    doc_id = str(uuid.uuid4())

    async with _pg.AsyncSessionLocal() as session:
        audit = AuditDB(session)
        await audit.register_document(
            doc_id=doc_id,
            client_slug=client_slug,
            filename="contract.pdf",
            size_bytes=4096,
            upload_ts=_ts(),
        )
        await session.commit()

    async with _pg.AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.doc_id == doc_id))
        row = result.scalar_one_or_none()

    assert row is not None, "Row must exist after registration"
    assert row.indexed is False, "Freshly registered document must not be marked indexed"


async def test_document_marked_indexed_after_reindex(client_slug: str):
    """mark_document_indexed() must transition indexed from False to True (indexed state)."""
    doc_id = str(uuid.uuid4())

    async with _pg.AsyncSessionLocal() as session:
        audit = AuditDB(session)
        await audit.register_document(
            doc_id=doc_id,
            client_slug=client_slug,
            filename="statute.pdf",
            size_bytes=8192,
            upload_ts=_ts(),
        )
        await session.commit()

    # Simulate the reindex worker calling mark_document_indexed after completion.
    async with _pg.AsyncSessionLocal() as session:
        audit = AuditDB(session)
        await audit.mark_document_indexed(doc_id, client_slug)
        await session.commit()

    async with _pg.AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.doc_id == doc_id))
        row = result.scalar_one_or_none()

    assert row is not None
    assert row.indexed is True, "Document must be indexed=True after mark_document_indexed()"


async def test_document_full_lifecycle_register_list_delete(client_slug: str):
    """Full lifecycle: register → appears in list → delete → disappears from list."""
    doc_id = str(uuid.uuid4())

    # 1. Register
    async with _pg.AsyncSessionLocal() as session:
        audit = AuditDB(session)
        await audit.register_document(
            doc_id=doc_id,
            client_slug=client_slug,
            filename="judgment.pdf",
            size_bytes=2048,
            upload_ts=_ts(),
        )
        await session.commit()

    # 2. Verify it appears in list_documents
    async with _pg.AsyncSessionLocal() as session:
        audit = AuditDB(session)
        rows = await audit.list_documents(client_slug)

    assert len(rows) == 1
    assert rows[0]["doc_id"] == doc_id
    assert rows[0]["indexed"] is False

    # 3. Delete
    async with _pg.AsyncSessionLocal() as session:
        audit = AuditDB(session)
        deleted = await audit.delete_document(doc_id, client_slug)
        await session.commit()

    assert deleted == 1

    # 4. Verify it is gone from list_documents
    async with _pg.AsyncSessionLocal() as session:
        audit = AuditDB(session)
        rows_after = await audit.list_documents(client_slug)

    assert len(rows_after) == 0, "Document must not appear in list after deletion"
