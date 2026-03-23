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
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

RESULTS_PATH = BENCH_DIR / "results.json"


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
# Pipeline adapter
# ---------------------------------------------------------------------------

async def run_pipeline(question: str, corpus_index: dict) -> dict:
    """Run our pipeline on a question against the Legal RAG Bench corpus.

    Since our pipeline is built for DIFC documents, we adapt by:
    1. Using full-corpus retrieval mode (no routing)
    2. Treating each corpus passage as a virtual document page
    3. Generating an answer with our answerer

    Returns dict with: answer, retrieved_passage_ids, contexts
    """
    from arlc.answerer import generate_answer

    # For this benchmark, we do a simple text similarity retrieval
    # against the corpus passages since our retriever is DIFC-specific.
    # This measures our answerer's quality given relevant context.
    retrieved_ids = _simple_retrieve(question, corpus_index, top_k=3)

    # Build source pages from retrieved passages
    source_pages = []
    contexts = []
    for pid in retrieved_ids:
        passage = corpus_index.get(pid, {})
        text = passage.get("text", "")
        contexts.append(text)
        source_pages.append({
            "doc_id": pid,
            "page_number": 1,
            "text": text,
        })

    # Generate answer (async)
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


def _simple_retrieve(question: str, corpus_index: dict, top_k: int = 3) -> list[str]:
    """Simple BM25-style keyword retrieval over corpus passages.

    This is a lightweight retrieval fallback for benchmarks where our
    DIFC-specific retriever doesn't apply directly.
    """
    query_terms = set(re.findall(r'\w+', question.lower()))

    scores = []
    for pid, passage in corpus_index.items():
        text = passage.get("text", "").lower()
        # Simple term overlap scoring
        doc_terms = set(re.findall(r'\w+', text))
        if not doc_terms:
            continue
        overlap = len(query_terms & doc_terms)
        score = overlap / (len(query_terms) + 1)  # +1 to avoid division by zero
        scores.append((pid, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in scores[:top_k]]


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
