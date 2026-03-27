"""Embedding backend configuration for NeoLex.

Supported backends
------------------
llama-server (default, recommended):
    Qwen3-Embedding-8B via llama.cpp Q4_K_M GGUF. Requires a running
    llama-server instance (see LLAMA_SERVER_URL).

    Start the server:
        llama-server -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \\
            --embedding --pooling last -ngl 99 -c 4096 --port 8088

snowflake:
    Snowflake Arctic Embed L v2.0. No server needed, loads via
    sentence-transformers. Lower quality than llama-server.

Environment variables
---------------------
EMBEDDING_MODEL     "llama-server" (default) | "snowflake"
EMBEDDING_DIM       Output dimension for Matryoshka truncation (default 1024).
                    Only applies to the snowflake backend.
                    Use "full" for native dim; ignored by llama-server.
LLAMA_SERVER_URL    URL of the llama-server instance (default: http://localhost:8088).
LLAMA_MODEL_PATH    Path to .gguf file — used only by start_server() helper.
"""
import os

_raw = os.environ.get("EMBEDDING_MODEL", "llama-server").lower()

VALID_BACKENDS = {"snowflake", "llama-server"}

if _raw not in VALID_BACKENDS:
    raise ValueError(
        f"EMBEDDING_MODEL must be one of {VALID_BACKENDS}, got {os.environ.get('EMBEDDING_MODEL')!r}"
    )

EMBEDDING_BACKEND: str = _raw

# Output dimension for Matryoshka truncation (snowflake only).
_dim_env = os.environ.get("EMBEDDING_DIM", "1024").lower()
EMBEDDING_DIM: int = 8192 if _dim_env == "full" else int(_dim_env)
