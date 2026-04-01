#!/usr/bin/env python3
"""Build FAISS index for Legal RAG Bench corpus using llama-server embeddings.

Downloads 4,876 passages from HuggingFace isaacus/legal-rag-bench corpus,
embeds them via llama-server (Qwen3-Embedding-8B Q4_K_M), and saves:
  - data/faiss_llama-server.bin  — FAISS flat IP index (4096-dim native)
  - data/faiss_llama-server.json — metadata (id, text, title)

The BM25 index is shared across backends (tokenization is model-agnostic).

Usage:
    # Start llama-server first, then:
    cd ~/ai-challenge-legal
    PYTHONPATH=. python3 benchmarks/legal-rag-bench/build_qwen3_index.py

Resume after interruption:
    Re-run the same command. The checkpoint file
    (data/faiss_llama-server.ckpt.npy) is detected automatically.
    Transfer it to another machine to resume there.
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

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "64"))  # llama-server handles GPU batching
CHECKPOINT_EVERY = 200


def main():
    import faiss
    from datasets import load_dataset as hf_load

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    faiss_path = DATA_DIR / "faiss_llama-server.bin"
    meta_path = DATA_DIR / "faiss_llama-server.json"
    ckpt_path = DATA_DIR / "faiss_llama-server.ckpt.npy"

    # Step 1: Load corpus
    print("[build_bench_index] Loading corpus from HuggingFace...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    print(f"[build_bench_index] Loaded {len(corpus_ds)} passages")

    ids = [row["id"] for row in corpus_ds]
    texts = [row["text"] for row in corpus_ds]
    titles = [row.get("title", "") for row in corpus_ds]

    # Step 2: Load checkpoint if present
    start_from = 0
    all_embeddings = []

    if ckpt_path.exists():
        print(f"[build_bench_index] Found checkpoint: {ckpt_path}")
        ckpt = np.load(str(ckpt_path), allow_pickle=True).item()
        start_from = ckpt["next_start"]
        all_embeddings = [ckpt["embeddings"]]
        print(
            f"[build_bench_index] Resuming from passage {start_from}/{len(texts)} "
            f"({start_from / len(texts) * 100:.1f}% done)"
        )
    else:
        print("[build_bench_index] No checkpoint found, starting from scratch")

    if start_from < len(texts):
        # Step 3: Load embedder
        from neolex.embeddings.llama_embedder import LlamaServerEmbedder

        embedder = LlamaServerEmbedder(batch_size=BATCH_SIZE)
        print(f"[build_bench_index] Using llama-server at {embedder.url} (batch_size={BATCH_SIZE})")

        # Step 4: Embed remaining passages
        t0 = time.monotonic()
        print(f"[build_bench_index] Embedding {len(texts) - start_from} passages...")

        for start in range(start_from, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            embs = embedder.embed_texts(batch)
            all_embeddings.append(embs)
            done = start + len(batch)

            if (start - start_from) % 40 == 0:
                elapsed = time.monotonic() - t0
                newly_done = done - start_from
                rate = newly_done / elapsed if elapsed > 0 else 0
                eta_min = (len(texts) - done) / rate / 60 if rate > 0 else 0
                pct = done / len(texts) * 100
                print(
                    f"[build_bench_index]   {done}/{len(texts)} ({pct:.1f}%) — "
                    f"{elapsed:.0f}s, {rate:.2f} p/s, ETA {eta_min:.0f}min"
                )

            if done % CHECKPOINT_EVERY == 0 or done == len(texts):
                combined = np.concatenate(all_embeddings, axis=0).astype(np.float32)
                tmp = ckpt_path.with_suffix(".tmp.npy")
                np.save(str(tmp), {"next_start": done, "embeddings": combined})
                tmp.rename(ckpt_path)
                print(f"[build_bench_index]   ✓ Checkpoint: {done}/{len(texts)}")

    # Step 5: Build FAISS index
    matrix = np.concatenate(all_embeddings, axis=0).astype(np.float32)
    actual_dim = matrix.shape[1]
    print(f"[build_bench_index] Embedding matrix: {matrix.shape} (dim={actual_dim})")

    index = faiss.IndexFlatIP(actual_dim)
    index.add(matrix)
    faiss.write_index(index, str(faiss_path))
    print(f"[build_bench_index] FAISS index saved: {index.ntotal} vectors -> {faiss_path}")

    metadata = [{"id": pid, "text": text, "title": title} for pid, text, title in zip(ids, texts, titles)]
    with open(meta_path, "w") as f:
        json.dump(metadata, f)
    print(f"[build_bench_index] Metadata saved -> {meta_path}")

    if ckpt_path.exists():
        ckpt_path.unlink()
        print("[build_bench_index] Checkpoint removed.")

    print("[build_bench_index] Done!")


if __name__ == "__main__":
    main()
