#!/usr/bin/env python3
"""ContractNLI evaluation harness.

Tests our pipeline as a boolean/classification QA system on 607 NDAs
with 17 hypotheses each (entailment/contradiction/not_mentioned).

Usage:
    python benchmarks/contractnli/run.py [--dry-run] [--limit N] [--workers N]
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
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
RESULTS_PATH = BENCH_DIR / "results.json"

DATASET_URL = "https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip"
DATASET_ALT_URL = "https://github.com/stanfordnlp/contract-nli/raw/main/data/contract-nli.zip"

# Model config
MODEL = os.environ.get("CONTRACTNLI_MODEL", "claude-sonnet-4-6")

# ---------------------------------------------------------------------------
# Anthropic client
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
    """Download ContractNLI dataset."""
    dataset_dir = DATA_DIR / "contract-nli"
    if dataset_dir.exists() and any(dataset_dir.iterdir()):
        print(f"[contractnli] Dataset already exists at {dataset_dir}")
        return dataset_dir

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / "contract-nli.zip"

    print("[contractnli] Downloading ContractNLI dataset...")
    for url in [DATASET_URL, DATASET_ALT_URL]:
        try:
            resp = requests.get(url, timeout=120, allow_redirects=True)
            resp.raise_for_status()
            zip_path.write_bytes(resp.content)
            print(f"[contractnli] Downloaded from {url}")
            break
        except Exception as e:
            print(f"[contractnli] Failed from {url}: {e}")
            continue
    else:
        print("[contractnli] ERROR: Could not download dataset from any URL.")
        raise SystemExit(1)

    print("[contractnli] Extracting...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(DATA_DIR)
    zip_path.unlink()

    for d in DATA_DIR.iterdir():
        if d.is_dir() and "contract" in d.name.lower():
            return d

    return dataset_dir


def load_dataset(dataset_dir: Path) -> dict:
    """Load ContractNLI JSON data."""
    for fname in ["test.json", "dev.json", "train.json", "contract_nli.json"]:
        fpath = dataset_dir / fname
        if fpath.exists():
            with open(fpath) as f:
                return json.load(f)

    for json_file in sorted(dataset_dir.rglob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
            if "documents" in data and "labels" in data:
                print(f"[contractnli] Found dataset at {json_file}")
                return data
        except (json.JSONDecodeError, KeyError):
            continue

    print(f"[contractnli] ERROR: Could not find valid dataset in {dataset_dir}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# OLD SYSTEM_PROMPT (baseline: Accuracy=0.763, Macro F1=0.725):
# SYSTEM_PROMPT = """You are a legal expert specializing in NDA (Non-Disclosure Agreement) analysis.
#
# Your task: determine whether a hypothesis is Entailment, Contradiction, or NotMentioned with respect to the NDA.
#
# Definitions:
# - **Entailment**: The NDA contains a clause or language that explicitly supports or logically implies the hypothesis is TRUE. There must be specific text you can point to.
# - **Contradiction**: The NDA contains a clause or language that explicitly states the OPPOSITE of the hypothesis. The NDA must actively negate or forbid what the hypothesis claims. Simply not mentioning something is NOT contradiction.
# - **NotMentioned**: The NDA does not contain any clause addressing the topic of the hypothesis. The hypothesis topic is simply absent from the agreement.
#
# CRITICAL distinction — Contradiction vs NotMentioned:
# - If the NDA says NOTHING about the topic → NotMentioned (NOT Contradiction)
# - If the NDA has a clause that DIRECTLY OPPOSES the hypothesis → Contradiction
# - Silence is NOT contradiction. Only explicit opposing language counts.
# - Example: If hypothesis is "Receiving Party can share with employees" and the NDA says nothing about employees → NotMentioned
# - Example: If hypothesis is "Receiving Party can share with employees" and the NDA says "shall not disclose to any employee" → Contradiction
#
# Think step by step:
# 1. Identify the topic of the hypothesis
# 2. Search the NDA for clauses addressing that topic
# 3. If no clause addresses it → NotMentioned
# 4. If a clause supports the hypothesis → Entailment
# 5. If a clause directly opposes the hypothesis → Contradiction
#
# After your reasoning, output your final answer on the LAST line as exactly one word: Entailment, Contradiction, or NotMentioned."""

SYSTEM_PROMPT = """You are a legal expert specializing in NDA (Non-Disclosure Agreement) analysis.

Your task: determine whether a hypothesis is Entailment, Contradiction, or NotMentioned with respect to the NDA.

Definitions:
- **Entailment**: The NDA contains a clause or language that explicitly supports or logically implies the hypothesis is TRUE. There must be specific text you can point to.
- **Contradiction**: The NDA contains a clause or language that explicitly states the OPPOSITE of the hypothesis. The NDA must actively negate or forbid what the hypothesis claims. Simply not mentioning something is NOT contradiction.
- **NotMentioned**: The NDA does not contain any clause addressing the topic of the hypothesis. The hypothesis topic is simply absent from the agreement.

CRITICAL distinction — Contradiction vs NotMentioned:
- If the NDA says NOTHING about the topic → NotMentioned (NOT Contradiction)
- If the NDA has a clause that DIRECTLY OPPOSES the hypothesis → Contradiction
- Silence is NOT contradiction. Only explicit opposing language counts.
- Example: If hypothesis is "Receiving Party can share with employees" and the NDA says nothing about employees → NotMentioned
- Example: If hypothesis is "Receiving Party can share with employees" and the NDA says "shall not disclose to any employee" → Contradiction

Think step by step:
1. Identify the topic of the hypothesis
2. Search the NDA for clauses addressing that topic
3. If no clause addresses it → NotMentioned
4. If a clause supports the hypothesis → Entailment
5. If a clause directly opposes the hypothesis → Contradiction

After your reasoning, output your final answer on the LAST line as exactly one word: Entailment, Contradiction, or NotMentioned."""


def build_user_prompt(nda_text: str, hypothesis: str) -> str:
    """Build the user prompt for NLI classification."""
    return (
        f"NDA Text:\n{nda_text}\n\n"
        f"Hypothesis: {hypothesis}\n\n"
        f"Classification:"
    )


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

LABEL_MAP = {
    "Entailment": "entailment",
    "Contradiction": "contradiction",
    "NotMentioned": "not_mentioned",
}


async def classify_nli(nda_text: str, hypothesis: str, sem: asyncio.Semaphore) -> str:
    """Classify NDA + hypothesis as entailment/contradiction/not_mentioned."""
    user_prompt = build_user_prompt(nda_text, hypothesis)

    async with sem:
        try:
            if _use_litellm:
                import asyncio
                from arlc.llm import litellm_backend
                answer, *_ = await asyncio.to_thread(
                    litellm_backend.call_llm, SYSTEM_PROMPT, user_prompt, 300, MODEL)
                answer = answer.strip()
            else:
                client = get_client()
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=300,
                    temperature=0.0,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                answer = response.content[0].text.strip()
        except Exception as e:
            print(f"  [ERROR] LLM call failed: {e}")
            return "not_mentioned"

    # Parse the LAST line for the classification (chain-of-thought before it)
    last_line = answer.strip().split("\n")[-1].strip().lower()

    if "entailment" in last_line:
        return "entailment"
    elif "contradiction" in last_line:
        return "contradiction"
    elif "notmentioned" in last_line or "not_mentioned" in last_line or "not mentioned" in last_line:
        return "not_mentioned"

    # Fallback: search full response for classification keywords
    lower = answer.lower()
    if "notmentioned" in lower or "not mentioned" in lower or "not_mentioned" in lower:
        return "not_mentioned"
    elif "entailment" in lower:
        return "entailment"
    elif "contradiction" in lower:
        return "contradiction"
    return "not_mentioned"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(predictions: list[str], golds: list[str]) -> dict:
    """Compute accuracy, per-class precision/recall/F1, and macro F1."""
    labels = ["entailment", "contradiction", "not_mentioned"]

    correct = sum(1 for p, g in zip(predictions, golds) if p == g)
    accuracy = correct / len(predictions) if predictions else 0

    per_class = {}
    for label in labels:
        tp = sum(1 for p, g in zip(predictions, golds) if p == label and g == label)
        fp = sum(1 for p, g in zip(predictions, golds) if p == label and g != label)
        fn = sum(1 for p, g in zip(predictions, golds) if p != label and g == label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        per_class[label] = {"precision": precision, "recall": recall, "f1": f1}

    macro_f1 = sum(c["f1"] for c in per_class.values()) / len(labels)

    confusion = defaultdict(Counter)
    for p, g in zip(predictions, golds):
        confusion[g][p] += 1

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "num_samples": len(predictions),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ContractNLI evaluation")
    parser.add_argument("--dry-run", action="store_true", help="Download data only")
    parser.add_argument("--limit", type=int, default=0, help="Limit NDAs (0=all)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers")
    args = parser.parse_args()

    # Initialize LLM backend (sets _use_litellm flag)
    get_client()

    # Step 1: Download
    dataset_dir = download_dataset()

    # Step 2: Load
    data = load_dataset(dataset_dir)
    documents = data.get("documents", [])
    labels = data.get("labels", {})

    print(f"[contractnli] Loaded {len(documents)} NDAs, {len(labels)} hypotheses")

    if args.dry_run:
        print("[contractnli] Hypotheses:")
        for key, info in labels.items():
            print(f"  {key}: {info.get('short_description', info.get('hypothesis', '')[:60])}")
        if documents:
            doc = documents[0]
            text = doc.get("text", "")
            print(f"\n[contractnli] Sample NDA length: {len(text)} chars")
            print(f"[contractnli] Sample NDA preview: {text[:200]}...")
        print("[contractnli] Dry run complete.")
        return

    if args.limit > 0:
        documents = documents[:args.limit]
        print(f"[contractnli] Limited to {args.limit} NDAs")

    # Step 3: Build all (NDA, hypothesis) pairs
    pairs = []
    for doc in documents:
        nda_text = doc.get("text", "")
        annotations = {}
        for ann_set in doc.get("annotation_sets", []):
            annotations.update(ann_set.get("annotations", {}))

        for hyp_key, hyp_info in labels.items():
            hypothesis = hyp_info.get("hypothesis", hyp_info.get("short_description", ""))
            gold_ann = annotations.get(hyp_key, {})
            gold_label = LABEL_MAP.get(gold_ann.get("choice", "NotMentioned"), "not_mentioned")
            pairs.append({
                "doc_id": doc.get("id", "?"),
                "nda_text": nda_text,
                "hyp_key": hyp_key,
                "hypothesis": hypothesis,
                "gold": gold_label,
            })

    print(f"[contractnli] Total pairs: {len(pairs)}")

    # Step 4: Classify with concurrency
    sem = asyncio.Semaphore(args.workers)

    async def classify_pair(pair):
        pred = await classify_nli(pair["nda_text"], pair["hypothesis"], sem)
        return {**pair, "prediction": pred}

    async def run_all():
        tasks = [classify_pair(p) for p in pairs]
        done = 0
        results = []
        for coro in asyncio.as_completed(tasks):
            result = await coro
            done += 1
            if done % 10 == 0 or done == len(tasks):
                print(f"  [{done}/{len(tasks)}] ...")
            results.append(result)
        return results

    t0 = time.time()
    classified = asyncio.run(run_all())
    elapsed = time.time() - t0

    # Step 5: Compute metrics
    all_predictions = [c["prediction"] for c in classified]
    all_golds = [c["gold"] for c in classified]

    overall = compute_metrics(all_predictions, all_golds)

    # Per-hypothesis metrics
    per_hyp = defaultdict(lambda: {"predictions": [], "golds": []})
    for c in classified:
        per_hyp[c["hyp_key"]]["predictions"].append(c["prediction"])
        per_hyp[c["hyp_key"]]["golds"].append(c["gold"])

    per_hyp_metrics = {}
    for hyp_key, d in per_hyp.items():
        per_hyp_metrics[hyp_key] = compute_metrics(d["predictions"], d["golds"])

    output = {
        "aggregate": {**overall, "elapsed_seconds": elapsed},
        "per_hypothesis": per_hyp_metrics,
    }

    # Remove nda_text from saved results to keep file small
    per_query = [{k: v for k, v in c.items() if k != "nda_text"} for c in classified]
    output["per_query"] = per_query

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[contractnli] Results ({len(all_predictions)} pairs, {elapsed:.1f}s)")
    print(f"  Accuracy: {overall['accuracy']:.4f}")
    print(f"  Macro F1: {overall['macro_f1']:.4f}")
    for label, metrics in overall["per_class"].items():
        print(f"    {label}: P={metrics['precision']:.3f} R={metrics['recall']:.3f} F1={metrics['f1']:.3f}")
    print(f"\n  Per-hypothesis accuracy:")
    for hyp_key in sorted(per_hyp_metrics.keys()):
        m = per_hyp_metrics[hyp_key]
        print(f"    {hyp_key}: {m['accuracy']:.3f} ({m['num_samples']} samples)")
    print(f"\n  Confusion matrix:")
    for gold_label, preds in overall["confusion_matrix"].items():
        print(f"    {gold_label}: {dict(preds)}")
    print(f"\n  Results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
