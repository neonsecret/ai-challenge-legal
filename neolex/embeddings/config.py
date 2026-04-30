"""Embedding backend configuration for Vitreon Legal.

Supported backends
------------------
openrouter (default):
    Qwen3-Embedding-8B via OpenRouter API ($0.01/M tokens).
    Requires OPENROUTER_API_KEY in .env. No local server needed.

Environment variables
---------------------
OPENROUTER_API_KEY      Primary key (required)
OPENROUTER_API_KEY_BACKUP_1  First backup
OPENROUTER_API_KEY_BACKUP_2  Second backup
EMBEDDING_DIM           Output dimension (default 4096 for Qwen3-8B full dim).
                        Use "full" for native dim.
"""

import os

_raw = os.environ.get("EMBEDDING_MODEL", "openrouter").lower()

VALID_BACKENDS = {"openrouter", "llama-server"}  # llama-server kept for compat

if _raw not in VALID_BACKENDS:
    raise ValueError(f"EMBEDDING_MODEL must be one of {VALID_BACKENDS}, got {os.environ.get('EMBEDDING_MODEL')!r}")

EMBEDDING_BACKEND: str = _raw

# Output dimension for Matryoshka truncation.
_dim_env = os.environ.get("EMBEDDING_DIM", "4096").lower()
EMBEDDING_DIM: int = 8192 if _dim_env == "full" else int(_dim_env)
