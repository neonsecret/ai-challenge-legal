"""Monkey-patch arlc.retriever to use a Qwen3 embedding backend.

Call `activate()` before any arlc pipeline code runs (e.g. in neolex lifespan
startup, before _import_pipeline_modules).  When EMBEDDING_MODEL is "snowflake"
(default), activate() is a no-op and arlc behaviour is completely unchanged.

Patched symbols in arlc.retriever:
  - get_embedding_model()  → returns Qwen3Embedder instance
  - embed_query()          → uses Qwen3 instruction prefix
  - _embedding_model       → set to Qwen3Embedder (so the lazy singleton skips loading)
"""
from __future__ import annotations

import logging

from neolex.embeddings.qwen3_embedder import load_qwen3_embedder

logger = logging.getLogger(__name__)

_activated = False


def activate() -> bool:
    """Activate the Qwen3 embedding backend if configured.

    Returns True if the patch was applied, False if snowflake (no-op).
    Idempotent — safe to call multiple times.
    """
    global _activated

    from neolex.embeddings.config import EMBEDDING_BACKEND, EMBEDDING_DIM

    if EMBEDDING_BACKEND == "snowflake":
        logger.debug("EMBEDDING_MODEL=snowflake — using default arlc retriever, no patch.")
        return False

    if _activated:
        logger.debug("Qwen3 embedding adapter already activated, skipping.")
        return True

    logger.info(
        "Activating Qwen3 embedding adapter (backend=%s, dim=%d).",
        EMBEDDING_BACKEND,
        EMBEDDING_DIM,
    )

    embedder = load_qwen3_embedder(backend=EMBEDDING_BACKEND, dim=EMBEDDING_DIM)

    import arlc.retriever as _ret

    # 1. Set the cached singleton so the lazy-init block inside get_embedding_model
    #    is never entered (avoids loading a SentenceTransformer for a Qwen3 ID).
    _ret._embedding_model = embedder  # type: ignore[attr-defined]

    # 2. Replace get_embedding_model so that anything calling it gets the Qwen3 model.
    def _patched_get_embedding_model():
        return embedder

    _ret.get_embedding_model = _patched_get_embedding_model  # type: ignore[attr-defined]

    # 3. Replace embed_query so the correct instruction prefix is applied.
    #    The original falls through to a BGE prefix branch (neither arctic nor qwen3).
    def _patched_embed_query(question: str) -> list[float]:
        return embedder.embed_query(question).tolist()

    _ret.embed_query = _patched_embed_query  # type: ignore[attr-defined]

    _activated = True
    logger.info("Qwen3 embedding adapter activated.")
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
    logger.info("Qwen3 embedding adapter deactivated (arlc.retriever reloaded).")
