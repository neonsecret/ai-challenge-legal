"""Unit tests for neolex.embeddings — embedder loading, encoding, dimension config.

All tests mock heavy dependencies (torch, transformers, bitsandbytes) so they
run in CI without a GPU or model downloads.
"""
from __future__ import annotations

import importlib
import os
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_model(hidden_size: int = 4096) -> MagicMock:
    """Return a mock transformers model whose forward pass returns last_hidden_state."""
    import torch

    model = MagicMock()
    model.eval.return_value = model
    model.to.return_value = model

    def _forward(**kwargs):
        batch = kwargs["input_ids"].shape[0]
        seq = kwargs["input_ids"].shape[1]
        out = MagicMock()
        out.last_hidden_state = torch.randn(batch, seq, hidden_size)
        return out

    model.side_effect = _forward
    return model


def _make_mock_tokenizer() -> MagicMock:
    """Return a mock tokenizer that returns dummy tensors."""
    import torch
    tok = MagicMock()
    tok.pad_token = "<pad>"
    tok.eos_token = "<eos>"

    def _call(texts, **kwargs):
        if isinstance(texts, str):
            texts = [texts]
        n = len(texts)
        seq = 16
        return {
            "input_ids": torch.ones(n, seq, dtype=torch.long),
            "attention_mask": torch.ones(n, seq, dtype=torch.long),
        }

    tok.side_effect = _call
    return tok


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestEmbeddingConfig:
    def test_default_backend_is_snowflake(self, monkeypatch):
        monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)
        assert cfg.EMBEDDING_BACKEND == "snowflake"

    def test_qwen3_8b_backend(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "qwen3-8b")
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)
        assert cfg.EMBEDDING_BACKEND == "qwen3-8b"

    def test_qwen3_06b_backend(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "qwen3-0.6b")
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)
        assert cfg.EMBEDDING_BACKEND == "qwen3-0.6b"

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


# ---------------------------------------------------------------------------
# Qwen3Embedder unit tests (mocked model)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_torch_cpu(monkeypatch):
    """Patch torch device detection to always return CPU."""
    import torch
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)


@pytest.fixture
def mock_transformers(monkeypatch):
    """Patch AutoTokenizer and AutoModel to return lightweight mocks."""
    mock_tok = _make_mock_tokenizer()
    mock_mdl = _make_mock_model(hidden_size=4096)

    with (
        patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tok),
        patch("transformers.AutoModel.from_pretrained", return_value=mock_mdl),
    ):
        yield mock_tok, mock_mdl


class TestQwen3Embedder:
    def test_loads_without_gpu(self, mock_torch_cpu, mock_transformers):
        from neolex.embeddings.qwen3_embedder import Qwen3Embedder

        emb = Qwen3Embedder(model_name="Qwen/Qwen3-Embedding-0.6B", dim=1024, use_4bit=False)
        assert emb.dim == 1024
        assert emb.device == "cpu"

    def test_embed_texts_shape(self, mock_torch_cpu, mock_transformers):
        from neolex.embeddings.qwen3_embedder import Qwen3Embedder

        emb = Qwen3Embedder(model_name="Qwen/Qwen3-Embedding-0.6B", dim=256, use_4bit=False)
        texts = ["First passage.", "Second passage."]
        result = emb.embed_texts(texts)
        assert result.shape == (2, 256)

    def test_embed_query_shape(self, mock_torch_cpu, mock_transformers):
        from neolex.embeddings.qwen3_embedder import Qwen3Embedder

        emb = Qwen3Embedder(model_name="Qwen/Qwen3-Embedding-0.6B", dim=512, use_4bit=False)
        result = emb.embed_query("What is the limitation period?")
        assert result.shape == (512,)

    def test_embed_query_adds_instruction_prefix(self, mock_torch_cpu):
        """embed_query should prepend the instruction before encoding."""
        import torch
        calls: list[list[str]] = []

        def capturing_tokenizer(texts, **kwargs):
            if isinstance(texts, list):
                calls.append(list(texts))
            n = len(texts) if isinstance(texts, list) else 1
            return {
                "input_ids": torch.ones(n, 16, dtype=torch.long),
                "attention_mask": torch.ones(n, 16, dtype=torch.long),
            }

        mock_tok = MagicMock()
        mock_tok.pad_token = "<pad>"
        mock_tok.eos_token = "<eos>"
        mock_tok.side_effect = capturing_tokenizer

        mock_mdl = _make_mock_model(hidden_size=4096)

        with (
            patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tok),
            patch("transformers.AutoModel.from_pretrained", return_value=mock_mdl),
            patch("torch.backends.mps.is_available", return_value=False),
            patch("torch.cuda.is_available", return_value=False),
        ):
            from neolex.embeddings import qwen3_embedder as qmod
            importlib.reload(qmod)
            emb = qmod.Qwen3Embedder(
                model_name="Qwen/Qwen3-Embedding-0.6B", dim=128, use_4bit=False
            )
            emb.embed_query("What is the claim amount?")

        # At least one call should include the instruction prefix
        all_texts = [t for batch in calls for t in batch]
        assert any("Instruct:" in t for t in all_texts), (
            f"Expected instruction prefix in encoded texts, got: {all_texts}"
        )

    def test_encode_compat_prompt_name_query(self, mock_torch_cpu, mock_transformers):
        """encode(prompt_name='query') should add instruction prefix."""
        from neolex.embeddings.qwen3_embedder import Qwen3Embedder

        emb = Qwen3Embedder(model_name="Qwen/Qwen3-Embedding-0.6B", dim=64, use_4bit=False)
        result = emb.encode("test query", prompt_name="query")
        # Returns 1D array for scalar input
        assert result.ndim == 1
        assert result.shape[0] == 64

    def test_encode_compat_batch(self, mock_torch_cpu, mock_transformers):
        from neolex.embeddings.qwen3_embedder import Qwen3Embedder

        emb = Qwen3Embedder(model_name="Qwen/Qwen3-Embedding-0.6B", dim=128, use_4bit=False)
        result = emb.encode(["text a", "text b", "text c"])
        assert result.shape == (3, 128)

    def test_output_is_l2_normalised(self, mock_torch_cpu, mock_transformers):
        from neolex.embeddings.qwen3_embedder import Qwen3Embedder

        emb = Qwen3Embedder(model_name="Qwen/Qwen3-Embedding-0.6B", dim=256, use_4bit=False)
        result = emb.embed_texts(["some text"])
        norms = np.linalg.norm(result, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_matryoshka_dim_truncation(self, mock_torch_cpu, mock_transformers):
        from neolex.embeddings.qwen3_embedder import Qwen3Embedder

        # Native hidden size is 4096 (mocked); dim=128 should truncate
        emb = Qwen3Embedder(model_name="Qwen/Qwen3-Embedding-0.6B", dim=128, use_4bit=False)
        result = emb.embed_texts(["truncation test"])
        assert result.shape == (1, 128)

    def test_vram_fallback_to_06b(self, monkeypatch):
        """load_qwen3_embedder falls back to 0.6B when VRAM is insufficient."""
        monkeypatch.setattr(
            "neolex.embeddings.qwen3_embedder._available_vram_gb", lambda: 2.0
        )

        mock_tok = _make_mock_tokenizer()
        mock_mdl = _make_mock_model()
        loaded_models: list[str] = []

        def capturing_from_pretrained(model_name, **kwargs):
            loaded_models.append(model_name)
            return mock_mdl

        with (
            patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tok),
            patch("transformers.AutoModel.from_pretrained", side_effect=capturing_from_pretrained),
            patch("torch.backends.mps.is_available", return_value=False),
            patch("torch.cuda.is_available", return_value=False),
        ):
            from neolex.embeddings import qwen3_embedder as qmod
            importlib.reload(qmod)
            qmod.load_qwen3_embedder(backend="qwen3-8b", dim=1024)

        assert any("0.6B" in m for m in loaded_models), (
            f"Expected 0.6B fallback, loaded: {loaded_models}"
        )


# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------

class TestAdapter:
    def _make_embedder_mock(self, dim: int = 1024) -> MagicMock:
        emb = MagicMock()
        emb.embed_query.return_value = np.ones(dim, dtype=np.float32)
        emb.encode.return_value = np.ones((1, dim), dtype=np.float32)
        return emb

    def test_activate_noop_for_snowflake(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "snowflake")
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)

        import neolex.embeddings.adapter as adapter
        importlib.reload(adapter)

        result = adapter.activate()
        assert result is False

    def test_activate_patches_get_embedding_model(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "qwen3-8b")
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)

        import neolex.embeddings.adapter as adapter
        importlib.reload(adapter)

        mock_embedder = self._make_embedder_mock()

        with patch(
            "neolex.embeddings.adapter.load_qwen3_embedder",
            return_value=mock_embedder,
        ):
            import arlc.retriever as _ret
            original_fn = _ret.get_embedding_model

            result = adapter.activate()
            assert result is True

            # get_embedding_model should now return our mock
            assert _ret.get_embedding_model() is mock_embedder

            # Restore for other tests
            _ret.get_embedding_model = original_fn

    def test_activate_patches_embed_query(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "qwen3-0.6b")
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)

        import neolex.embeddings.adapter as adapter
        importlib.reload(adapter)

        mock_embedder = self._make_embedder_mock(dim=512)

        with patch(
            "neolex.embeddings.adapter.load_qwen3_embedder",
            return_value=mock_embedder,
        ):
            import arlc.retriever as _ret
            original_fn = _ret.embed_query

            adapter.activate()

            result = _ret.embed_query("test question")
            assert isinstance(result, list)
            assert len(result) == 512

            # Restore
            _ret.embed_query = original_fn

    def test_activate_is_idempotent(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "qwen3-8b")
        import neolex.embeddings.config as cfg
        importlib.reload(cfg)

        import neolex.embeddings.adapter as adapter
        importlib.reload(adapter)

        mock_embedder = self._make_embedder_mock()
        load_calls: list[int] = []

        def counting_loader(**kwargs):
            load_calls.append(1)
            return mock_embedder

        with patch(
            "neolex.embeddings.adapter.load_qwen3_embedder",
            side_effect=counting_loader,
        ):
            import arlc.retriever as _ret
            original_fn = _ret.get_embedding_model

            adapter.activate()
            adapter.activate()  # second call should be no-op
            assert len(load_calls) == 1

            _ret.get_embedding_model = original_fn
