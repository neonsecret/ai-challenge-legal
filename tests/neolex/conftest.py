import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_pipeline_result() -> dict:
    """Minimal valid pipeline output dict."""
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


@pytest.fixture
async def app_client(mock_pipeline_result):
    """Test client with pipeline fully mocked. Never touches arlc/ or data/."""
    from neolex.main import app

    # Inject mock state directly — bypasses lifespan so tests run without data/
    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    # Patch where the name is used (the router module), not where it's defined.
    # "neolex.routers.query.run_single_question" intercepts the already-bound
    # reference that was imported at router module load time.
    # Using the service module path would not intercept the router's local binding.
    with patch(
        "neolex.routers.query.run_single_question",
        new_callable=AsyncMock,
        return_value=mock_pipeline_result,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
