"""
Full pipeline analysis: run all 900 questions through router + retriever (no LLM)
to identify routing and retrieval quality patterns.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from arlc.answerer import _lookup_oracle
from arlc.retriever import retrieve_pages
from arlc.router import route

questions = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")))

results = []
type_stats = {}
oracle_count = 0
low_confidence_count = 0
no_pages_count = 0
fallback_count = 0

print(f"Analyzing {len(questions)} questions (router + retriever, no LLM)...")
t_start = time.time()

for i, q in enumerate(questions):
    qid = q["id"][:16]
    question = q["question"]
    at = q["answer_type"]

    if at not in type_stats:
        type_stats[at] = {"total": 0, "oracle": 0, "routed": 0, "retrieved": 0,
                          "low_conf": 0, "high_conf": 0, "no_pages": 0,
                          "avg_score": 0, "scores": []}
    type_stats[at]["total"] += 1

    # Route
    r = route(question, at)
    target_docs = r.target_doc_ids or []

    # Oracle check
    oracle = _lookup_oracle(question, at, r.metadata_pages or {})
    if oracle is not None:
        oracle_count += 1
        type_stats[at]["oracle"] += 1

    if target_docs:
        type_stats[at]["routed"] += 1

    # Retrieve (no LLM)
    try:
        pages = retrieve_pages(
            question, target_docs,
            max_per_doc=2 if at in ("free_text", "boolean", "name") else 1,
            max_total=3,
            answer_type=at,
        )

        if pages:
            type_stats[at]["retrieved"] += 1
            top_score = pages[0].score if hasattr(pages[0], "score") else pages[0].get("score", 0)
            type_stats[at]["scores"].append(top_score)

            if top_score < 0.4:
                type_stats[at]["low_conf"] += 1
                low_confidence_count += 1
            else:
                type_stats[at]["high_conf"] += 1

            result = {
                "id": q["id"],
                "type": at,
                "q": question[:80],
                "n_docs": len(target_docs),
                "n_pages": len(pages),
                "top_score": round(top_score, 3),
                "oracle": oracle is not None,
                "pages": [
                    {"doc": (p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", ""))[:16],
                     "pg": p.page_number if hasattr(p, "page_number") else p.get("page_number", 0),
                     "score": round(p.score if hasattr(p, "score") else p.get("score", 0), 3)}
                    for p in pages[:3]
                ]
            }
        else:
            no_pages_count += 1
            type_stats[at]["no_pages"] += 1
            result = {"id": q["id"], "type": at, "q": question[:80], "n_docs": len(target_docs),
                      "n_pages": 0, "top_score": 0, "oracle": oracle is not None, "pages": []}

        results.append(result)
    except Exception as e:
        results.append({"id": q["id"], "type": at, "q": question[:80], "error": str(e)})

    if (i + 1) % 100 == 0:
        elapsed = time.time() - t_start
        print(f"  [{i + 1}/{len(questions)}] {elapsed:.1f}s elapsed")

elapsed = time.time() - t_start
print(f"\nCompleted in {elapsed:.1f}s")
print(f"\n{'=' * 70}")
print(f"SUMMARY: {len(questions)} questions")
print(f"  Oracle hits: {oracle_count} ({oracle_count / len(questions) * 100:.1f}%)")
print(f"  No pages retrieved: {no_pages_count}")
print(f"  Low confidence (<0.4): {low_confidence_count}")
print("\nBy answer type:")
print(
    f"  {'Type':15s} {'Total':>5s} {'Oracle':>7s} {'Routed':>7s} {'Retr':>5s} {'NoPg':>5s} {'LowC':>5s} {'AvgTopScore':>12s}")
for at in sorted(type_stats.keys()):
    s = type_stats[at]
    avg = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
    print(
        f"  {at:15s} {s['total']:5d} {s['oracle']:7d} {s['routed']:7d} {s['retrieved']:5d} {s['no_pages']:5d} {s['low_conf']:5d} {avg:12.3f}")

# Find worst questions (lowest top scores, excluding oracle)
non_oracle = [r for r in results if not r.get("oracle") and "error" not in r and r["n_pages"] > 0]
non_oracle.sort(key=lambda x: x["top_score"])

print(f"\n{'=' * 70}")
print("LOWEST CONFIDENCE (non-oracle, retrieved):")
for r in non_oracle[:20]:
    print(f"  [{r['type']:10s}] score={r['top_score']:.3f} docs={r['n_docs']} pages={r['n_pages']} | {r['q']}")

# Questions with no pages at all
no_pg = [r for r in results if r["n_pages"] == 0 and "error" not in r]
if no_pg:
    print(f"\nNO PAGES RETRIEVED ({len(no_pg)}):")
    for r in no_pg[:15]:
        print(f"  [{r['type']:10s}] docs={r['n_docs']} | {r['q']}")

# Save full results
os.makedirs(os.path.join(os.path.dirname(__file__), "..", "output"), exist_ok=True)
out_path = os.path.join(os.path.dirname(__file__), "..", "output", "pipeline_analysis.json")
with open(out_path, "w") as f:
    json.dump({"summary": {"total": len(questions), "oracle": oracle_count,
                           "no_pages": no_pages_count, "low_confidence": low_confidence_count},
               "by_type": type_stats, "results": results}, f, indent=2, default=str)
print(f"\nFull results saved to {out_path}")
