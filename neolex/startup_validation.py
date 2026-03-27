"""Startup validation — fail fast on misconfiguration.

Called from the lifespan context manager before any expensive ML model loading.
Raises SystemExit with a clear error message if a required precondition is not met.

Checks performed:
1. Required environment variables are set (or have acceptable defaults).
2. data/ directory exists with required index files.
3. Log a warning for any optional but recommended env vars that are missing.

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
    ("VERTEX_PROJECT_ID", "LLM requests via Vertex AI will fail without a GCP project ID"),
    ("GOOGLE_APPLICATION_CREDENTIALS", "Vertex AI auth will fail without service account credentials"),
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
        errors.append(
            f"data directory not found: '{data_dir}'. "
            f"Set NEOLEX_DATA_DIR or run from the project root."
        )
    else:
        for fname in _REQUIRED_DATA_FILES:
            fpath = os.path.join(data_dir, fname)
            if not os.path.isfile(fpath):
                errors.append(f"Required index file missing: {fpath}")

        # Check FAISS index exists at the configured path
        faiss_path = os.environ.get("FAISS_INDEX_PATH", "data/faiss_llama-server.bin")
        if not os.path.isabs(faiss_path):
            faiss_path = os.path.join(os.getcwd(), faiss_path)
        if not os.path.isfile(faiss_path):
            errors.append(
                f"FAISS index not found: {faiss_path}. "
                f"Build it with: EMBEDDING_MODEL=llama-server python3 -m "
                f"neolex.embeddings.build_index --corpus data/chunks/ "
                f"--output {os.environ.get('FAISS_INDEX_PATH', 'data/faiss_llama-server.bin')}"
            )

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
                f"--embedding --pooling last -ngl 99 -c 4096 --port 8088"
            )

    # --- Check recommended env vars ---
    for var, reason in _RECOMMENDED_ENV_VARS:
        if not os.environ.get(var):
            warnings.append(f"  {var} not set — {reason}")

    # --- Emit warnings ---
    if warnings:
        logger.warning(
            "Optional env vars not set (non-fatal):\n%s", "\n".join(warnings)
        )

    # --- Fatal errors ---
    if errors:
        for err in errors:
            logger.critical("STARTUP VALIDATION FAILED: %s", err)
        sys.exit(
            "NeoLex startup failed. Fix the above errors and restart.\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    logger.info(
        "Startup validation passed: data_dir=%s, %d index files verified",
        data_dir,
        len(_REQUIRED_DATA_FILES),
    )
