"""Tests for API key authentication (AUTH-01, AUTH-02, AUTH-03, AUTH-05, API-06)."""
import os
import pytest
from neolex.auth.keys import generate_key


# ---------------------------------------------------------------------------
# Exemption: /health needs no key
# ---------------------------------------------------------------------------

async def test_health_exempt(app_client):
    """GET /health must work without any Authorization header (AUTH exempt)."""
    response = await app_client.get("/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Missing / malformed key -> 401
# ---------------------------------------------------------------------------

async def test_missing_key_returns_401(authed_client):
    """No Authorization header -> 401."""
    client, _ = authed_client
    response = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
    )
    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]


async def test_invalid_bearer_format_returns_401(authed_client):
    """Authorization without 'Bearer ' prefix -> 401."""
    client, _ = authed_client
    response = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
        headers={"Authorization": "myrawkey"},
    )
    assert response.status_code == 401


async def test_wrong_key_returns_401(authed_client):
    """Valid format but wrong key value -> 401."""
    client, _ = authed_client
    fake_key = generate_key()  # different from seeded key
    response = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
        headers={"Authorization": f"Bearer {fake_key}"},
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Revoked key -> 401
# ---------------------------------------------------------------------------

async def test_revoked_key_returns_401(seeded_db, monkeypatch):
    """Revoked key (active=0) -> 401."""
    import asyncio
    from unittest.mock import patch, AsyncMock, MagicMock
    from httpx import AsyncClient, ASGITransport
    from neolex.main import app
    from neolex.config import settings
    from neolex.db.audit import get_audit_db

    db_path, raw_key, row = seeded_db
    monkeypatch.setattr(settings, "db_path", db_path)

    # Revoke the key
    async with get_audit_db() as db:
        n = await db.revoke_key(row["key_prefix"])
    assert n == 1

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/query",
            json={"question": "Test?", "answer_type": "free_text"},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Valid key -> passes auth
# ---------------------------------------------------------------------------

async def test_valid_key_passes(authed_client):
    """Valid active key -> request succeeds (mocked pipeline returns 200)."""
    client, raw_key = authed_client
    response = await client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period?", "answer_type": "free_text"},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body


# ---------------------------------------------------------------------------
# Rate limiting (API-06)
# ---------------------------------------------------------------------------

async def test_rate_limit_exceeded(authed_client, monkeypatch):
    """More requests than RATE_LIMIT_RPM in one window -> 429."""
    client, raw_key = authed_client
    monkeypatch.setenv("RATE_LIMIT_RPM", "2")

    # Reset rate state for this key to avoid pollution from other tests
    from neolex.auth.middleware import _rate_state
    from neolex.auth.keys import hash_key
    k_hash = hash_key(raw_key)
    _rate_state.pop(k_hash, None)

    headers = {"Authorization": f"Bearer {raw_key}"}
    payload = {"question": "What is the limitation period?", "answer_type": "free_text"}

    # First 2 requests should pass
    r1 = await client.post("/api/v1/query", json=payload, headers=headers)
    r2 = await client.post("/api/v1/query", json=payload, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200

    # 3rd request exceeds limit
    r3 = await client.post("/api/v1/query", json=payload, headers=headers)
    assert r3.status_code == 429
    assert "Rate limit" in r3.json()["detail"]

    # Cleanup rate state
    _rate_state.pop(k_hash, None)
