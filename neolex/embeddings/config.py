"""Embedding backend configuration for NeoLex.

Environment variables:
    EMBEDDING_MODEL   "snowflake" (default) | "qwen3-8b" | "qwen3-0.6b"
    EMBEDDING_DIM     Output dimension via Matryoshka truncation (default: 1024)
"""
import os

# Which embedder backend to use.
# "snowflake"  — Snowflake Arctic Embed L v2.0 (default, unchanged arlc behaviour)
# "qwen3-8b"   — Qwen/Qwen3-Embedding-8B with 4-bit quantization
# "qwen3-0.6b" — Qwen/Qwen3-Embedding-0.6B (fallback for low-VRAM machines)
EMBEDDING_BACKEND: str = os.environ.get("EMBEDDING_MODEL", "snowflake").lower()

# Output dimension. Qwen3-8B native dim is 4096; Matryoshka truncation is used
# to produce a smaller vector that still matches the FAISS index dimensionality.
EMBEDDING_DIM: int = int(os.environ.get("EMBEDDING_DIM", "1024"))

# HuggingFace model IDs for each backend
QWEN3_8B_MODEL_ID = "Qwen/Qwen3-Embedding-8B"
QWEN3_06B_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"

VALID_BACKENDS = {"snowflake", "qwen3-8b", "qwen3-0.6b"}

if EMBEDDING_BACKEND not in VALID_BACKENDS:
    raise ValueError(
        f"EMBEDDING_MODEL must be one of {VALID_BACKENDS}, got {EMBEDDING_BACKEND!r}"
    )
