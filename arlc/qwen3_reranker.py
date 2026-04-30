"""Reranker backends: OpenRouterReranker (primary) + legacy llama-server / PyTorch classes.

OpenRouterReranker uses Cohere Rerank 4 Fast via OpenRouter ($0.002/search, 32K context,
100+ languages). Drop-in replacement for LlamaServerReranker — same predict() interface.

Legacy classes (Qwen3Reranker, LlamaServerReranker) kept for reference but no longer
instantiated by default. retriever.py now calls OpenRouterReranker.
"""

# ---------------------------------------------------------------------------
# OpenRouterReranker — active backend
# ---------------------------------------------------------------------------

from __future__ import annotations as _annotations

import logging as _logging
import os as _os
import time as _time
from typing import Optional as _Optional

import numpy as _np
import requests as _requests

_logger = _logging.getLogger(__name__)

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_RERANK_MODEL = "cohere/rerank-4-fast"

_RERANK_API_KEYS: list[str] = [
    k
    for k in [
        _os.environ.get("OPENROUTER_API_KEY", ""),
        _os.environ.get("OPENROUTER_API_KEY_BACKUP_1", ""),
        _os.environ.get("OPENROUTER_API_KEY_BACKUP_2", ""),
    ]
    if k
]


class OpenRouterReranker:
    """Reranker via OpenRouter's /v1/rerank endpoint (Cohere Rerank 4 Fast).

    Drop-in replacement for LlamaServerReranker — same predict() interface.

    Model: cohere/rerank-4-fast
      - $0.002 per search, 32K context, 100+ languages, multilingual Czech ✓
      - Released 2026-04-06, 100% uptime

    Parameters
    ----------
    model:
        OpenRouter model ID. Defaults to cohere/rerank-4-fast.
    """

    def __init__(self, model: str = _RERANK_MODEL) -> None:
        self._model = model
        if not _RERANK_API_KEYS:
            raise RuntimeError("No OpenRouter API key found. Set OPENROUTER_API_KEY in .env.")
        _logger.info("OpenRouterReranker ready (model=%s, %d key(s))", model, len(_RERANK_API_KEYS))

    def predict(
        self,
        sentences: list[tuple[str, str]],
        batch_size: _Optional[int] = None,
        on_progress=None,
        timeout: _Optional[float] = None,
        **kwargs,
    ) -> "_np.ndarray":
        """Score (query, document) pairs via OpenRouter /v1/rerank.

        Returns float32 numpy array of relevance scores in original pair order.

        Parameters
        ----------
        sentences:
            List of (query, document) tuples. All must share the same query.
        on_progress:
            Optional callback ``(done: int, total: int)``.
        timeout:
            HTTP read timeout in seconds (default 60).
        """
        if not sentences:
            return _np.array([], dtype=_np.float32)

        query = sentences[0][0]
        documents = [doc for _, doc in sentences]
        total = len(documents)
        read_timeout = timeout or 60

        last_err: Exception | None = None
        for key in _RERANK_API_KEYS:
            try:
                r = _requests.post(
                    f"{_OPENROUTER_BASE}/rerank",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "query": query,
                        "documents": documents,
                        "top_n": total,
                    },
                    timeout=(5, read_timeout),
                )
                if r.status_code == 429 or r.status_code >= 500:
                    _logger.warning("OpenRouter rerank: %d on key …%s, trying next", r.status_code, key[-6:])
                    last_err = _requests.HTTPError(response=r)
                    _time.sleep(0.5)
                    continue
                r.raise_for_status()  # 4xx auth errors (401/403/400) — fail immediately, don't rotate
                results = r.json()["results"]
                # results is sorted by relevance_score descending; restore original order
                scores = _np.zeros(total, dtype=_np.float32)
                for item in results:
                    scores[item["index"]] = item["relevance_score"]
                if on_progress:
                    on_progress(total, total)
                return scores
            except _requests.HTTPError as e:
                last_err = e
                continue

        raise RuntimeError(f"All OpenRouter keys exhausted for reranking: {last_err}")


# ---------------------------------------------------------------------------
# Legacy classes below — kept for reference, not used by default
# ---------------------------------------------------------------------------

import logging
import os
import re
import time
from typing import Optional

import numpy as np

try:
    import torch

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Regex to detect and parse the "Instruct: ...\nQuery: ..." prefix that
# _format_reranker_pairs() prepends for Qwen3-Reranker models.
# The Qwen3Reranker (PyTorch) class uses this prefix inside its own _make_prompt()
# method.  LlamaServerReranker sends queries directly to llama-server's /v1/rerank
# endpoint, which constructs the full chat template itself — receiving a
# double-wrapped prompt produces inverted/wrong relevance scores.
# This pattern is used by LlamaServerReranker to strip the prefix and pass the
# instruction as a native API field instead.
_INSTRUCT_QUERY_RE = re.compile(r"^Instruct: (.*?)\nQuery: (.+)$", re.DOTALL)

# System prompt used by all Qwen3-Reranker model variants
_SYSTEM_PROMPT = (
    "Judge whether the Document meets the requirements based on the Query and the Instruct. "
    'Note that the answer can only be "yes" or "no".'
)


class Qwen3Reranker:
    """Instruction-aware reranker using Qwen3-Reranker causal LM inference.

    Extracts the log-probability of the "yes" token at the final position as
    the relevance score — the correct approach for generative reranker models.

    Parameters
    ----------
    model_name:
        HuggingFace model ID. Defaults to Qwen/Qwen3-Reranker-0.6B.
    instruction:
        Task-level instruction injected into the prompt. Keep general so it
        works across customer domains.
    device:
        Torch device. Auto-detected (CUDA > MPS > CPU) if None.
    batch_size:
        Number of pairs processed per forward pass.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Reranker-0.6B",
        instruction: str = "Given a legal question, retrieve the most relevant passage that directly answers it.",
        device: Optional[str] = None,
        batch_size: int = 16,
    ) -> None:
        self.model_name = model_name
        self.instruction = instruction
        self.batch_size = batch_size

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device

        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading Qwen3-Reranker %s on %s", model_name, device)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            padding_side="left",
            trust_remote_code=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float16 if device in ("cuda", "mps") else torch.float32,
            trust_remote_code=True,
        ).to(device)
        self.model.eval()

        # Token IDs for "yes" and "no" in Qwen tokenizer
        self._yes_id = self.tokenizer.convert_tokens_to_ids("yes")
        self._no_id = self.tokenizer.convert_tokens_to_ids("no")
        logger.info("Qwen3-Reranker loaded. yes_id=%d, no_id=%d", self._yes_id, self._no_id)

    def _make_prompt(self, query: str, document: str) -> str:
        """Build the full chat-template prompt for one (query, document) pair."""
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (f"<Instruct>: {self.instruction}\n<Query>: {query}\n<Document>: {document}"),
            },
        ]
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    def _score_batch(self, prompts: list[str]) -> list[float]:
        """Run one forward pass and return P(yes) for each prompt."""
        encoded = self.tokenizer(
            prompts,
            padding=True,
            truncation=True,
            max_length=1024,
            return_tensors="pt",
        )
        target = "cuda:0" if self.device == "cuda" else self.device
        encoded = {k: v.to(target) for k, v in encoded.items()}

        with torch.no_grad():
            logits = self.model(**encoded).logits  # (B, seq_len, vocab)

        # Score = log-softmax over (yes, no) at last token position
        last_logits = logits[:, -1, :]  # (B, vocab)
        yes_no = last_logits[:, [self._yes_id, self._no_id]]  # (B, 2)
        probs = torch.softmax(yes_no, dim=-1)[:, 0]  # P(yes), shape (B,)
        scores = probs.cpu().float().tolist()

        # Flush MPS pipeline between batches to prevent memory fragmentation hangs
        if self.device == "mps":
            torch.mps.synchronize()
            torch.mps.empty_cache()

        return scores

    def predict(
        self,
        sentences: list[tuple[str, str]],
        batch_size: Optional[int] = None,
        on_progress=None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> np.ndarray:
        """Score (query, document) pairs. Returns float32 numpy array of relevance scores.

        Drop-in replacement for CrossEncoder.predict().

        on_progress: optional callback(done: int, total: int) called after each batch.
        timeout: optional timeout in seconds; raises TimeoutError if exceeded.
        """
        bs = batch_size or self.batch_size
        prompts = [self._make_prompt(q, doc) for q, doc in sentences]
        total = len(prompts)
        all_scores: list[float] = []
        t_start = time.monotonic()
        for start in range(0, total, bs):
            if timeout and (time.monotonic() - t_start) > timeout:
                raise TimeoutError(f"Reranking exceeded {timeout}s after {len(all_scores)}/{total} pairs")
            batch = prompts[start : start + bs]
            all_scores.extend(self._score_batch(batch))
            if on_progress:
                on_progress(min(start + bs, total), total)
        return np.array(all_scores, dtype=np.float32)


class LlamaServerReranker:
    """HTTP client for llama-server's /v1/rerank endpoint (GGUF model on CUDA/Metal).

    Drop-in replacement for Qwen3Reranker — same predict() interface.
    Uses llama-server with --reranking flag and a GGUF reranker model.

    Supports batched requests to reduce Metal memory pressure and provide
    mid-processing progress callbacks. Documents are split into batches
    (default size from RERANKER_BATCH_SIZE env var, fallback 10) and sent
    as separate HTTP POSTs. Per-batch ``index`` fields are offset to
    reconstruct original document order. When batching is unnecessary
    (batch_size >= total docs, or no on_progress callback), a single
    request fast path is used to avoid overhead.

    Start the server with::

        llama-server -m Qwen3-Reranker-0.6B-Q8_0.gguf --reranking -ngl 99 \\
            -c 4096 --port 8089 --host 0.0.0.0

    Parameters
    ----------
    url:
        Base URL of the llama-server reranking instance.
    """

    # Default batch size, overridable via RERANKER_BATCH_SIZE env var.
    # llama-server's /v1/rerank packs ALL documents into ONE context window
    # (measured: ~540 tokens per 2051-char doc, ~597 tokens with instruction prefix).
    # With -c 4096 context: max 6 docs × ~597 tokens = 3582 tokens (safe margin).
    # Documents are truncated to 1500 chars before sending (see retriever.py).
    DEFAULT_BATCH_SIZE = int(os.environ.get("RERANKER_BATCH_SIZE", "6"))

    def __init__(self, url: str) -> None:
        import requests as _requests

        self._requests = _requests
        self.url = url.rstrip("/")
        try:
            r = self._requests.get(f"{self.url}/health", timeout=3)
            r.raise_for_status()
            logger.info("llama-server reranker at %s is healthy", self.url)
        except Exception as e:
            raise RuntimeError(f"llama-server reranker at {self.url} not reachable: {e}") from e

    # Connect timeout: how long to wait for TCP handshake (seconds).
    # Keeps failures fast when the remote host is unreachable — avoids 75s
    # OS-level TCP SYN retransmission delays on macOS.
    CONNECT_TIMEOUT = 5

    def _rerank_single_batch(
        self,
        query: str,
        documents: list[str],
        read_timeout: float,
    ) -> list[dict]:
        """Send one /v1/rerank request and return raw results list.

        Each result dict has ``index`` (0-based within this batch) and
        ``relevance_score``.

        Handles the ``_format_reranker_pairs`` instruction prefix transparently:
        if the query starts with ``"Instruct: ...\\nQuery: ..."`` (added by
        ``_format_reranker_pairs`` for Qwen3-Reranker models), the prefix is
        parsed and the instruction is passed as the native llama-server
        ``instruction`` API field.  Embedding the instruction inside the query
        string causes llama-server to double-wrap it in its own chat template,
        which inverts relevance scores for substantive legal passages.
        """
        payload: dict = {"model": "local", "documents": documents}
        m = _INSTRUCT_QUERY_RE.match(query)
        if m:
            payload["instruction"] = m.group(1).strip()
            payload["query"] = m.group(2).strip()
        else:
            payload["query"] = query
        r = self._requests.post(
            f"{self.url}/v1/rerank",
            json=payload,
            timeout=(self.CONNECT_TIMEOUT, read_timeout),
        )
        if not r.ok:
            logger.warning(
                "llama-server rerank %s returned %d: %s",
                self.url,
                r.status_code,
                r.text[:300],
            )
        r.raise_for_status()
        return r.json()["results"]

    def predict(
        self,
        sentences: list[tuple[str, str]],
        batch_size: Optional[int] = None,
        on_progress=None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> np.ndarray:
        """Score (query, document) pairs via llama-server /v1/rerank.

        Documents are always sent in batches of ``batch_size`` (default 6) to
        avoid context-window overflow. llama-server packs all documents in a
        single request into ONE context window, so large batches overflow the
        4096-token limit. Progress callbacks are fired after each batch.

        Parameters
        ----------
        sentences:
            List of (query, document) tuples to score.
        batch_size:
            Number of documents per HTTP request. Defaults to
            ``RERANKER_BATCH_SIZE`` env var (or 10).
        on_progress:
            Optional callback ``(done: int, total: int)`` called after each
            batch completes.
        timeout:
            Read timeout in seconds for each HTTP request (default 180).
        """
        if not sentences:
            return np.array([], dtype=np.float32)

        # All pairs share the same query (reranking is query-vs-many-docs)
        query = sentences[0][0]
        documents = [doc for _, doc in sentences]
        total = len(documents)
        read_timeout = timeout or 180
        bs = batch_size if batch_size is not None else self.DEFAULT_BATCH_SIZE

        # Fast path: single request when all documents fit in one safe batch.
        # IMPORTANT: always respect batch_size — the `on_progress is None` bypass
        # was removed because it caused context overflow (all docs in one 4096-token
        # window, crashing llama-server with "context size exceeded" / "input too large").
        if bs >= total:
            try:
                results = self._rerank_single_batch(query, documents, read_timeout)
                results.sort(key=lambda x: x["index"])
                scores = [x["relevance_score"] for x in results]
                if on_progress:
                    on_progress(total, total)
                return np.array(scores, dtype=np.float32)
            except Exception as e:
                raise RuntimeError(f"llama-server reranking failed: {e}") from e

        # Batched path: split documents, merge results in original order
        try:
            # Pre-allocate scores array to place results at correct positions
            scores = np.zeros(total, dtype=np.float32)
            done = 0

            for batch_start in range(0, total, bs):
                batch_end = min(batch_start + bs, total)
                batch_docs = documents[batch_start:batch_end]

                results = self._rerank_single_batch(query, batch_docs, read_timeout)

                # Map batch-local indices back to global positions
                for item in results:
                    global_idx = batch_start + item["index"]
                    scores[global_idx] = item["relevance_score"]

                done = batch_end
                if on_progress:
                    on_progress(done, total)

            return scores
        except Exception as e:
            raise RuntimeError(f"llama-server reranking failed: {e}") from e
