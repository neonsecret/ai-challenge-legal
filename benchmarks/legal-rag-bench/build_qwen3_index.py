#!/usr/bin/env python3
"""Build Qwen3 FAISS index for Legal RAG Bench corpus.

Downloads 4,876 passages from HuggingFace isaacus/legal-rag-bench corpus,
embeds them with a Qwen3 model, and saves:
  - data/faiss_qwen3-4b.bin   — FAISS flat IP index (1024-dim Matryoshka)
  - data/faiss_qwen3-4b.json  — metadata (id, text, title)

The BM25 index is shared with the Snowflake run (tokenization is model-agnostic).

Usage:
    # MPS (Apple Silicon) — auto-detected, batch_size=8 by default
    cd ~/ai-challenge-legal
    PYTHONPATH=. EMBEDDING_MODEL=qwen3-4b python3 \
        benchmarks/legal-rag-bench/build_qwen3_index.py

    # CUDA (RTX 3070, 8.6 GB VRAM) — batch_size=1 required for 4B model
    PYTHONPATH=. EMBEDDING_MODEL=qwen3-4b BATCH_SIZE=1 python3 \
        benchmarks/legal-rag-bench/build_qwen3_index.py

Notes:
    - Qwen3-4B in float16 fills RTX 3070 VRAM → BATCH_SIZE=1 required on CUDA.
    - On MPS (Apple Silicon) unified memory is more flexible → BATCH_SIZE=8.
    - Qwen3-8B 4-bit has CUDA 13.0 kernel issues; use 4B for reliable GPU inference.
"""

import json
import sys
from pathlib import Path

import numpy as np

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = BENCH_DIR / "data"

import os
import torch

# Model controlled by env var; default to qwen3-4b
_MODEL_BACKEND = os.environ.get("EMBEDDING_MODEL", "qwen3-4b").lower()

# Qwen3 output dimension (Matryoshka truncation).
# EMBEDDING_DIM=1024  — Matryoshka-truncated (default, smaller index, slightly lower quality)
# EMBEDDING_DIM=full  — native model dim (2560 for 4B, no truncation, larger index)
# EMBEDDING_DIM=N     — any integer
_dim_env = os.environ.get("EMBEDDING_DIM", "1024").lower()
# Use a large sentinel (8192) for "full" so Qwen3Embedder skips truncation
EMBED_DIM = 8192 if _dim_env == "full" else int(_dim_env)
_dim_label = "full" if _dim_env == "full" else str(EMBED_DIM)

# Batch size: auto-detect from device, or override with BATCH_SIZE env var.
# CUDA (RTX 3070): Qwen3-4B fills all 8.6 GB VRAM → 1 required.
# MPS (Apple Silicon): unified memory → 8 is safe and fast.
# CPU: 32 works fine.
def _auto_batch_size() -> int:
    if torch.backends.mps.is_available():
        return 8
    if torch.cuda.is_available():
        return 1
    return 32

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", str(_auto_batch_size())))
MAX_LENGTH = 512  # token budget; legal passages are typically < 200 tokens


def main():
    from datasets import load_dataset as hf_load
    import faiss

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Load corpus from HuggingFace
    print("[build_qwen3_index] Loading corpus from HuggingFace...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    print(f"[build_qwen3_index] Loaded {len(corpus_ds)} passages")

    ids = [row["id"] for row in corpus_ds]
    texts = [row["text"] for row in corpus_ds]
    titles = [row.get("title", "") for row in corpus_ds]

    # Step 2: Load Qwen3 embedder via the factory
    print(f"[build_qwen3_index] Loading {_MODEL_BACKEND} embedder (dim={_dim_label}, batch_size={BATCH_SIZE})...")
    from neolex.embeddings.qwen3_embedder import load_qwen3_embedder

    embedder = load_qwen3_embedder(backend=_MODEL_BACKEND, dim=EMBED_DIM)

    # Output file names encode the dimension so different-dim indexes don't collide
    _idx_stem = _MODEL_BACKEND.replace("/", "-")
    _dim_suffix = "" if _dim_label == "1024" else f"_dim{_dim_label}"
    faiss_path = DATA_DIR / f"faiss_{_idx_stem}{_dim_suffix}.bin"
    meta_path = DATA_DIR / f"faiss_{_idx_stem}{_dim_suffix}.json"

    # Step 3: Embed all passages
    print(f"[build_qwen3_index] Embedding {len(texts)} passages (batch_size={BATCH_SIZE}, max_length={MAX_LENGTH})...")
    all_embeddings = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start: start + BATCH_SIZE]
        embs = embedder.embed_texts(batch, max_length=MAX_LENGTH, batch_size=BATCH_SIZE)
        all_embeddings.append(embs)
        if start % 200 == 0:  # log every 200 passages
            pct = (start + len(batch)) / len(texts) * 100
            print(f"[build_qwen3_index]   {start + len(batch)}/{len(texts)} ({pct:.1f}%)...")

    matrix = np.concatenate(all_embeddings, axis=0).astype(np.float32)
    print(f"[build_qwen3_index] Embedding matrix: {matrix.shape}")

    # Step 4: Build and save FAISS index
    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(matrix)
    faiss.write_index(index, str(faiss_path))
    print(f"[build_qwen3_index] FAISS index saved: {index.ntotal} vectors -> {faiss_path}")

    # Step 5: Save metadata
    metadata = [{"id": pid, "text": text, "title": title}
                for pid, text, title in zip(ids, texts, titles)]
    with open(meta_path, "w") as f:
        json.dump(metadata, f)
    print(f"[build_qwen3_index] Metadata saved -> {meta_path}")

    print("[build_qwen3_index] Done!")


if __name__ == "__main__":
    main()
