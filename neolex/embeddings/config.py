"""Embedding backend configuration for NeoLex.

Environment variables:
    EMBEDDING_MODEL   "snowflake" (default) | "qwen3-8b" | "qwen3-4b" | "qwen3-0.6b"
    EMBEDDING_DIM     Output dimension via Matryoshka truncation (default: 1024)

Notes on GPU compatibility (RTX 3070, 8.6 GB VRAM):
    - qwen3-8b: 8B params, requires 8-bit quantization (~8.5 GB VRAM).
                CUDA 13.0 (torch 2.9+) degrades 8-bit kernel performance severely.
                Effective throughput: ~1.5 texts/sec on RTX 3070 with CUDA 13.0.
    - qwen3-4b: 4B params, runs in float16 (~8.4 GB VRAM, batch_size=1 to avoid OOM).
                Native GPU inference, no quantization needed.
                Effective throughput: ~6 texts/sec on RTX 3070. RECOMMENDED for indexing.
    - qwen3-0.6b: 0.6B params, float16 (~1.2 GB VRAM). Fast but lower quality.
"""
import os

# Which embedder backend to use.
# "snowflake"  — Snowflake Arctic Embed L v2.0 (default, unchanged arlc behaviour)
# "qwen3-8b"   — Qwen/Qwen3-Embedding-8B (4-bit or 8-bit quantization, CUDA ≥ 13 auto-upgrades to 8-bit)
# "qwen3-4b"   — Qwen/Qwen3-Embedding-4B (float16, batch_size=1 for RTX 3070 8 GB)
# "qwen3-0.6b" — Qwen/Qwen3-Embedding-0.6B (fallback for low-VRAM machines)
EMBEDDING_BACKEND: str = os.environ.get("EMBEDDING_MODEL", "snowflake").lower()

# Output dimension. Qwen3 native dim is 4096; Matryoshka truncation is used
# to produce a smaller vector that still matches the FAISS index dimensionality.
# "full" means no Matryoshka truncation — uses native model output dim (2560 for 4B).
_embedding_dim_env = os.environ.get("EMBEDDING_DIM", "1024").lower()
EMBEDDING_DIM: int = 8192 if _embedding_dim_env == "full" else int(_embedding_dim_env)

# HuggingFace model IDs for each backend
QWEN3_8B_MODEL_ID = "Qwen/Qwen3-Embedding-8B"
QWEN3_4B_MODEL_ID = "Qwen/Qwen3-Embedding-4B"
QWEN3_06B_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"

# Map HuggingFace model IDs to short backend names for convenience
_HF_TO_BACKEND = {
    "qwen/qwen3-embedding-8b": "qwen3-8b",
    "qwen/qwen3-embedding-4b": "qwen3-4b",
    "qwen/qwen3-embedding-0.6b": "qwen3-0.6b",
}
EMBEDDING_BACKEND = _HF_TO_BACKEND.get(EMBEDDING_BACKEND, EMBEDDING_BACKEND)

VALID_BACKENDS = {"snowflake", "qwen3-8b", "qwen3-4b", "qwen3-0.6b"}

if EMBEDDING_BACKEND not in VALID_BACKENDS:
    raise ValueError(
        f"EMBEDDING_MODEL must be one of {VALID_BACKENDS} "
        f"(or a full HuggingFace Qwen3 model ID), got {os.environ.get('EMBEDDING_MODEL')!r}"
    )
