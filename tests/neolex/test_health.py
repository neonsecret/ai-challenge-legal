import pytest


async def test_health_ready(app_client):
    response = await app_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["pipeline_ready"] is True
    assert body["workers"] == 5
    assert "version" in body


async def test_health_not_ready(app_client):
    # Temporarily mark not ready
    from neolex.main import app
    app.state.ready = False
    try:
        response = await app_client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["pipeline_ready"] is False
        assert body["status"] == "starting"
    finally:
        app.state.ready = True
