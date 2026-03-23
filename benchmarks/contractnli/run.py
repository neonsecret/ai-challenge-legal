#!/usr/bin/env python3
"""ContractNLI evaluation harness.

Tests our pipeline as a boolean/classification QA system on 607 NDAs
with 17 hypotheses each (entailment/contradiction/not_mentioned).

Usage:
    python benchmarks/contractnli/run.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import json
import os
import re
import sys
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

# ContractNLI dataset URL (from the project page)
DATASET_URL = "https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip"
DATASET_ALT_URL = "https://github.com/stanfordnlp/contract-nli/raw/main/data/contract-nli.zip"


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
        print("  Please manually download from: https://stanfordnlp.github.io/contract-nli/")
        print(f"  and extract into {DATA_DIR}/")
        raise SystemExit(1)

    print("[contractnli] Extracting...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(DATA_DIR)
    zip_path.unlink()

    # Find the extracted directory
    for d in DATA_DIR.iterdir():
        if d.is_dir() and "contract" in d.name.lower():
            return d

    return dataset_dir


def load_dataset(dataset_dir: Path) -> dict:
    """Load ContractNLI JSON data.

    The dataset structure:
    {
        "documents": [
            {
                "id": "...",
                "text": "full NDA text",
                "spans": ["sentence1", "sentence2", ...],
                "annotation_sets": [
                    {
                        "annotations": {
                            "hypothesis_key": {
                                "choice": "Entailment|Contradiction|NotMentioned",
                                "spans": [span_indices]
                            }
                        }
                    }
                ]
            }
        ],
        "labels": {
            "hypothesis_key": {
                "short_description": "...",
                "hypothesis": "..."
            }
        }
    }
    """
    # Try common file names
    for fname in ["test.json", "dev.json", "train.json", "contract_nli.json"]:
        fpath = dataset_dir / fname
        if fpath.exists():
            with open(fpath) as f:
                return json.load(f)

    # Search recursively
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
    print(f"  Contents: {[f.name for f in dataset_dir.rglob('*') if f.is_file()][:20]}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Pipeline adapter
# ---------------------------------------------------------------------------

LABEL_MAP = {"Entailment": "entailment", "Contradiction": "contradiction", "NotMentioned": "not_mentioned"}


async def classify_nli(nda_text: str, hypothesis: str) -> str:
    """Use our pipeline to classify NDA + hypothesis as entailment/contradiction/not_mentioned.

    We frame this as a boolean QA: ask the model whether the hypothesis is
    supported, contradicted, or not mentioned in the NDA.
    """
    from arlc.answerer import generate_answer

    # Frame the NLI task as a question
    question = (
        f"Based on the following contract, classify the hypothesis as one of: "
        f"Entailment, Contradiction, or NotMentioned.\n\n"
        f"Hypothesis: {hypothesis}\n\n"
        f"Respond with ONLY one word: Entailment, Contradiction, or NotMentioned."
    )

    # Truncate NDA to avoid token limits (use first ~8000 chars)
    truncated_text = nda_text[:8000]

    source_pages = [{
        "doc_id": "nda_document",
        "page_number": 1,
        "text": truncated_text,
    }]

    result = await generate_answer(
        question=question,
        answer_type="name",  # single label classification
        source_pages=source_pages,
    )

    answer = str(result.answer).strip().lower() if result.answer else ""

    # Parse the classification from the answer
    if "entailment" in answer or "support" in answer or "true" in answer:
        return "entailment"
    elif "contradiction" in answer or "contradict" in answer or "false" in answer:
        return "contradiction"
    else:
        return "not_mentioned"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(predictions: list[str], golds: list[str]) -> dict:
    """Compute accuracy, per-class precision/recall/F1, and macro F1."""
    labels = ["entailment", "contradiction", "not_mentioned"]

    correct = sum(1 for p, g in zip(predictions, golds) if p == g)
    accuracy = correct / len(predictions) if predictions else 0

    # Per-class metrics
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

    # Confusion matrix
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
    args = parser.parse_args()

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
        print("[contractnli] Dry run complete.")
        return

    if args.limit > 0:
        documents = documents[:args.limit]
        print(f"[contractnli] Limited to {args.limit} NDAs")

    # Step 3: Classify each (NDA, hypothesis) pair
    all_predictions = []
    all_golds = []
    per_hypothesis_results = defaultdict(lambda: {"predictions": [], "golds": []})

    total_pairs = len(documents) * len(labels)
    done = 0

    for doc in documents:
        nda_text = doc.get("text", "")
        annotations = {}
        for ann_set in doc.get("annotation_sets", []):
            annotations.update(ann_set.get("annotations", {}))

        for hyp_key, hyp_info in labels.items():
            hypothesis = hyp_info.get("hypothesis", hyp_info.get("short_description", ""))
            gold_ann = annotations.get(hyp_key, {})
            gold_label = LABEL_MAP.get(gold_ann.get("choice", "NotMentioned"), "not_mentioned")

            done += 1
            print(f"  [{done}/{total_pairs}] Doc {doc.get('id', '?')[:20]} / {hyp_key}")

            prediction = asyncio.run(classify_nli(nda_text, hypothesis))

            all_predictions.append(prediction)
            all_golds.append(gold_label)
            per_hypothesis_results[hyp_key]["predictions"].append(prediction)
            per_hypothesis_results[hyp_key]["golds"].append(gold_label)

    # Step 4: Compute metrics
    overall = compute_metrics(all_predictions, all_golds)

    per_hyp_metrics = {}
    for hyp_key, data in per_hypothesis_results.items():
        per_hyp_metrics[hyp_key] = compute_metrics(data["predictions"], data["golds"])

    output = {
        "aggregate": overall,
        "per_hypothesis": per_hyp_metrics,
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[contractnli] Results saved to {RESULTS_PATH}")
    print(f"  Accuracy: {overall['accuracy']:.4f}")
    print(f"  Macro F1: {overall['macro_f1']:.4f}")
    for label, metrics in overall["per_class"].items():
        print(f"    {label}: P={metrics['precision']:.3f} R={metrics['recall']:.3f} F1={metrics['f1']:.3f}")


if __name__ == "__main__":
    main()
