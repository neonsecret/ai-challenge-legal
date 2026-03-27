#!/usr/bin/env python3
"""Legal RAG Bench evaluation harness.

Tests full pipeline (route -> retrieve -> answer) on 100 expert criminal law
questions from the Victorian Judicial College Criminal Charge Book.

Usage:
    python benchmarks/legal-rag-bench/run.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import json
import os
import re
import sys
import threading
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = BENCH_DIR / "data"
BM25_CACHE_DIR = DATA_DIR / "bm25_cache"
BM25_IDS_PATH = BM25_CACHE_DIR / "corpus_ids.json"

# Embedding backend selection: "snowflake" (default) | "qwen3-4b" | "qwen3-8b" | "qwen3-0.6b"
_EMBEDDING_BACKEND = os.environ.get("EMBEDDING_MODEL", "snowflake").lower()
if _EMBEDDING_BACKEND.startswith("qwen3"):
    # Use model-specific FAISS index file so results are comparable
    _idx_stem = _EMBEDDING_BACKEND.replace("/", "-")  # e.g. "qwen3-4b"
    FAISS_INDEX_PATH = DATA_DIR / f"faiss_{_idx_stem}.bin"
    FAISS_METADATA_PATH = DATA_DIR / f"faiss_{_idx_stem}.json"
    RESULTS_PATH = BENCH_DIR / f"results_{_idx_stem}_full.json"
else:
    FAISS_INDEX_PATH = DATA_DIR / "faiss_index.bin"
    FAISS_METADATA_PATH = DATA_DIR / "faiss_metadata.json"
    RESULTS_PATH = BENCH_DIR / "results.json"

# Module-level caches
_faiss_index = None
_faiss_metadata = None
_faiss_metadata_dict = None
_bm25_index = None
_bm25_ids = None
_embedding_model = None
_reranker = None
_reranker_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_dataset():
    """Load the Legal RAG Bench dataset from HuggingFace."""
    from datasets import load_dataset as hf_load

    print("[legal-rag-bench] Loading dataset from HuggingFace...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    qa_ds = hf_load("isaacus/legal-rag-bench", "qa", split="test")
    print(f"[legal-rag-bench] Loaded {len(corpus_ds)} corpus passages, {len(qa_ds)} QA pairs")
    return corpus_ds, qa_ds


def build_corpus_index(corpus_ds) -> dict:
    """Build passage_id -> text mapping from the corpus."""
    index = {}
    for row in corpus_ds:
        pid = row["id"]
        text = row.get("text", "")
        title = row.get("title", "")
        index[pid] = {"text": text, "title": title}
    return index


# ---------------------------------------------------------------------------
# Index loading
# ---------------------------------------------------------------------------

def _load_faiss():
    """Load FAISS index and metadata (cached)."""
    global _faiss_index, _faiss_metadata, _faiss_metadata_dict
    if _faiss_index is None:
        import faiss
        _faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
        with open(FAISS_METADATA_PATH) as f:
            _faiss_metadata = json.load(f)
        _faiss_metadata_dict = {e["id"]: e for e in _faiss_metadata}
        print(f"[legal-rag-bench] FAISS index loaded: {_faiss_index.ntotal} vectors")
    return _faiss_index, _faiss_metadata


def _load_bm25():
    """Load BM25 index and corpus IDs (cached)."""
    global _bm25_index, _bm25_ids
    if _bm25_index is None:
        import bm25s
        _bm25_index = bm25s.BM25.load(str(BM25_CACHE_DIR))
        with open(BM25_IDS_PATH) as f:
            _bm25_ids = json.load(f)
        print(f"[legal-rag-bench] BM25 index loaded: {len(_bm25_ids)} documents")
    return _bm25_index, _bm25_ids


def _get_embedding_model():
    """Get embedding model (cached). Supports Snowflake (default) and Qwen3 family."""
    global _embedding_model
    if _embedding_model is None:
        if _EMBEDDING_BACKEND.startswith("qwen3"):
            from neolex.embeddings.qwen3_embedder import load_qwen3_embedder
            _embedding_model = load_qwen3_embedder(backend=_EMBEDDING_BACKEND, dim=1024)
        else:
            from sentence_transformers import SentenceTransformer
            import torch
            device = (
                'mps' if torch.backends.mps.is_available()
                else 'cuda' if torch.cuda.is_available()
                else 'cpu'
            )
            _embedding_model = SentenceTransformer(
                "Snowflake/snowflake-arctic-embed-l-v2.0",
                device=device,
                trust_remote_code=True,
            )
    return _embedding_model


def _get_reranker():
    """Get cross-encoder reranker (cached)."""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        import torch
        _reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=2048)
        if torch.backends.mps.is_available():
            _reranker.model.to('mps')
    return _reranker


# ---------------------------------------------------------------------------
# Hybrid retrieval
# ---------------------------------------------------------------------------

def _hybrid_retrieve(question: str, top_k: int = 10) -> list[dict]:
    """Hybrid BM25 + vector + cross-encoder retrieval over the benchmark corpus.

    Returns list of {"id": str, "text": str, "title": str} for top_k passages.
    """
    from arlc.indexing.legal_tokenizer import legal_tokenize_queries

    has_faiss = FAISS_INDEX_PATH.exists()
    has_bm25 = BM25_CACHE_DIR.exists()

    if not has_faiss and not has_bm25:
        raise RuntimeError(
            "No indexes found. Run build_index.py first:\n"
            "  python benchmarks/legal-rag-bench/build_index.py"
        )

    # Collect per-system rankings for RRF
    passage_info = {}  # pid -> {"text", "title"}
    vec_rank = {}      # pid -> rank (1-based)
    bm25_rank = {}     # pid -> rank (1-based)

    # --- Vector search ---
    if has_faiss:
        index, metadata = _load_faiss()
        model = _get_embedding_model()
        query_emb = model.encode(question, prompt_name='query', normalize_embeddings=True)
        query_np = np.array([query_emb], dtype='float32')
        import faiss
        faiss.normalize_L2(query_np)
        k_vec = min(200, index.ntotal)
        D, I = index.search(query_np, k_vec)
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
                passage_info[pid] = {
                    "text": entry["text"],
                    "title": entry.get("title", ""),
                }

    # --- BM25 search ---
    if has_bm25:
        bm25, bm25_ids = _load_bm25()
        tokenized_q = legal_tokenize_queries(question)
        results, scores = bm25.retrieve(tokenized_q, k=200)
        rank = 0
        for j in range(len(results[0])):
            doc_idx = int(results[0][j])
            if doc_idx < 0 or doc_idx >= len(bm25_ids):
                continue
            pid = bm25_ids[doc_idx]
            if pid not in bm25_rank:
                rank += 1
                bm25_rank[pid] = rank
                if pid not in passage_info and has_faiss:
                    entry = _faiss_metadata_dict.get(pid)
                    if entry:
                        passage_info[pid] = {
                            "text": entry["text"],
                            "title": entry.get("title", ""),
                        }

    # --- Reciprocal Rank Fusion (RRF) ---
    RRF_K = 60  # standard RRF constant
    rrf_scores = {}
    all_pids = set(vec_rank) | set(bm25_rank)
    for pid in all_pids:
        score = 0.0
        if pid in vec_rank:
            score += 1.0 / (RRF_K + vec_rank[pid])
        if pid in bm25_rank:
            score += 1.0 / (RRF_K + bm25_rank[pid])
        rrf_scores[pid] = score

    # --- Cross-encoder reranking on top 100 by RRF ---
    candidate_list = [
        {"id": pid, "score": rrf_scores[pid], **passage_info.get(pid, {"text": "", "title": ""})}
        for pid in all_pids if pid in passage_info
    ]
    candidate_list.sort(key=lambda x: x["score"], reverse=True)
    candidate_list = candidate_list[:100]

    if len(candidate_list) > top_k:
        reranker = _get_reranker()
        pairs = [(question, (c["title"] + "\n" + c["text"])[:2000]) for c in candidate_list]
        with _reranker_lock:
            rerank_scores = reranker.predict(pairs)
        for i, score in enumerate(rerank_scores):
            candidate_list[i]["score"] = float(score)
        candidate_list.sort(key=lambda x: x["score"], reverse=True)

    return candidate_list[:top_k]


# ---------------------------------------------------------------------------
# Pipeline adapter
# ---------------------------------------------------------------------------

async def run_pipeline(question: str, corpus_index: dict) -> dict:
    """Run our hybrid pipeline on a question against the Legal RAG Bench corpus.

    Returns dict with: answer, retrieved_passage_ids, contexts
    """
    from arlc.answerer import generate_answer

    retrieved = _hybrid_retrieve(question, top_k=10)
    retrieved_ids = [r["id"] for r in retrieved]

    source_pages = []
    contexts = []
    for r in retrieved:
        contexts.append(r["text"])
        source_pages.append({
            "doc_id": r["id"],
            "page_number": 1,
            "text": r["text"],
        })

    answer_result = await generate_answer(
        question=question,
        answer_type="free_text",
        source_pages=source_pages,
    )

    return {
        "answer": str(answer_result.answer) if answer_result.answer else "",
        "retrieved_passage_ids": retrieved_ids,
        "contexts": contexts,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def rouge_l(prediction: str, reference: str) -> float:
    """Compute ROUGE-L F1 score between prediction and reference."""
    if not prediction or not reference:
        return 0.0
    pred_tokens = prediction.lower().split()
    ref_tokens = reference.lower().split()
    if not pred_tokens or not ref_tokens:
        return 0.0

    # LCS via SequenceMatcher
    matcher = SequenceMatcher(None, pred_tokens, ref_tokens)
    lcs_len = sum(block.size for block in matcher.get_matching_blocks())

    precision = lcs_len / len(pred_tokens) if pred_tokens else 0
    recall = lcs_len / len(ref_tokens) if ref_tokens else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return f1


def retrieval_accuracy(predicted_ids: list[str], gold_id: str) -> float:
    """Check if the gold passage ID is in the retrieved set."""
    return 1.0 if gold_id in predicted_ids else 0.0


def groundedness_score(answer: str, contexts: list[str]) -> float:
    """Simple groundedness: fraction of answer sentences found in contexts."""
    if not answer or not contexts:
        return 0.0
    context_text = " ".join(contexts).lower()
    sentences = [s.strip() for s in re.split(r'[.!?]+', answer) if s.strip()]
    if not sentences:
        return 0.0

    grounded = 0
    for sent in sentences:
        sent_words = set(sent.lower().split())
        if not sent_words:
            continue
        context_words = set(context_text.split())
        overlap = len(sent_words & context_words) / len(sent_words)
        if overlap >= 0.5:  # at least 50% word overlap
            grounded += 1

    return grounded / len(sentences)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Legal RAG Bench evaluation")
    parser.add_argument("--dry-run", action="store_true", help="Download data only")
    parser.add_argument("--limit", type=int, default=0, help="Limit queries (0=all)")
    args = parser.parse_args()

    # Step 1: Load dataset
    corpus_ds, qa_ds = load_dataset()
    corpus_index = build_corpus_index(corpus_ds)

    if args.dry_run:
        print("[legal-rag-bench] Dry run complete. Dataset loaded successfully.")
        print(f"  Corpus: {len(corpus_index)} passages")
        print(f"  QA: {len(qa_ds)} questions")
        return

    qa_items = list(qa_ds)
    if args.limit > 0:
        qa_items = qa_items[:args.limit]
        print(f"[legal-rag-bench] Limited to {args.limit} queries")

    # Step 2: Run pipeline on each question
    results = []
    total_retrieval_acc = 0.0
    total_rouge = 0.0
    total_groundedness = 0.0

    for i, item in enumerate(qa_items):
        question = item["question"]
        gold_answer = item["answer"]
        gold_passage_id = item["relevant_passage_id"]

        print(f"  [{i+1}/{len(qa_items)}] {question[:80]}...")

        pipeline_output = asyncio.run(run_pipeline(question, corpus_index))

        ret_acc = retrieval_accuracy(pipeline_output["retrieved_passage_ids"], gold_passage_id)
        rouge = rouge_l(pipeline_output["answer"], gold_answer)
        grounded = groundedness_score(pipeline_output["answer"], pipeline_output["contexts"])

        results.append({
            "question": question,
            "gold_passage_id": gold_passage_id,
            "retrieved_ids": pipeline_output["retrieved_passage_ids"],
            "retrieval_hit": ret_acc,
            "rouge_l": rouge,
            "groundedness": grounded,
            "answer_preview": pipeline_output["answer"][:200],
        })
        total_retrieval_acc += ret_acc
        total_rouge += rouge
        total_groundedness += grounded

    n = len(results)
    aggregate = {
        "num_queries": n,
        "retrieval_accuracy": total_retrieval_acc / n if n else 0,
        "avg_rouge_l": total_rouge / n if n else 0,
        "avg_groundedness": total_groundedness / n if n else 0,
    }
    output = {"aggregate": aggregate, "per_query": results}

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[legal-rag-bench] Results saved to {RESULTS_PATH}")
    print(f"  Retrieval Accuracy: {aggregate['retrieval_accuracy']:.4f}")
    print(f"  ROUGE-L:           {aggregate['avg_rouge_l']:.4f}")
    print(f"  Groundedness:      {aggregate['avg_groundedness']:.4f}")


if __name__ == "__main__":
    main()
