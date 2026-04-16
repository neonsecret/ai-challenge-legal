"""Shared fixtures for the E2E quality test suite.

Tests in this directory require the live dev stack (localhost:8000 + DB + embeddings).
All live tests are marked @pytest.mark.e2e and skip gracefully when the stack is
unavailable.

Usage:
    uv run pytest tests/e2e/ -m e2e -v          # run all e2e tests
    uv run pytest tests/e2e/ -v                  # include unit-level regression guards
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
TEST_ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@vitreon.app")
TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "Vt9mK2xPqL7nR$#8!")

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Backend availability check
# ---------------------------------------------------------------------------


def _backend_available() -> bool:
    try:
        r = httpx.get(f"{BACKEND_URL}/health", timeout=3)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# ---------------------------------------------------------------------------
# Shared HTTP client with session auth
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def authed_client() -> httpx.AsyncClient:
    """httpx client logged in as admin, reused for the entire session.

    Skips (pytest.skip) if the backend is not reachable.
    """
    if not _backend_available():
        pytest.skip("Backend not reachable — skipping e2e tests")

    client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=120.0)
    headers = {"X-Requested-With": "XMLHttpRequest"}

    login_resp = await client.post(
        "/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
        headers=headers,
    )
    if login_resp.status_code != 200:
        await client.aclose()
        pytest.skip(f"Admin login failed ({login_resp.status_code}) — check TEST_ADMIN_PASSWORD")

    # Copy session cookies into the client for subsequent requests
    for name, value in login_resp.cookies.items():
        client.cookies.set(name, value)

    yield client
    await client.aclose()


# ---------------------------------------------------------------------------
# SSE streaming helper
# ---------------------------------------------------------------------------


async def stream_query(
    client: httpx.AsyncClient,
    question: str,
    corpus: str = "difc",
    use_agent: bool = True,
    corpora_id: str | None = None,
    timeout: float = 120.0,
) -> dict:
    """POST /api/v1/query/stream and collect the full SSE response.

    Returns dict with keys: answer, sources, status_events.
    The ``sources`` list contains raw SourceCitation dicts as emitted by the backend.
    """
    body: dict = {
        "question": question,
        "corpus": corpus,
        "use_agent": use_agent,
        "answer_type": "free_text",
    }
    if corpora_id:
        body["corpora_id"] = corpora_id

    answer = ""
    sources: list[dict] = []
    status_events: list[str] = []
    current_event = ""

    async with client.stream(
        "POST",
        "/api/v1/query/stream",
        json=body,
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=timeout,
    ) as response:
        if response.status_code in (401, 403):
            pytest.skip(f"Auth error {response.status_code}")
        response.raise_for_status()

        async for raw_line in response.aiter_lines():
            raw_line = raw_line.strip()
            if not raw_line:
                current_event = ""
                continue
            if raw_line.startswith("event:"):
                current_event = raw_line[6:].strip()
                continue
            if not raw_line.startswith("data:"):
                continue
            data_str = raw_line[5:].strip()
            if not data_str:
                continue
            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = current_event or (payload.get("event") if isinstance(payload, dict) else "")

            if event_type == "status":
                msg = payload.get("status", "") if isinstance(payload, dict) else str(payload)
                status_events.append(msg)
            elif event_type == "token":
                answer += payload.get("text", "") if isinstance(payload, dict) else ""
            elif event_type == "answer":
                if not answer:
                    answer = payload.get("answer", "") or ""
                sources = payload.get("sources", [])
            elif event_type == "sources":
                sources = payload if isinstance(payload, list) else []

    return {"answer": answer, "sources": sources, "status_events": status_events}
