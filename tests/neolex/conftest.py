import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_MOCK_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_MOCK_KEY_ROW = {
    "user_id": str(_MOCK_USER_ID),
    "id": 1,
    "name": "test-client",
    "key_hash": "mockhash",
    "key_prefix": "mockpref",
    "client_slug": str(_MOCK_USER_ID),
    "scope": "admin",
    "email": "test@vitreon.app",
    "active": 1,
    "created_at": "2026-03-26T00:00:00",
    "last_used": None,
}


@pytest.fixture
def mock_pipeline_result() -> dict:
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


def _make_mock_user():
    u = MagicMock()
    u.id = _MOCK_USER_ID
    u.email = "test@vitreon.app"
    u.subscription_status = "enterprise"
    u.daily_queries_used = 0
    u.daily_queries_reset_at = None
    u.monthly_queries_used = 0
    u.monthly_queries_reset_at = None
    u.payment_warning = False
    u.name = "Test User"
    return u


def _make_mock_db(mock_user=None):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_result.scalars.return_value.all.return_value = []
    mock_result.rowcount = 1
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    return session


def _make_mock_audit_db():
    audit = AsyncMock()
    audit.log_query = AsyncMock()
    audit.check_and_increment_rate = AsyncMock(return_value=(0, False))
    audit.create_key = AsyncMock()
    audit.init_schema = AsyncMock()
    return audit


def _make_app_patches(mock_pipeline_result, mock_audit):
    @asynccontextmanager
    async def mock_get_audit_db():
        yield mock_audit

    return [
        patch("neolex.routers.query.run_single_question", new_callable=AsyncMock, return_value=mock_pipeline_result),
        patch("neolex.routers.query.get_audit_db", mock_get_audit_db),
        patch("neolex.services.conversation.create_pipeline_job", new_callable=AsyncMock, return_value=uuid.uuid4()),
        patch("neolex.services.conversation.complete_pipeline_job", new_callable=AsyncMock),
        patch("neolex.services.conversation.fail_pipeline_job", new_callable=AsyncMock),
        patch("neolex.services.conversation.update_pipeline_job_status", new_callable=AsyncMock),
    ]


@pytest.fixture
async def app_client(mock_pipeline_result):
    """Test client with pipeline and auth fully mocked."""
    from neolex.auth.middleware import get_api_key
    from neolex.db.postgres import get_db
    from neolex.main import app

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.startup_time = time.monotonic()
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    mock_user = _make_mock_user()
    mock_db = _make_mock_db(mock_user)
    mock_audit = _make_mock_audit_db()

    async def mock_get_api_key():
        return _MOCK_KEY_ROW

    async def mock_get_db():
        yield mock_db

    app.dependency_overrides[get_api_key] = mock_get_api_key
    app.dependency_overrides[get_db] = mock_get_db

    patches = _make_app_patches(mock_pipeline_result, mock_audit)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Requested-With": "XMLHttpRequest"},
        ) as client:
            yield client

    app.dependency_overrides.pop(get_api_key, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def tmp_db_path(tmp_path) -> str:
    return str(tmp_path / "test_audit.db")


@pytest.fixture(autouse=False)
def override_db_path(tmp_db_path):
    """No-op — settings.db_path removed in PostgreSQL migration."""
    return tmp_db_path


@pytest.fixture
async def seeded_db(tmp_db_path):
    """Stub fixture for backward compat (SQLite audit DB removed)."""
    import hashlib
    import secrets

    raw_key = f"sk_{secrets.token_hex(16)}"
    k_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    k_prefix = raw_key[:8]
    return (
        tmp_db_path,
        raw_key,
        {"key_hash": k_hash, "key_prefix": k_prefix, "client_slug": "test-co", "scope": "query"},
    )


@pytest.fixture
async def authed_client(seeded_db, mock_pipeline_result):
    """Test client yielding (AsyncClient, raw_key)."""
    from neolex.auth.middleware import get_api_key
    from neolex.db.postgres import get_db
    from neolex.main import app

    _db_path, raw_key, _row = seeded_db

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.startup_time = time.monotonic()
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    mock_user = _make_mock_user()
    mock_db = _make_mock_db(mock_user)
    mock_audit = _make_mock_audit_db()

    async def mock_get_api_key():
        return _MOCK_KEY_ROW

    async def mock_get_db():
        yield mock_db

    app.dependency_overrides[get_api_key] = mock_get_api_key
    app.dependency_overrides[get_db] = mock_get_db

    patches = _make_app_patches(mock_pipeline_result, mock_audit)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Requested-With": "XMLHttpRequest"},
        ) as client:
            yield client, raw_key

    app.dependency_overrides.pop(get_api_key, None)
    app.dependency_overrides.pop(get_db, None)
