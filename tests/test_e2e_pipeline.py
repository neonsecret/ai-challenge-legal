"""End-to-end pipeline test on real ARLC corpus.

Runs individual questions through the full pipeline:
  router → retriever → answerer → page_verifier → post-processing

Tests each component in isolation AND the full chain. Uses Vertex AI for LLM calls.

Usage:
    python -m tests.test_e2e_pipeline              # run all tests
    python -m tests.test_e2e_pipeline --quick       # 5 questions only
    python -m tests.test_e2e_pipeline --full        # 20 questions
"""

import asyncio
import json
import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

from arlc.router import route
from arlc.retriever import retrieve_pages
from arlc.answerer import generate_answer, AnswerResult, _lookup_oracle
from arlc.page_verifier import verify_pages


def load_questions(path="data/questions.json"):
    with open(path) as f:
        return json.load(f)


def select_test_questions(questions, n=20):
    """Select diverse questions covering all answer types."""
    by_type = {}
    for q in questions:
        t = q["answer_type"]
        by_type.setdefault(t, []).append(q)

    selected = []
    # Proportional selection
    type_counts = {"boolean": 4, "number": 4, "date": 3, "name": 3, "names": 3, "free_text": 3}
    if n <= 5:
        type_counts = {t: 1 for t in type_counts}

    for atype, count in type_counts.items():
        pool = by_type.get(atype, [])
        # Pick from different positions in the list for variety
        step = max(1, len(pool) // (count + 1))
        for i in range(min(count, len(pool))):
            selected.append(pool[i * step])

    return selected[:n]


def test_single_question(q, verbose=True):
    """Run a single question through the full pipeline. Returns result dict."""
    qid = q["id"][:12]
    question = q["question"]
    answer_type = q["answer_type"]

    result = {
        "id": q["id"],
        "question": question[:80],
        "answer_type": answer_type,
        "steps": {},
        "errors": [],
        "success": False,
    }

    # Step 1: Route
    t0 = time.perf_counter()
    try:
        route_result = route(question, answer_type)
        target_docs = route_result.target_doc_ids or []
        result["steps"]["route"] = {
            "docs": len(target_docs),
            "has_oracle": route_result.metadata_answer is not None,
            "time_ms": (time.perf_counter() - t0) * 1000,
        }
        if verbose:
            print(f"  [route] {len(target_docs)} docs, oracle={route_result.metadata_answer is not None}")
    except Exception as e:
        result["errors"].append(f"route: {e}")
        if verbose:
            print(f"  [route] ERROR: {e}")
        return result

    # Step 2: Oracle check (no LLM)
    oracle_result = None
    try:
        oracle_result = _lookup_oracle(question, answer_type, route_result.metadata_pages or [])
        if oracle_result is not None:
            result["steps"]["oracle"] = {"answer": str(oracle_result)[:60]}
            if verbose:
                print(f"  [oracle] {str(oracle_result)[:60]}")
    except Exception as e:
        result["errors"].append(f"oracle: {e}")

    # Step 3: Retrieve pages
    t0 = time.perf_counter()
    try:
        pages = retrieve_pages(
            question, target_docs,
            max_per_doc=2 if answer_type in ("free_text", "boolean", "name") else 1,
            max_total=3,
            answer_type=answer_type,
        )
        result["steps"]["retrieve"] = {
            "pages": len(pages),
            "time_ms": (time.perf_counter() - t0) * 1000,
            "page_details": [
                {"doc": (p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", ""))[:12],
                 "page": p.page_number if hasattr(p, "page_number") else p.get("page_number", 0),
                 "score": round(p.score if hasattr(p, "score") else p.get("score", 0), 3)}
                for p in pages[:5]
            ],
        }
        if verbose:
            for p in pages[:3]:
                doc = (p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", ""))[:12]
                pg = p.page_number if hasattr(p, "page_number") else p.get("page_number", 0)
                sc = p.score if hasattr(p, "score") else p.get("score", 0)
                print(f"  [retrieve] {doc}:p{pg} score={sc:.3f}")
    except Exception as e:
        result["errors"].append(f"retrieve: {e}")
        if verbose:
            print(f"  [retrieve] ERROR: {e}")
        pages = []

    # Step 4: Generate answer (LLM call)
    if oracle_result is not None:
        result["steps"]["answer"] = {"value": str(oracle_result)[:60], "source": "oracle", "time_ms": 0}
        answer_value = oracle_result
    elif pages:
        t0 = time.perf_counter()
        try:
            source_pages = []
            for p in pages:
                source_pages.append({
                    "doc_id": p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", ""),
                    "page_number": p.page_number if hasattr(p, "page_number") else p.get("page_number", 0),
                    "text": p.text if hasattr(p, "text") else p.get("text", ""),
                })
            ar = asyncio.run(generate_answer(question, answer_type, source_pages))
            answer_value = ar.answer
            result["steps"]["answer"] = {
                "value": str(ar.answer)[:100],
                "source": "llm",
                "model": ar.model_name,
                "ttft_ms": round(ar.ttft_ms, 0),
                "total_ms": round(ar.total_time_ms, 0),
                "tokens_in": ar.input_tokens,
                "tokens_out": ar.output_tokens,
                "grounding": ar.grounding if ar.grounding else [],
                "time_ms": (time.perf_counter() - t0) * 1000,
            }
            if verbose:
                print(f"  [answer] {str(ar.answer)[:60]} (model={ar.model_name}, ttft={ar.ttft_ms:.0f}ms)")
                if ar.grounding:
                    print(f"  [grounding] {len(ar.grounding)} citations")
        except Exception as e:
            result["errors"].append(f"answer: {e}")
            if verbose:
                print(f"  [answer] ERROR: {e}")
            answer_value = None
    else:
        result["steps"]["answer"] = {"value": "None", "source": "no_pages"}
        answer_value = None

    # Step 5: Page verification
    if answer_value is not None and pages:
        t0 = time.perf_counter()
        try:
            chunk_pages = []
            for p in pages:
                doc_id = p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", "")
                pg = p.page_number if hasattr(p, "page_number") else p.get("page_number", 0)
                # Group by doc_id
                found = False
                for cp in chunk_pages:
                    if cp["doc_id"] == doc_id:
                        cp["page_numbers"].append(pg)
                        found = True
                        break
                if not found:
                    chunk_pages.append({"doc_id": doc_id, "page_numbers": [pg]})

            verified = verify_pages(question, answer_value, answer_type, chunk_pages)
            result["steps"]["verify"] = {
                "pages_before": sum(len(cp["page_numbers"]) for cp in chunk_pages),
                "pages_after": sum(len(cp["page_numbers"]) for cp in verified),
                "changed": str(chunk_pages) != str(verified),
                "time_ms": (time.perf_counter() - t0) * 1000,
            }
            if verbose:
                changed = "CHANGED" if str(chunk_pages) != str(verified) else "unchanged"
                print(f"  [verify] {changed}")
        except Exception as e:
            result["errors"].append(f"verify: {e}")
            if verbose:
                print(f"  [verify] ERROR: {e}")

    result["success"] = len(result["errors"]) == 0
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="5 questions only")
    parser.add_argument("--full", action="store_true", help="20 questions")
    parser.add_argument("--n", type=int, default=None, help="Exact number of questions")
    args = parser.parse_args()

    n = args.n or (5 if args.quick else 20 if args.full else 10)

    print(f"Loading questions...")
    questions = load_questions()
    selected = select_test_questions(questions, n)
    print(f"Testing {len(selected)} questions across {len(set(q['answer_type'] for q in selected))} types\n")

    results = []
    total_start = time.perf_counter()

    for i, q in enumerate(selected):
        print(f"[{i+1}/{len(selected)}] ({q['answer_type']}) {q['question'][:70]}...")
        t0 = time.perf_counter()
        r = test_single_question(q)
        elapsed = time.perf_counter() - t0
        print(f"  [{elapsed:.1f}s] {'OK' if r['success'] else 'ERRORS: ' + ', '.join(r['errors'])}\n")
        results.append(r)

    total_time = time.perf_counter() - total_start

    # Summary
    print("=" * 70)
    print(f"RESULTS: {sum(1 for r in results if r['success'])}/{len(results)} passed in {total_time:.1f}s")
    print()

    # Per-type breakdown
    by_type = {}
    for r in results:
        t = r["answer_type"]
        by_type.setdefault(t, {"ok": 0, "fail": 0, "errors": []})
        if r["success"]:
            by_type[t]["ok"] += 1
        else:
            by_type[t]["fail"] += 1
            by_type[t]["errors"].extend(r["errors"])

    print(f"{'Type':<12} {'Pass':>5} {'Fail':>5} {'Errors'}")
    print("-" * 50)
    for t, d in sorted(by_type.items()):
        err_str = ", ".join(d["errors"][:3]) if d["errors"] else ""
        print(f"{t:<12} {d['ok']:>5} {d['fail']:>5} {err_str[:40]}")

    # LLM call stats
    llm_calls = [r for r in results if r.get("steps", {}).get("answer", {}).get("source") == "llm"]
    oracle_calls = [r for r in results if r.get("steps", {}).get("answer", {}).get("source") == "oracle"]
    print(f"\nLLM calls: {len(llm_calls)}, Oracle hits: {len(oracle_calls)}")
    if llm_calls:
        avg_ttft = sum(r["steps"]["answer"].get("ttft_ms", 0) for r in llm_calls) / len(llm_calls)
        avg_total = sum(r["steps"]["answer"].get("total_ms", 0) for r in llm_calls) / len(llm_calls)
        print(f"Avg TTFT: {avg_ttft:.0f}ms, Avg total: {avg_total:.0f}ms")

    # Page verification stats
    verified = [r for r in results if "verify" in r.get("steps", {})]
    changed = [r for r in verified if r["steps"]["verify"].get("changed")]
    print(f"Page verification: {len(verified)} questions, {len(changed)} pages changed")

    # Errors
    all_errors = [(r["question"], e) for r in results for e in r["errors"]]
    if all_errors:
        print(f"\nERRORS ({len(all_errors)}):")
        for q, e in all_errors:
            print(f"  {q[:50]}: {e}")

    # Save detailed results
    os.makedirs("output", exist_ok=True)
    with open("output/e2e_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nDetailed results saved to output/e2e_test_results.json")


if __name__ == "__main__":
    main()
