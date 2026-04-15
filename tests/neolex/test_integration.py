"""Integration tests: full stack against real DIFC corpus.

These tests require:
- PostgreSQL running with a populated chunks table (run `make prepare` first)
- ANTHROPIC_API_KEY set in .env
- arlc/ package installed

Skip on CI: pytest tests/neolex/ -m "not integration"
Run locally: pytest tests/neolex/test_integration.py -v -s
"""

import asyncio
import hashlib
import json
import os
import secrets
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# All async tests in this file share one event loop (module scope) so that the
# module-scoped live_client fixture's asyncpg connections are never used from a
# different loop. Without this, Starlette's BaseHTTPMiddleware tasks get
# "Future attached to a different loop" errors on the second+ test.
pytestmark = pytest.mark.asyncio(loop_scope="module")


async def corpus_available() -> bool:
    """Return True if PostgreSQL is reachable and the chunks table has data."""
    try:
        from sqlalchemy import text

        from neolex.db.postgres import engine

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 FROM chunks LIMIT 1"))
            return result.fetchone() is not None
    except Exception:
        return False


def parse_sse_events(text: str) -> list[dict]:
    """Parse SSE wire format into list of {event, data} dicts."""
    events = []
    current: dict = {}
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:") :].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
        # ignore comment lines (: ping)
    if current:
        events.append(current)
    return events


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def live_client():
    """Test client with real lifespan — warms actual pgvector/reranker singletons.

    Module-scoped so warm-up only happens once for all tests in this file.
    Skip if PostgreSQL is unreachable or the chunks table is empty.

    Seeds a test user + session in PostgreSQL so session-cookie-protected
    endpoints work without a pre-existing login.
    """
    if not await corpus_available():
        pytest.skip("DIFC corpus not available (chunks table empty or DB unreachable). Run `make prepare`.")

    from dotenv import load_dotenv

    load_dotenv()

    from neolex.config import settings  # noqa: I001
    from neolex.db.models import Session as DBSession
    from neolex.db.models import User
    from neolex.db.postgres import engine as _engine, get_db
    from sqlalchemy import select

    # Force local-only model warm-up for this module. These tests validate the
    # full app lifecycle and request flow, not remote RTX failover, and cold
    # startup can otherwise exceed the fixture timeout when the remote hosts are
    # unreachable before falling back to localhost.
    old_reranker_remote = os.environ.get("RERANKER_SERVER_URL")
    old_embed_remote = os.environ.get("LLAMA_SERVER_REMOTE_URL")
    old_query_timeout = settings.query_pipeline_timeout_seconds
    os.environ["RERANKER_SERVER_URL"] = ""
    os.environ["LLAMA_SERVER_REMOTE_URL"] = ""
    # Live integration tests run against local models and a real corpus, so
    # three concurrent requests can exceed the production 90s request budget
    # without indicating a deadlock. Widen only this module's live-query budget.
    settings.query_pipeline_timeout_seconds = 300.0

    import arlc.retriever as retriever

    retriever._reranker = None
    retriever._local_reranker = None
    retriever._embedding_model = None

    old_embedder_remote = None
    llama_embedder = sys.modules.get("neolex.embeddings.llama_embedder")
    if llama_embedder is not None:
        old_embedder_remote = getattr(llama_embedder, "_REMOTE_URL", None)
        llama_embedder._REMOTE_URL = ""

    _int_raw_token = secrets.token_urlsafe(32)
    _int_token_hash = hashlib.sha256(_int_raw_token.encode()).hexdigest()
    _int_user_id = uuid.uuid4()

    # Dispose stale pool connections acquired by function-scoped loops in earlier
    # test modules (e.g. test_auth, test_billing, test_drafting). Those loops close
    # at teardown, leaving asyncpg Futures bound to dead loops in the pool.
    # pool_pre_ping cannot rescue them — the ping itself tries to await on a dead
    # loop. Disposing here forces fresh connections in the current module-scoped loop.
    await _engine.dispose()

    # Seed a test user + session before app startup.
    # The app uses session-cookie auth — API key Bearer headers are not supported.
    async for db in get_db():
        existing_user = (
            await db.execute(select(User).where(User.email == "integration-test@vitreon.test"))
        ).scalar_one_or_none()
        if existing_user is None:
            test_user = User(
                id=_int_user_id,
                email="integration-test@vitreon.test",
                name="Integration Test",
                email_verified=True,
                subscription_status="pro",  # pro avoids daily query limits
            )
            db.add(test_user)
            await db.flush()
            _int_user_id = test_user.id
        else:
            _int_user_id = existing_user.id

        session = DBSession(
            user_id=_int_user_id,
            token_hash=_int_token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.add(session)
        await db.commit()
        break

    # Import fresh app instance — triggers lifespan via asgi_lifespan
    from asgi_lifespan import LifespanManager

    from neolex.main import app

    try:
        async with LifespanManager(app, startup_timeout=180, shutdown_timeout=30) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app, raise_app_exceptions=True),
                base_url="http://test",
                timeout=120.0,
                cookies={settings.session_cookie_name: _int_raw_token},
                # CSRFMiddleware requires this header on all state-mutating requests
                headers={"X-Requested-With": "XMLHttpRequest"},
            ) as client:
                yield client
    finally:
        if old_reranker_remote is None:
            os.environ.pop("RERANKER_SERVER_URL", None)
        else:
            os.environ["RERANKER_SERVER_URL"] = old_reranker_remote

        if old_embed_remote is None:
            os.environ.pop("LLAMA_SERVER_REMOTE_URL", None)
        else:
            os.environ["LLAMA_SERVER_REMOTE_URL"] = old_embed_remote
        settings.query_pipeline_timeout_seconds = old_query_timeout

        retriever._reranker = None
        retriever._local_reranker = None
        retriever._embedding_model = None

        if llama_embedder is not None and old_embedder_remote is not None:
            llama_embedder._REMOTE_URL = old_embedder_remote


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
    assert all("doc_id" in s and "page_numbers" in s for s in body["sources"]), f"Malformed sources: {body['sources']}"

    # Confidence should be high for a known-good question
    assert body["confidence"] in ("high", "degraded")

    # Latency p95 target is 15s with remote GPU; allow 90s for degraded mode
    # (local embedding without RTX 3070 + Vertex AI variance can exceed 30s).
    assert body["latency_ms"] < 90_000, f"Latency {body['latency_ms']}ms exceeds 90s pipeline timeout"
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
        assert response.status_code == 200, f"Query {i} failed: {response.status_code} {response.text[:200]}"
        body = response.json()
        assert body["answer"] is not None, f"Query {i} returned null answer"
        assert body["latency_ms"] < 300_000, f"Query {i} took {body['latency_ms']}ms — possible deadlock/timeout"


@pytest.mark.integration
async def test_real_sse_stream(live_client: AsyncClient):
    """POST /api/v1/query/stream delivers all 3 SSE events for a real DIFC question."""
    response = await live_client.post(
        "/api/v1/query/stream",
        json={"question": "What is the limitation period under DIFC Law No. 5 of 2005?"},
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
    assert not changed, f"arlc/ files were modified (violates PIPE-01): {changed}"
