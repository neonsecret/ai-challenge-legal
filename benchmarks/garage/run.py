#!/usr/bin/env python3
"""GaRAGe evaluation harness.

Tests passage-level grounding accuracy on 2,366 questions with 35K+ annotated
passages from the GaRAGe benchmark (Amazon Science).

Metrics:
  - RAF (Relevance-Aware Factuality): factuality weighted by passage relevance
  - Deflection: TPR/FPR for abstaining when no passage is relevant
  - Attribution F1: per-passage grounding accuracy

Usage:
    python benchmarks/garage/run.py [--dry-run] [--limit N] [--workers N]
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
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

DATASET_URL = "https://raw.githubusercontent.com/amazon-science/GaRAGe/main/GaRAGe_benchmark.jsonl"
REPO_URL = "https://github.com/amazon-science/GaRAGe.git"

# Model config
MODEL = os.environ.get("GARAGE_MODEL", "claude-sonnet-4-6")

# ---------------------------------------------------------------------------
# Anthropic client (reuses pipeline's backend logic)
# ---------------------------------------------------------------------------

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
            _client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                timeout=120.0,
            )
    return _client


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
            for f in clone_dir.rglob("*.jsonl"):
                import shutil
                shutil.copy2(f, DATASET_PATH)
                break
            else:
                print(f"[garage] ERROR: Could not find dataset.")
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
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a precise question-answering system. You answer questions based ONLY on the provided passages.

Rules:
1. For EVERY factual claim in your answer, you MUST cite ALL passage(s) that support it using [P1], [P2], etc. Cite generously — if a passage contains supporting information, cite it.
2. CRITICAL: If NONE of the passages contain information relevant to answering the question, you MUST respond EXACTLY with: "I cannot answer based on the provided passages." Do NOT attempt to answer from general knowledge.
3. Be concise and factual. Do not add information beyond what the passages state.
4. Multiple passages may support the same claim — cite ALL of them.
5. Before answering, mentally check: does ANY passage actually address this question? If not, deflect."""


def extract_passage_text(passage, index: int) -> str:
    """Extract text from a GaRAGe passage dict.

    Each passage is a dict with keys: age, date, provider, cite_N
    where N is the 1-indexed passage number.
    """
    if isinstance(passage, str):
        return passage
    if isinstance(passage, dict):
        # Try cite_N key first (the actual passage text)
        cite_key = f"cite_{index + 1}"
        if cite_key in passage:
            return str(passage[cite_key]).strip()
        # Fallback: try any cite_ key
        for k, v in passage.items():
            if k.startswith("cite_"):
                return str(v).strip()
        # Last resort
        return str(passage)
    return str(passage)


def build_user_prompt(question: str, passages: list) -> str:
    """Build the user prompt with numbered passages."""
    parts = ["Here are the passages:\n"]
    for i, passage in enumerate(passages):
        text = extract_passage_text(passage, i)
        parts.append(f"[P{i + 1}] {text}\n")
    parts.append(f"\nQuestion: {question}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

async def call_llm(question: str, passages: list) -> str:
    """Call Claude to answer a question given passages."""
    user_prompt = build_user_prompt(question, passages)

    try:
        if _use_litellm:
            import asyncio
            from arlc.llm import litellm_backend
            text, *_ = await asyncio.to_thread(
                litellm_backend.call_llm, SYSTEM_PROMPT, user_prompt, 512, MODEL)
            return text
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"  [ERROR] LLM call failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_citations(response: str, num_passages: int) -> set[int]:
    """Extract cited passage indices from the response (0-indexed)."""
    # Match [P1], [P2], etc.
    cited = set()
    for m in re.finditer(r'\[P(\d+)\]', response):
        idx = int(m.group(1)) - 1  # convert to 0-indexed
        if 0 <= idx < num_passages:
            cited.add(idx)
    return cited


def is_deflection(response: str) -> bool:
    """Check if the response is a deflection (refusing to answer)."""
    deflection_patterns = [
        "i cannot answer based on the provided passages",
        "cannot answer based on the provided",
        "none of the passages",
        "no passage contains",
        "passages do not contain",
        "passages don't contain",
        "not mentioned in any",
        "no relevant information",
        "cannot be answered",
    ]
    lower = response.lower().strip()
    return any(p in lower for p in deflection_patterns)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_attribution_metrics(
        cited_passages: set[int],
        gold_relevant: list[bool],
) -> dict:
    """Compute attribution precision, recall, F1."""
    gold_set = {i for i, r in enumerate(gold_relevant) if r}

    if not gold_set and not cited_passages:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    tp = len(cited_passages & gold_set)
    fp = len(cited_passages - gold_set)
    fn = len(gold_set - cited_passages)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def compute_raf_score(
        response: str,
        cited_passages: set[int],
        gold_relevant: list[bool],
        deflected: bool,
) -> float:
    """Compute Relevance-Aware Factuality score for a single item.

    RAF combines:
    - Eligibility: did the model cite at least one relevant passage?
    - Factuality: are the cited passages actually relevant?

    If no passages are relevant and model deflects → perfect score.
    If no passages are relevant and model answers → 0.
    If passages are relevant and model deflects → 0.
    """
    has_relevant = any(gold_relevant)

    if not has_relevant:
        # No relevant passages exist
        return 1.0 if deflected else 0.0

    if deflected:
        # Model deflected but there ARE relevant passages
        return 0.0

    if not cited_passages:
        # Model answered but cited nothing
        return 0.0

    # Factuality: fraction of cited passages that are actually relevant
    gold_set = {i for i, r in enumerate(gold_relevant) if r}
    correct_citations = len(cited_passages & gold_set)
    factuality = correct_citations / len(cited_passages) if cited_passages else 0.0

    # Eligibility: did the model cite at least one relevant passage?
    eligibility = 1.0 if (cited_passages & gold_set) else 0.0

    return eligibility * factuality


# ---------------------------------------------------------------------------
# Evaluate single item
# ---------------------------------------------------------------------------

async def evaluate_item(item: dict, sem: asyncio.Semaphore) -> dict:
    """Evaluate our pipeline on a single GaRAGe item."""
    question = item.get("question", "")
    passages = item.get("grounding", [])
    evidence_relevant = item.get("evidence_relevant", [])

    if not question or not passages:
        return {"skipped": True}

    # Parse gold relevance labels
    gold_relevant = []
    for label in evidence_relevant:
        if isinstance(label, str):
            gold_relevant.append(label.upper() == "YES")
        else:
            gold_relevant.append(bool(label))

    # Pad if needed
    while len(gold_relevant) < len(passages):
        gold_relevant.append(False)

    async with sem:
        response = await call_llm(question, passages)

    # Parse response
    deflected = is_deflection(response)
    cited = parse_citations(response, len(passages))

    # Compute metrics
    attribution = compute_attribution_metrics(cited, gold_relevant)
    raf = compute_raf_score(response, cited, gold_relevant, deflected)

    has_relevant = any(gold_relevant)

    return {
        "question": question[:100],
        "num_passages": len(passages),
        "num_gold_relevant": sum(gold_relevant),
        "has_relevant": has_relevant,
        "deflected": deflected,
        "num_cited": len(cited),
        "raf": raf,
        "attribution_precision": attribution["precision"],
        "attribution_recall": attribution["recall"],
        "attribution_f1": attribution["f1"],
        "answer_preview": response[:200],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GaRAGe evaluation")
    parser.add_argument("--dry-run", action="store_true", help="Download data only")
    parser.add_argument("--limit", type=int, default=0, help="Limit queries (0=all)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers")
    args = parser.parse_args()

    # Initialize LLM backend (sets _use_litellm flag)
    get_client()

    # Step 1: Download
    download_dataset()

    # Step 2: Load
    items = load_dataset()
    print(f"[garage] Loaded {len(items)} items")

    if args.dry_run:
        if items:
            sample = items[0]
            print(f"[garage] Sample item keys: {list(sample.keys())}")
            print(f"[garage] Sample question: {sample.get('question', '')[:100]}")
            grounding = sample.get("grounding", [])
            print(f"[garage] Sample grounding count: {len(grounding)}")
            if grounding:
                print(f"[garage] Sample passage type: {type(grounding[0])}")
                if isinstance(grounding[0], dict):
                    print(f"[garage] Sample passage keys: {list(grounding[0].keys())}")
            ev_rel = sample.get("evidence_relevant", [])
            print(f"[garage] Sample evidence_relevant: {ev_rel[:5]}")
        print("[garage] Dry run complete.")
        return

    if args.limit > 0:
        items = items[:args.limit]
        print(f"[garage] Limited to {args.limit} items")

    # Step 3: Evaluate with concurrency
    sem = asyncio.Semaphore(args.workers)

    async def run_all():
        tasks = [evaluate_item(item, sem) for item in items]
        return await asyncio.gather(*tasks)

    t0 = time.time()
    results_raw = asyncio.run(run_all())
    elapsed = time.time() - t0

    # Filter skipped
    results = [r for r in results_raw if not r.get("skipped")]
    evaluated = len(results)

    if not evaluated:
        print("[garage] No items evaluated!")
        return

    # Aggregate metrics
    avg_raf = sum(r["raf"] for r in results) / evaluated
    avg_attr_p = sum(r["attribution_precision"] for r in results) / evaluated
    avg_attr_r = sum(r["attribution_recall"] for r in results) / evaluated
    avg_attr_f1 = sum(r["attribution_f1"] for r in results) / evaluated

    # Deflection metrics
    has_relevant = [r for r in results if r["has_relevant"]]
    no_relevant = [r for r in results if not r["has_relevant"]]

    defl_tpr = (sum(1 for r in no_relevant if r["deflected"]) / len(no_relevant)) if no_relevant else 0
    defl_fpr = (sum(1 for r in has_relevant if r["deflected"]) / len(has_relevant)) if has_relevant else 0

    # Eligibility: model cited at least one relevant passage
    eligible = sum(1 for r in has_relevant if r["num_cited"] > 0 and not r["deflected"]) / len(
        has_relevant) if has_relevant else 0

    aggregate = {
        "num_evaluated": evaluated,
        "num_with_relevant": len(has_relevant),
        "num_without_relevant": len(no_relevant),
        "raf": avg_raf,
        "eligibility": eligible,
        "attribution_precision": avg_attr_p,
        "attribution_recall": avg_attr_r,
        "attribution_f1": avg_attr_f1,
        "deflection_tpr": defl_tpr,
        "deflection_fpr": defl_fpr,
        "elapsed_seconds": elapsed,
    }

    output = {"aggregate": aggregate, "per_query": results}

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[garage] Results ({evaluated} items, {elapsed:.1f}s)")
    print(f"  RAF:                 {avg_raf:.4f}")
    print(f"  Eligibility:         {eligible:.4f}")
    print(f"  Attribution P/R/F1:  {avg_attr_p:.3f} / {avg_attr_r:.3f} / {avg_attr_f1:.3f}")
    print(f"  Deflection TPR/FPR:  {defl_tpr:.3f} / {defl_fpr:.3f}")
    print(f"  Results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
