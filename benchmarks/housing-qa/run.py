#!/usr/bin/env python3
"""Housing QA evaluation harness.

Tests hybrid retrieval + LLM answering on 6,853 questions about US state
housing law statutes across 50+ jurisdictions.

Source: reglab/housing_qa (Stanford RegLab, ACL/CS+Law 2025)
Paper: "A Reasoning-Focused Legal Retrieval Benchmark"

Corpus: 1,837,403 US state statute rows — requires RTX 3070 GPU for
        efficient Qwen3-8B embedding indexing (~6-8 hours, one-time).

Metrics:
  - Retrieval hit@10: gold statute in top-10 retrieved?
  - Answer accuracy: does LLM answer match gold?

Usage:
    # Step 1: Build index (requires 3070 for practical speed):
    LLAMA_SERVER_URL=http://100.98.171.97:8088 python benchmarks/housing-qa/run.py --build-index

    # Step 2: Evaluate:
    python benchmarks/housing-qa/run.py [--limit N] [--workers N]
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = BENCH_DIR / "data"
INDEX_DIR = DATA_DIR / "index"
RESULTS_PATH = BENCH_DIR / "results.json"
MODEL = os.environ.get("HOUSINGQA_MODEL", "claude-sonnet-4-6")

csv.field_size_limit(2**31 - 1)

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


def download_data():
    """Download Housing QA data from HuggingFace."""
    from huggingface_hub import hf_hub_download

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Questions
    q_local = DATA_DIR / "questions.json"
    if not q_local.exists():
        print("[housing-qa] Downloading questions...")
        cached = hf_hub_download("reglab/housing_qa", "data/questions.json.zip", repo_type="dataset")
        with zipfile.ZipFile(cached) as z:
            with z.open(z.namelist()[0]) as f:
                data = json.load(f)
        with open(q_local, "w") as f:
            json.dump(data, f)
        print(f"[housing-qa] Saved {len(data)} questions")

    # Statutes corpus
    statutes_local = DATA_DIR / "statutes.tsv"
    if not statutes_local.exists():
        print("[housing-qa] Downloading statutes corpus (large file)...")
        cached = hf_hub_download("reglab/housing_qa", "data/statutes.tsv.zip", repo_type="dataset")
        with zipfile.ZipFile(cached) as z:
            with z.open(z.namelist()[0]) as f:
                content = f.read()
        with open(statutes_local, "wb") as f:
            f.write(content)
        print(f"[housing-qa] Statutes saved ({len(content) / 1e6:.1f} MB)")


def load_questions() -> list[dict]:
    with open(DATA_DIR / "questions.json") as f:
        return json.load(f)


def load_statutes() -> list[dict]:
    """Load statutes corpus into memory. ~1.8M rows, needs significant RAM."""
    rows = []
    print("[housing-qa] Loading statutes corpus...")
    t0 = time.time()
    with open(DATA_DIR / "statutes.tsv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
            if len(rows) % 100000 == 0:
                print(f"  [{len(rows):,}] rows loaded...")
    print(f"[housing-qa] Loaded {len(rows):,} statutes in {time.time()-t0:.1f}s")
    return rows


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------


def build_index(statutes: list[dict]):
    """Build FAISS + BM25 index. Requires GPU (RTX 3070) for practical speed.

    ~1.8M statutes × 4096-dim embedding = ~28GB RAM for index, ~6-8h on 3070.
    """
    import bm25s
    import faiss

    from arlc.indexing.legal_tokenizer import legal_tokenize_corpus
    from neolex.embeddings.llama_embedder import LlamaServerEmbedder

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    texts = [s["text"] for s in statutes]
    ids = [s["idx"] for s in statutes]
    n = len(statutes)

    print(f"[housing-qa] Building index for {n:,} statutes...")

    # BM25 (fast)
    print("[housing-qa] Building BM25 index...")
    t_bm25 = time.time()
    tokenized = legal_tokenize_corpus(texts)
    bm25 = bm25s.BM25()
    bm25.index(tokenized)
    bm25_dir = INDEX_DIR / "bm25_cache"
    bm25_dir.mkdir(parents=True, exist_ok=True)
    bm25.save(str(bm25_dir))
    with open(bm25_dir / "corpus_ids.json", "w") as f:
        json.dump(ids, f)
    print(f"[housing-qa] BM25 done: {time.time()-t_bm25:.1f}s")

    # FAISS via llama-server (3070 recommended)
    embedder_url = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8088")
    print(f"[housing-qa] Embedding {n:,} statutes via {embedder_url}...")
    print(f"  Note: At 100ms/text this would take {n * 0.1 / 3600:.1f}h. Use RTX 3070 for ~10ms/text.")

    embedder = LlamaServerEmbedder()

    t0 = time.time()
    batch_size = 64
    all_embeddings = []
    # Save metadata incrementally (in case of crash)
    metadata = [{"idx": s["idx"], "citation": s.get("citation", ""), "state": s.get("state", ""), "text": s["text"][:500]} for s in statutes]

    for i in range(0, n, batch_size):
        batch = texts[i : i + batch_size]
        embs = embedder.embed_texts(batch)
        all_embeddings.extend(embs)
        if (i // batch_size) % 100 == 0:
            elapsed = time.time() - t0
            pct = (i + len(batch)) / n
            eta = elapsed / pct * (1 - pct) if pct > 0 else 0
            print(f"  [{i + len(batch):,}/{n:,}] {elapsed:.0f}s, ETA {eta/3600:.1f}h")

    embed_time = time.time() - t0
    print(f"[housing-qa] Embedding done: {embed_time/3600:.1f}h")

    embeddings_np = np.array(all_embeddings, dtype=np.float32)
    dim = embeddings_np.shape[1]
    print(f"[housing-qa] Building FAISS IndexFlatIP (dim={dim}, n={n:,})...")
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings_np)
    index.add(embeddings_np)
    faiss.write_index(index, str(INDEX_DIR / "faiss_index.bin"))
    with open(INDEX_DIR / "faiss_metadata.json", "w") as f:
        json.dump(metadata, f)
    print(f"[housing-qa] FAISS saved: {index.ntotal:,} vectors")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

_faiss_index = None
_faiss_metadata = None
_faiss_metadata_dict = None
_bm25_index = None
_bm25_ids = None
_embedder = None


_BM25_ONLY = not (INDEX_DIR / "faiss_index.bin").exists()
_STATE_POSITIONS: dict | None = None


def _get_state_positions() -> dict:
    global _STATE_POSITIONS
    if _STATE_POSITIONS is None:
        p = INDEX_DIR / "state_to_positions.json"
        if p.exists():
            with open(p) as f:
                _STATE_POSITIONS = json.load(f)
        else:
            _STATE_POSITIONS = {}
    return _STATE_POSITIONS


def _load_indexes():
    global _faiss_index, _faiss_metadata, _faiss_metadata_dict, _bm25_index, _bm25_ids, _embedder
    if _bm25_index is None:
        import bm25s

        print("[housing-qa] Loading BM25 index...")
        bm25_dir = INDEX_DIR / "bm25_cache"
        _bm25_index = bm25s.BM25.load(str(bm25_dir))
        with open(bm25_dir / "corpus_ids.json") as f:
            _bm25_ids = json.load(f)
        print(f"[housing-qa] BM25 ready: {len(_bm25_ids):,} docs")

        if not _BM25_ONLY:
            import faiss

            _faiss_index = faiss.read_index(str(INDEX_DIR / "faiss_index.bin"))
            with open(INDEX_DIR / "faiss_metadata.json") as f:
                _faiss_metadata = json.load(f)
            _faiss_metadata_dict = {e["idx"]: e for e in _faiss_metadata}

            from neolex.embeddings.llama_embedder import LlamaServerEmbedder

            _embedder = LlamaServerEmbedder()
            print(f"[housing-qa] FAISS ready: {_faiss_index.ntotal:,} vectors")
        else:
            print("[housing-qa] Running BM25-only mode (FAISS index not built)")


def retrieve(query: str, state: str = "", top_k: int = 10) -> list[dict]:
    """Hybrid BM25 + vector retrieval, optionally filtered to a state.

    Falls back to BM25-only if FAISS index is not built (corpus too large to embed).
    """
    from arlc.indexing.legal_tokenizer import legal_tokenize_queries

    _load_indexes()

    # State-filtered BM25 positions (dramatically narrows 1.8M → ~36K per state)
    bm25_allowed_positions: set | None = None
    if state:
        state_pos = _get_state_positions()
        positions = state_pos.get(state.lower(), [])
        if positions:
            bm25_allowed_positions = set(positions)

    # Vector search (only if FAISS index is available)
    vec_scores = {}
    if not _BM25_ONLY:
        import faiss

        state_lower = state.lower() if state else ""
        state_indices = (
            {i for i, m in enumerate(_faiss_metadata) if m.get("state", "").lower() == state_lower}
            if state
            else None
        )
        query_emb = np.array(_embedder.embed_query(query), dtype=np.float32).reshape(1, -1)
        faiss.normalize_L2(query_emb)
        k_vec = min(500, _faiss_index.ntotal)
        D, I = _faiss_index.search(query_emb, k_vec)
        for j in range(k_vec):
            idx = int(I[0][j])
            if idx < 0 or (state_indices is not None and idx not in state_indices):
                continue
            pid = _faiss_metadata[idx]["idx"]
            vec_scores[pid] = float(D[0][j])

    # BM25 search
    tokenized_q = legal_tokenize_queries(query)
    results, _ = _bm25_index.retrieve(tokenized_q, k=500)
    bm25_rank = {}
    for j in range(len(results[0])):
        doc_idx = int(results[0][j])
        if doc_idx < 0 or doc_idx >= len(_bm25_ids):
            continue
        if bm25_allowed_positions is not None and doc_idx not in bm25_allowed_positions:
            continue
        pid = _bm25_ids[doc_idx]
        if pid not in bm25_rank:
            bm25_rank[pid] = j + 1

    # RRF fusion (BM25 only if no FAISS)
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
    meta = _faiss_metadata_dict or {}
    return [{"idx": pid, "score": score, "text": meta.get(pid, {}).get("text", "")[:500]} for pid, score in ranked]


# ---------------------------------------------------------------------------
# LLM answering
# ---------------------------------------------------------------------------

QA_SYSTEM = """You are a legal expert specializing in US housing and landlord-tenant law.

Answer the question based on the provided statute excerpts. Be concise and precise.
If the statutes don't contain the answer, state that explicitly."""


async def answer_question(question: str, retrieved: list[dict], sem: asyncio.Semaphore) -> str:
    context = "\n\n".join([f"[{i+1}] {r['text']}" for i, r in enumerate(retrieved[:5])])
    user_prompt = f"Relevant statutes:\n{context}\n\nQuestion: {question}\n\nAnswer:"

    async with sem:
        try:
            if _use_litellm:
                from arlc.llm import litellm_backend

                text, *_ = await asyncio.to_thread(litellm_backend.call_llm, QA_SYSTEM, user_prompt, 256, MODEL)
                return text
            client = get_client()
            resp = client.messages.create(
                model=MODEL, max_tokens=256, temperature=0.0,
                system=QA_SYSTEM, messages=[{"role": "user", "content": user_prompt}]
            )
            return resp.content[0].text
        except Exception as e:
            print(f"  [ERROR] {e}")
            return ""


def answer_matches_gold(predicted: str, gold: str) -> bool:
    """Simple overlap check for answer accuracy."""
    p = predicted.lower().strip()
    g = gold.lower().strip()
    if g in p or p in g:
        return True
    # Check for yes/no agreement
    if g in ("yes", "no") and g in p[:20]:
        return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Housing QA evaluation")
    parser.add_argument("--build-index", action="store_true", help="Build FAISS+BM25 index (requires 3070)")
    parser.add_argument("--limit", type=int, default=0, help="Limit questions (0=all)")
    parser.add_argument("--workers", type=int, default=5, help="LLM workers")
    parser.add_argument("--retrieval-only", action="store_true", help="Skip LLM answering")
    args = parser.parse_args()

    get_client()
    download_data()

    if args.build_index:
        statutes = load_statutes()
        build_index(statutes)
        if args.retrieval_only and not args.limit:
            return

    bm25_cache = INDEX_DIR / "bm25_cache" / "corpus_ids.json"
    if not (INDEX_DIR / "faiss_index.bin").exists():
        if bm25_cache.exists():
            print("[housing-qa] FAISS index not found — running in BM25-only mode.")
            print("  (FAISS requires RTX 3070 + ~666h embedding time for 1.8M statutes)")
        else:
            print("[housing-qa] ERROR: No index found. Run --build-index first.")
            sys.exit(1)

    # Load questions
    questions = load_questions()
    if args.limit > 0:
        questions = questions[: args.limit]

    print(f"[housing-qa] Evaluating {len(questions)} questions...")
    results = []
    total_hits = 0
    total_correct = 0
    t0 = time.time()
    sem = asyncio.Semaphore(args.workers)
    answer_tasks = []

    for i, q in enumerate(questions):
        question = q["question"]
        state = q.get("state", "")
        gold_statutes = q.get("statutes", [])
        gold_ids = {str(s["statute_idx"]) for s in gold_statutes}

        retrieved = retrieve(question, state=state, top_k=10)
        retrieved_ids = {r["idx"] for r in retrieved}
        hit = bool(retrieved_ids & gold_ids)
        total_hits += int(hit)

        results.append({
            "idx": q.get("idx", ""),
            "state": state,
            "gold_ids": list(gold_ids),
            "retrieved_ids": list(retrieved_ids)[:5],
            "retrieval_hit": hit,
            "answer_correct": None,
        })
        answer_tasks.append((i, question, q.get("answer", ""), retrieved))

        if (i + 1) % 100 == 0:
            print(f"  [retrieval {i+1}/{len(questions)}] hit@10={total_hits/(i+1):.3f}")

    retrieval_acc = total_hits / len(results) if results else 0
    print(f"\n[housing-qa] Retrieval hit@10: {retrieval_acc:.4f} ({total_hits}/{len(results)})")

    if not args.retrieval_only:

        async def run_answers():
            tasks = [answer_question(question, retrieved, sem) for _, question, _, retrieved in answer_tasks]
            return await asyncio.gather(*tasks)

        responses = asyncio.run(run_answers())
        for i, response in enumerate(responses):
            gold_answer = answer_tasks[i][2]
            correct = answer_matches_gold(response, gold_answer)
            results[i]["predicted"] = response[:200]
            results[i]["answer_correct"] = correct
            total_correct += int(correct)

        ans_acc = total_correct / len(results) if results else 0
        print(f"[housing-qa] Answer accuracy: {ans_acc:.4f} ({total_correct}/{len(results)})")

    elapsed = time.time() - t0
    aggregate = {
        "num_questions": len(results),
        "retrieval_hit_at_10": retrieval_acc,
        "answer_accuracy": total_correct / len(results) if results and not args.retrieval_only else None,
        "elapsed_seconds": elapsed,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump({"aggregate": aggregate, "per_query": results}, f, indent=2)
    print(f"\n[housing-qa] Results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
