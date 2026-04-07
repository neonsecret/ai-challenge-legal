"""Tests for authentication middleware and session-based auth.

NOTE: The old API-key-based auth module (neolex.auth.keys) has been removed.
Auth is now session-based (HttpOnly cookie). Integration tests for session
auth endpoints live in tests/integration/test_auth_endpoints.py.

This file retains only the tests that still apply to the current middleware.
"""


# ---------------------------------------------------------------------------
# Exemption: /health needs no auth
# ---------------------------------------------------------------------------


async def test_health_exempt(app_client):
    """GET /health must work without any authentication (auth exempt)."""
    response = await app_client.get("/health")
    assert response.status_code == 200
