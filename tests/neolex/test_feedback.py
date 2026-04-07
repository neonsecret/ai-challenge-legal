"""Tests for POST /api/feedback endpoint (NEO-235)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from neolex.routers.feedback import FeedbackRequest

# ---------------------------------------------------------------------------
# Pydantic model validation (pure unit tests, no DB)
# ---------------------------------------------------------------------------


def test_feedback_request_valid_positive():
    req = FeedbackRequest(
        trace_id="abc123",
        message_id="msg-001",
        conversation_id="conv-001",
        rating="positive",
    )
    assert req.rating == "positive"
    assert req.comment is None


def test_feedback_request_valid_negative_with_comment():
    req = FeedbackRequest(
        trace_id="abc123",
        message_id="msg-001",
        conversation_id="conv-001",
        rating="negative",
        comment="The answer missed the key article.",
    )
    assert req.rating == "negative"
    assert req.comment == "The answer missed the key article."


def test_feedback_request_invalid_rating():
    with pytest.raises(ValidationError):
        FeedbackRequest(
            trace_id="abc123",
            message_id="msg-001",
            conversation_id="conv-001",
            rating="neutral",  # not allowed
        )


def test_feedback_request_comment_max_length():
    with pytest.raises(ValidationError):
        FeedbackRequest(
            trace_id="abc123",
            message_id="msg-001",
            conversation_id="conv-001",
            rating="positive",
            comment="x" * 2001,  # exceeds 2000 char limit
        )


def test_feedback_request_empty_trace_id_rejected():
    with pytest.raises(ValidationError):
        FeedbackRequest(
            trace_id="",
            message_id="msg-001",
            conversation_id="conv-001",
            rating="positive",
        )


# ---------------------------------------------------------------------------
# HTTP endpoint tests — DB and auth mocked
# ---------------------------------------------------------------------------


def _make_mock_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


@pytest.fixture
async def feedback_client():
    """AsyncClient with auth and DB mocked — never touches a real DB."""
    import asyncio

    from neolex.auth.session import get_current_user
    from neolex.db.postgres import get_db
    from neolex.main import app

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    mock_user = _make_mock_user()

    async def mock_get_current_user():
        return mock_user

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


_FEEDBACK_BODY = {
    "trace_id": "a1b2c3d4-0000-0000-0000-000000000001",
    "message_id": "msg-001",
    "conversation_id": "conv-001",
    "rating": "positive",
    "comment": "Great answer!",
}

_REQUIRED_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def test_submit_feedback_positive(feedback_client):
    """Happy path: positive feedback returns 200 with status ok."""
    response = await feedback_client.post(
        "/api/feedback",
        json=_FEEDBACK_BODY,
        headers=_REQUIRED_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_submit_feedback_negative(feedback_client):
    """Negative rating accepted."""
    body = {**_FEEDBACK_BODY, "rating": "negative", "comment": None}
    response = await feedback_client.post(
        "/api/feedback",
        json=body,
        headers=_REQUIRED_HEADERS,
    )
    assert response.status_code == 200


async def test_submit_feedback_invalid_rating(feedback_client):
    """Invalid rating rejected with 422."""
    body = {**_FEEDBACK_BODY, "rating": "meh"}
    response = await feedback_client.post(
        "/api/feedback",
        json=body,
        headers=_REQUIRED_HEADERS,
    )
    assert response.status_code == 422


async def test_submit_feedback_missing_csrf_header(feedback_client):
    """Missing X-Requested-With header rejected with 403 (CSRF)."""
    response = await feedback_client.post("/api/feedback", json=_FEEDBACK_BODY)
    assert response.status_code == 403


async def test_submit_feedback_no_auth():
    """No session cookie → 401 (auth required)."""
    import asyncio

    from neolex.main import app

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()
    # No dependency override — real auth runs and rejects the request
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/feedback",
            json=_FEEDBACK_BODY,
            headers=_REQUIRED_HEADERS,
        )
    assert response.status_code == 401


async def test_langfuse_failure_does_not_affect_response(feedback_client):
    """Langfuse score push failure must not propagate to the HTTP response."""
    with patch("neolex.routers.feedback._push_score_sync", side_effect=RuntimeError("langfuse down")):
        response = await feedback_client.post(
            "/api/feedback",
            json=_FEEDBACK_BODY,
            headers=_REQUIRED_HEADERS,
        )
    # Still 200 — Langfuse errors are swallowed
    assert response.status_code == 200
