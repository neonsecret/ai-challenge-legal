#!/usr/bin/env python3
"""LegalBench-RAG evaluation harness.

Tests our retriever's character-level precision/recall against the LegalBench-RAG
benchmark corpus (legal contracts from ContractNLI, CUAD, MAUD, PrivacyQA).

Usage:
    python benchmarks/legalbench-rag/run.py [--dry-run] [--limit N]
"""

import argparse
import json
import os
import sys
import zipfile
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
CORPUS_DIR = DATA_DIR / "corpus"
BENCHMARKS_DIR = DATA_DIR / "benchmarks"
RESULTS_PATH = BENCH_DIR / "results.json"

# Dropbox download URL for pre-generated data
DROPBOX_URL = "https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4?dl=1"


# ---------------------------------------------------------------------------
# Data download
# ---------------------------------------------------------------------------

def download_dataset():
    """Download the LegalBench-RAG corpus and benchmarks from Dropbox."""
    if CORPUS_DIR.exists() and BENCHMARKS_DIR.exists():
        print(f"[legalbench-rag] Data already exists at {DATA_DIR}")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / "legalbenchrag_data.zip"

    print(f"[legalbench-rag] Downloading dataset from Dropbox...")
    print(f"  NOTE: If this fails, manually download from:")
    print(f"  https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4")
    print(f"  and extract into {DATA_DIR}/")

    try:
        resp = requests.get(DROPBOX_URL, stream=True, timeout=120)
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[legalbench-rag] Extracting...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(DATA_DIR)
        zip_path.unlink()
    except Exception as e:
        print(f"[legalbench-rag] Auto-download failed: {e}")
        print(f"  Please manually download and extract into {DATA_DIR}/")
        print(f"  Expected structure: {DATA_DIR}/corpus/ and {DATA_DIR}/benchmarks/")
        raise SystemExit(1)


def load_benchmarks() -> list[dict]:
    """Load all benchmark JSON files. Each contains queries + ground-truth snippets."""
    benchmarks = []
    if not BENCHMARKS_DIR.exists():
        print(f"[legalbench-rag] ERROR: No benchmarks directory at {BENCHMARKS_DIR}")
        raise SystemExit(1)

    for json_file in sorted(BENCHMARKS_DIR.glob("*.json")):
        with open(json_file) as f:
            data = json.load(f)
        # Each benchmark file may be a list of items or a dict with items
        if isinstance(data, list):
            benchmarks.extend(data)
        elif isinstance(data, dict):
            # Try common keys
            for key in ("queries", "benchmarks", "items", "data"):
                if key in data:
                    benchmarks.extend(data[key])
                    break
            else:
                benchmarks.append(data)
    return benchmarks


# ---------------------------------------------------------------------------
# Retrieval adapter: map our pipeline output to character spans
# ---------------------------------------------------------------------------

def retrieve_for_query(query: str, corpus_dir: Path) -> list[dict]:
    """Run our retriever on a query and return retrieved text spans.

    Returns list of {"file": str, "start": int, "end": int, "text": str}.
    We use full-corpus retrieval since legalbench-rag has its own corpus.
    """
    from arlc.retriever import retrieve

    # Use our retriever in full-corpus mode (no target doc IDs)
    results = retrieve(query, n_results=10, use_hyde=False)

    # Map retrieved chunks back to character positions in corpus files.
    # Our retriever returns chunks with doc_id and text. We do a simple
    # substring search to find character spans in the corpus files.
    spans = []
    for chunk in results:
        text = chunk.get("text", "")
        doc_id = chunk.get("doc_id", "")
        if not text or not doc_id:
            continue

        # Search for this text in corpus files
        for corpus_file in corpus_dir.rglob("*.txt"):
            try:
                content = corpus_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            idx = content.find(text[:200])  # match on first 200 chars
            if idx >= 0:
                spans.append({
                    "file": str(corpus_file.relative_to(corpus_dir)),
                    "start": idx,
                    "end": idx + len(text),
                    "text": text,
                })
                break

    return spans


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_char_overlap(predicted_spans: list[dict], gold_spans: list[dict]) -> dict:
    """Compute character-level precision, recall, F1 for a single query.

    Both predicted and gold are lists of {"file": str, "start": int, "end": int}.
    """
    # Build character sets per file
    def char_set(spans):
        chars = set()
        for s in spans:
            f = s.get("file", "")
            start = s.get("start", 0)
            end = s.get("end", 0)
            for i in range(start, end):
                chars.add((f, i))
        return chars

    pred_chars = char_set(predicted_spans)
    gold_chars = char_set(gold_spans)

    if not pred_chars and not gold_chars:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    overlap = pred_chars & gold_chars
    precision = len(overlap) / len(pred_chars) if pred_chars else 0.0
    recall = len(overlap) / len(gold_chars) if gold_chars else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LegalBench-RAG evaluation")
    parser.add_argument("--dry-run", action="store_true", help="Download data only, skip LLM calls")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of queries (0=all)")
    args = parser.parse_args()

    # Step 1: Download dataset
    download_dataset()

    # Step 2: Load benchmarks
    benchmarks = load_benchmarks()
    print(f"[legalbench-rag] Loaded {len(benchmarks)} benchmark queries")

    if args.dry_run:
        print("[legalbench-rag] Dry run complete. Dataset downloaded and loaded.")
        return

    if args.limit > 0:
        benchmarks = benchmarks[:args.limit]
        print(f"[legalbench-rag] Limited to {args.limit} queries")

    # Step 3: Run retrieval and compute metrics
    results = []
    total_p, total_r, total_f1 = 0.0, 0.0, 0.0

    for i, item in enumerate(benchmarks):
        query = item.get("query", item.get("question", ""))
        gold_snippets = item.get("snippets", item.get("ground_truth", []))

        # Normalize gold snippets to {"file", "start", "end"} format
        gold_spans = []
        for snippet in gold_snippets:
            if isinstance(snippet, dict):
                gold_spans.append({
                    "file": snippet.get("file", snippet.get("file_path", "")),
                    "start": snippet.get("start", snippet.get("char_start", 0)),
                    "end": snippet.get("end", snippet.get("char_end", 0)),
                })

        print(f"  [{i+1}/{len(benchmarks)}] {query[:80]}...")
        predicted_spans = retrieve_for_query(query, CORPUS_DIR)
        metrics = compute_char_overlap(predicted_spans, gold_spans)

        results.append({
            "query": query,
            "num_predicted": len(predicted_spans),
            "num_gold": len(gold_spans),
            **metrics,
        })
        total_p += metrics["precision"]
        total_r += metrics["recall"]
        total_f1 += metrics["f1"]

    n = len(results)
    aggregate = {
        "num_queries": n,
        "avg_precision": total_p / n if n else 0,
        "avg_recall": total_r / n if n else 0,
        "avg_f1": total_f1 / n if n else 0,
    }
    output = {"aggregate": aggregate, "per_query": results}

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[legalbench-rag] Results saved to {RESULTS_PATH}")
    print(f"  Precision: {aggregate['avg_precision']:.4f}")
    print(f"  Recall:    {aggregate['avg_recall']:.4f}")
    print(f"  F1:        {aggregate['avg_f1']:.4f}")


if __name__ == "__main__":
    main()
