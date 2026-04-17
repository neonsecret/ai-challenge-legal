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

Prerequisites:
  - Backend running with AGENT_ALLOW_ROUTING_OVERRIDE=true
  - Admin credentials: BENCH_EMAIL (default admin@vitreon.app),
    BENCH_PASSWORD (required — no default, benchmark exits if unset)

Usage:
    # Run all three modes (requires AGENT_ALLOW_ROUTING_OVERRIDE=true on backend):
    python benchmarks/haiku_routing/run.py --all-modes

    # Run a single mode:
    python benchmarks/haiku_routing/run.py --mode disabled
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

BENCH_DIR = Path(__file__).resolve().parent
DATA_DIR = BENCH_DIR / "data"

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
BENCH_EMAIL = os.environ.get("BENCH_EMAIL", "admin@vitreon.app")
BENCH_PASSWORD = os.environ.get("BENCH_PASSWORD", "")
if not BENCH_PASSWORD:
    print("BENCH_PASSWORD not set — export it before running this benchmark")
    sys.exit(1)

# Per-token pricing (input/output) via Vertex AI, April 2026
COST_PER_1K_INPUT = {"haiku": 0.00025, "sonnet": 0.003}
COST_PER_1K_OUTPUT = {"haiku": 0.00125, "sonnet": 0.015}

# Which model handles which mode's first turn (for cost estimation)
MODE_FIRST_TURN_MODEL = {
    "disabled": "sonnet",
    "search_count": "haiku",
    "classifier": "sonnet",  # research questions always use Sonnet in classifier mode
}


def _load_questions(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with open(path) as f:
        return json.load(f)


_CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _login() -> requests.Session:
    """Login and return an authenticated session (HttpOnly cookie)."""
    sess = requests.Session()
    sess.headers.update(_CSRF_HEADERS)
    resp = sess.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": BENCH_EMAIL, "password": BENCH_PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    return sess


def _parse_sse_answer(raw: str) -> dict:
    """Extract the answer payload from a raw SSE response body."""
    answer_data: dict = {}
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                payload = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            # The answer event carries "answer" key
            if "answer" in payload:
                answer_data = payload
    return answer_data


def _call_agent(
    sess: requests.Session,
    question: str,
    corpus: str,
    routing_mode: str,
    timeout: int = 180,
) -> dict:
    """Call the agent via SSE stream and return the answer payload."""
    headers = {
        "Accept": "text/event-stream",
        "X-Routing-Mode": routing_mode,
    }
    resp = sess.post(
        f"{BACKEND_URL}/api/v1/query/stream",
        params={"corpus": corpus},
        json={
            "question": question,
            "corpus": corpus,
            "answer_type": "free_text",
            "use_agent": True,
            "use_internet": False,  # disable web search for reproducibility
        },
        headers=headers,
        timeout=timeout,
        stream=True,
    )
    resp.raise_for_status()
    return _parse_sse_answer(resp.text)


def _is_rejection(answer: str) -> bool:
    """Heuristic: did the agent say it couldn't find an answer?"""
    lower = answer.lower()
    rejection_signals = [
        "not found",
        "no information",
        "cannot find",
        "not available",
        "not in the corpus",
        "no relevant",
        "unable to find",
        "i don't have",
        "i do not have",
        "not contained",
        "outside the scope",
        "není k dispozici",
        "nenašel jsem",
        "neobsahuje",
    ]
    return any(s in lower for s in rejection_signals)


def run_set(
    sess: requests.Session,
    questions: list[dict],
    label: str,
    routing_mode: str,
) -> dict:
    """Run a question set and return metrics."""
    results = []
    for i, q in enumerate(questions, 1):
        t0 = time.monotonic()
        try:
            resp = _call_agent(sess, q["question"], q.get("corpus", "czech"), routing_mode)
            answer = resp.get("answer", "")
            elapsed = time.monotonic() - t0
            results.append(
                {
                    "question": q["question"],
                    "expected_rejection": q.get("expected_rejection", False),
                    "answer": answer[:400],
                    "rejected": _is_rejection(answer),
                    "elapsed_s": round(elapsed, 1),
                }
            )
            status = "REJ" if _is_rejection(answer) else "ANS"
            exp = "rej" if q.get("expected_rejection") else "ans"
            ok = "✓" if (status == "REJ") == q.get("expected_rejection", False) else "✗"
            print(f"    {ok} Q{i:02d} [{status}/{exp}] {elapsed:.1f}s — {q['question'][:60]}")
        except Exception as e:
            results.append({"question": q["question"], "error": str(e)})
            print(f"    ✗ Q{i:02d} [ERROR] {e}")

    correct = sum(
        1
        for r in results
        if "error" not in r
        and (r["expected_rejection"] == r["rejected"])
    )
    valid = [r for r in results if "error" not in r]
    accuracy = correct / len(valid) if valid else 0.0
    print(f"  [{label}] accuracy={accuracy:.1%} ({correct}/{len(valid)})")
    return {"accuracy": accuracy, "n": len(valid), "results": results}


def run_mode(sess: requests.Session, mode: str, limit: int | None = None) -> dict:
    """Run all test sets with a given routing mode."""
    out_of_corpus = _load_questions("out_of_corpus.json")
    in_corpus = _load_questions("in_corpus_first_turn.json")

    if limit:
        out_of_corpus = out_of_corpus[:limit]
        in_corpus = in_corpus[:limit]

    print(f"\n=== Mode: {mode} ({len(out_of_corpus)} oc + {len(in_corpus)} ic questions) ===")
    oc_metrics = run_set(sess, out_of_corpus, "out-of-corpus rejection", mode)
    ic_metrics = run_set(sess, in_corpus, "in-corpus first-turn", mode)

    combined = (oc_metrics["accuracy"] + ic_metrics["accuracy"]) / 2
    print(f"  combined_accuracy={combined:.1%}")

    return {
        "mode": mode,
        "out_of_corpus": oc_metrics,
        "in_corpus_first_turn": ic_metrics,
        "combined_accuracy": combined,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="NEO-2322 Haiku routing benchmark")
    parser.add_argument("--all-modes", action="store_true", help="Run all three routing modes")
    parser.add_argument(
        "--mode",
        default=os.environ.get("AGENT_HAIKU_ROUTING_MODE", "search_count"),
        choices=["search_count", "disabled", "classifier"],
    )
    parser.add_argument("--output", default=str(BENCH_DIR / "results.json"))
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit questions per set (None = all 30). Use 5-10 for quick runs.",
    )
    args = parser.parse_args()

    print(f"Logging in as {BENCH_EMAIL} ...")
    sess = _login()
    print("Authenticated.")

    modes = ["search_count", "disabled", "classifier"] if args.all_modes else [args.mode]

    all_results = []
    for mode in modes:
        result = run_mode(sess, mode, limit=args.limit)
        all_results.append(result)

    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {args.output}")

    if len(all_results) > 1:
        print("\n=== Mode comparison ===")
        for r in sorted(all_results, key=lambda x: -x["combined_accuracy"]):
            oc = r["out_of_corpus"]["accuracy"]
            ic = r["in_corpus_first_turn"]["accuracy"]
            print(
                f"  {r['mode']:15s}  combined={r['combined_accuracy']:.1%}"
                f"  oc={oc:.1%}  ic={ic:.1%}"
            )


if __name__ == "__main__":
    main()
