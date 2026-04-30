"""OpenRouter embedding client for Qwen3-Embedding-8B.

Replaces the previous llama-server HTTP client with a call to OpenRouter's
OpenAI-compatible embeddings API.  Drop-in replacement: same public interface
(embed_texts / embed_query / encode) so no callers need to change.

Model: qwen/qwen3-embedding-8b  ($0.01/M tokens, 32K context, zero retention)
API:   POST https://openrouter.ai/api/v1/embeddings

Asymmetric embedding (CRITICAL — preserve this):
- embed_query()  → prepends Qwen3 instruction prefix ("Instruct: ...\nQuery: ")
- embed_texts()  → raw text, no prefix (document subspace)
These must stay separate or retrieval quality degrades significantly.

Environment variables
---------------------
OPENROUTER_API_KEY          Primary key (required)
OPENROUTER_API_KEY_BACKUP_1 First backup (tried if primary fails with 429/5xx)
OPENROUTER_API_KEY_BACKUP_2 Second backup
LLAMA_QUERY_TASK            Override the query instruction text
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Union

import numpy as np
import requests

logger = logging.getLogger(__name__)

QWEN_QUERY_TASK = os.environ.get(
    "LLAMA_QUERY_TASK",
    "Given a legal question, find the relevant legal provision, court judgment, or statutory rule",
)
QWEN_QUERY_PREFIX = f"Instruct: {QWEN_QUERY_TASK}\nQuery: "

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"

# Key carousel: primary first, then backups
_API_KEYS: list[str] = [
    k
    for k in [
        os.environ.get("OPENROUTER_API_KEY", ""),
        os.environ.get("OPENROUTER_API_KEY_BACKUP_1", ""),
        os.environ.get("OPENROUTER_API_KEY_BACKUP_2", ""),
    ]
    if k
]


def _get_key() -> str:
    """Return a valid API key or raise if none configured."""
    if not _API_KEYS:
        raise RuntimeError("No OpenRouter API key found. Set OPENROUTER_API_KEY in .env.")
    return _API_KEYS[0]


class LlamaServerEmbedder:
    """OpenRouter embedding client for Qwen3-Embedding-8B.

    Named LlamaServerEmbedder for drop-in compatibility with existing callers.
    Internally calls https://openrouter.ai/api/v1/embeddings — no local
    llama-server required.

    Parameters
    ----------
    url:
        Ignored (kept for interface compatibility). OpenRouter base URL is used.
    batch_size:
        Number of texts per HTTP request. 64 is a safe default.
    """

    def __init__(self, url: str = "", batch_size: int = 64) -> None:
        self.batch_size = batch_size
        self._base = _OPENROUTER_BASE
        self._model = _EMBEDDING_MODEL
        _get_key()  # fail fast if no key configured
        logger.info(
            "OpenRouter embedder ready (model=%s, %d key(s) configured)",
            self._model,
            len(_API_KEYS),
        )

    def _embed_batch(self, texts: list[str]) -> tuple[np.ndarray, int]:
        """POST a single batch; returns (matrix, prompt_tokens).

        matrix: (N, dim) float32, L2-normalised.
        prompt_tokens: total input tokens as reported by OpenRouter (for cost tracking).

        Tries keys in carousel order on 429 / 5xx.
        """
        last_err: Exception | None = None
        for key in _API_KEYS:
            try:
                r = requests.post(
                    f"{self._base}/embeddings",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "input": texts,
                        "encoding_format": "float",
                    },
                    timeout=(5, 60),  # (connect, read)
                )
                if r.status_code == 429 or r.status_code >= 500:
                    logger.warning("OpenRouter embeddings: %d on key …%s, trying next", r.status_code, key[-6:])
                    last_err = requests.HTTPError(response=r)
                    time.sleep(0.5)
                    continue
                r.raise_for_status()  # 4xx auth errors (401/403/400) — fail immediately, don't rotate
                body = r.json()
                data = body["data"]
                data.sort(key=lambda x: x["index"])
                matrix = np.array([d["embedding"] for d in data], dtype=np.float32)
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                norms = np.where(norms == 0.0, 1.0, norms)
                prompt_tokens = int((body.get("usage") or {}).get("prompt_tokens", 0))
                return matrix / norms, prompt_tokens
            except requests.HTTPError as e:
                last_err = e
                continue
        raise RuntimeError(f"All OpenRouter keys exhausted for embeddings: {last_err}")

    def embed_texts(
        self,
        texts: list[str],
        batch_size: Optional[int] = None,
        **kwargs,
    ) -> np.ndarray:
        """Embed document passages without an instruction prefix.

        Use this for DOCUMENTS (indexing time). Returns (N, dim) float32, L2-normalised.
        """
        bs = batch_size or self.batch_size
        chunks = []
        for start in range(0, len(texts), bs):
            matrix, _ = self._embed_batch(texts[start : start + bs])
            chunks.append(matrix)
        return np.concatenate(chunks, axis=0)

    def embed_query(
        self,
        query: str,
        task: str = QWEN_QUERY_TASK,
    ) -> np.ndarray:
        """Embed a search query with the Qwen3 instruction prefix.

        Use this for QUERIES (search time). Returns (dim,) float32, L2-normalised.
        """
        prefixed = f"Instruct: {task}\nQuery: {query}"
        matrix, _ = self._embed_batch([prefixed])
        return matrix[0]

    def embed_query_with_usage(
        self,
        query: str,
        task: str = QWEN_QUERY_TASK,
    ) -> tuple[np.ndarray, int]:
        """Like embed_query but also returns prompt_tokens from OpenRouter for cost tracking.

        Returns (embedding_vector, prompt_tokens).
        cost_usd = prompt_tokens * 0.01 / 1_000_000
        """
        prefixed = f"Instruct: {task}\nQuery: {query}"
        matrix, prompt_tokens = self._embed_batch([prefixed])
        return matrix[0], prompt_tokens

    def encode(
        self,
        sentences: Union[str, list[str]],
        normalize_embeddings: bool = True,
        prompt_name: Optional[str] = None,
        **kwargs,
    ) -> np.ndarray:
        """SentenceTransformer-compatible encode() API.

        When ``prompt_name='query'``, prepends the Qwen3 instruction prefix.
        Returns (N, dim) or (dim,) float32, L2-normalised.
        """
        scalar = isinstance(sentences, str)
        if scalar:
            sentences = [sentences]
        if prompt_name == "query":
            sentences = [QWEN_QUERY_PREFIX + s for s in sentences]
        result = self.embed_texts(sentences)
        return result[0] if scalar else result


# Legacy alias
OpenRouterEmbedder = LlamaServerEmbedder
