#!/usr/bin/env python3
"""Bar Exam QA evaluation harness.

Tests hybrid retrieval + LLM answering on 1,195 US Multistate Bar Exam (MBE)
questions with gold passage annotations from US caselaw.

Source: reglab/barexam_qa (Stanford RegLab, ACL/CS+Law 2025)
Paper: "A Reasoning-Focused Legal Retrieval Benchmark"

Metrics:
  - Retrieval hit@10: is the gold passage in the top-10 retrieved?
  - MCQ accuracy: does the LLM answer A/B/C/D correctly?

Usage:
    # First build the index (one-time, ~60 min on local llama-server):
    python benchmarks/barexam-qa/run.py --build-index

    # Then run evaluation:
    python benchmarks/barexam-qa/run.py [--split test|all] [--limit N]
"""

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = BENCH_DIR / "data"
INDEX_DIR = DATA_DIR / "index"
PASSAGES_DIR = DATA_DIR / "passages"
QA_DIR = DATA_DIR / "qa"
RESULTS_PATH = BENCH_DIR / "results.json"

MODEL = os.environ.get("BAREXAM_MODEL", "claude-sonnet-4-6")

_client = None
_use_litellm = False


def get_client():
    global _client, _use_litellm
    if _client is None and not _use_litellm:
        import anthropic

        backend = os.environ.get("LLM_BACKEND", "litellm").lower()
        if backend == "litellm":
            from arlc.llm import litellm_backend

            if litellm_backend.is_configured():
                _use_litellm = True
                return None
        if backend == "vertex" or (backend == "auto" and os.environ.get("VERTEX_PROJECT_ID")):
            from anthropic import AnthropicVertex

            _client = AnthropicVertex(
                project_id=os.environ["VERTEX_PROJECT_ID"],
                region=os.environ.get("VERTEX_LOCATION", "us-east5"),
            )
        elif backend != "litellm":
            _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), timeout=120.0)
    return _client


# ---------------------------------------------------------------------------
# Data download
# ---------------------------------------------------------------------------

csv.field_size_limit(2**31 - 1)


def download_data():
    """Download passages and QA data from HuggingFace."""
    from huggingface_hub import hf_hub_download

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "data/passages/test.tsv": PASSAGES_DIR / "test.tsv",
        "data/passages/passages.tsv": PASSAGES_DIR / "passages.tsv",
        "data/qa/test.csv": QA_DIR / "test.csv",
        "data/qa/qa.csv": QA_DIR / "qa.csv",
    }

    for hf_path, local_path in files.items():
        if local_path.exists():
            print(f"[barexam] Already have {local_path.name}")
            continue
        print(f"[barexam] Downloading {hf_path}...")
        try:
            cached = hf_hub_download("reglab/barexam_qa", hf_path, repo_type="dataset")
            import shutil

            shutil.copy2(cached, local_path)
            print(f"[barexam] -> {local_path.name}")
        except Exception as e:
            print(f"[barexam] Warning: could not download {hf_path}: {e}")


def load_passages(use_test_split: bool = True) -> tuple[list[dict], dict]:
    """Load passages corpus. Returns (rows, id_to_row)."""
    # Prefer test-split passages (85K) over full corpus (856K)
    path = PASSAGES_DIR / ("test.tsv" if use_test_split else "passages.tsv")
    if not path.exists():
        path = PASSAGES_DIR / "passages.tsv"
    if not path.exists():
        raise FileNotFoundError(f"Passages not found at {path}. Run --build-index first.")

    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)

    id_to_row = {r["idx"]: r for r in rows}
    print(f"[barexam] Loaded {len(rows)} passages from {path.name}")
    return rows, id_to_row


def load_qa(split: str = "test") -> list[dict]:
    """Load QA pairs."""
    fname = "test.csv" if split == "test" else "qa.csv"
    path = QA_DIR / fname
    if not path.exists():
        raise FileNotFoundError(f"QA data not found at {path}. Run --build-index first.")

    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"[barexam] Loaded {len(rows)} QA items from {fname}")
    return rows


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------


def build_index(passages: list[dict]):
    """Build FAISS + BM25 indexes from passages using llama-server embeddings."""
    import bm25s
    import faiss

    from arlc.indexing.legal_tokenizer import legal_tokenize_corpus
    from neolex.embeddings.llama_embedder import LlamaServerEmbedder

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    texts = [p["text"] for p in passages]
    ids = [p["idx"] for p in passages]
    n = len(passages)

    print(f"[barexam] Building index for {n} passages...")

    # BM25 (fast, no GPU needed)
    print("[barexam] Building BM25 index...")
    tokenized = legal_tokenize_corpus(texts)
    bm25 = bm25s.BM25()
    bm25.index(tokenized)
    bm25_dir = INDEX_DIR / "bm25_cache"
    bm25_dir.mkdir(parents=True, exist_ok=True)
    bm25.save(str(bm25_dir))
    with open(bm25_dir / "corpus_ids.json", "w") as f:
        json.dump(ids, f)
    print(f"[barexam] BM25 saved: {n} docs")

    # FAISS with llama-server embeddings (Qwen3-8B)
    print("[barexam] Embedding passages with llama-server (Qwen3-8B)...")
    embedder = LlamaServerEmbedder()

    t0 = time.time()
    batch_size = 64
    all_embeddings = []
    for i in range(0, n, batch_size):
        batch = texts[i : i + batch_size]
        embs = embedder.embed_texts(batch)
        all_embeddings.extend(embs)
        if (i // batch_size) % 20 == 0:
            elapsed = time.time() - t0
            progress = (i + len(batch)) / n
            eta = elapsed / progress * (1 - progress) if progress > 0 else 0
            print(f"  [{i + len(batch)}/{n}] {elapsed:.0f}s elapsed, ETA {eta:.0f}s")

    embed_time = time.time() - t0
    print(f"[barexam] Embedding done: {embed_time:.1f}s ({embed_time / n * 1000:.1f}ms/passage)")

    embeddings_np = np.array(all_embeddings, dtype=np.float32)
    dim = embeddings_np.shape[1]
    print(f"[barexam] Building FAISS IndexFlatIP (dim={dim}, n={n})...")
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings_np)
    index.add(embeddings_np)
    faiss.write_index(index, str(INDEX_DIR / "faiss_index.bin"))

    # Save metadata
    metadata = [{"idx": p["idx"], "text": p["text"][:1000], "source": p.get("source", "")} for p in passages]
    with open(INDEX_DIR / "faiss_metadata.json", "w") as f:
        json.dump(metadata, f)

    print(f"[barexam] FAISS saved: {index.ntotal} vectors, dim={dim}")
    return embed_time


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

_faiss_index = None
_faiss_metadata = None
_faiss_metadata_dict = None
_bm25_index = None
_bm25_ids = None
_embedder = None


def _load_indexes():
    global _faiss_index, _faiss_metadata, _faiss_metadata_dict, _bm25_index, _bm25_ids, _embedder
    if _faiss_index is None:
        import bm25s
        import faiss

        _faiss_index = faiss.read_index(str(INDEX_DIR / "faiss_index.bin"))
        with open(INDEX_DIR / "faiss_metadata.json") as f:
            _faiss_metadata = json.load(f)
        _faiss_metadata_dict = {e["idx"]: e for e in _faiss_metadata}

        bm25_dir = INDEX_DIR / "bm25_cache"
        _bm25_index = bm25s.BM25.load(str(bm25_dir))
        with open(bm25_dir / "corpus_ids.json") as f:
            _bm25_ids = json.load(f)

        from neolex.embeddings.llama_embedder import LlamaServerEmbedder

        _embedder = LlamaServerEmbedder()
        print(f"[barexam] Indexes loaded: {_faiss_index.ntotal} vectors, {len(_bm25_ids)} BM25 docs")


def retrieve(query: str, top_k: int = 10) -> list[dict]:
    """Hybrid BM25 + vector retrieval."""
    import faiss

    from arlc.indexing.legal_tokenizer import legal_tokenize_queries

    _load_indexes()

    # Vector search
    query_emb = np.array(_embedder.embed_query(query), dtype=np.float32).reshape(1, -1)
    faiss.normalize_L2(query_emb)
    k_vec = min(200, _faiss_index.ntotal)
    D, I = _faiss_index.search(query_emb, k_vec)

    vec_scores = {}
    for j in range(k_vec):
        idx = int(I[0][j])
        if idx < 0:
            continue
        pid = _faiss_metadata[idx]["idx"]
        vec_scores[pid] = float(D[0][j])

    # BM25 search
    tokenized_q = legal_tokenize_queries(query)
    results, scores = _bm25_index.retrieve(tokenized_q, k=200)
    bm25_rank = {}
    for j in range(len(results[0])):
        doc_idx = int(results[0][j])
        if doc_idx < 0 or doc_idx >= len(_bm25_ids):
            continue
        pid = _bm25_ids[doc_idx]
        if pid not in bm25_rank:
            bm25_rank[pid] = j + 1

    # RRF fusion
    RRF_K = 60
    all_pids = set(vec_scores) | set(bm25_rank)
    fused = {}
    for pid in all_pids:
        score = 0.0
        if pid in vec_scores:
            score += vec_scores[pid]
        if pid in bm25_rank:
            score += 1.0 / (RRF_K + bm25_rank[pid])
        fused[pid] = score

    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"idx": pid, "score": score, "text": _faiss_metadata_dict.get(pid, {}).get("text", "")[:500]} for pid, score in ranked]


# ---------------------------------------------------------------------------
# LLM answering
# ---------------------------------------------------------------------------

MCQ_SYSTEM = """You are a bar exam expert. Answer multiple-choice questions based on the provided legal passages.

After reasoning, output your answer on the LAST LINE as exactly one letter: A, B, C, or D."""


async def answer_mcq(item: dict, retrieved: list[dict], sem: asyncio.Semaphore) -> str:
    """Answer MCQ question using retrieved passages."""
    prompt = item.get("prompt", "") + "\n" + item.get("question", "")
    choices = "\n".join(
        [
            f"A. {item.get('choice_a', '')}",
            f"B. {item.get('choice_b', '')}",
            f"C. {item.get('choice_c', '')}",
            f"D. {item.get('choice_d', '')}",
        ]
    )

    context = "\n\n".join([f"[P{i+1}] {r['text']}" for i, r in enumerate(retrieved[:5])])
    user_prompt = f"Relevant passages:\n{context}\n\nQuestion: {prompt}\n\n{choices}\n\nSelect A, B, C, or D."

    async with sem:
        try:
            if _use_litellm:
                from arlc.llm import litellm_backend

                text, *_ = await asyncio.to_thread(litellm_backend.call_llm, MCQ_SYSTEM, user_prompt, 256, MODEL)
                return text
            client = get_client()
            resp = client.messages.create(
                model=MODEL,
                max_tokens=256,
                temperature=0.0,
                system=MCQ_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return resp.content[0].text
        except Exception as e:
            print(f"  [ERROR] {e}")
            return ""


def parse_mcq_letter(response: str) -> str:
    for line in reversed(response.strip().split("\n")):
        line = line.strip().strip('"').strip("*").strip("'")
        if line in ("A", "B", "C", "D"):
            return line
    for c in reversed(response):
        if c in "ABCD":
            return c
    return "?"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Bar Exam QA evaluation")
    parser.add_argument("--build-index", action="store_true", help="Build FAISS+BM25 index from passages")
    parser.add_argument("--split", default="test", choices=["test", "all"], help="QA split to evaluate")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of questions (0=all)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent LLM workers")
    parser.add_argument("--retrieval-only", action="store_true", help="Skip LLM answering, report retrieval only")
    args = parser.parse_args()

    get_client()

    # Step 1: Download data
    download_data()

    # Step 2: Build index if requested
    use_test_split = True  # always prefer smaller test-split corpus
    if args.build_index:
        passages, _ = load_passages(use_test_split)
        build_index(passages)
        if args.retrieval_only and not args.limit:
            return

    # Verify index exists
    if not (INDEX_DIR / "faiss_index.bin").exists() or not (INDEX_DIR / "bm25_cache").exists():
        print("[barexam] ERROR: Index not built. Run with --build-index first.")
        sys.exit(1)

    # Step 3: Load QA data
    qa_items = load_qa(args.split)
    if args.limit > 0:
        qa_items = qa_items[: args.limit]

    # Step 4: Retrieve + evaluate
    results = []
    total_hits = 0
    total_correct = 0
    t0 = time.time()

    sem = asyncio.Semaphore(args.workers)
    answer_tasks = []

    for i, item in enumerate(qa_items):
        question = (item.get("prompt", "") + " " + item.get("question", "")).strip()
        gold_idx = item.get("gold_idx", "")

        retrieved = retrieve(question, top_k=10)
        retrieved_ids = [r["idx"] for r in retrieved]
        hit = gold_idx in retrieved_ids

        total_hits += int(hit)
        result = {
            "idx": item.get("idx", ""),
            "subject": item.get("subject", ""),
            "gold_idx": gold_idx,
            "retrieved_ids": retrieved_ids[:5],
            "retrieval_hit": hit,
            "answer_correct": None,
        }
        results.append(result)
        answer_tasks.append((i, item, retrieved))

        if (i + 1) % 20 == 0:
            print(f"  [retrieval {i+1}/{len(qa_items)}] hit@10={total_hits/(i+1):.3f}")

    retrieval_acc = total_hits / len(results) if results else 0
    print(f"\n[barexam] Retrieval hit@10: {retrieval_acc:.4f} ({total_hits}/{len(results)})")

    if not args.retrieval_only:
        print("[barexam] Running LLM answering...")

        async def run_answers():
            tasks = [answer_mcq(item, retrieved, sem) for _, item, retrieved in answer_tasks]
            return await asyncio.gather(*tasks)

        responses = asyncio.run(run_answers())

        for i, response in enumerate(responses):
            predicted = parse_mcq_letter(response)
            gold_letter = results[i]["gold_idx"]  # Note: gold is the letter in qa.csv's 'answer' field
            gold_letter = qa_items[i].get("answer", "?").upper()
            correct = predicted == gold_letter
            results[i]["predicted"] = predicted
            results[i]["gold_letter"] = gold_letter
            results[i]["answer_correct"] = correct
            total_correct += int(correct)

        mcq_acc = total_correct / len(results) if results else 0
        print(f"[barexam] MCQ accuracy: {mcq_acc:.4f} ({total_correct}/{len(results)})")
        print(f"\n[barexam] Comparison vs published:")
        print(f"  GPT-4 bar exam pass: ~66.5% (uniform passing threshold)")
        print(f"  This system:         {mcq_acc*100:.1f}% MCQ on {len(results)} MBE questions")

    elapsed = time.time() - t0
    aggregate = {
        "num_questions": len(results),
        "retrieval_hit_at_10": retrieval_acc,
        "mcq_accuracy": total_correct / len(results) if results and not args.retrieval_only else None,
        "elapsed_seconds": elapsed,
    }
    output = {"aggregate": aggregate, "per_query": results}

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n[barexam] Results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
