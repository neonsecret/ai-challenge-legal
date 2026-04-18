#!/usr/bin/env python3
"""LEXam evaluation harness.

Tests LLM legal reasoning on law school exam questions from 340 law school
courses (LEXam, ICLR 2026). Supports MCQ and open-ended question types.

Benchmarks Claude's performance against published scores:
  - Gemini 2.5 Pro: 82.2 overall, 55.7% on open questions
  - Claude 3.7 Sonnet: 57.2% on open questions
  - GPT-4.1: 68.2 overall

Usage:
    python benchmarks/lexam/run.py [--type mcq|open|all] [--lang en|de|all]
                                   [--limit N] [--workers N] [--no-shuffle]
"""

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

RESULTS_DIR = BENCH_DIR
MODEL = os.environ.get("LEXAM_MODEL", "claude-sonnet-4-6")

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
                timeout=90.0,
            )
        elif backend != "litellm":
            _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), timeout=90.0)
    return _client


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def load_mcq(lang_filter: str = "all") -> list[dict]:
    """Load MCQ-4 questions from LEXam."""
    from datasets import load_dataset

    ds = load_dataset("LEXam-Benchmark/LEXam", "mcq_4_choices", split="test")
    items = list(ds)
    if lang_filter != "all":
        items = [x for x in items if x.get("language", "") == lang_filter]
    return items


def load_open(lang_filter: str = "all") -> list[dict]:
    """Load open-ended questions from LEXam."""
    from datasets import load_dataset

    ds = load_dataset("LEXam-Benchmark/LEXam", "open_question", split="test")
    items = list(ds)
    if lang_filter != "all":
        items = [x for x in items if x.get("language", "") == lang_filter]
    return items


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

MCQ_SYSTEM = """You are a legal expert taking a law school exam.

Read the question carefully. Think through each option step by step, briefly explaining why each option is correct or incorrect.

Then state your final answer in this exact format:
Final answer: X

Where X is exactly one letter: A, B, C, or D.

Important: The correct answer is equally likely to be A, B, C, or D. Evaluate each option on its own merits — do not default to any particular letter."""

OPEN_SYSTEM = """You are a legal expert taking a law school exam. Answer the question in a structured, concise manner as expected in a law school exam setting.

Provide a clear, well-reasoned answer. Use legal terminology correctly. Be concise but complete."""


def parse_choices(item: dict) -> list:
    """Parse choices from item into a list of strings."""
    choices = item.get("choices", "[]")
    if isinstance(choices, str):
        try:
            choices = json.loads(choices)
        except Exception:
            choices = [s.strip() for s in choices.strip("[]").split(",")]
    return choices


def build_mcq_prompt(item: dict, choices: list | None = None) -> str:
    if choices is None:
        choices = parse_choices(item)

    prompt = f"Question: {item['question']}\n\n"
    labels = ["A", "B", "C", "D"]
    for label, choice in zip(labels, choices):
        prompt += f"{label}. {choice}\n"
    prompt += "\nSelect the single best answer (A, B, C, or D)."
    return prompt


def shuffle_choices(choices: list, gold_letter: str, question_id: str) -> tuple[list, str]:
    """Shuffle answer choices deterministically per question to eliminate position bias.

    Returns new choices list and updated gold letter reflecting the new positions.
    """
    labels = ["A", "B", "C", "D"]
    original_gold_idx = labels.index(gold_letter)

    seed = int(hashlib.md5(str(question_id).encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    perm = list(range(len(choices)))
    rng.shuffle(perm)

    new_choices = [choices[i] for i in perm]
    new_gold_idx = perm.index(original_gold_idx)
    new_gold_letter = labels[new_gold_idx]

    return new_choices, new_gold_letter


def build_open_prompt(item: dict) -> str:
    course = item.get("course", "")
    area = item.get("area", "")
    jurisdiction = item.get("jurisdiction", "")

    context = []
    if course:
        context.append(f"Course: {course}")
    if area:
        context.append(f"Area: {area}")
    if jurisdiction:
        context.append(f"Jurisdiction: {jurisdiction}")

    prompt = ""
    if context:
        prompt += "[" + ", ".join(context) + "]\n\n"
    prompt += f"Question: {item['question']}"
    return prompt


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


async def call_llm(system: str, user: str, max_tokens: int, sem: asyncio.Semaphore) -> str:
    async with sem:
        try:
            if _use_litellm:
                from arlc.llm import litellm_backend

                text, *_ = await asyncio.to_thread(litellm_backend.call_llm, system, user, max_tokens, MODEL)
                return text
            client = get_client()
            # Run synchronous AnthropicVertex client in thread pool to avoid blocking the event loop
            response = await asyncio.to_thread(
                client.messages.create,
                model=MODEL,
                max_tokens=max_tokens,
                temperature=0.0,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except Exception as e:
            print(f"  [ERROR] LLM call failed: {e}")
            return ""


# ---------------------------------------------------------------------------
# MCQ evaluation
# ---------------------------------------------------------------------------


def parse_mcq_answer(response: str) -> str:
    """Extract A/B/C/D from CoT response.

    Priority:
    1. Explicit "Final answer: X" / "My answer: X" (CoT canonical form)
    2. "The answer is X" / "answer: X"
    3. Last standalone letter on its own line
    4. Last word-boundary match of A/B/C/D in the full response
    """
    if not response:
        return "?"

    # 1. Canonical CoT final-answer marker
    m = re.search(r"(?i)(?:final answer|my answer)\s*[:\-]\s*\**([A-D])\b", response)
    if m:
        return m.group(1).upper()

    # 2. "the answer is X" / "answer is X" / "answer: X"
    m = re.search(r"(?i)(?:the answer is|answer is|answer:)\s*\**([A-D])\b", response)
    if m:
        return m.group(1).upper()

    # 3. Last line that is a bare letter
    for line in reversed(response.strip().split("\n")):
        stripped = line.strip().strip('"').strip("'").strip("*").strip(".").strip()
        if stripped in ("A", "B", "C", "D"):
            return stripped

    # 4. Last word-boundary occurrence of A/B/C/D
    matches = re.findall(r"\b([A-D])\b", response)
    if matches:
        return matches[-1]

    return "?"


def gold_to_letter(gold: str, choices: list) -> str:
    """Convert gold index (0-indexed int or letter) to A/B/C/D."""
    if isinstance(gold, str):
        if gold in ("0", "1", "2", "3"):
            return ["A", "B", "C", "D"][int(gold)]
        if gold in ("A", "B", "C", "D"):
            return gold
    try:
        return ["A", "B", "C", "D"][int(gold)]
    except Exception:
        return "?"


async def eval_mcq_item(item: dict, sem: asyncio.Semaphore, do_shuffle: bool = True) -> dict:
    choices = parse_choices(item)
    gold_letter = gold_to_letter(item.get("gold", "?"), choices)

    # Shuffle choices to eliminate position bias using deterministic per-question seed
    if do_shuffle and gold_letter in ("A", "B", "C", "D") and len(choices) == 4:
        qid = str(item.get("id", item["question"][:30]))
        choices, gold_letter = shuffle_choices(choices, gold_letter, qid)

    prompt = build_mcq_prompt(item, choices)
    response = await call_llm(MCQ_SYSTEM, prompt, 600, sem)
    predicted = parse_mcq_answer(response)
    correct = predicted == gold_letter

    return {
        "id": item.get("id", ""),
        "language": item.get("language", ""),
        "jurisdiction": item.get("jurisdiction", ""),
        "area": item.get("area", ""),
        "course": item.get("course", ""),
        "gold": gold_letter,
        "predicted": predicted,
        "correct": correct,
        "question_preview": item["question"][:80],
    }


# ---------------------------------------------------------------------------
# Open question evaluation (LLM-as-judge)
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = """You are a strict but fair law school exam grader.

Score the student answer on a scale of 0-10:
- 10: Complete, accurate, legally precise, well-structured
- 7-9: Mostly correct with minor omissions
- 4-6: Partially correct, missing key elements
- 1-3: Mostly wrong but shows some understanding
- 0: Completely wrong or no answer

Respond with ONLY a JSON object: {"score": N, "feedback": "brief reason"}"""


async def eval_open_item(item: dict, sem: asyncio.Semaphore) -> dict:
    prompt = build_open_prompt(item)
    student_answer = await call_llm(OPEN_SYSTEM, prompt, 800, sem)

    # Judge the answer against gold
    gold = item.get("answer", "")
    judge_prompt = (
        f"QUESTION:\n{item['question']}\n\n"
        f"GOLD ANSWER:\n{gold[:1500]}\n\n"
        f"STUDENT ANSWER:\n{student_answer[:1500]}\n\n"
        f"Score the student answer."
    )
    judge_response = await call_llm(JUDGE_SYSTEM, judge_prompt, 200, sem)

    score = 0.0
    try:
        # Parse JSON from judge
        m = re.search(r'\{"score":\s*(\d+(?:\.\d+)?)', judge_response)
        if m:
            score = float(m.group(1)) / 10.0
    except Exception:
        pass

    return {
        "id": item.get("id", ""),
        "language": item.get("language", ""),
        "jurisdiction": item.get("jurisdiction", ""),
        "area": item.get("area", ""),
        "course": item.get("course", ""),
        "score": score,
        "answer_preview": student_answer[:200],
        "question_preview": item["question"][:80],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="LEXam evaluation")
    parser.add_argument("--type", choices=["mcq", "open", "all"], default="mcq", help="Question type")
    parser.add_argument("--lang", default="en", help="Language filter: en, de, all")
    parser.add_argument("--limit", type=int, default=0, help="Limit questions (0=all)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--no-shuffle", action="store_true", help="Disable answer choice shuffling (re-enables position bias)")
    args = parser.parse_args()
    do_shuffle = not args.no_shuffle

    get_client()

    all_results = {}
    t0 = time.time()

    if args.type in ("mcq", "all"):
        items = load_mcq(args.lang)
        print(f"[lexam] MCQ-4 ({args.lang}): {len(items)} questions loaded")
        if args.limit > 0:
            items = items[: args.limit]
        if items:
            n_workers = args.workers

            async def run_mcq():
                sem = asyncio.Semaphore(n_workers)
                return await asyncio.gather(*[eval_mcq_item(item, sem, do_shuffle) for item in items])

            results = asyncio.run(run_mcq())

            correct = sum(1 for r in results if r["correct"])
            accuracy = correct / len(results)

            # Per-jurisdiction breakdown
            by_juris = defaultdict(lambda: {"correct": 0, "total": 0})
            by_area = defaultdict(lambda: {"correct": 0, "total": 0})
            pred_dist: dict[str, int] = defaultdict(int)
            for r in results:
                j = r.get("jurisdiction", "unknown")
                a = r.get("area", "unknown")
                by_juris[j]["total"] += 1
                by_area[a]["total"] += 1
                pred_dist[r["predicted"]] += 1
                if r["correct"]:
                    by_juris[j]["correct"] += 1
                    by_area[a]["correct"] += 1

            mcq_agg = {
                "num_questions": len(results),
                "correct": correct,
                "accuracy": accuracy,
                "predicted_distribution": dict(sorted(pred_dist.items())),
                "shuffle_enabled": do_shuffle,
                "by_jurisdiction": {j: v for j, v in sorted(by_juris.items())},
                "by_area": {a: v for a, v in sorted(by_area.items())},
            }
            all_results["mcq"] = {"aggregate": mcq_agg, "per_query": results}

            print(f"\n[lexam] MCQ Results:")
            print(f"  Accuracy: {accuracy:.4f} ({correct}/{len(results)})")
            print(f"  Predicted distribution: {dict(sorted(pred_dist.items()))}")
            n = len(results)
            for lbl in ("A", "B", "C", "D"):
                pct = pred_dist.get(lbl, 0) / n * 100
                print(f"    {lbl}: {pct:.1f}%")
            for j, v in sorted(by_juris.items()):
                if v["total"] >= 5:
                    acc = v["correct"] / v["total"]
                    print(f"  {j}: {acc:.3f} ({v['correct']}/{v['total']})")

    if args.type in ("open", "all"):
        items = load_open(args.lang)
        print(f"\n[lexam] Open ({args.lang}): {len(items)} questions loaded")
        if args.limit > 0:
            items = items[: args.limit]
        if items:
            n_workers = args.workers

            async def run_open():
                sem = asyncio.Semaphore(n_workers)
                return await asyncio.gather(*[eval_open_item(item, sem) for item in items])

            results = asyncio.run(run_open())

            avg_score = sum(r["score"] for r in results) / len(results)

            open_agg = {
                "num_questions": len(results),
                "avg_score": avg_score,
            }
            all_results["open"] = {"aggregate": open_agg, "per_query": results}

            print(f"\n[lexam] Open Results:")
            print(f"  Avg score (0-1): {avg_score:.4f}")
            print(f"  As percentage: {avg_score * 100:.1f}%")

    elapsed = time.time() - t0

    lang_tag = args.lang if args.lang != "all" else "all"
    results_path = RESULTS_DIR / f"results_{args.type}_{lang_tag}.json"
    with open(results_path, "w") as f:
        json.dump({"elapsed_seconds": elapsed, **all_results}, f, indent=2, ensure_ascii=False)

    print(f"\n[lexam] Done in {elapsed:.1f}s. Results: {results_path}")

    # Compare vs published benchmarks
    print("\n[lexam] Comparison vs published scores (MCQ-4 overall):")
    print("  Gemini 2.5 Pro: 82.2%")
    print("  GPT-4.1:        68.2%")
    print("  Claude 3.7 S:   ~65%")
    if "mcq" in all_results:
        acc = all_results["mcq"]["aggregate"]["accuracy"] * 100
        print(f"  Claude 4.6+RAG: {acc:.1f}% (this run)")
    print("\n[lexam] Comparison vs published (Open questions):")
    print("  Claude 3.7 S:   57.2%")
    print("  Gemini 2.5 Pro: 55.7%")
    if "open" in all_results:
        score = all_results["open"]["aggregate"]["avg_score"] * 100
        print(f"  Claude 4.6+RAG: {score:.1f}% (this run, LLM-as-judge)")


if __name__ == "__main__":
    main()
