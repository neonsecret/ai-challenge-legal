"""Component-level pipeline metrics instrumentation.

Tracks precision/recall at each pipeline stage separately (router, retrieval,
reranker) so we can identify exactly where the pipeline loses points.

Inspired by CPBD (Azamat Yelmagambetov, 1st place) who measured precision/recall
at each stage independently to guide targeted improvements.

Usage:
    ARLC_METRICS=true python run.py --workers 5 ...

All tracking is no-op when ARLC_METRICS is not set, so there is zero overhead
in normal production runs.
"""

import json
import os
import threading
from collections import defaultdict
from typing import Any

# Enable via environment variable — zero overhead when not set
METRICS_ENABLED = os.environ.get("ARLC_METRICS", "").lower() in ("1", "true", "yes")

_lock = threading.Lock()

# Accumulated metric counters (thread-safe)
_counters: dict[str, dict[str, Any]] = defaultdict(lambda: {
    "hits": 0,
    "misses": 0,
    "total": 0,
})

# Per-question detail log (for post-run analysis)
_question_log: list[dict] = []


def _noop(*args, **kwargs) -> None:
    """No-op placeholder when metrics are disabled."""
    return None


def record_router_hit(question: str, answer_type: str, routed_doc_ids: list[str], gold_doc_id: str | None) -> None:
    """Record whether the router found the correct document.

    Parameters
    ----------
    question : str
        The question being answered.
    answer_type : str
        Answer type (boolean, date, name, etc.)
    routed_doc_ids : list[str]
        Documents the router selected.
    gold_doc_id : str | None
        The known-correct document ID (from gold labels, if available).
        If None, the hit/miss cannot be determined — still recorded as total.
    """
    if not METRICS_ENABLED:
        return

    hit = gold_doc_id is not None and gold_doc_id in routed_doc_ids
    with _lock:
        c = _counters["router"]
        c["total"] += 1
        if gold_doc_id is not None:
            if hit:
                c["hits"] += 1
            else:
                c["misses"] += 1
        _question_log.append({
            "stage": "router",
            "question": question[:80],
            "answer_type": answer_type,
            "routed": routed_doc_ids,
            "gold_doc": gold_doc_id,
            "hit": hit if gold_doc_id else None,
        })


def record_retrieval_recall(
        question: str,
        answer_type: str,
        retrieved_pages: list[tuple[str, int]],
        gold_pages: list[tuple[str, int]] | None,
        top_k: int,
) -> None:
    """Record retrieval recall@K: is the gold page in top-K retrieved results?

    Parameters
    ----------
    question : str
        The question being answered.
    answer_type : str
        Answer type.
    retrieved_pages : list[tuple[str, int]]
        List of (doc_id, page_number) tuples from retrieval, ranked by score.
    gold_pages : list[tuple[str, int]] | None
        Known-correct (doc_id, page_number) pairs. None if unavailable.
    top_k : int
        The retrieval depth used (for logging).
    """
    if not METRICS_ENABLED:
        return

    retrieved_set = set(retrieved_pages)
    hit = False
    if gold_pages:
        hit = any(gp in retrieved_set for gp in gold_pages)

    with _lock:
        c = _counters[f"retrieval_recall@{top_k}"]
        c["total"] += 1
        if gold_pages is not None:
            if hit:
                c["hits"] += 1
            else:
                c["misses"] += 1
        _question_log.append({
            "stage": "retrieval",
            "question": question[:80],
            "answer_type": answer_type,
            "retrieved": list(retrieved_pages)[:5],
            "gold_pages": gold_pages,
            "top_k": top_k,
            "recall_hit": hit if gold_pages else None,
        })


def record_reranker_recall(
        question: str,
        answer_type: str,
        reranked_pages: list[tuple[str, int]],
        pre_rerank_pages: list[tuple[str, int]],
        gold_pages: list[tuple[str, int]] | None,
) -> None:
    """Record whether reranking preserved the gold page.

    A reranker "miss" is when the gold page was in the pre-rerank set but NOT
    in the final reranked output — meaning reranking actively hurt retrieval.

    Parameters
    ----------
    question : str
        The question being answered.
    answer_type : str
        Answer type.
    reranked_pages : list[tuple[str, int]]
        Final pages after reranking (doc_id, page_number).
    pre_rerank_pages : list[tuple[str, int]]
        Pages before reranking (the input to the reranker).
    gold_pages : list[tuple[str, int]] | None
        Known-correct pages.
    """
    if not METRICS_ENABLED:
        return

    reranked_set = set(reranked_pages)
    pre_set = set(pre_rerank_pages)
    reranker_hit = False
    reranker_drop = False  # was in pre but not in post (reranker hurt us)
    if gold_pages:
        gold_in_pre = any(gp in pre_set for gp in gold_pages)
        gold_in_post = any(gp in reranked_set for gp in gold_pages)
        reranker_hit = gold_in_post
        reranker_drop = gold_in_pre and not gold_in_post  # reranker filtered it out

    with _lock:
        c = _counters["reranker"]
        c["total"] += 1
        if gold_pages is not None:
            if reranker_hit:
                c["hits"] += 1
            else:
                c["misses"] += 1
            if reranker_drop:
                c.setdefault("drops", 0)
                c["drops"] += 1
        _question_log.append({
            "stage": "reranker",
            "question": question[:80],
            "answer_type": answer_type,
            "reranked": list(reranked_pages),
            "gold_pages": gold_pages,
            "reranker_hit": reranker_hit if gold_pages else None,
            "reranker_drop": reranker_drop if gold_pages else None,
        })


def get_summary() -> dict:
    """Return a dict summary of all accumulated metrics.

    Computes hit_rate (hits / (hits + misses)) for each stage.
    """
    if not METRICS_ENABLED:
        return {}

    with _lock:
        summary = {}
        for stage, counts in _counters.items():
            evaluated = counts["hits"] + counts["misses"]
            hit_rate = counts["hits"] / evaluated if evaluated > 0 else None
            summary[stage] = {
                "total_questions": counts["total"],
                "evaluated": evaluated,
                "hits": counts["hits"],
                "misses": counts["misses"],
                "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
                **{k: v for k, v in counts.items() if k not in ("hits", "misses", "total")},
            }
        return summary


def print_summary() -> None:
    """Print a formatted metrics summary to stdout."""
    if not METRICS_ENABLED:
        return

    summary = get_summary()
    if not summary:
        print("[metrics] No data recorded.")
        return

    print("\n" + "=" * 60)
    print("PIPELINE COMPONENT METRICS SUMMARY")
    print("=" * 60)
    for stage, stats in sorted(summary.items()):
        hit_rate = stats["hit_rate"]
        hr_str = f"{hit_rate:.1%}" if hit_rate is not None else "N/A"
        print(f"  {stage:<30} hit_rate={hr_str}  "
              f"({stats['hits']}/{stats['evaluated']} evaluated, "
              f"{stats['total_questions']} total)")
        # Print extra counters (e.g. drops)
        for k, v in stats.items():
            if k not in ("total_questions", "evaluated", "hits", "misses", "hit_rate"):
                print(f"    {k}: {v}")
    print("=" * 60 + "\n")


def save_question_log(path: str) -> None:
    """Save per-question detail log to a JSON file for offline analysis."""
    if not METRICS_ENABLED:
        return

    with _lock:
        log_copy = list(_question_log)

    with open(path, "w") as f:
        json.dump(log_copy, f, indent=2)
    print(f"[metrics] Question log saved to {path} ({len(log_copy)} entries)")


def reset() -> None:
    """Reset all accumulated metrics (useful for test isolation)."""
    with _lock:
        _counters.clear()
        _question_log.clear()
