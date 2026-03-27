"""Qwen3-Embedding embedder with 4-bit quantization and Matryoshka truncation.

Provides a SentenceTransformer-compatible .encode() API so it can be used as
a drop-in replacement when monkey-patching arlc.retriever.get_embedding_model().

Qwen3-Embedding is a decoder-only model, so the embedding is extracted via
last-token pooling (not mean-pooling used by BERT-style encoders).
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Union

import numpy as np
import torch

from neolex.embeddings.config import (
    EMBEDDING_DIM,
    QWEN3_06B_MODEL_ID,
    QWEN3_8B_MODEL_ID,
)

logger = logging.getLogger(__name__)

# Default task description for legal retrieval queries
_DEFAULT_TASK = "Given a legal document query, retrieve the most relevant passages"

# Approximate VRAM requirement for 8B model in 4-bit (GB)
_QWEN3_8B_VRAM_GB = 5.5


def _available_vram_gb() -> float:
    """Return available CUDA VRAM in GB, 0 if not available."""
    if not torch.cuda.is_available():
        return 0.0
    try:
        free, _ = torch.cuda.mem_get_info()
        return free / (1024**3)
    except Exception:
        return 0.0


def _last_token_pool(
    last_hidden_state: torch.Tensor,
    attention_mask: torch.Tensor,
) -> torch.Tensor:
    """Extract the last non-padding token embedding (decoder-model pooling)."""
    # If left-padded (all last tokens are non-pad), just take position -1.
    left_padded = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padded:
        return last_hidden_state[:, -1]
    # Right-padded: find the actual last token per sequence.
    seq_lengths = attention_mask.sum(dim=1) - 1
    batch_idx = torch.arange(last_hidden_state.shape[0], device=last_hidden_state.device)
    return last_hidden_state[batch_idx, seq_lengths]


class Qwen3Embedder:
    """Wraps Qwen3-Embedding with optional 4-bit quantization and Matryoshka truncation.

    Parameters
    ----------
    model_name:
        HuggingFace model ID.  Defaults to Qwen3-Embedding-8B.
    dim:
        Output dimension via Matryoshka truncation.  Must be <= model native dim.
    device:
        Torch device string.  Auto-detected (CUDA > MPS > CPU) if None.
    use_4bit:
        Enable bitsandbytes 4-bit NF4 quantization (CUDA only).
    """

    def __init__(
        self,
        model_name: str = QWEN3_8B_MODEL_ID,
        dim: int = EMBEDDING_DIM,
        device: Optional[str] = None,
        use_4bit: bool = True,
    ) -> None:
        self.dim = dim
        self.model_name = model_name

        if device is None:
            device = (
                "mps"
                if torch.backends.mps.is_available()
                else "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        self.device = device

        logger.info(
            "Loading Qwen3 embedder %s on %s (4-bit=%s, dim=%d)",
            model_name,
            device,
            use_4bit and device == "cuda",
            dim,
        )

        from transformers import AutoModel, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="left",  # decoder models use left-padding for batch consistency
        )
        # Ensure pad token is set (some Qwen models don't set it by default)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        if use_4bit and device == "cuda":
            from transformers import BitsAndBytesConfig

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            self.model = AutoModel.from_pretrained(
                model_name,
                trust_remote_code=True,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=torch.float16,
            )
        else:
            self.model = AutoModel.from_pretrained(
                model_name,
                trust_remote_code=True,
                torch_dtype=torch.float16 if device in ("cuda", "mps") else torch.float32,
            ).to(device)

        self.model.eval()
        logger.info("Qwen3 embedder loaded.")

    # ------------------------------------------------------------------
    # Core encode
    # ------------------------------------------------------------------

    def _encode_batch(
        self,
        texts: list[str],
        max_length: int = 8192,
        batch_size: int = 8,
    ) -> np.ndarray:
        """Encode a list of texts, returning (N, dim) float32 numpy array."""
        all_embeddings: list[np.ndarray] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            # Move to device.  For 4-bit models loaded with device_map="auto"
            # the model itself handles device placement, so we fall back to
            # self.device (which is "cuda" in that case).
            encoded = {k: v.to(self.device) for k, v in encoded.items()}

            with torch.no_grad():
                outputs = self.model(**encoded)

            embeddings = _last_token_pool(
                outputs.last_hidden_state, encoded["attention_mask"]
            )

            # Matryoshka truncation: take first `dim` dimensions
            if self.dim < embeddings.shape[-1]:
                embeddings = embeddings[:, : self.dim]

            # L2 normalise
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=-1)
            all_embeddings.append(embeddings.cpu().float().numpy())

        return np.concatenate(all_embeddings, axis=0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_texts(
        self,
        texts: list[str],
        task: str = "retrieval.passage",
    ) -> np.ndarray:
        """Embed document passages without an instruction prefix.

        Returns (N, dim) float32 numpy array, L2-normalised.
        """
        return self._encode_batch(texts)

    def embed_query(
        self,
        query: str,
        task: str = _DEFAULT_TASK,
    ) -> np.ndarray:
        """Embed a query with the Qwen3 instruction prefix.

        Returns (dim,) float32 numpy array, L2-normalised.
        """
        prefixed = f"Instruct: {task}\nQuery: {query}"
        return self._encode_batch([prefixed])[0]

    def encode(
        self,
        sentences: Union[str, list[str]],
        normalize_embeddings: bool = True,
        prompt_name: Optional[str] = None,
        **kwargs,
    ) -> np.ndarray:
        """SentenceTransformer-compatible encode() API.

        When `prompt_name='query'` (Arctic Embed convention), wraps each
        sentence with the Qwen3 instruction prefix so that query vs. passage
        asymmetry is preserved without modifying arlc/.

        Returns (N, dim) or (dim,) float32 numpy array (already L2-normalised).
        """
        scalar = isinstance(sentences, str)
        if scalar:
            sentences = [sentences]

        if prompt_name == "query":
            task = _DEFAULT_TASK
            sentences = [f"Instruct: {task}\nQuery: {s}" for s in sentences]

        result = self._encode_batch(sentences)
        # _encode_batch always L2-normalises; normalise_embeddings is a no-op here
        # but we honour the interface contract.
        return result[0] if scalar else result


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def load_qwen3_embedder(
    backend: str = "qwen3-8b",
    dim: int = EMBEDDING_DIM,
) -> Qwen3Embedder:
    """Load the appropriate Qwen3 model, falling back to 0.6B if VRAM is low.

    Parameters
    ----------
    backend:
        "qwen3-8b" or "qwen3-0.6b"
    dim:
        Output dimension (Matryoshka truncation).
    """
    use_8b = backend == "qwen3-8b"

    if use_8b:
        vram = _available_vram_gb()
        if vram < _QWEN3_8B_VRAM_GB:
            logger.warning(
                "Only %.1f GB VRAM available (need %.1f GB for 8B 4-bit). "
                "Falling back to Qwen3-Embedding-0.6B.",
                vram,
                _QWEN3_8B_VRAM_GB,
            )
            model_name = QWEN3_06B_MODEL_ID
        else:
            model_name = QWEN3_8B_MODEL_ID
    else:
        model_name = QWEN3_06B_MODEL_ID

    return Qwen3Embedder(model_name=model_name, dim=dim)
