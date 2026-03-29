import json, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from arlc.router import route
from arlc.answerer import _lookup_oracle

questions = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")))
oracle_hits = 0
oracle_types = {}
route_stats = {}
unrouted = []

for q in questions:
    r = route(q["question"], q["answer_type"])
    oracle = _lookup_oracle(q["question"], q["answer_type"], r.metadata_pages or {})
    at = q["answer_type"]
    if at not in oracle_types:
        oracle_types[at] = {"total": 0, "oracle": 0}
    oracle_types[at]["total"] += 1
    if oracle is not None:
        oracle_hits += 1
        oracle_types[at]["oracle"] += 1

    ndocs = len(r.target_doc_ids) if r.target_doc_ids else 0
    if at not in route_stats:
        route_stats[at] = {"total": 0, "routed": 0, "multi_doc": 0, "has_article": 0, "has_meta_pages": 0}
    route_stats[at]["total"] += 1
    if ndocs > 0:
        route_stats[at]["routed"] += 1
    if ndocs > 1:
        route_stats[at]["multi_doc"] += 1
    if r.article_numbers:
        route_stats[at]["has_article"] += 1
    if r.metadata_pages:
        route_stats[at]["has_meta_pages"] += 1
    if ndocs == 0:
        unrouted.append({"id": q.get("id", "?"), "type": at, "q": q["question"][:80]})

print(f"Oracle: {oracle_hits}/{len(questions)} ({oracle_hits / len(questions) * 100:.1f}%)")
print()
print("Oracle coverage by answer type:")
for at, counts in sorted(oracle_types.items(), key=lambda x: x[1]["oracle"] / max(x[1]["total"], 1)):
    pct = counts["oracle"] / counts["total"] * 100
    print(f"  {at:20s}: {counts['oracle']:3d}/{counts['total']:3d} ({pct:5.1f}%)")

print()
print("Routing coverage by answer type:")
for at, counts in sorted(route_stats.items(), key=lambda x: x[1]["routed"] / max(x[1]["total"], 1)):
    pct = counts["routed"] / counts["total"] * 100
    print(
        f"  {at:20s}: routed {counts['routed']:3d}/{counts['total']:3d} ({pct:5.1f}%), multi-doc: {counts['multi_doc']}, articles: {counts['has_article']}, meta_pages: {counts['has_meta_pages']}")

print()
print(f"Unrouted questions: {len(unrouted)}")
for u in unrouted[:30]:
    print(f"  [{u['type']:15s}] {u['id']:5s}: {u['q']}")
if len(unrouted) > 30:
    print(f"  ... and {len(unrouted) - 30} more")
