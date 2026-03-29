#!/usr/bin/env python3
"""RAGAS evaluation harness.

Runs RAGAS metrics (faithfulness, answer relevancy, context precision,
context recall) on ARLC pipeline output.

Usage:
    python benchmarks/ragas/run.py --input output/submission.json [--dry-run] [--limit N]
"""

import argparse
import json
import os
import sys
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
# Input loading
# ---------------------------------------------------------------------------

def load_submission(input_path: str) -> list[dict]:
    """Load ARLC submission or evaluation data.

    Accepts either:
    1. ARLC submission JSON (list of question entries with pages/answer)
    2. Pre-formatted evaluation JSON with question/answer/contexts/ground_truth
    """
    with open(input_path) as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = data.get("questions", data.get("items", [data]))

    samples = []
    for item in data:
        # Try ARLC submission format first
        question = item.get("question", item.get("question_text", ""))
        answer = item.get("answer", "")
        if isinstance(answer, (bool, int, float)):
            answer = str(answer)

        # Extract contexts from pages
        contexts = item.get("contexts", [])
        if not contexts:
            pages = item.get("pages", [])
            for page in pages:
                text = page.get("text", "")
                if text:
                    contexts.append(text)

        ground_truth = item.get("ground_truth", item.get("expected_answer", ""))

        if question and answer:
            samples.append({
                "question": question,
                "answer": answer,
                "contexts": contexts if contexts else [""],
                "ground_truth": ground_truth if ground_truth else answer,
            })

    return samples


# ---------------------------------------------------------------------------
# RAGAS evaluation
# ---------------------------------------------------------------------------

def run_ragas_evaluation(samples: list[dict]) -> dict:
    """Run RAGAS metrics on the samples.

    Uses the RAGAS evaluate() API with SingleTurnSample and EvaluationDataset.
    """
    try:
        from ragas import evaluate
        from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
        from ragas.metrics import (
            Faithfulness,
            ResponseRelevancy,
            LLMContextPrecisionWithoutReference,
            LLMContextRecall,
        )
    except ImportError as e:
        print(f"[ragas] Import error: {e}")
        print("[ragas] Trying alternative imports...")
        try:
            from ragas import evaluate
            from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            # Use lowercase metric instances directly
            metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
            return _run_with_legacy_api(samples, evaluate, metrics)
        except ImportError as e2:
            print(f"[ragas] Legacy import also failed: {e2}")
            print("[ragas] Please install ragas: pip install ragas>=0.4.0")
            raise SystemExit(1)

    # Build RAGAS evaluation samples
    ragas_samples = []
    for s in samples:
        sample = SingleTurnSample(
            user_input=s["question"],
            response=s["answer"],
            retrieved_contexts=s["contexts"],
            reference=s["ground_truth"],
        )
        ragas_samples.append(sample)

    dataset = EvaluationDataset(samples=ragas_samples)

    # Define metrics
    metrics = [
        Faithfulness(),
        ResponseRelevancy(),
        LLMContextPrecisionWithoutReference(),
        LLMContextRecall(),
    ]

    print(f"[ragas] Running evaluation on {len(ragas_samples)} samples...")
    print(f"[ragas] Metrics: {[type(m).__name__ for m in metrics]}")

    result = evaluate(dataset=dataset, metrics=metrics)

    return _process_ragas_result(result)


def _run_with_legacy_api(samples, evaluate_fn, metrics):
    """Fallback for older RAGAS versions that use Dataset format."""
    from datasets import Dataset

    eval_data = {
        "question": [s["question"] for s in samples],
        "answer": [s["answer"] for s in samples],
        "contexts": [s["contexts"] for s in samples],
        "ground_truth": [s["ground_truth"] for s in samples],
    }
    dataset = Dataset.from_dict(eval_data)

    print(f"[ragas] Running evaluation (legacy API) on {len(samples)} samples...")
    result = evaluate_fn(dataset, metrics=metrics)
    return _process_ragas_result(result)


def _process_ragas_result(result) -> dict:
    """Extract scores from RAGAS result object."""
    output = {"aggregate": {}, "per_query": []}

    # RAGAS result is typically a dict-like with metric names as keys
    if hasattr(result, "to_pandas"):
        df = result.to_pandas()
        for col in df.columns:
            if col not in ("question", "answer", "contexts", "ground_truth",
                           "user_input", "response", "retrieved_contexts", "reference"):
                values = df[col].dropna().tolist()
                if values:
                    output["aggregate"][col] = sum(values) / len(values)

        # Per-query results
        for _, row in df.iterrows():
            entry = {}
            for col in df.columns:
                val = row[col]
                if isinstance(val, (int, float)):
                    entry[col] = val
                elif isinstance(val, str) and len(val) < 200:
                    entry[col] = val
            output["per_query"].append(entry)
    else:
        # Direct dict-like result
        for key, value in dict(result).items():
            if isinstance(value, (int, float)):
                output["aggregate"][key] = value

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RAGAS evaluation")
    parser.add_argument("--input", required=True, help="Path to submission/evaluation JSON")
    parser.add_argument("--dry-run", action="store_true", help="Validate input only")
    parser.add_argument("--limit", type=int, default=0, help="Limit samples (0=all)")
    args = parser.parse_args()

    # Step 1: Load input
    input_path = args.input
    if not os.path.isabs(input_path):
        input_path = str(PROJECT_ROOT / input_path)

    samples = load_submission(input_path)
    print(f"[ragas] Loaded {len(samples)} evaluation samples")

    if not samples:
        print("[ragas] ERROR: No valid samples found in input file")
        raise SystemExit(1)

    if args.dry_run:
        print("[ragas] Dry run - sample format check:")
        s = samples[0]
        print(f"  question: {s['question'][:80]}...")
        print(f"  answer: {s['answer'][:80]}...")
        print(f"  contexts: {len(s['contexts'])} passages")
        print(f"  ground_truth: {s['ground_truth'][:80]}...")
        print("[ragas] Input format valid. Dry run complete.")
        return

    if args.limit > 0:
        samples = samples[:args.limit]
        print(f"[ragas] Limited to {args.limit} samples")

    # Step 2: Check for required API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("[ragas] WARNING: OPENAI_API_KEY not set. RAGAS metrics require an LLM.")
        print("  Set OPENAI_API_KEY in .env or environment, or use ANTHROPIC_API_KEY")
        print("  with a compatible wrapper.")

    # Step 3: Run RAGAS evaluation
    output = run_ragas_evaluation(samples)

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[ragas] Results saved to {RESULTS_PATH}")
    print(f"  Scores:")
    for metric, score in output.get("aggregate", {}).items():
        print(f"    {metric}: {score:.4f}")


if __name__ == "__main__":
    main()
