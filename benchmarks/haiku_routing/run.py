#!/usr/bin/env python3
"""NEO-2322: Haiku routing experiment benchmark.

Evaluates three routing modes on first-turn correctness:
  A) disabled     — Sonnet for all calls
  B) search_count — Haiku on turn-1 (current/default), configurable max_tokens
  C) classifier   — Haiku only for greetings/meta, Sonnet for research

Two test sets:
  1. out_of_corpus.json  — ~30 questions with no answer in the corpus
     (agent must say "not found" or similar, NOT hallucinate an answer)
  2. in_corpus_first_turn.json — ~30 first-turn legal research questions
     that DO have answers in the corpus

Metrics per mode:
  - Correct rejection rate on out-of-corpus set (↑ = better)
  - Correct answer rate on in-corpus set (↑ = better)
  - Estimated cost delta (tokens × price per token)

Usage:
    AGENT_HAIKU_ROUTING_MODE=search_count python benchmarks/haiku_routing/run.py
    AGENT_HAIKU_ROUTING_MODE=disabled     python benchmarks/haiku_routing/run.py
    AGENT_HAIKU_ROUTING_MODE=classifier   python benchmarks/haiku_routing/run.py

    # Or run all three and compare:
    python benchmarks/haiku_routing/run.py --all-modes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
DATA_DIR = BENCH_DIR / "data"

# Haiku and Sonnet per-token costs (input/output) as of April 2026 via Vertex AI
# Used for cost-delta estimation only — not exact billing.
COST_PER_1K_INPUT = {"haiku": 0.00025, "sonnet": 0.003}
COST_PER_1K_OUTPUT = {"haiku": 0.00125, "sonnet": 0.015}

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


def _load_questions(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with open(path) as f:
        return json.load(f)


def _call_agent(question: str, corpus: str = "czech", timeout: int = 120) -> dict:
    """Call the agent pipeline and return the response dict."""
    import requests

    resp = requests.post(
        f"{BACKEND_URL}/api/agent",
        json={"question": question, "corpus": corpus},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _is_rejection(answer: str) -> bool:
    """Heuristic: did the agent say it couldn't find an answer?"""
    lower = answer.lower()
    rejection_signals = [
        "not found", "no information", "cannot find", "not available",
        "not in the corpus", "no relevant", "unable to find", "i don't have",
        "i do not have", "not contained", "outside the scope",
    ]
    return any(s in lower for s in rejection_signals)


async def run_set(questions: list[dict], label: str) -> dict:
    """Run a question set and return metrics."""
    results = []
    for q in questions:
        try:
            resp = _call_agent(q["question"], q.get("corpus", "czech"))
            answer = resp.get("answer", "")
            results.append(
                {
                    "question": q["question"],
                    "expected_rejection": q.get("expected_rejection", False),
                    "answer": answer[:300],
                    "rejected": _is_rejection(answer),
                    "usage": resp.get("usage", {}),
                }
            )
        except Exception as e:
            results.append({"question": q["question"], "error": str(e)})

    correct = 0
    for r in results:
        if "error" in r:
            continue
        expected_rej = r["expected_rejection"]
        if expected_rej and r["rejected"]:
            correct += 1
        elif not expected_rej and not r["rejected"]:
            correct += 1

    valid = [r for r in results if "error" not in r]
    accuracy = correct / len(valid) if valid else 0.0
    print(f"  [{label}] accuracy={accuracy:.1%} ({correct}/{len(valid)})")
    return {"accuracy": accuracy, "n": len(valid), "results": results}


async def run_mode(mode: str) -> dict:
    """Run all test sets with a given routing mode."""
    env = os.environ.copy()
    env["AGENT_HAIKU_ROUTING_MODE"] = mode

    out_of_corpus = _load_questions("out_of_corpus.json")
    in_corpus = _load_questions("in_corpus_first_turn.json")

    print(f"\n=== Mode: {mode} ===")
    oc_metrics = await run_set(out_of_corpus, "out-of-corpus rejection")
    ic_metrics = await run_set(in_corpus, "in-corpus first-turn")

    return {
        "mode": mode,
        "out_of_corpus": oc_metrics,
        "in_corpus_first_turn": ic_metrics,
        "combined_accuracy": (oc_metrics["accuracy"] + ic_metrics["accuracy"]) / 2,
    }


async def main():
    parser = argparse.ArgumentParser(description="NEO-2322 Haiku routing benchmark")
    parser.add_argument("--all-modes", action="store_true", help="Run all three routing modes")
    parser.add_argument(
        "--mode",
        default=os.environ.get("AGENT_HAIKU_ROUTING_MODE", "search_count"),
        choices=["search_count", "disabled", "classifier"],
    )
    parser.add_argument("--output", default=str(BENCH_DIR / "results.json"))
    args = parser.parse_args()

    modes = ["search_count", "disabled", "classifier"] if args.all_modes else [args.mode]

    all_results = []
    for mode in modes:
        result = await run_mode(mode)
        all_results.append(result)

    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {args.output}")

    if len(all_results) > 1:
        print("\n=== Mode comparison ===")
        for r in sorted(all_results, key=lambda x: -x["combined_accuracy"]):
            print(f"  {r['mode']}: combined={r['combined_accuracy']:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
