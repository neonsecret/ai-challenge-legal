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
import threading
import zipfile
from pathlib import Path

import numpy as np
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
INDEX_DIR = DATA_DIR / "index"
FAISS_INDEX_PATH = INDEX_DIR / "faiss_index.bin"
FAISS_METADATA_PATH = INDEX_DIR / "faiss_metadata.json"
BM25_CACHE_DIR = INDEX_DIR / "bm25_cache"
BM25_IDS_PATH = BM25_CACHE_DIR / "corpus_ids.json"

# Module-level caches
_faiss_index = None
_faiss_metadata = None
_bm25_index = None
_bm25_ids = None
_embedding_model = None
_reranker = None
_reranker_lock = threading.Lock()

# Dropbox download URL for pre-generated data
DROPBOX_URL = "https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4?rlkey=5n8zrbk4c08lbit3iiexofmwg&st=0hu354cq&dl=1"


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

    print("[legalbench-rag] Downloading dataset from Dropbox...")
    print("  NOTE: If this fails, manually download from:")
    print("  https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4")
    print(f"  and extract into {DATA_DIR}/")

    try:
        resp = requests.get(DROPBOX_URL, stream=True, timeout=120)
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print("[legalbench-rag] Extracting...")
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
            for key in ("tests", "queries", "benchmarks", "items", "data"):
                if key in data:
                    benchmarks.extend(data[key])
                    break
            else:
                benchmarks.append(data)
    return benchmarks


# ---------------------------------------------------------------------------
# Index loading
# ---------------------------------------------------------------------------


def _load_faiss():
    """Load FAISS index and metadata (cached)."""
    global _faiss_index, _faiss_metadata
    if _faiss_index is None:
        import faiss

        _faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
        with open(FAISS_METADATA_PATH) as f:
            _faiss_metadata = json.load(f)
        print(f"[legalbench-rag] FAISS index loaded: {_faiss_index.ntotal} vectors")
    return _faiss_index, _faiss_metadata


def _load_bm25():
    """Load BM25 index and chunk IDs (cached)."""
    global _bm25_index, _bm25_ids
    if _bm25_index is None:
        import bm25s

        _bm25_index = bm25s.BM25.load(str(BM25_CACHE_DIR))
        with open(BM25_IDS_PATH) as f:
            _bm25_ids = json.load(f)
        print(f"[legalbench-rag] BM25 index loaded: {len(_bm25_ids)} chunks")
    return _bm25_index, _bm25_ids


_EMBEDDING_BACKEND = os.environ.get("EMBEDDING_MODEL", "llama-server").lower()


def _get_embedding_model():
    """Get embedding model (cached).

    Defaults to llama-server (Qwen3-8B, production embedder).
    Set EMBEDDING_MODEL=snowflake to use Snowflake Arctic instead.
    """
    global _embedding_model
    if _embedding_model is None:
        if _EMBEDDING_BACKEND == "llama-server":
            from neolex.embeddings.llama_embedder import LlamaServerEmbedder

            _embedding_model = LlamaServerEmbedder()
        else:
            import torch
            from sentence_transformers import SentenceTransformer

            device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
            _embedding_model = SentenceTransformer(
                "Snowflake/snowflake-arctic-embed-l-v2.0",
                device=device,
                trust_remote_code=True,
            )
    return _embedding_model


# ---------------------------------------------------------------------------
# Retrieval adapter: map our pipeline output to character spans
# ---------------------------------------------------------------------------


def _extract_document_filter(query: str, metadata: list[dict]) -> set[int] | None:
    """Extract a document-level filter from the query.

    LegalBench-RAG queries often name the specific contract:
      "Consider the NDA between CopAcc and ToP Mentors; ..."
      "Consider EFCA's Non-Disclosure Agreement; ..."

    When the party/company name is found, restrict retrieval to chunks from
    that file. This eliminates the dominant failure mode where semantically
    similar text in OTHER contracts ranks ahead of the gold document.

    Returns a set of allowed chunk indices, or None to search all chunks.
    """
    import re

    # Pattern: "Consider X's ..." or "Consider the ... between X and Y; ..."
    m = re.match(r"Consider (?:the .+ between (.+?) and (.+?)|(.+?)'s .+?);", query, re.IGNORECASE)
    if not m:
        return None

    # Collect candidate party names
    parties = [p.strip() for p in (m.group(1), m.group(2), m.group(3)) if p]
    if not parties:
        return None

    # Find all chunks whose file path contains any party name (case-insensitive)
    allowed: set[int] = set()
    for i, entry in enumerate(metadata):
        file_lower = entry.get("file", "").lower()
        if any(p.lower() in file_lower for p in parties):
            allowed.add(i)

    # Only apply the filter if we found matching chunks
    return allowed if allowed else None


def retrieve_for_query(query: str, corpus_dir: Path) -> list[dict]:
    """Hybrid BM25 + vector retrieval over LegalBench-RAG corpus.

    Returns list of {"file": str, "start": int, "end": int, "text": str}.
    Note: No cross-encoder reranking — paper found rerankers HURT on legal text.

    Document routing: when the query names a specific contract (e.g., "Consider
    EFCA's NDA"), restrict search to chunks from that document. Without routing,
    semantically similar text from other contracts dominates the results.
    """
    from arlc.indexing.legal_tokenizer import legal_tokenize_queries

    has_faiss = FAISS_INDEX_PATH.exists()
    has_bm25 = BM25_CACHE_DIR.exists()

    if not has_faiss and not has_bm25:
        raise RuntimeError(
            "No indexes found. Run build_index.py first:\n  python benchmarks/legalbench-rag/build_index.py"
        )

    _, metadata = _load_faiss()

    # Document-level pre-filter from party names in query
    doc_filter = _extract_document_filter(query, metadata)

    # Score by chunk_id (int index into metadata)
    scores = {}  # chunk_id -> score

    # --- Vector search ---
    if has_faiss:
        index, _ = _load_faiss()
        model = _get_embedding_model()
        # Use only the question part after the semicolon for semantic search
        # (party names add noise; the legal concept is what matters for ranking)
        semantic_query = query.split(";", 1)[-1].strip() if ";" in query else query
        if _EMBEDDING_BACKEND == "llama-server":
            query_emb = np.array(model.embed_query(semantic_query), dtype="float32")
        else:
            query_emb = model.encode(semantic_query, prompt_name="query", normalize_embeddings=True)
        query_np = np.array([query_emb], dtype="float32")
        import faiss

        faiss.normalize_L2(query_np)
        k_vec = min(200, index.ntotal)
        D, I = index.search(query_np, k_vec)
        for j in range(k_vec):
            idx = int(I[0][j])
            if idx < 0:
                continue
            if doc_filter is not None and idx not in doc_filter:
                continue
            scores[idx] = float(D[0][j])

    # --- BM25 search ---
    if has_bm25:
        bm25, bm25_ids = _load_bm25()
        tokenized_q = legal_tokenize_queries(query)
        results, bm25_scores = bm25.retrieve(tokenized_q, k=200)
        for j in range(len(results[0])):
            chunk_idx = int(results[0][j])
            if chunk_idx < 0:
                continue
            if doc_filter is not None and chunk_idx not in doc_filter:
                continue
            bm25_score = float(bm25_scores[0][j])
            if chunk_idx in scores:
                scores[chunk_idx] += bm25_score * 0.3
            else:
                scores[chunk_idx] = bm25_score * 0.3

    # Sort by score, take top 10 (paper uses k=10)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]

    spans = []
    for chunk_idx, _ in ranked:
        if chunk_idx >= len(metadata):
            continue
        entry = metadata[chunk_idx]
        spans.append(
            {
                "file": entry["file"],
                "start": entry["start"],
                "end": entry["end"],
                "text": entry["text"],
            }
        )

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
        benchmarks = benchmarks[: args.limit]
        print(f"[legalbench-rag] Limited to {args.limit} queries")

    # Step 3: Run retrieval and compute metrics
    results = []
    total_p, total_r, total_f1 = 0.0, 0.0, 0.0

    for i, item in enumerate(benchmarks):
        query = item.get("query", item.get("question", ""))
        gold_snippets = item.get("snippets", item.get("ground_truth", []))

        # Normalize gold snippets to {"file", "start", "end"} format
        # LegalBench-RAG format: {"file_path": "...", "span": "[start, end]", "answer": "..."}
        gold_spans = []
        for snippet in gold_snippets:
            if isinstance(snippet, dict):
                file_path = snippet.get("file", snippet.get("file_path", ""))
                # Parse span: may be "[start, end]" string or {"start", "end"} dict
                span = snippet.get("span")
                if isinstance(span, str):
                    span = json.loads(span)
                if isinstance(span, list) and len(span) == 2:
                    gold_spans.append({"file": file_path, "start": span[0], "end": span[1]})
                else:
                    gold_spans.append(
                        {
                            "file": file_path,
                            "start": snippet.get("start", snippet.get("char_start", 0)),
                            "end": snippet.get("end", snippet.get("char_end", 0)),
                        }
                    )

        print(f"  [{i + 1}/{len(benchmarks)}] {query[:80]}...")
        predicted_spans = retrieve_for_query(query, CORPUS_DIR)
        metrics = compute_char_overlap(predicted_spans, gold_spans)

        results.append(
            {
                "query": query,
                "num_predicted": len(predicted_spans),
                "num_gold": len(gold_spans),
                **metrics,
            }
        )
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
