import pytest
from unittest.mock import patch, AsyncMock


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
        side_effect=RuntimeError("FAISS index not found"),
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
