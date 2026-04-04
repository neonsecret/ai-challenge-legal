"""Startup validation — fail fast on misconfiguration.

Called from the lifespan context manager before any expensive ML model loading.
Raises SystemExit with a clear error message if a required precondition is not met.

Checks performed:
1. Required environment variables are set (or have acceptable defaults).
2. data/ directory exists with required index files.
3. PostgreSQL chunks table has data.
4. Log a warning for any optional but recommended env vars that are missing.

Design rationale: fail on startup rather than on the first request so that
misconfigurations are caught immediately in CI/CD and not in production traffic.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required index files in data/
# ---------------------------------------------------------------------------

_REQUIRED_DATA_FILES = [
    "article_page_index.json",
    "law_name_index.json",
    "case_metadata_index.json",
]

# ---------------------------------------------------------------------------
# Recommended env vars (missing = warning only, not fatal)
# ---------------------------------------------------------------------------

_RECOMMENDED_ENV_VARS = [
    ("GOOGLE_APPLICATION_CREDENTIALS", "Vertex AI auth will fail without service account credentials"),
    # RERANKER_MODEL not checked here because it has a safe default (Qwen/Qwen3-Reranker-0.6B),
    # but we log it so operators know which model will be downloaded on first warm-up.
]

# Info-level log: which reranker will be loaded (model download can take 1-2 min on first run).
_RERANKER_INFO_VARS = [
    ("RERANKER_MODEL", "Qwen/Qwen3-Reranker-0.6B"),
    ("RERANKER_INSTRUCTION", "Given a legal question, retrieve the most relevant passage that directly answers it."),
]


def validate_startup(data_dir: str) -> None:
    """Validate that the server is correctly configured before loading ML models.

    Args:
        data_dir: Path to the data directory (from settings.data_dir).

    Raises:
        SystemExit: On any fatal misconfiguration.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Check data/ directory ---
    if not os.path.isdir(data_dir):
        errors.append(f"data directory not found: '{data_dir}'. Set NEOLEX_DATA_DIR or run from the project root.")
    else:
        for fname in _REQUIRED_DATA_FILES:
            fpath = os.path.join(data_dir, fname)
            if not os.path.isfile(fpath):
                errors.append(f"Required index file missing: {fpath}")

        # Check PostgreSQL chunks table has data
        try:
            from arlc.retriever import get_chunk_count

            difc_count = get_chunk_count("difc")
            if difc_count == 0:
                errors.append(
                    "No chunks found in PostgreSQL for corpus 'difc'. "
                    "Run the indexer: uv run python3 -m arlc.indexing.indexer",
                )
            else:
                logger.info("PostgreSQL chunks: difc=%d", difc_count)
        except Exception as exc:
            errors.append(f"Cannot connect to PostgreSQL to verify chunks: {exc}")

    # --- Check llama-server if embedding backend requires it ---
    if os.environ.get("EMBEDDING_MODEL", "llama-server") == "llama-server":
        llama_url = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8088")
        try:
            import urllib.request

            with urllib.request.urlopen(f"{llama_url}/health", timeout=3) as resp:
                if resp.status != 200:
                    errors.append(f"llama-server at {llama_url} returned status {resp.status}.")
        except Exception as exc:
            errors.append(
                f"llama-server not reachable at {llama_url}: {exc}. "
                f"Start it with: llama-server -m models/Qwen3-Embedding-8B-Q4_K_M.gguf "
                f"--embedding --pooling last -ngl 99 -c 4096 --port 8088",
            )

    # --- VERTEX_PROJECT_ID is required for agent queries ---
    if not os.environ.get("VERTEX_PROJECT_ID"):
        errors.append(
            "VERTEX_PROJECT_ID must be set — agent queries (use_agent=True) will crash "
            "with KeyError without a configured GCP project ID."
        )

    # --- Auth / billing secret validation ---
    from neolex.config import settings as _s

    if _s.auth_enabled:
        if not _s.jwt_secret_key:
            errors.append("JWT_SECRET_KEY must be set when AUTH_ENABLED=true")
        if not _s.database_url:
            errors.append("DATABASE_URL must be set when AUTH_ENABLED=true")
    if _s.stripe_enabled:
        if not _s.stripe_secret_key:
            errors.append("STRIPE_SECRET_KEY must be set when STRIPE_ENABLED=true")
        if not _s.stripe_webhook_secret:
            errors.append("STRIPE_WEBHOOK_SECRET must be set when STRIPE_ENABLED=true")

    # --- Check recommended env vars ---
    for var, reason in _RECOMMENDED_ENV_VARS:
        if not os.environ.get(var):
            warnings.append(f"  {var} not set — {reason}")

    # --- Log effective reranker config (model download can take 1-2 min on first boot) ---
    for var, default in _RERANKER_INFO_VARS:
        effective = os.environ.get(var, default)
        logger.info("Reranker config: %s=%s%s", var, effective, " (default)" if var not in os.environ else "")

    # --- Emit warnings ---
    if warnings:
        logger.warning("Optional env vars not set (non-fatal):\n%s", "\n".join(warnings))

    # --- Fatal errors ---
    if errors:
        for err in errors:
            logger.critical("STARTUP VALIDATION FAILED: %s", err)
        sys.exit(
            "Vitreon Legal startup failed. Fix the above errors and restart.\n" + "\n".join(f"  - {e}" for e in errors),
        )

    logger.info(
        "Startup validation passed: data_dir=%s, %d index files verified",
        data_dir,
        len(_REQUIRED_DATA_FILES),
    )
