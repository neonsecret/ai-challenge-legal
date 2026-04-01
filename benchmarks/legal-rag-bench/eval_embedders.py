#!/usr/bin/env python3
"""Pure-embedding evaluation for Legal RAG Bench.

Embeds all corpus passages + questions with a single model, then measures
retrieval accuracy @k using cosine similarity (no BM25, no reranker).

Usage:
    python benchmarks/legal-rag-bench/eval_embedders.py \
        --model Snowflake/snowflake-arctic-embed-l-v2.0

    python benchmarks/legal-rag-bench/eval_embedders.py \
        --model Qwen/Qwen3-Embedding-0.6B

    python benchmarks/legal-rag-bench/eval_embedders.py \
        --model Qwen/Qwen3-Embedding-4B --quantize
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def get_vram_gb() -> float:
    if torch.cuda.is_available():
        return torch.cuda.get_device_properties(0).total_memory / 1e9
    return 0.0


def get_vram_used_gb() -> float:
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated(0) / 1e9
    return 0.0


def is_qwen3(model_name: str) -> bool:
    return "qwen3" in model_name.lower()


def load_model(model_name: str, quantize: bool = False):
    """Load SentenceTransformer model with appropriate settings."""
    from sentence_transformers import SentenceTransformer

    device = get_device()
    print(f"[embedder] Loading {model_name} on {device}")
    t0 = time.time()

    kwargs = {
        "trust_remote_code": True,
        "tokenizer_kwargs": {"padding_side": "left"},
    }

    if quantize and device == "cuda":
        try:
            from transformers import BitsAndBytesConfig

            bnb = BitsAndBytesConfig(load_in_4bit=True)
            kwargs["model_kwargs"] = {"quantization_config": bnb, "device_map": "auto"}
            print("[embedder] Using 4-bit quantization")
        except ImportError:
            print("[embedder] bitsandbytes not available, skipping quantization")
    elif device == "cuda":
        # Try flash attention for speed (optional, falls back gracefully)
        try:
            import flash_attn  # noqa: F401

            kwargs["model_kwargs"] = {"attn_implementation": "flash_attention_2", "device_map": "auto"}
            print("[embedder] Using flash_attention_2")
        except ImportError:
            pass

    model = SentenceTransformer(
        model_name, device=device if "device_map" not in kwargs.get("model_kwargs", {}) else None, **kwargs
    )
    params = sum(p.numel() for p in model.parameters())
    print(f"[embedder] Loaded in {time.time() - t0:.1f}s — {params / 1e6:.0f}M params")
    return model


def embed_passages(model, texts: list[str], model_name: str, batch_size: int = 16) -> np.ndarray:
    """Embed corpus passages (no task instruction)."""
    print(f"[embedder] Embedding {len(texts)} passages (batch_size={batch_size})...")
    t0 = time.time()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=batch_size,
    )
    elapsed = time.time() - t0
    print(f"[embedder] Passages embedded in {elapsed:.1f}s ({elapsed / len(texts) * 1000:.1f}ms/passage)")
    return np.array(embeddings, dtype=np.float32)


def embed_queries(model, questions: list[str], model_name: str, batch_size: int = 16) -> np.ndarray:
    """Embed queries with task instruction for supported models."""
    print(f"[embedder] Embedding {len(questions)} queries...")
    t0 = time.time()

    encode_kwargs = dict(normalize_embeddings=True, show_progress_bar=False, batch_size=batch_size)

    if is_qwen3(model_name):
        # Qwen3-Embedding uses prompt_name="query" for queries
        try:
            embeddings = model.encode(questions, prompt_name="query", **encode_kwargs)
        except Exception as e:
            print(f"[embedder] prompt_name='query' failed ({e}), using plain encode")
            embeddings = model.encode(questions, **encode_kwargs)
    else:
        # Snowflake and others — try prompt_name="query", fall back
        try:
            embeddings = model.encode(questions, prompt_name="query", **encode_kwargs)
        except Exception:
            embeddings = model.encode(questions, **encode_kwargs)

    elapsed = time.time() - t0
    print(f"[embedder] Queries embedded in {elapsed:.1f}s")
    return np.array(embeddings, dtype=np.float32)


def compute_accuracy_at_k(
    query_embs: np.ndarray,
    passage_embs: np.ndarray,
    gold_ids: list[str],
    passage_ids: list[str],
    ks: list[int] = (1, 3, 5, 10),
) -> dict[int, float]:
    """Compute Acc@k via brute-force cosine similarity."""
    print(f"[embedder] Computing similarities ({len(query_embs)} queries × {len(passage_embs)} passages)...")
    t0 = time.time()

    # Cosine similarity matrix [Q x P] — embeddings are already normalized
    scores = query_embs @ passage_embs.T  # [Q, P]
    top10_indices = np.argsort(-scores, axis=1)[:, : max(ks)]

    elapsed = time.time() - t0
    print(f"[embedder] Similarity computed in {elapsed:.2f}s")

    pid_to_idx = {pid: i for i, pid in enumerate(passage_ids)}

    results = {k: 0 for k in ks}
    misses = []
    for q_idx, gold_id in enumerate(gold_ids):
        gold_idx = pid_to_idx.get(gold_id, -1)
        if gold_idx == -1:
            print(f"[embedder] WARNING: gold_id {gold_id} not in corpus!")
            continue
        top_indices = top10_indices[q_idx]
        for k in ks:
            if gold_idx in top_indices[:k]:
                results[k] += 1
            elif k == max(ks):
                # Collect miss details for debugging
                top1_id = passage_ids[top_indices[0]]
                top1_score = float(scores[q_idx, top_indices[0]])
                gold_score = float(scores[q_idx, gold_idx])
                misses.append(
                    {
                        "q_idx": q_idx,
                        "gold_id": gold_id,
                        "top1_id": top1_id,
                        "top1_score": top1_score,
                        "gold_score": gold_score,
                        "rank": int(np.where(top_indices == gold_idx)[0][0]) + 1 if gold_idx in top_indices else -1,
                    }
                )

    n = len(gold_ids)
    return {k: results[k] / n for k in ks}, misses


def main():
    parser = argparse.ArgumentParser(description="Embedding model benchmark on Legal RAG Bench")
    parser.add_argument("--model", required=True, help="HuggingFace model ID")
    parser.add_argument("--quantize", action="store_true", help="4-bit quantization (for large models)")
    parser.add_argument("--batch-size", type=int, default=16, help="Encoding batch size")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions (default: all)")
    parser.add_argument("--output", help="Save results to JSON path")
    args = parser.parse_args()

    total_vram = get_vram_gb()
    print(f"[embedder] GPU VRAM: {total_vram:.1f}GB")
    print(f"[embedder] Model: {args.model}")

    # --- Load dataset ---
    from datasets import load_dataset as hf_load

    print("[embedder] Loading Legal RAG Bench corpus...")
    t0 = time.time()
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    passage_ids = [row["id"] for row in corpus_ds]
    passage_texts = [row["text"] for row in corpus_ds]
    print(f"[embedder] Corpus: {len(passage_ids)} passages (loaded in {time.time() - t0:.1f}s)")

    print("[embedder] Loading QA pairs...")
    qa_ds = hf_load("isaacus/legal-rag-bench", "qa", split="test")
    qa_items = list(qa_ds)
    if args.limit:
        qa_items = qa_items[: args.limit]
    questions = [item["question"] for item in qa_items]
    gold_ids = [item["relevant_passage_id"] for item in qa_items]
    print(f"[embedder] Questions: {len(questions)}")

    # --- Load model ---
    vram_before = get_vram_used_gb()
    model = load_model(args.model, quantize=args.quantize)
    vram_after_load = get_vram_used_gb()
    model_vram = vram_after_load - vram_before
    print(f"[embedder] Model VRAM: {model_vram:.2f}GB")

    # --- Embed ---
    t_embed_start = time.time()
    passage_embs = embed_passages(model, passage_texts, args.model, batch_size=args.batch_size)
    query_embs = embed_queries(model, questions, args.model, batch_size=args.batch_size)
    embed_time = time.time() - t_embed_start
    vram_peak = get_vram_used_gb()

    print(f"[embedder] Embedding dim: {passage_embs.shape[1]}")
    print(f"[embedder] Total embed time: {embed_time:.1f}s")
    print(f"[embedder] Peak VRAM used: {vram_peak:.2f}GB")

    # --- Eval ---
    ks = [1, 3, 5, 10]
    acc_at_k, misses = compute_accuracy_at_k(query_embs, passage_embs, gold_ids, passage_ids, ks)

    print(f"\n{'=' * 60}")
    print(f"Model: {args.model}")
    print(f"Corpus: {len(passage_ids)} passages | Questions: {len(questions)}")
    print(f"Embed time: {embed_time:.1f}s | VRAM used: {vram_peak:.2f}GB / {total_vram:.1f}GB")
    print(f"Embedding dim: {passage_embs.shape[1]}")
    print()
    print(f"{'k':>4} | {'Acc@k':>8} | {'Hits':>6}")
    print(f"{'-' * 25}")
    for k in ks:
        hits = int(acc_at_k[k] * len(questions))
        print(f"{k:>4} | {acc_at_k[k]:>8.4f} | {hits:>6}/{len(questions)}")
    print(f"{'=' * 60}")

    result = {
        "model": args.model,
        "num_passages": len(passage_ids),
        "num_queries": len(questions),
        "embed_dim": int(passage_embs.shape[1]),
        "embed_time_s": embed_time,
        "vram_used_gb": round(vram_peak, 2),
        "vram_total_gb": round(total_vram, 1),
        "acc_at_k": {str(k): round(acc_at_k[k], 4) for k in ks},
        "misses_top10": misses[:20],  # first 20 misses for debugging
    }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"[embedder] Results saved to {args.output}")

    return result


if __name__ == "__main__":
    main()
