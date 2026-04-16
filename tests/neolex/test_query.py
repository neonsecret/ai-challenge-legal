import uuid
from unittest.mock import AsyncMock, MagicMock, patch


async def test_post_query_happy_path(app_client, mock_pipeline_result):
    response = await app_client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period under DIFC Law No. 5 of 2005?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "sources" in body
    assert "confidence" in body
    assert "latency_ms" in body
    assert "model_name" in body
    assert body["confidence"] == "high"
    assert body["sources"][0]["doc_id"] == "DIFC-LAW-5-2005"


async def test_post_query_default_answer_type(app_client, mock_pipeline_result):
    # No answer_type in body — should default to free_text and return 200
    response = await app_client.post(
        "/api/v1/query",
        json={"question": "What is the governing law for contracts?"},
    )
    assert response.status_code == 200


async def test_post_query_validation_error_too_short(app_client):
    response = await app_client.post("/api/v1/query", json={"question": "hi"})
    assert response.status_code == 422


async def test_post_query_missing_question(app_client):
    response = await app_client.post("/api/v1/query", json={})
    assert response.status_code == 422


async def test_post_query_invalid_answer_type(app_client):
    response = await app_client.post(
        "/api/v1/query",
        json={"question": "Is arbitration mandatory?", "answer_type": "blob"},
    )
    assert response.status_code == 422


async def test_post_query_pipeline_failure(app_client):
    with patch(
        "neolex.routers.query.run_single_question",
        new_callable=AsyncMock,
        side_effect=RuntimeError("pgvector query failed"),
    ):
        response = await app_client.post(
            "/api/v1/query",
            json={"question": "What is the limitation period?"},
        )
    assert response.status_code == 500
    body = response.json()
    assert "error" in body["detail"]


async def test_post_query_not_ready(app_client):
    from neolex.main import app

    app.state.ready = False
    try:
        response = await app_client.post(
            "/api/v1/query",
            json={"question": "What is the limitation period?"},
        )
        assert response.status_code == 503
    finally:
        app.state.ready = True


# ---------------------------------------------------------------------------
# doc_id ownership validation tests
# ---------------------------------------------------------------------------

_ATTACKER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_VICTIM_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def test_validate_doc_ids_ownership_rejects_cross_tenant():
    """Helper raises 403 when a doc_id has a tenant_id different from the user."""
    import pytest
    from fastapi import HTTPException

    from neolex.routers.query import _validate_doc_ids_ownership

    mock_result = MagicMock()
    mock_result.mappings.return_value = [{"tenant_id": _VICTIM_TENANT_ID}]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await _validate_doc_ids_ownership(["some-doc-id"], str(_ATTACKER_ID), mock_db)

    assert exc_info.value.status_code == 403


async def test_validate_doc_ids_ownership_allows_own_docs():
    """Helper passes when tenant_id matches the requesting user."""
    from neolex.routers.query import _validate_doc_ids_ownership

    mock_result = MagicMock()
    mock_result.mappings.return_value = [{"tenant_id": _ATTACKER_ID}]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Must not raise
    await _validate_doc_ids_ownership(["own-doc-id"], str(_ATTACKER_ID), mock_db)


async def test_validate_doc_ids_ownership_allows_builtin_docs():
    """Helper passes when no tenant-owned rows are returned (builtin corpus docs)."""
    from neolex.routers.query import _validate_doc_ids_ownership

    mock_result = MagicMock()
    mock_result.mappings.return_value = []  # SQL WHERE tenant_id IS NOT NULL filtered all out
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    await _validate_doc_ids_ownership(["builtin-doc-id"], str(_ATTACKER_ID), mock_db)


async def test_validate_doc_ids_ownership_empty_list_skips_query():
    """Helper is a no-op when doc_ids is empty — no DB call made."""
    from neolex.routers.query import _validate_doc_ids_ownership

    mock_db = AsyncMock()

    await _validate_doc_ids_ownership([], str(_ATTACKER_ID), mock_db)

    mock_db.execute.assert_not_called()


async def test_query_endpoint_rejects_cross_tenant_doc_ids(mock_pipeline_result):
    """Exploit scenario: user sends doc_ids owned by another tenant → 403."""
    import asyncio
    import time
    from contextlib import asynccontextmanager

    from httpx import ASGITransport, AsyncClient

    from neolex.auth.middleware import get_api_key
    from neolex.db.postgres import get_db
    from neolex.main import app

    victim_doc_id = str(uuid.uuid4())
    attacker_key_row = {
        "user_id": str(_ATTACKER_ID),
        "id": 1,
        "name": "attacker",
        "key_hash": "mockhash",
        "key_prefix": "mockpref",
        "client_slug": str(_ATTACKER_ID),
        "scope": "admin",
        "email": "attacker@test.com",
        "active": 1,
        "created_at": "2026-03-26T00:00:00",
        "last_used": None,
    }

    # Mock user for the initial SELECT User query
    mock_user = MagicMock()
    mock_user.id = _ATTACKER_ID
    mock_user.email = "attacker@test.com"
    mock_user.subscription_status = "enterprise"
    mock_user.daily_queries_used = 0
    mock_user.daily_queries_reset_at = None
    mock_user.monthly_queries_used = 0
    mock_user.monthly_queries_reset_at = None
    mock_user.payment_warning = False
    mock_user.name = "Attacker"

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = mock_user

    # Ownership check returns a row with the victim's tenant_id
    ownership_result = MagicMock()
    ownership_result.mappings.return_value = [{"tenant_id": _VICTIM_TENANT_ID}]

    call_count = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return user_result if call_count == 1 else ownership_result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    mock_audit = AsyncMock()
    mock_audit.log_query = AsyncMock()
    mock_audit.check_and_increment_rate = AsyncMock(return_value=(0, False))

    @asynccontextmanager
    async def mock_get_audit_db():
        yield mock_audit

    async def mock_get_api_key():
        return attacker_key_row

    async def mock_get_db():
        yield mock_db

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.startup_time = time.monotonic()
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    app.dependency_overrides[get_api_key] = mock_get_api_key
    app.dependency_overrides[get_db] = mock_get_db
    try:
        with patch("neolex.routers.query.get_audit_db", mock_get_audit_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-Requested-With": "XMLHttpRequest"},
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={
                        "question": "What is the governing law for contracts in DIFC?",
                        "doc_ids": [victim_doc_id],
                    },
                )
    finally:
        app.dependency_overrides.pop(get_api_key, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
