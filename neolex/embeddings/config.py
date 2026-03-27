"""Embedding backend configuration for NeoLex.

Recommended backend: llama-server
----------------------------------
Run Qwen3-Embedding-8B via llama.cpp (Q4_K_M GGUF, ~4.3 GB) rather than PyTorch.
Advantages: fits both RTX 3070 (8 GB) and Apple Silicon; Metal/CUDA paths are
more reliable than PyTorch MPS; no torch needed at inference time.

    # Start the server (do this once, keep it running):
    llama-server -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \\
        --embedding --pooling last -ngl 99 -c 4096 --port 8088

    # Set in .env:
    EMBEDDING_MODEL=llama-server
    LLAMA_SERVER_URL=http://localhost:8088       # default
    LLAMA_MODEL_PATH=models/Qwen3-Embedding-8B-Q4_K_M.gguf  # for auto-start

Environment variables:
    EMBEDDING_MODEL     Backend selection (see VALID_BACKENDS below).
                        Default: "snowflake" (no extra setup required).
    EMBEDDING_DIM       Output dimension for Matryoshka truncation (default: 1024).
                        Use "full" for native model dim (4096 for 8B).
                        Ignored by llama-server backend (server controls output dim).
    LLAMA_SERVER_URL    URL of the llama-server instance (default: http://localhost:8088).
    LLAMA_MODEL_PATH    Path to .gguf file — used only by start_server() helper.

PyTorch backends (legacy, not recommended):
    - qwen3-8b:   ~14 GB VRAM float16; CUDA 13.0 kernel issues. Use llama-server instead.
    - qwen3-4b:   ~8.4 GB VRAM float16; batch_size=1 on RTX 3070.
    - qwen3-0.6b: ~1.2 GB VRAM; fast but significantly lower quality.
"""
import os

# Which embedder backend to use.
# "llama-server" — Qwen3-Embedding-8B GGUF via llama-server HTTP API (RECOMMENDED)
# "snowflake"    — Snowflake Arctic Embed L v2.0 (default, no extra setup needed)
# "qwen3-8b"     — Qwen3-Embedding-8B via PyTorch (legacy, use llama-server instead)
# "qwen3-4b"     — Qwen3-Embedding-4B via PyTorch (legacy)
# "qwen3-0.6b"   — Qwen3-Embedding-0.6B via PyTorch (legacy, low quality)
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

VALID_BACKENDS = {"snowflake", "qwen3-8b", "qwen3-4b", "qwen3-0.6b", "llama-server"}

if EMBEDDING_BACKEND not in VALID_BACKENDS:
    raise ValueError(
        f"EMBEDDING_MODEL must be one of {VALID_BACKENDS} "
        f"(or a full HuggingFace Qwen3 model ID), got {os.environ.get('EMBEDDING_MODEL')!r}"
    )
