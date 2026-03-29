import asyncio
import os
import pathlib
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_pipeline_result() -> dict:
    """Minimal valid pipeline output dict."""
    return {
        "id": "test-id-001",
        "question": "What is the limitation period?",
        "answer_type": "free_text",
        "answer": "The limitation period is 6 years under Article 10.",
        "chunk_pages": [{"doc_id": "DIFC-LAW-5-2005", "page_numbers": [12]}],
        "ttft_ms": 500,
        "tpot_ms": 10.0,
        "total_time_ms": 3200,
        "input_tokens": 1500,
        "output_tokens": 80,
        "model_name": "claude-sonnet-4-6",
    }


_MOCK_KEY_ROW = {
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
async def app_client(mock_pipeline_result):
    """Test client with pipeline and auth fully mocked. Never touches arlc/, data/, or DB.

    Auth dependency (get_api_key) is patched to return a fixed key row so that
    pipeline-focused tests can run without seeding a real SQLite DB.
    """
    from neolex.main import app
    from neolex.auth.middleware import get_api_key

    # Inject mock state directly — bypasses lifespan so tests run without data/
    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    # Override auth dependency: returns a mock key row without touching the DB.
    # Tests in test_auth.py use authed_client (real DB) to test auth itself.
    async def mock_get_api_key():
        return _MOCK_KEY_ROW

    app.dependency_overrides[get_api_key] = mock_get_api_key

    # Patch where the name is used (the router module), not where it's defined.
    # "neolex.routers.query.run_single_question" intercepts the already-bound
    # reference that was imported at router module load time.
    # Using the service module path would not intercept the router's local binding.
    with patch(
            "neolex.routers.query.run_single_question",
            new_callable=AsyncMock,
            return_value=mock_pipeline_result,
    ):
        async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    # Clean up dependency override after test
    app.dependency_overrides.pop(get_api_key, None)


@pytest.fixture
def tmp_db_path(tmp_path) -> str:
    """Return a temporary SQLite DB path for tests. Never touches neolex.db."""
    return str(tmp_path / "test_audit.db")


@pytest.fixture(autouse=False)
def override_db_path(tmp_db_path, monkeypatch):
    """Override settings.db_path so all DB operations in this test use tmp DB."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)
    return tmp_db_path


@pytest.fixture
async def seeded_db(tmp_db_path, monkeypatch):
    """Tmp DB with schema initialized and one active query-scoped key inserted.

    Returns: (db_path, raw_key, key_row_dict)
    """
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)

    from neolex.auth.keys import generate_key, hash_key, key_prefix
    from neolex.db.audit import get_audit_db

    raw_key = generate_key()
    k_hash = hash_key(raw_key)
    k_prefix = key_prefix(raw_key)

    async with get_audit_db() as db:
        await db.init_schema()
        await db.create_key(
            name="test-client",
            key_hash=k_hash,
            key_prefix=k_prefix,
            client_slug="test-co",
            scope="query",
        )

    return tmp_db_path, raw_key, {"key_hash": k_hash, "key_prefix": k_prefix, "client_slug": "test-co",
                                  "scope": "query"}


@pytest.fixture
async def authed_client(seeded_db):
    """app_client with a valid API key pre-seeded in the tmp DB.

    Yields (AsyncClient, raw_key) tuple.
    The client will pass auth if Authorization: Bearer <raw_key> is sent.
    """
    from neolex.main import app

    _db_path, raw_key, _row = seeded_db

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    mock_result = {
        "id": "test-id-001",
        "question": "What is the limitation period?",
        "answer_type": "free_text",
        "answer": "The limitation period is 6 years under Article 10.",
        "chunk_pages": [{"doc_id": "DIFC-LAW-5-2005", "page_numbers": [12]}],
        "ttft_ms": 500,
        "tpot_ms": 10.0,
        "total_time_ms": 3200,
        "input_tokens": 1500,
        "output_tokens": 80,
        "model_name": "claude-sonnet-4-6",
    }

    with patch(
            "neolex.routers.query.run_single_question",
            new_callable=AsyncMock,
            return_value=mock_result,
    ):
        async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, raw_key
