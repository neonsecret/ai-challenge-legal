#!/usr/bin/env python3
"""Retrieval-only evaluation for Legal RAG Bench — model comparison script.

Compares embedding models on retrieval accuracy without running the LLM answerer.
Supports configurable embedding models and separate index paths.

Usage:
    python benchmarks/legal-rag-bench/eval_retrieval_only.py \
        --model Snowflake/snowflake-arctic-embed-l-v2.0 \
        --index-dir benchmarks/legal-rag-bench/data \
        --limit 20

    python benchmarks/legal-rag-bench/eval_retrieval_only.py \
        --model Qwen/Qwen3-Embedding-0.6B \
        --index-dir benchmarks/legal-rag-bench/data_qwen06b \
        --build-index \
        --limit 20
"""

import argparse
import json
import os
import sys
import time
import threading
from pathlib import Path

import numpy as np

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_device():
    import torch
    if torch.backends.mps.is_available():
        return 'mps'
    if torch.cuda.is_available():
        return 'cuda'
    return 'cpu'


def load_embedding_model(model_name: str):
    from sentence_transformers import SentenceTransformer
    device = get_device()
    print(f"[eval] Loading embedding model: {model_name} on {device}")
    t0 = time.time()

    # Qwen3 models need specific config
    kwargs = {"trust_remote_code": True}
    if "qwen3" in model_name.lower() or "qwen/qwen3" in model_name.lower():
        # Qwen3-Embedding requires specific prompt_name handling
        model = SentenceTransformer(model_name, device=device, **kwargs)
    else:
        model = SentenceTransformer(model_name, device=device, **kwargs)

    elapsed = time.time() - t0
    params = sum(p.numel() for p in model.parameters())
    print(f"[eval] Model loaded in {elapsed:.1f}s — {params/1e6:.0f}M params")
    return model, device


def embed_query(model, question: str, model_name: str) -> np.ndarray:
    """Embed a query with the correct prompt format for the model."""
    if "qwen3" in model_name.lower() or "qwen/qwen3" in model_name.lower():
        # Qwen3-Embedding uses 'query' task prefix
        try:
            emb = model.encode(question, prompt_name='query', normalize_embeddings=True)
        except Exception:
            emb = model.encode(question, normalize_embeddings=True)
    else:
        try:
            emb = model.encode(question, prompt_name='query', normalize_embeddings=True)
        except Exception:
            emb = model.encode(question, normalize_embeddings=True)
    return emb


def build_index(model, model_name: str, data_dir: Path):
    """Build FAISS + BM25 indexes for the corpus."""
    from datasets import load_dataset as hf_load
    import faiss
    import bm25s

    data_dir.mkdir(parents=True, exist_ok=True)

    print("[eval] Loading corpus from HuggingFace...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    print(f"[eval] Loaded {len(corpus_ds)} passages")

    ids = [row["id"] for row in corpus_ds]
    texts = [row["text"] for row in corpus_ds]
    titles = [row.get("title", "") for row in corpus_ds]

    # Embed corpus
    print(f"[eval] Embedding {len(texts)} passages...")
    t0 = time.time()
    if "qwen3" in model_name.lower() or "qwen/qwen3" in model_name.lower():
        try:
            embeddings = model.encode(
                texts,
                prompt_name='passage',
                normalize_embeddings=True,
                show_progress_bar=True,
                batch_size=8,
            )
        except Exception:
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=True,
                batch_size=8,
            )
    else:
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
            batch_size=16,
        )
    embed_time = time.time() - t0
    print(f"[eval] Embedding done in {embed_time:.1f}s ({embed_time/len(texts)*1000:.1f}ms/passage)")

    # FAISS index
    print("[eval] Building FAISS index...")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings.astype(np.float32))
    faiss.write_index(index, str(data_dir / "faiss_index.bin"))

    metadata = [{"id": pid, "text": text, "title": title}
                for pid, text, title in zip(ids, texts, titles)]
    with open(data_dir / "faiss_metadata.json", "w") as f:
        json.dump(metadata, f)
    print(f"[eval] FAISS: {index.ntotal} vectors, dim={embeddings.shape[1]}")

    # BM25 index
    print("[eval] Building BM25 index...")
    from arlc.indexing.legal_tokenizer import legal_tokenize_corpus
    tokenized = legal_tokenize_corpus(texts)
    bm25 = bm25s.BM25()
    bm25.index(tokenized)

    bm25_dir = data_dir / "bm25_cache"
    bm25_dir.mkdir(parents=True, exist_ok=True)
    bm25.save(str(bm25_dir))

    with open(bm25_dir / "corpus_ids.json", "w") as f:
        json.dump(ids, f)

    print(f"[eval] BM25: {len(ids)} documents")
    return embed_time


def hybrid_retrieve(
    question: str,
    model,
    model_name: str,
    data_dir: Path,
    top_k: int = 10,
    use_reranker: bool = True,
) -> list[dict]:
    """Hybrid BM25 + vector + cross-encoder retrieval."""
    import faiss
    import bm25s
    from arlc.indexing.legal_tokenizer import legal_tokenize_queries

    faiss_index_path = data_dir / "faiss_index.bin"
    faiss_meta_path = data_dir / "faiss_metadata.json"
    bm25_dir = data_dir / "bm25_cache"
    bm25_ids_path = bm25_dir / "corpus_ids.json"

    # Load FAISS
    faiss_index = faiss.read_index(str(faiss_index_path))
    with open(faiss_meta_path) as f:
        metadata = json.load(f)
    metadata_dict = {e["id"]: e for e in metadata}

    # Load BM25
    bm25_index = bm25s.BM25.load(str(bm25_dir))
    with open(bm25_ids_path) as f:
        bm25_ids = json.load(f)

    passage_info = {}
    vec_rank = {}
    bm25_rank = {}

    # Vector search
    query_emb = embed_query(model, question, model_name)
    query_np = np.array([query_emb], dtype='float32')
    faiss.normalize_L2(query_np)
    k_vec = min(200, faiss_index.ntotal)
    D, I = faiss_index.search(query_np, k_vec)
    rank = 0
    for j in range(k_vec):
        idx = int(I[0][j])
        if idx < 0:
            continue
        entry = metadata[idx]
        pid = entry["id"]
        if pid not in vec_rank:
            rank += 1
            vec_rank[pid] = rank
            passage_info[pid] = {"text": entry["text"], "title": entry.get("title", "")}

    # BM25 search
    tokenized_q = legal_tokenize_queries(question)
    results, scores = bm25_index.retrieve(tokenized_q, k=200)
    rank = 0
    for j in range(len(results[0])):
        doc_idx = int(results[0][j])
        if doc_idx < 0 or doc_idx >= len(bm25_ids):
            continue
        pid = bm25_ids[doc_idx]
        if pid not in bm25_rank:
            rank += 1
            bm25_rank[pid] = rank
            if pid not in passage_info:
                entry = metadata_dict.get(pid)
                if entry:
                    passage_info[pid] = {"text": entry["text"], "title": entry.get("title", "")}

    # RRF fusion
    RRF_K = 60
    rrf_scores = {}
    all_pids = set(vec_rank) | set(bm25_rank)
    for pid in all_pids:
        score = 0.0
        if pid in vec_rank:
            score += 1.0 / (RRF_K + vec_rank[pid])
        if pid in bm25_rank:
            score += 1.0 / (RRF_K + bm25_rank[pid])
        rrf_scores[pid] = score

    candidates = [
        {"id": pid, "score": rrf_scores[pid], **passage_info.get(pid, {"text": "", "title": ""})}
        for pid in all_pids if pid in passage_info
    ]
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:100]

    # Cross-encoder reranking
    if use_reranker and len(candidates) > top_k:
        from sentence_transformers import CrossEncoder
        import torch
        reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=2048)
        if torch.backends.mps.is_available():
            reranker.model.to('mps')
        pairs = [(question, (c["title"] + "\n" + c["text"])[:2000]) for c in candidates]
        rerank_scores = reranker.predict(pairs)
        for i, score in enumerate(rerank_scores):
            candidates[i]["score"] = float(score)
        candidates.sort(key=lambda x: x["score"], reverse=True)

    return candidates[:top_k]


def main():
    parser = argparse.ArgumentParser(description="Retrieval-only Legal RAG Bench eval")
    parser.add_argument("--model", required=True, help="HuggingFace model ID")
    parser.add_argument("--index-dir", required=True, help="Path to index directory")
    parser.add_argument("--build-index", action="store_true", help="Build index before eval")
    parser.add_argument("--limit", type=int, default=20, help="Number of questions to eval")
    parser.add_argument("--no-reranker", action="store_true", help="Skip cross-encoder reranking")
    parser.add_argument("--output", help="Output JSON path (optional)")
    args = parser.parse_args()

    data_dir = Path(args.index_dir)
    use_reranker = not args.no_reranker

    import psutil
    mem = psutil.virtual_memory()
    print(f"[eval] RAM: {mem.total/1e9:.1f}GB total, {mem.available/1e9:.1f}GB available")

    t_start = time.time()
    model, device = load_embedding_model(args.model)

    embed_time = None
    if args.build_index:
        embed_time = build_index(model, args.model, data_dir)
    else:
        if not (data_dir / "faiss_index.bin").exists():
            print(f"[eval] ERROR: No index at {data_dir}. Use --build-index to create it.")
            sys.exit(1)
        print(f"[eval] Using existing index at {data_dir}")

    # Load dataset
    from datasets import load_dataset as hf_load
    print("[eval] Loading QA dataset...")
    qa_ds = hf_load("isaacus/legal-rag-bench", "qa", split="test")
    qa_items = list(qa_ds)[:args.limit]
    print(f"[eval] Evaluating {len(qa_items)} questions...")

    hits = 0
    results = []
    t_eval_start = time.time()

    for i, item in enumerate(qa_items):
        question = item["question"]
        gold_id = item["relevant_passage_id"]

        retrieved = hybrid_retrieve(
            question, model, args.model, data_dir,
            top_k=10, use_reranker=use_reranker
        )
        retrieved_ids = [r["id"] for r in retrieved]
        hit = 1.0 if gold_id in retrieved_ids else 0.0
        hits += hit

        results.append({
            "question": question[:80],
            "gold_id": gold_id,
            "retrieved_ids": retrieved_ids[:5],
            "hit": hit,
        })
        print(f"  [{i+1}/{len(qa_items)}] {'HIT' if hit else 'MISS'} — {question[:60]}...")

    n = len(results)
    retrieval_accuracy = hits / n if n else 0
    total_time = time.time() - t_start
    eval_time = time.time() - t_eval_start

    mem_after = psutil.virtual_memory()

    print(f"\n{'='*60}")
    print(f"Model: {args.model}")
    print(f"Retrieval Accuracy ({n} questions): {retrieval_accuracy:.4f} ({int(hits)}/{n})")
    print(f"Total time: {total_time:.1f}s (eval: {eval_time:.1f}s)")
    if embed_time:
        print(f"Index build time: {embed_time:.1f}s")
    print(f"RAM used: {(mem_after.used - mem.used)/1e9:+.1f}GB change")
    print(f"{'='*60}")

    output = {
        "model": args.model,
        "num_queries": n,
        "retrieval_accuracy": retrieval_accuracy,
        "hits": int(hits),
        "index_dir": str(data_dir),
        "total_time_s": total_time,
        "embed_time_s": embed_time,
        "use_reranker": use_reranker,
        "per_query": results,
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"[eval] Results saved to {out_path}")

    return retrieval_accuracy


if __name__ == "__main__":
    main()
