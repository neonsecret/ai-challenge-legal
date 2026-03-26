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
    ("ANTHROPIC_API_KEY", "LLM requests will fail without an Anthropic key"),
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
