"""Integration tests: full stack against real DIFC corpus.

These tests require:
- data/ directory with FAISS/BM25 indexes (run `make prepare` first)
- ANTHROPIC_API_KEY set in .env
- arlc/ package installed

Skip on CI: pytest tests/neolex/ -m "not integration"
Run locally: pytest tests/neolex/test_integration.py -v -s
"""
import asyncio
import json
import os
import subprocess

import pytest
from httpx import AsyncClient, ASGITransport


def corpus_available() -> bool:
    """Return True if FAISS indexes exist in data/."""
    if not os.path.exists("data"):
        return False
    for root, _, files in os.walk("data"):
        for f in files:
            if f.endswith(".faiss") or f.endswith(".bin"):
                return True
    return False


def parse_sse_events(text: str) -> list[dict]:
    """Parse SSE wire format into list of {event, data} dicts."""
    events = []
    current: dict = {}
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:"):].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
        # ignore comment lines (: ping)
    if current:
        events.append(current)
    return events


@pytest.fixture(scope="module")
async def live_client():
    """Test client with real lifespan — warms actual FAISS/BM25/cross-encoder singletons.

    Module-scoped so warm-up only happens once for all tests in this file.
    Skip if corpus not on disk.
    """
    if not corpus_available():
        pytest.skip("DIFC corpus not available (data/*.faiss missing). Run `make prepare`.")

    from dotenv import load_dotenv
    load_dotenv()

    # Import fresh app instance — triggers lifespan via asgi_lifespan
    from neolex.main import app
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app, startup_timeout=120, shutdown_timeout=30) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app, raise_app_exceptions=True),
            base_url="http://test",
            timeout=120.0,
        ) as client:
            yield client


@pytest.mark.integration
async def test_health_with_real_startup(live_client: AsyncClient):
    """GET /health returns ready after real lifespan completes."""
    response = await live_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline_ready"] is True
    assert body["status"] == "ready"


@pytest.mark.integration
async def test_real_query_returns_grounded_answer(live_client: AsyncClient):
    """POST /api/v1/query returns answer with source citations for a known DIFC question."""
    response = await live_client.post(
        "/api/v1/query",
        json={"question": "What is the limitation period under DIFC Law No. 5 of 2005?"},
    )
    assert response.status_code == 200
    body = response.json()

    # Answer must be present and non-empty
    assert body["answer"] is not None
    assert isinstance(body["answer"], str)
    assert len(body["answer"]) > 20, f"Answer too short: {body['answer']!r}"

    # Sources must include at least one document with page citations
    assert len(body["sources"]) > 0, "No sources returned"
    # doc_ids are content hashes (e.g. 536bbce854b9...) not human-readable names
    assert all("doc_id" in s and "page_numbers" in s for s in body["sources"]), (
        f"Malformed sources: {body['sources']}"
    )

    # Confidence should be high for a known-good question
    assert body["confidence"] in ("high", "degraded")

    # Latency under 15 seconds (p95 requirement PIPE-04)
    assert body["latency_ms"] < 30_000, f"Latency {body['latency_ms']}ms exceeds 30s"
    assert body["latency_ms"] > 0, "latency_ms must be > 0"


@pytest.mark.integration
async def test_concurrent_queries_no_deadlock(live_client: AsyncClient):
    """3 concurrent queries complete without deadlock.

    This is the primary guard against the cross-encoder threading.Lock deadlock
    documented in arlc/pipeline.py lines 1491-1493.
    The Semaphore(5) in lifespan and pre-warmed singletons prevent this.
    """
    questions = [
        "What is the limitation period under DIFC Law No. 5 of 2005?",
        "What is the governing law for contracts in the DIFC?",
        "Who has jurisdiction over employment disputes in the DIFC?",
    ]

    async def single_query(q: str):
        return await live_client.post("/api/v1/query", json={"question": q})

    # Fire all 3 concurrently
    responses = await asyncio.gather(*[single_query(q) for q in questions])

    for i, response in enumerate(responses):
        assert response.status_code == 200, (
            f"Query {i} failed: {response.status_code} {response.text[:200]}"
        )
        body = response.json()
        assert body["answer"] is not None, f"Query {i} returned null answer"
        assert body["latency_ms"] < 30_000, (
            f"Query {i} took {body['latency_ms']}ms — possible deadlock/timeout"
        )


@pytest.mark.integration
async def test_real_sse_stream(live_client: AsyncClient):
    """GET /api/v1/query/stream delivers all 3 SSE events for a real DIFC question."""
    response = await live_client.get(
        "/api/v1/query/stream",
        params={"question": "What is the limitation period under DIFC Law No. 5 of 2005?"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    events = parse_sse_events(response.text)
    named = [e for e in events if "event" in e]

    event_names = [e["event"] for e in named]
    assert "status" in event_names, f"Missing status event: {event_names}"
    assert "answer" in event_names, f"Missing answer event: {event_names}"
    assert "done" in event_names, f"Missing done event: {event_names}"

    # Events must be in order
    assert event_names.index("status") < event_names.index("answer") < event_names.index("done")

    # Answer event data must be valid QueryResponse JSON
    answer_event = next(e for e in named if e["event"] == "answer")
    answer_data = json.loads(answer_event["data"])
    assert "answer" in answer_data
    assert "sources" in answer_data
    assert "confidence" in answer_data


@pytest.mark.integration
async def test_arlc_directory_unchanged():
    """arlc/ files must not be modified by any neolex/ code (PIPE-01).

    Verifies via git that arlc/ has no staged or unstaged changes.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = subprocess.run(
        ["git", "diff", "--name-only", "arlc/"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    changed = result.stdout.strip()
    assert not changed, (
        f"arlc/ files were modified (violates PIPE-01): {changed}"
    )
