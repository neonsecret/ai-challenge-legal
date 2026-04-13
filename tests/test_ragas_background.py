"""Tests for neolex.services.ragas_background.

Covers:
- Sampling logic: rate=0.0 always skips, rate=1.0 always runs, mid-value behaviour
- Error handling: RAGAS / Langfuse failure → warning log, no exception raised
- Langfuse disabled → early no-op
- Empty answer or empty contexts → early no-op
- Happy path: scores are pushed to Langfuse with the correct metric names
- ragas unavailable → early no-op (CVE-2025-69872 remediation: ragas is eval-only)
"""

from __future__ import annotations

# Ensure .env is not required for unit tests
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUESTION = "What is the limitation period under DIFC law?"
ANSWER = "The limitation period is 6 years for contractual claims."
CONTEXTS = [
    "DIFC Law No. 5 of 2005, Article 7: The limitation period is 6 years.",
    "Claims must be brought within the applicable statutory period.",
]
TRACE_ID = "test-trace-id-abc123"


async def _call_eval(**overrides):
    """Call run_ragas_eval with default happy-path arguments, merged with overrides."""
    from neolex.services.ragas_background import run_ragas_eval

    kwargs = dict(
        question=QUESTION,
        answer=ANSWER,
        contexts=CONTEXTS,
        trace_id=TRACE_ID,
        corpus="difc",
        answer_type="free_text",
    )
    kwargs.update(overrides)
    await run_ragas_eval(**kwargs)


# ---------------------------------------------------------------------------
# 0. ragas unavailable → early no-op (production guard)
# ---------------------------------------------------------------------------


class TestRagasUnavailable:
    @pytest.mark.asyncio
    async def test_skips_when_ragas_not_installed(self):
        """_RAGAS_AVAILABLE=False must short-circuit before any eval work."""
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", False),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.asyncio.to_thread") as mock_thread,
        ):
            await _call_eval()
            mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_exception_when_ragas_not_installed(self):
        """Missing ragas must never raise."""
        with patch("neolex.services.ragas_background._RAGAS_AVAILABLE", False):
            await _call_eval()


# ---------------------------------------------------------------------------
# 1. Langfuse disabled → early return, no RAGAS call
# ---------------------------------------------------------------------------


class TestLangfuseDisabled:
    @pytest.mark.asyncio
    async def test_skips_when_langfuse_disabled(self):
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=False),
            patch("neolex.services.ragas_background.asyncio.to_thread") as mock_thread,
        ):
            await _call_eval()
            mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_exception_when_langfuse_disabled(self):
        """Langfuse disabled must never raise."""
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=False),
        ):
            await _call_eval()


# ---------------------------------------------------------------------------
# 2. Sampling logic
# ---------------------------------------------------------------------------


class TestSamplingLogic:
    @pytest.mark.asyncio
    async def test_rate_zero_always_skips(self):
        """RAGAS_SAMPLE_RATE=0.0 must skip 100% of queries."""
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch("neolex.services.ragas_background.asyncio.to_thread") as mock_thread,
        ):
            mock_settings.ragas_sample_rate = 0.0
            await _call_eval()
            mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_one_always_runs(self):
        """RAGAS_SAMPLE_RATE=1.0 must run on every query."""
        fake_scores = {"faithfulness": 0.9, "answer_relevancy": 0.85}
        mock_langfuse = MagicMock()

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=mock_langfuse),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.99),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread", new_callable=AsyncMock, return_value=fake_scores
            ),
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval()
            # Scores should be pushed
            assert mock_langfuse.create_score.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_half_skips_when_random_above(self):
        """With rate=0.5, a random value of 0.7 must skip."""
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.7),
            patch("neolex.services.ragas_background.asyncio.to_thread") as mock_thread,
        ):
            mock_settings.ragas_sample_rate = 0.5
            await _call_eval()
            mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_half_runs_when_random_below(self):
        """With rate=0.5, a random value of 0.3 must proceed."""
        fake_scores = {"faithfulness": 0.8, "answer_relevancy": 0.75}
        mock_langfuse = MagicMock()

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=mock_langfuse),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.3),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread", new_callable=AsyncMock, return_value=fake_scores
            ),
        ):
            mock_settings.ragas_sample_rate = 0.5
            await _call_eval()
            assert mock_langfuse.create_score.call_count == 2


# ---------------------------------------------------------------------------
# 3. Empty answer / no contexts → early no-op
# ---------------------------------------------------------------------------


class TestEmptyInputGuards:
    @pytest.mark.asyncio
    async def test_empty_answer_skips_ragas(self):
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch("neolex.services.ragas_background.asyncio.to_thread") as mock_thread,
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval(answer="")
            mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_contexts_skips_ragas(self):
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch("neolex.services.ragas_background.asyncio.to_thread") as mock_thread,
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval(contexts=[])
            mock_thread.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Error handling: RAGAS failure → warning, no crash
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_ragas_exception_does_not_propagate(self):
        """A crash inside _run_ragas_sync must be swallowed, not raised."""
        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=MagicMock()),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread",
                new_callable=AsyncMock,
                side_effect=RuntimeError("RAGAS evaluation blew up"),
            ),
        ):
            mock_settings.ragas_sample_rate = 1.0
            # Must not raise
            await _call_eval()

    @pytest.mark.asyncio
    async def test_ragas_exception_is_logged_as_warning(self, caplog):
        """A RAGAS failure must emit a warning-level log entry."""
        import logging

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=MagicMock()),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread",
                new_callable=AsyncMock,
                side_effect=RuntimeError("RAGAS evaluation blew up"),
            ),
            caplog.at_level(logging.WARNING, logger="neolex.services.ragas_background"),
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval()
            assert any("RAGAS eval failed" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_langfuse_score_push_failure_does_not_propagate(self):
        """Even if Langfuse.create_score raises, run_ragas_eval must not crash."""
        fake_scores = {"faithfulness": 0.9, "answer_relevancy": 0.85}
        mock_langfuse = MagicMock()
        mock_langfuse.create_score.side_effect = ConnectionError("Langfuse unreachable")

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=mock_langfuse),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=fake_scores,
            ),
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval()


# ---------------------------------------------------------------------------
# 5. Happy path: correct score names and trace_id forwarded to Langfuse
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_score_names_are_prefixed_ragas(self):
        """Scores pushed to Langfuse must be named 'ragas-<metric>'."""
        fake_scores = {"faithfulness": 0.92, "answer_relevancy": 0.88}
        mock_langfuse = MagicMock()

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=mock_langfuse),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=fake_scores,
            ),
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval()

        pushed_names = {call.kwargs["name"] for call in mock_langfuse.create_score.call_args_list}
        assert pushed_names == {"ragas-faithfulness", "ragas-answer_relevancy"}

    @pytest.mark.asyncio
    async def test_trace_id_forwarded_to_langfuse(self):
        """The trace_id argument must be passed verbatim to Langfuse.create_score."""
        fake_scores = {"faithfulness": 0.9}
        mock_langfuse = MagicMock()

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=mock_langfuse),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=fake_scores,
            ),
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval(trace_id="my-specific-trace-id")

        for call in mock_langfuse.create_score.call_args_list:
            assert call.kwargs["trace_id"] == "my-specific-trace-id"

    @pytest.mark.asyncio
    async def test_langfuse_flush_called_after_scores(self):
        """Langfuse.flush() must be called after pushing all scores."""
        fake_scores = {"faithfulness": 0.9, "answer_relevancy": 0.85}
        mock_langfuse = MagicMock()

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=mock_langfuse),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=fake_scores,
            ),
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval()

        mock_langfuse.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_scores_from_ragas_skips_langfuse_push(self):
        """When RAGAS returns an empty dict, no Langfuse scores should be pushed."""
        mock_langfuse = MagicMock()

        with (
            patch("neolex.services.ragas_background._RAGAS_AVAILABLE", True),
            patch("neolex.services.ragas_background.is_enabled", return_value=True),
            patch("neolex.services.ragas_background.get_langfuse", return_value=mock_langfuse),
            patch("neolex.services.ragas_background.settings") as mock_settings,
            patch("neolex.services.ragas_background.random.random", return_value=0.0),
            patch(
                "neolex.services.ragas_background.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            mock_settings.ragas_sample_rate = 1.0
            await _call_eval()

        mock_langfuse.create_score.assert_not_called()
        mock_langfuse.flush.assert_not_called()
