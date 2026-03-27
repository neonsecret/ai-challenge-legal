#!/usr/bin/env python3
"""Build Qwen3 FAISS index for Legal RAG Bench corpus.

Downloads 4,876 passages from HuggingFace isaacus/legal-rag-bench corpus,
embeds them with Qwen3-Embedding-4B (float16, recommended for RTX 3070), and saves:
  - data/faiss_qwen3-4b.bin   — FAISS flat IP index (1024-dim Matryoshka)
  - data/faiss_qwen3-4b.json  — metadata (id, text, title)

The BM25 index is shared with the Snowflake run (tokenization is model-agnostic).

Usage on remote GPU machine (RTX 3070, 8.6 GB VRAM):
    cd ~/ai-challenge-legal-new
    PYTHONPATH=. EMBEDDING_MODEL=qwen3-4b ~/.conda/envs/torch313/bin/python3 \
        benchmarks/legal-rag-bench/build_qwen3_index.py

Notes:
    - Qwen3-4B float16 uses 8.4 GB VRAM (fills RTX 3070 completely).
      batch_size=1 is required to avoid OOM during forward passes.
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
# Model controlled by env var; default to qwen3-4b (recommended for RTX 3070)
_MODEL_BACKEND = os.environ.get("EMBEDDING_MODEL", "qwen3-4b").lower()

# Qwen3 output dimension (Matryoshka truncation)
EMBED_DIM = 1024
# Qwen3-4B fills all 8.6 GB VRAM → batch_size=1 required to avoid OOM
# Qwen3-8B 8-bit also fills VRAM → also batch_size=1
BATCH_SIZE = 1
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
    print(f"[build_qwen3_index] Loading {_MODEL_BACKEND} embedder...")
    from neolex.embeddings.qwen3_embedder import load_qwen3_embedder

    embedder = load_qwen3_embedder(backend=_MODEL_BACKEND, dim=EMBED_DIM)

    # Output file names based on model
    _idx_stem = _MODEL_BACKEND.replace("/", "-")
    faiss_path = DATA_DIR / f"faiss_{_idx_stem}.bin"
    meta_path = DATA_DIR / f"faiss_{_idx_stem}.json"

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
