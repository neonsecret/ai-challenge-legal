#!/usr/bin/env python3
"""GaRAGe evaluation harness.

Tests passage-level grounding accuracy on 2,366 questions with 35K+ annotated
passages from the GaRAGe benchmark (Amazon Science).

Usage:
    python benchmarks/garage/run.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = BENCH_DIR / "data"
DATASET_PATH = DATA_DIR / "GaRAGe_benchmark.jsonl"
RESULTS_PATH = BENCH_DIR / "results.json"

# Raw GitHub URL for the dataset
DATASET_URL = "https://raw.githubusercontent.com/amazon-science/GaRAGe/main/GaRAGe_benchmark.jsonl"
# Fallback: clone the repo
REPO_URL = "https://github.com/amazon-science/GaRAGe.git"


# ---------------------------------------------------------------------------
# Data download
# ---------------------------------------------------------------------------

def download_dataset():
    """Download GaRAGe JSONL from GitHub."""
    if DATASET_PATH.exists():
        print(f"[garage] Dataset already exists at {DATASET_PATH}")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("[garage] Downloading GaRAGe dataset from GitHub...")

    try:
        resp = requests.get(DATASET_URL, timeout=120)
        resp.raise_for_status()
        DATASET_PATH.write_bytes(resp.content)
        print(f"[garage] Downloaded {len(resp.content)} bytes")
    except Exception as e:
        print(f"[garage] Direct download failed: {e}")
        print(f"  Trying git clone...")
        clone_dir = DATA_DIR / "GaRAGe"
        os.system(f"git clone --depth 1 {REPO_URL} {clone_dir}")
        src = clone_dir / "GaRAGe_benchmark.jsonl"
        if src.exists():
            import shutil
            shutil.copy2(src, DATASET_PATH)
        else:
            # Search for JSONL files in the clone
            for f in clone_dir.rglob("*.jsonl"):
                import shutil
                shutil.copy2(f, DATASET_PATH)
                break
            else:
                print(f"[garage] ERROR: Could not find dataset. Clone to {clone_dir} and check.")
                raise SystemExit(1)


def load_dataset() -> list[dict]:
    """Load JSONL dataset."""
    items = []
    with open(DATASET_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


# ---------------------------------------------------------------------------
# Pipeline adapter
# ---------------------------------------------------------------------------

async def evaluate_grounding(item: dict) -> dict:
    """Evaluate our pipeline's grounding on a single GaRAGe item.

    The item contains:
    - question: the query
    - grounding: list of passages (with text, citation info)
    - evidence_relevant: list of YES/NO labels
    - evidence_correct: list of classification labels
    - answer_generate: gold answer

    We feed the passages as context to our answerer, then compare the
    generated answer's grounding citations against the gold labels.
    """
    from arlc.answerer import generate_answer

    question = item.get("question", "")
    passages = item.get("grounding", [])
    evidence_relevant = item.get("evidence_relevant", [])
    answer_gold = item.get("answer_generate", "")

    if not question or not passages:
        return {"skipped": True}

    # Build source pages from passages
    source_pages = []
    for i, passage in enumerate(passages):
        text = passage if isinstance(passage, str) else str(passage)
        source_pages.append({
            "doc_id": f"garage_passage_{i}",
            "page_number": 1,
            "text": text,
        })

    # Limit to first 5 passages to control cost
    source_pages = source_pages[:5]

    # Generate answer
    answer_result = await generate_answer(
        question=question,
        answer_type="free_text",
        source_pages=source_pages,
    )

    generated_answer = str(answer_result.answer) if answer_result.answer else ""

    # Evaluate passage-level grounding
    # Check which passages our answer references / is grounded in
    gold_relevant = []
    for i, label in enumerate(evidence_relevant):
        if isinstance(label, str):
            gold_relevant.append(label.upper() == "YES")
        else:
            gold_relevant.append(bool(label))

    # Simple grounding check: does the answer contain key phrases from relevant passages?
    predicted_relevant = []
    for i, passage in enumerate(passages[:5]):
        text = passage if isinstance(passage, str) else str(passage)
        # Check if key phrases from this passage appear in the answer
        words = set(re.findall(r'\w{4,}', text.lower()))
        answer_words = set(re.findall(r'\w{4,}', generated_answer.lower()))
        overlap = len(words & answer_words) / max(len(words), 1)
        predicted_relevant.append(overlap > 0.05)

    # Compute passage-level metrics
    tp = sum(1 for p, g in zip(predicted_relevant, gold_relevant[:5]) if p and g)
    fp = sum(1 for p, g in zip(predicted_relevant, gold_relevant[:5]) if p and not g)
    fn = sum(1 for p, g in zip(predicted_relevant, gold_relevant[:5]) if not p and g)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "question": question[:100],
        "num_passages": len(passages),
        "num_gold_relevant": sum(gold_relevant),
        "grounding_precision": precision,
        "grounding_recall": recall,
        "grounding_f1": f1,
        "answer_preview": generated_answer[:200],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GaRAGe evaluation")
    parser.add_argument("--dry-run", action="store_true", help="Download data only")
    parser.add_argument("--limit", type=int, default=0, help="Limit queries (0=all)")
    args = parser.parse_args()

    # Step 1: Download
    download_dataset()

    # Step 2: Load
    items = load_dataset()
    print(f"[garage] Loaded {len(items)} items")

    if args.dry_run:
        # Show sample structure
        if items:
            sample = items[0]
            print(f"[garage] Sample item keys: {list(sample.keys())}")
            print(f"[garage] Sample question: {sample.get('question', '')[:100]}")
        print("[garage] Dry run complete.")
        return

    if args.limit > 0:
        items = items[:args.limit]
        print(f"[garage] Limited to {args.limit} items")

    # Step 3: Evaluate
    results = []
    total_p, total_r, total_f1 = 0.0, 0.0, 0.0
    evaluated = 0

    for i, item in enumerate(items):
        print(f"  [{i+1}/{len(items)}] {item.get('question', '')[:80]}...")
        result = asyncio.run(evaluate_grounding(item))

        if result.get("skipped"):
            continue

        results.append(result)
        total_p += result["grounding_precision"]
        total_r += result["grounding_recall"]
        total_f1 += result["grounding_f1"]
        evaluated += 1

    aggregate = {
        "num_evaluated": evaluated,
        "avg_grounding_precision": total_p / evaluated if evaluated else 0,
        "avg_grounding_recall": total_r / evaluated if evaluated else 0,
        "avg_grounding_f1": total_f1 / evaluated if evaluated else 0,
    }
    output = {"aggregate": aggregate, "per_query": results}

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[garage] Results saved to {RESULTS_PATH}")
    print(f"  Grounding Precision: {aggregate['avg_grounding_precision']:.4f}")
    print(f"  Grounding Recall:    {aggregate['avg_grounding_recall']:.4f}")
    print(f"  Grounding F1:        {aggregate['avg_grounding_f1']:.4f}")


if __name__ == "__main__":
    main()
