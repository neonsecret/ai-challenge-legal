"""Monkey-patch arlc.retriever to use a non-default embedding backend.

Call `activate()` before any arlc pipeline code runs (e.g. in neolex lifespan
startup, before _import_pipeline_modules).  When EMBEDDING_MODEL is "snowflake"
(default), activate() is a no-op and arlc behaviour is completely unchanged.

Supported backends
------------------
llama-server (recommended):
    Connects to a running llama-server instance.  Start the server first:

        llama-server -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \\
            --embedding --pooling last -ngl 99 -c 4096 --port 8088

    Then set EMBEDDING_MODEL=llama-server (and optionally LLAMA_SERVER_URL).
    Note: arlc/retriever.py handles llama-server natively, so activate() is
    only needed here to avoid the torch import at neolex server startup.

qwen3-8b / qwen3-4b / qwen3-0.6b:
    PyTorch-based Qwen3Embedder (requires GPU with enough VRAM).
    Prefer llama-server — it is faster and more memory-efficient.

Patched symbols in arlc.retriever:
  - get_embedding_model()  → returns the configured embedder instance
  - embed_query()          → uses the correct instruction prefix
  - _embedding_model       → set to the embedder (lazy singleton is skipped)
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_activated = False


def activate() -> bool:
    """Activate the configured embedding backend if it is not "snowflake".

    Returns True if the patch was applied, False if snowflake (no-op).
    Idempotent — safe to call multiple times.
    """
    global _activated

    from neolex.embeddings.config import EMBEDDING_BACKEND, EMBEDDING_DIM

    if EMBEDDING_BACKEND == "snowflake":
        logger.debug("EMBEDDING_MODEL=snowflake — using default arlc retriever, no patch.")
        return False

    if _activated:
        logger.debug("Embedding adapter already activated, skipping.")
        return True

    logger.info("Activating embedding adapter (backend=%s).", EMBEDDING_BACKEND)

    if EMBEDDING_BACKEND == "llama-server":
        from neolex.embeddings.llama_embedder import LlamaServerEmbedder
        embedder = LlamaServerEmbedder()
    else:
        from neolex.embeddings.qwen3_embedder import load_qwen3_embedder
        embedder = load_qwen3_embedder(backend=EMBEDDING_BACKEND, dim=EMBEDDING_DIM)

    import arlc.retriever as _ret

    # 1. Set the cached singleton so the lazy-init block in get_embedding_model
    #    is never entered (avoids loading SentenceTransformer / torch).
    _ret._embedding_model = embedder  # type: ignore[attr-defined]

    # 2. Replace get_embedding_model so callers receive the configured embedder.
    def _patched_get_embedding_model():
        return embedder

    _ret.get_embedding_model = _patched_get_embedding_model  # type: ignore[attr-defined]

    # 3. Replace embed_query to use the embedder's own query method (handles
    #    instruction prefix and normalisation internally).
    def _patched_embed_query(question: str) -> list[float]:
        return embedder.embed_query(question).tolist()

    _ret.embed_query = _patched_embed_query  # type: ignore[attr-defined]

    _activated = True
    logger.info("Embedding adapter activated (backend=%s).", EMBEDDING_BACKEND)
    return True


def deactivate() -> None:
    """Remove the monkey-patch (for testing).  Reloads the arlc.retriever module."""
    global _activated
    if not _activated:
        return
    import importlib
    import arlc.retriever as _ret
    importlib.reload(_ret)
    _activated = False
    logger.info("Embedding adapter deactivated (arlc.retriever reloaded).")
