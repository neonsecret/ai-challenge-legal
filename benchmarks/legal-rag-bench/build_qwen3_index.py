#!/usr/bin/env python3
"""Build Qwen3 FAISS index for Legal RAG Bench corpus.

Downloads 4,876 passages from HuggingFace isaacus/legal-rag-bench corpus,
embeds them with a Qwen3 model, and saves:
  - data/faiss_qwen3-4b.bin         — FAISS flat IP index (1024-dim Matryoshka)
  - data/faiss_qwen3-4b_dimfull.bin — full native-dim variant (2560-dim for 4B)
  - data/faiss_qwen3-4b.json        — metadata (id, text, title)

The BM25 index is shared with the Snowflake run (tokenization is model-agnostic).

Usage:
    # MPS (Apple Silicon) — auto-detected, batch_size=8 by default
    cd ~/ai-challenge-legal
    PYTHONPATH=. EMBEDDING_MODEL=qwen3-4b EMBEDDING_DIM=full python3 \
        benchmarks/legal-rag-bench/build_qwen3_index.py

    # CUDA (RTX 3070, 8.6 GB VRAM) — batch_size=1 required for 4B model
    PYTHONPATH=. EMBEDDING_MODEL=qwen3-4b BATCH_SIZE=1 python3 \
        benchmarks/legal-rag-bench/build_qwen3_index.py

Resume after interruption:
    Re-run the exact same command. The checkpoint file
    (data/faiss_qwen3-4b_dimfull.ckpt.npy) is detected automatically and
    embedding resumes from where it left off. Transfer the .ckpt.npy file
    to another machine to resume there.

Notes:
    - Qwen3-4B in float16 fills RTX 3070 VRAM → BATCH_SIZE=1 required on CUDA.
    - On MPS (Apple Silicon) unified memory is more flexible → BATCH_SIZE=8.
    - Qwen3-8B 4-bit has CUDA 13.0 kernel issues; use 4B for reliable GPU inference.
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = BENCH_DIR / "data"

import torch

# Model controlled by env var; default to qwen3-4b
_MODEL_BACKEND = os.environ.get("EMBEDDING_MODEL", "qwen3-4b").lower()

# Qwen3 output dimension (Matryoshka truncation).
# EMBEDDING_DIM=1024  — Matryoshka-truncated (default, smaller index)
# EMBEDDING_DIM=full  — native model dim (2560 for 4B, no truncation)
# EMBEDDING_DIM=N     — any integer
_dim_env = os.environ.get("EMBEDDING_DIM", "1024").lower()
# 8192 sentinel means "no truncation" — Qwen3Embedder skips the slice
EMBED_DIM = 8192 if _dim_env == "full" else int(_dim_env)
_dim_label = "full" if _dim_env == "full" else str(EMBED_DIM)

# Batch size: number of texts per embedding call.
# llama-server: client batch_size = HTTP request size; server manages GPU batching
#   internally, so large batches (64+) are efficient regardless of device.
# PyTorch Qwen3Embedder: CUDA RTX 3070 fills at batch_size>1 for 4B/8B float16.
def _auto_batch_size() -> int:
    if _MODEL_BACKEND == "llama-server":
        return 64
    if torch.backends.mps.is_available():
        return 8
    if torch.cuda.is_available():
        return 1
    return 32

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", str(_auto_batch_size())))
MAX_LENGTH = 512  # token budget; legal passages are typically < 200 tokens
CHECKPOINT_EVERY = 200  # save checkpoint every N passages


def main():
    from datasets import load_dataset as hf_load
    import faiss

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Derive output paths from model + dim so different configs don't collide
    _idx_stem = _MODEL_BACKEND.replace("/", "-")
    _dim_suffix = "" if _dim_label == "1024" else f"_dim{_dim_label}"
    faiss_path = DATA_DIR / f"faiss_{_idx_stem}{_dim_suffix}.bin"
    meta_path  = DATA_DIR / f"faiss_{_idx_stem}{_dim_suffix}.json"
    ckpt_path  = DATA_DIR / f"faiss_{_idx_stem}{_dim_suffix}.ckpt.npy"

    # Step 1: Load corpus
    print("[build_qwen3_index] Loading corpus from HuggingFace...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    print(f"[build_qwen3_index] Loaded {len(corpus_ds)} passages")

    ids    = [row["id"]           for row in corpus_ds]
    texts  = [row["text"]         for row in corpus_ds]
    titles = [row.get("title","") for row in corpus_ds]

    # Step 2: Load checkpoint if present
    start_from = 0
    all_embeddings = []  # list of numpy arrays, concatenated at the end

    if ckpt_path.exists():
        print(f"[build_qwen3_index] Found checkpoint: {ckpt_path}")
        ckpt = np.load(str(ckpt_path), allow_pickle=True).item()
        start_from = ckpt["next_start"]
        all_embeddings = [ckpt["embeddings"]]  # shape (N, actual_dim)
        print(f"[build_qwen3_index] Resuming from passage {start_from}/{len(texts)} "
              f"({start_from/len(texts)*100:.1f}% already done)")
    else:
        print(f"[build_qwen3_index] No checkpoint found, starting from scratch")

    if start_from >= len(texts):
        print("[build_qwen3_index] All passages already embedded (checkpoint is complete).")
    else:
        # Step 3: Load embedder
        print(f"[build_qwen3_index] Loading {_MODEL_BACKEND} embedder "
              f"(dim={_dim_label}, batch_size={BATCH_SIZE})...")
        if _MODEL_BACKEND == "llama-server":
            from neolex.embeddings.llama_embedder import LlamaServerEmbedder
            embedder = LlamaServerEmbedder(batch_size=BATCH_SIZE)
        else:
            from neolex.embeddings.qwen3_embedder import load_qwen3_embedder
            embedder = load_qwen3_embedder(backend=_MODEL_BACKEND, dim=EMBED_DIM)

        # Step 4: Embed remaining passages
        remaining = len(texts) - start_from
        print(f"[build_qwen3_index] Embedding {remaining} passages "
              f"(starting at {start_from}, batch_size={BATCH_SIZE}, max_length={MAX_LENGTH})...")
        t0 = time.monotonic()

        for start in range(start_from, len(texts), BATCH_SIZE):
            batch = texts[start: start + BATCH_SIZE]
            embs = embedder.embed_texts(batch, max_length=MAX_LENGTH, batch_size=BATCH_SIZE)
            all_embeddings.append(embs)
            done = start + len(batch)

            # Progress log every 40 passages
            if (start - start_from) % 40 == 0:
                elapsed = time.monotonic() - t0
                newly_done = done - start_from
                rate = newly_done / elapsed if elapsed > 0 else 0
                eta_min = (len(texts) - done) / rate / 60 if rate > 0 else 0
                pct = done / len(texts) * 100
                print(f"[build_qwen3_index]   {done}/{len(texts)} ({pct:.1f}%) — "
                      f"{elapsed:.0f}s, {rate:.2f} passages/s, ETA {eta_min:.0f}min")

            # Checkpoint every CHECKPOINT_EVERY passages (atomic: write tmp then rename)
            if done % CHECKPOINT_EVERY == 0 or done == len(texts):
                combined = np.concatenate(all_embeddings, axis=0).astype(np.float32)
                tmp = ckpt_path.with_suffix(".tmp.npy")
                np.save(str(tmp), {"next_start": done, "embeddings": combined})
                tmp.rename(ckpt_path)
                print(f"[build_qwen3_index]   ✓ Checkpoint saved: {done}/{len(texts)}")

    # Step 5: Build FAISS index
    matrix = np.concatenate(all_embeddings, axis=0).astype(np.float32)
    actual_dim = matrix.shape[1]
    print(f"[build_qwen3_index] Embedding matrix: {matrix.shape} (dim={actual_dim})")

    # Use actual_dim (not EMBED_DIM sentinel) so "full" mode works correctly
    index = faiss.IndexFlatIP(actual_dim)
    index.add(matrix)
    faiss.write_index(index, str(faiss_path))
    print(f"[build_qwen3_index] FAISS index saved: {index.ntotal} vectors -> {faiss_path}")

    # Step 6: Save metadata
    metadata = [{"id": pid, "text": text, "title": title}
                for pid, text, title in zip(ids, texts, titles)]
    with open(meta_path, "w") as f:
        json.dump(metadata, f)
    print(f"[build_qwen3_index] Metadata saved -> {meta_path}")

    # Remove checkpoint on clean completion
    if ckpt_path.exists():
        ckpt_path.unlink()
        print(f"[build_qwen3_index] Checkpoint removed.")

    print("[build_qwen3_index] Done!")


if __name__ == "__main__":
    main()
