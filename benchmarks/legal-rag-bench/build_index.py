#!/usr/bin/env python3
"""Build FAISS + BM25 indexes for Legal RAG Bench corpus.

Downloads 4,876 passages from HuggingFace isaacus/legal-rag-bench corpus,
embeds them with Snowflake Arctic Embed, and builds:
  - FAISS index (IndexFlatIP for cosine similarity)
  - BM25 index (bm25s with legal tokenizer)

Usage:
    python benchmarks/legal-rag-bench/build_index.py
"""

import json
import sys
from pathlib import Path

import numpy as np

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = BENCH_DIR / "data"


def main():
    from datasets import load_dataset as hf_load
    from sentence_transformers import SentenceTransformer
    import faiss
    import bm25s

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Load corpus from HuggingFace
    print("[build_index] Loading corpus from HuggingFace...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    print(f"[build_index] Loaded {len(corpus_ds)} passages")

    ids = [row["id"] for row in corpus_ds]
    texts = [row["text"] for row in corpus_ds]
    titles = [row.get("title", "") for row in corpus_ds]

    # Step 2: Build FAISS index
    print("[build_index] Loading embedding model...")
    import torch
    device = (
        'mps' if torch.backends.mps.is_available()
        else 'cuda' if torch.cuda.is_available()
        else 'cpu'
    )
    model = SentenceTransformer(
        "Snowflake/snowflake-arctic-embed-l-v2.0",
        device=device,
        trust_remote_code=True,
    )

    print(f"[build_index] Embedding {len(texts)} passages on {device}...")
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=16,
    )

    print("[build_index] Building FAISS index...")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings.astype(np.float32))
    faiss.write_index(index, str(DATA_DIR / "faiss_index.bin"))

    # Save metadata (id + text for each passage)
    metadata = []
    for pid, text, title in zip(ids, texts, titles):
        metadata.append({"id": pid, "text": text, "title": title})
    with open(DATA_DIR / "faiss_metadata.json", "w") as f:
        json.dump(metadata, f)
    print(f"[build_index] FAISS index saved: {index.ntotal} vectors")

    # Step 3: Build BM25 index
    print("[build_index] Building BM25 index...")
    from arlc.indexing.legal_tokenizer import legal_tokenize_corpus

    tokenized = legal_tokenize_corpus(texts)
    bm25 = bm25s.BM25()
    bm25.index(tokenized)

    bm25_dir = DATA_DIR / "bm25_cache"
    bm25_dir.mkdir(parents=True, exist_ok=True)
    bm25.save(str(bm25_dir))

    # Save corpus IDs for BM25 result mapping
    with open(bm25_dir / "corpus_ids.json", "w") as f:
        json.dump(ids, f)
    print(f"[build_index] BM25 index saved: {len(ids)} documents")

    print("[build_index] Done!")


if __name__ == "__main__":
    main()
