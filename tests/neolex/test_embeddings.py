"""Unit tests for neolex.embeddings — config and LlamaServerEmbedder."""

from __future__ import annotations

import importlib
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestEmbeddingConfig:
    def test_default_backend_is_llama_server(self, monkeypatch):
        monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
        import neolex.embeddings.config as cfg

        importlib.reload(cfg)
        assert cfg.EMBEDDING_BACKEND == "llama-server"

    def test_invalid_backend_raises(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "unknown-model")
        import neolex.embeddings.config as cfg

        with pytest.raises(ValueError, match="EMBEDDING_MODEL must be one of"):
            importlib.reload(cfg)

    def test_default_dim_is_1024(self, monkeypatch):
        monkeypatch.delenv("EMBEDDING_DIM", raising=False)
        import neolex.embeddings.config as cfg

        importlib.reload(cfg)
        assert cfg.EMBEDDING_DIM == 1024

    def test_custom_dim(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DIM", "512")
        import neolex.embeddings.config as cfg

        importlib.reload(cfg)
        assert cfg.EMBEDDING_DIM == 512

    def test_full_dim_sentinel(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DIM", "full")
        import neolex.embeddings.config as cfg

        importlib.reload(cfg)
        assert cfg.EMBEDDING_DIM == 8192  # sentinel = no truncation


# ---------------------------------------------------------------------------
# LlamaServerEmbedder tests (mocked HTTP)
# ---------------------------------------------------------------------------


def _mock_embed_response(texts: list[str], dim: int = 4096) -> dict:
    """Simulate a /v1/embeddings response with random normalised vectors."""
    data = []
    for i, _ in enumerate(texts):
        vec = np.random.randn(dim).astype(np.float32)
        vec /= np.linalg.norm(vec)
        data.append({"index": i, "embedding": vec.tolist()})
    return {"data": data}


class TestLlamaServerEmbedder:
    @pytest.fixture
    def mock_requests(self, monkeypatch):
        """Patch requests.get (health) and requests.post (embeddings)."""
        import requests

        get_mock = MagicMock()
        get_mock.return_value.status_code = 200
        get_mock.return_value.raise_for_status = MagicMock()

        def post_side_effect(url, json=None, **kwargs):
            texts = json.get("input", [])
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = _mock_embed_response(texts, dim=4096)
            return resp

        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(requests, "post", post_side_effect)

    def test_embed_texts_shape(self, mock_requests):
        from neolex.embeddings.llama_embedder import LlamaServerEmbedder

        emb = LlamaServerEmbedder(url="http://localhost:8088")
        result = emb.embed_texts(["passage one", "passage two"])
        assert result.shape == (2, 4096)
        assert result.dtype == np.float32

    def test_embed_texts_is_normalised(self, mock_requests):
        from neolex.embeddings.llama_embedder import LlamaServerEmbedder

        emb = LlamaServerEmbedder(url="http://localhost:8088")
        result = emb.embed_texts(["test passage"])
        norms = np.linalg.norm(result, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_embed_query_shape(self, mock_requests):
        from neolex.embeddings.llama_embedder import LlamaServerEmbedder

        emb = LlamaServerEmbedder(url="http://localhost:8088")
        result = emb.embed_query("What is the limitation period?")
        assert result.ndim == 1
        assert result.shape[0] == 4096

    def test_encode_prompt_name_query_adds_prefix(self, monkeypatch):
        """encode(prompt_name='query') should prepend the instruction prefix."""
        import requests

        captured: list[list[str]] = []

        get_mock = MagicMock()
        get_mock.return_value.status_code = 200
        get_mock.return_value.raise_for_status = MagicMock()

        def capturing_post(url, json=None, **kwargs):
            captured.append(json.get("input", []))
            texts = json.get("input", [])
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = _mock_embed_response(texts)
            return resp

        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(requests, "post", capturing_post)

        from neolex.embeddings.llama_embedder import QWEN_QUERY_PREFIX, LlamaServerEmbedder

        emb = LlamaServerEmbedder(url="http://localhost:8088")
        emb.encode("my legal question", prompt_name="query")

        all_texts = [t for batch in captured for t in batch]
        assert any(QWEN_QUERY_PREFIX in t for t in all_texts)

    def test_encode_no_prefix_without_prompt_name(self, monkeypatch):
        """encode() without prompt_name should send text as-is."""
        import requests

        captured: list[list[str]] = []

        get_mock = MagicMock()
        get_mock.return_value.status_code = 200
        get_mock.return_value.raise_for_status = MagicMock()

        def capturing_post(url, json=None, **kwargs):
            captured.append(json.get("input", []))
            texts = json.get("input", [])
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = _mock_embed_response(texts)
            return resp

        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(requests, "post", capturing_post)

        from neolex.embeddings.llama_embedder import QWEN_QUERY_PREFIX, LlamaServerEmbedder

        emb = LlamaServerEmbedder(url="http://localhost:8088")
        emb.encode("plain document text")

        all_texts = [t for batch in captured for t in batch]
        assert all(QWEN_QUERY_PREFIX not in t for t in all_texts)

    def test_server_unreachable_raises(self, monkeypatch):
        import requests

        monkeypatch.setattr(requests, "get", MagicMock(side_effect=requests.exceptions.ConnectionError("refused")))
        from neolex.embeddings.llama_embedder import LlamaServerEmbedder

        with pytest.raises(RuntimeError, match="llama-server not reachable"):
            LlamaServerEmbedder(url="http://localhost:8088")

    def test_background_poll_thread_starts_when_remote_configured(self, monkeypatch):
        """Background health poll thread is started when remote URL differs from local."""
        import threading

        import requests

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)
        # Ensure remote URL is distinct from local
        monkeypatch.setenv("LLAMA_SERVER_REMOTE_URL", "http://192.0.2.1:8088")

        from neolex.embeddings import llama_embedder

        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "http://192.0.2.1:8088")

        poll_threads_before = [t for t in threading.enumerate() if t.name == "embed-health-poll"]
        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        poll_threads_after = [t for t in threading.enumerate() if t.name == "embed-health-poll"]

        # A new poll thread must have been created
        assert len(poll_threads_after) > len(poll_threads_before)
        assert emb._remote_healthy is True

    def test_no_poll_thread_when_no_remote(self, monkeypatch):
        """No background thread is started when remote URL is not configured."""
        import threading

        import requests

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)

        from neolex.embeddings import llama_embedder

        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "")

        threads_before = {t.name for t in threading.enumerate()}
        llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        threads_after = {t.name for t in threading.enumerate()}

        new_threads = threads_after - threads_before
        poll_threads = {n for n in new_threads if "embed-health-poll" in n}
        assert not poll_threads

    def test_recovery_detection_logs_info(self, monkeypatch, caplog):
        """State transition offline→online is detected and logged."""
        import logging

        import requests

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)

        from neolex.embeddings import llama_embedder

        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "http://192.0.2.1:8088")
        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")

        # Simulate: remote was offline, now recovers
        emb._remote_healthy = False
        with caplog.at_level(logging.INFO, logger="neolex.embeddings.llama_embedder"):
            was_healthy = emb._remote_healthy
            emb._check_remote_health()
            now_healthy = emb._remote_healthy
            if not was_healthy and now_healthy:
                emb._logger_info_recovery_called = True

        assert emb._remote_healthy is True

    def test_demotion_on_remote_failure(self, monkeypatch):
        """Remote failure during embedding falls back to local and marks remote unhealthy."""
        import requests

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.raise_for_status = MagicMock()
            return resp

        def post_side_effect(url, json=None, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "192.0.2.1" in url:
                raise requests.exceptions.ConnectionError("remote down")
            texts = json.get("input", [])
            vec = [{"index": i, "embedding": [0.0] * 4096} for i, _ in enumerate(texts)]
            resp.json.return_value = {"data": vec}
            return resp

        monkeypatch.setattr(requests, "get", get_side_effect)
        monkeypatch.setattr(requests, "post", post_side_effect)

        from neolex.embeddings import llama_embedder

        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "http://192.0.2.1:8088")
        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")

        # Force remote as current primary
        emb._remote_healthy = True
        # Embed call should fail on remote, fall back to local, mark remote unhealthy
        emb.embed_texts(["test"])
        assert not emb._remote_healthy


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------


def _make_embedder_no_server(monkeypatch, llama_embedder, remote_url: str = ""):
    """Build a LlamaServerEmbedder with mocked health checks (no real server needed)."""
    import requests

    get_mock = MagicMock()
    get_mock.return_value.ok = True
    get_mock.return_value.raise_for_status = MagicMock()
    monkeypatch.setattr(requests, "get", get_mock)
    monkeypatch.setattr(llama_embedder, "_REMOTE_URL", remote_url)
    return llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")


class TestCircuitBreaker:
    def test_initial_state_is_closed(self, monkeypatch):
        from neolex.embeddings import llama_embedder
        from neolex.embeddings.llama_embedder import _CBState

        emb = _make_embedder_no_server(monkeypatch, llama_embedder)
        assert emb.circuit_state == _CBState.CLOSED

    def test_circuit_opens_after_threshold_failures(self, monkeypatch):
        """After _CB_THRESHOLD consecutive local failures the circuit should OPEN."""
        import requests

        from neolex.embeddings import llama_embedder
        from neolex.embeddings.llama_embedder import _CB_THRESHOLD, _CBState

        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "")
        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(
            requests,
            "post",
            MagicMock(side_effect=requests.exceptions.ConnectionError("server down")),
        )

        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        for _ in range(_CB_THRESHOLD):
            with pytest.raises(Exception):
                emb._embed_batch(["text"])

        assert emb.circuit_state == _CBState.OPEN

    def test_circuit_fails_fast_when_open(self, monkeypatch):
        """When circuit is OPEN, requests raise EmbeddingServerUnavailableError immediately."""
        import requests

        from neolex.embeddings import llama_embedder
        from neolex.embeddings.llama_embedder import (
            EmbeddingServerUnavailableError,
            _CBState,
        )

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        post_mock = MagicMock(side_effect=requests.exceptions.ConnectionError("down"))
        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(requests, "post", post_mock)
        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "")

        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        emb._cb_state = _CBState.OPEN
        emb._cb_open_at = time.monotonic()  # just opened, within cooldown

        call_count_before = post_mock.call_count
        with pytest.raises(EmbeddingServerUnavailableError):
            emb._embed_batch(["text"])

        # No HTTP call should have been made
        assert post_mock.call_count == call_count_before

    def test_half_open_after_cooldown(self, monkeypatch):
        """After cooldown elapses, OPEN transitions to HALF-OPEN on next request check."""
        import requests

        from neolex.embeddings import llama_embedder
        from neolex.embeddings.llama_embedder import _CBState

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "")

        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        emb._cb_state = _CBState.OPEN
        # Set open_at far in the past so cooldown has already elapsed
        emb._cb_open_at = time.monotonic() - 999

        allowed = emb._cb_allow_request()
        assert allowed is True
        assert emb.circuit_state == _CBState.HALF_OPEN

    def test_circuit_closes_on_successful_probe(self, monkeypatch):
        """A successful embed in HALF-OPEN state closes the circuit."""
        import requests

        from neolex.embeddings import llama_embedder
        from neolex.embeddings.llama_embedder import _CBState

        def post_ok(url, json=None, **kwargs):
            texts = json.get("input", [])
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"data": [{"index": i, "embedding": [0.0] * 4096} for i, _ in enumerate(texts)]}
            return resp

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(requests, "post", post_ok)
        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "")

        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        emb._cb_state = _CBState.HALF_OPEN
        emb._cb_fail_count = 3

        emb._embed_batch(["probe text"])
        assert emb.circuit_state == _CBState.CLOSED
        assert emb._cb_fail_count == 0

    def test_circuit_reopens_on_failed_probe(self, monkeypatch):
        """A failed embed in HALF-OPEN state re-opens the circuit."""
        import requests

        from neolex.embeddings import llama_embedder
        from neolex.embeddings.llama_embedder import _CBState

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(
            requests,
            "post",
            MagicMock(side_effect=requests.exceptions.ConnectionError("still down")),
        )
        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "")

        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        emb._cb_state = _CBState.HALF_OPEN

        with pytest.raises(Exception):
            emb._embed_batch(["probe"])

        assert emb.circuit_state == _CBState.OPEN

    def test_fail_count_resets_on_success(self, monkeypatch):
        """A successful request in CLOSED state resets the consecutive failure counter."""
        import requests

        from neolex.embeddings import llama_embedder

        def post_ok(url, json=None, **kwargs):
            texts = json.get("input", [])
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"data": [{"index": i, "embedding": [0.0] * 4096} for i, _ in enumerate(texts)]}
            return resp

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(requests, "post", post_ok)
        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "")

        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        emb._cb_fail_count = 2  # non-zero, below threshold

        emb._embed_batch(["text"])
        assert emb._cb_fail_count == 0

    def test_remote_recheck_triggered_on_circuit_close(self, monkeypatch):
        """Closing the circuit triggers a remote health re-check (auto-promotion)."""
        import requests

        from neolex.embeddings import llama_embedder
        from neolex.embeddings.llama_embedder import _CBState

        def post_ok(url, json=None, **kwargs):
            texts = json.get("input", [])
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"data": [{"index": i, "embedding": [0.0] * 4096} for i, _ in enumerate(texts)]}
            return resp

        get_mock = MagicMock()
        get_mock.return_value.ok = True
        get_mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", get_mock)
        monkeypatch.setattr(requests, "post", post_ok)
        monkeypatch.setattr(llama_embedder, "_REMOTE_URL", "http://192.0.2.1:8088")

        emb = llama_embedder.LlamaServerEmbedder(url="http://localhost:8088")
        # Force local as active server so the circuit breaker path is exercised
        emb._remote_healthy = False
        emb._cb_state = _CBState.HALF_OPEN
        health_calls_before = get_mock.call_count

        emb._embed_batch(["probe"])

        # Allow the background thread to run
        time.sleep(0.1)
        assert get_mock.call_count > health_calls_before
        assert emb.circuit_state == _CBState.CLOSED
