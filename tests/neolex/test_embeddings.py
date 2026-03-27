"""Unit tests for neolex.embeddings — config and LlamaServerEmbedder."""
from __future__ import annotations

import importlib
import os
from unittest.mock import MagicMock, patch

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

    def test_snowflake_backend(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "snowflake")
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)
        assert cfg.EMBEDDING_BACKEND == "snowflake"

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

        from neolex.embeddings.llama_embedder import LlamaServerEmbedder, QWEN_QUERY_PREFIX
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

        from neolex.embeddings.llama_embedder import LlamaServerEmbedder, QWEN_QUERY_PREFIX
        emb = LlamaServerEmbedder(url="http://localhost:8088")
        emb.encode("plain document text")

        all_texts = [t for batch in captured for t in batch]
        assert all(QWEN_QUERY_PREFIX not in t for t in all_texts)

    def test_server_unreachable_raises(self, monkeypatch):
        import requests
        monkeypatch.setattr(
            requests, "get",
            MagicMock(side_effect=requests.exceptions.ConnectionError("refused"))
        )
        from neolex.embeddings.llama_embedder import LlamaServerEmbedder
        with pytest.raises(RuntimeError, match="llama-server not reachable"):
            LlamaServerEmbedder(url="http://localhost:8088")
