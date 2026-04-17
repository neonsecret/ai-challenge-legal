#!/usr/bin/env python3
"""Accuracy benchmark for Vitreon Legal on DIFC and Czech corpora.

Tests citation accuracy, answer correctness, and grounding (DOC-N citations).
Uses the SSE streaming endpoint. Pass --agent to use the LangGraph agent
(requires langchain_google_vertexai); defaults to deterministic pipeline.
"""

import json
import os
import re
import sys
import time

import requests

USE_AGENT = "--agent" in sys.argv

BASE = os.environ.get("BACKEND_URL", "http://localhost:8000")
TIMEOUT = 180

# ── Login ────────────────────────────────────────────────────────────────────
session = requests.Session()
# CSRF middleware requires X-Requested-With on all state-mutating requests
session.headers.update({"X-Requested-With": "XMLHttpRequest"})

_email = os.environ.get("TEST_ADMIN_EMAIL", "admin@vitreon.app")
_password = os.environ.get("TEST_ADMIN_PASSWORD", "")
if not _password:
    print("TEST_ADMIN_PASSWORD not set — export it before running benchmarks")
    sys.exit(1)

r = session.post(
    f"{BASE}/auth/login",
    json={
        "email": _email,
        "password": _password,
    },
)
if r.status_code != 200:
    print(f"Login failed: {r.status_code} {r.text}")
    sys.exit(1)
print(f"Login OK (status {r.status_code})")


# ── Test data ────────────────────────────────────────────────────────────────

difc_tests = [
    {
        "q": "What is the limitation period under DIFC Law No. 5 of 2005?",
        "expected_section": "Article 9",
        "expected_answer_contains": "6 years",
    },
    {
        "q": "Can a contract be formed orally under DIFC law?",
        "expected_section": "Article 15",
        "expected_answer_contains": "oral",
    },
    {
        "q": "What constitutes unfair dismissal under DIFC Employment Law?",
        "expected_section": "Article 59",
        "expected_answer_contains": "unfair",
    },
    {
        "q": "What is the minimum notice period for termination of employment in DIFC?",
        "expected_section": "Article 58",
        "expected_answer_contains": "30 days",
    },
    {
        "q": "How is end of service gratuity calculated in DIFC?",
        "expected_section": "Article 62",
        "expected_answer_contains": "gratuity",
    },
    {
        "q": "What are the grounds for winding up a company in DIFC?",
        "expected_section": "Article 50",
        "expected_answer_contains": "wind",
    },
    {
        "q": "What is the role of the DIFC Courts?",
        "expected_section": "Court Law",
        "expected_answer_contains": "jurisdiction",
    },
    {
        "q": "What are the requirements for a valid trust under DIFC Trust Law?",
        "expected_section": "Trust",
        "expected_answer_contains": "trust",
    },
    {
        "q": "What is the definition of a 'person' under DIFC Interpretation Law?",
        "expected_section": "Interpretation",
        "expected_answer_contains": "person",
    },
    {
        "q": "What remedies are available for breach of contract under DIFC law?",
        "expected_section": "Law No. 5",
        "expected_answer_contains": "damages",
    },
    {
        "q": "What is the maximum working hours per week in DIFC?",
        "expected_section": "Employment",
        "expected_answer_contains": "48",
    },
    {
        "q": "Can DIFC Courts enforce foreign judgments?",
        "expected_section": "Court",
        "expected_answer_contains": "enforce",
    },
    {
        "q": "What are the anti-money laundering obligations in DIFC?",
        "expected_section": "AML",
        "expected_answer_contains": "money laundering",
    },
    {
        "q": "What is the role of the Registrar of Companies in DIFC?",
        "expected_section": "Companies",
        "expected_answer_contains": "registrar",
    },
    {
        "q": "What constitutes negligence under DIFC Law of Obligations?",
        "expected_section": "Article",
        "expected_answer_contains": "negligen",
    },
    {
        "q": "What is the maternity leave entitlement in DIFC?",
        "expected_section": "Employment",
        "expected_answer_contains": "maternity",
    },
    {
        "q": "How are disputes resolved in the DIFC Small Claims Tribunal?",
        "expected_section": "SCT",
        "expected_answer_contains": "small claims",
    },
    {
        "q": "What are the data protection requirements in DIFC?",
        "expected_section": "Data Protection",
        "expected_answer_contains": "data",
    },
    {
        "q": "What is constructive dismissal under DIFC law?",
        "expected_section": "Employment",
        "expected_answer_contains": "constructive",
    },
    {
        "q": "What are the shareholder rights under DIFC Companies Law?",
        "expected_section": "Companies",
        "expected_answer_contains": "shareholder",
    },
]

czech_tests = [
    {
        "q": "Jaká je výpovědní doba podle zákoníku práce?",
        "expected_section": "§ 51",
        "expected_answer_contains": "2 měsíc",
    },
    {"q": "Co je bezdůvodné obohacení?", "expected_section": "§ 2991", "expected_answer_contains": "obohac"},
    {
        "q": "Jaké jsou podmínky pro výpověď ze strany zaměstnavatele?",
        "expected_section": "§ 52",
        "expected_answer_contains": "výpověd",
    },
    {"q": "Kolik je zákonné odstupné?", "expected_section": "§ 67", "expected_answer_contains": "odstupn"},
    {"q": "Jaká je sazba DPH?", "expected_section": "zákon o DPH", "expected_answer_contains": "21"},
    {
        "q": "Může zaměstnanec vykonávat jinou výdělečnou činnost?",
        "expected_section": "§ 304",
        "expected_answer_contains": "výdělečn",
    },
    {
        "q": "Jak se zakládá společnost s ručením omezeným?",
        "expected_section": "zákon o obch",
        "expected_answer_contains": "společnost",
    },
    {"q": "Co je to nájem bytu?", "expected_section": "§ 2235", "expected_answer_contains": "nájem"},
    {"q": "Jaký je nárok na dovolenou?", "expected_section": "§ 211", "expected_answer_contains": "dovolen"},
    {"q": "Co je trestný čin podvodu?", "expected_section": "§ 209", "expected_answer_contains": "podvod"},
    {"q": "Jaké jsou podmínky pro vydržení?", "expected_section": "§ 1089", "expected_answer_contains": "vydržen"},
    {"q": "Jak funguje daň z příjmů pro OSVČ?", "expected_section": "§ 7", "expected_answer_contains": "příjm"},
    {"q": "Co je to výpověď dohodou?", "expected_section": "§ 49", "expected_answer_contains": "dohod"},
    {"q": "Jaká je promlčecí doba?", "expected_section": "§ 629", "expected_answer_contains": "3 rok"},
    {"q": "Jaké jsou podmínky pro zkušební dobu?", "expected_section": "§ 35", "expected_answer_contains": "zkušebn"},
]


# ── SSE parser ───────────────────────────────────────────────────────────────


def run_question_sse(question: str, corpus: str) -> dict:
    """Send a question via SSE and parse the answer event.

    Returns dict with keys: answer, sources, confidence, latency_ms, raw_answer,
                            tokens (concatenated), timed_out, error
    """
    payload = {
        "question": question,
        "answer_type": "free_text",
        "corpus": corpus,
        "use_agent": USE_AGENT,
    }
    result = {
        "answer": None,
        "sources": [],
        "confidence": None,
        "latency_ms": 0,
        "raw_answer": "",
        "tokens": "",
        "timed_out": False,
        "error": None,
        "used_web_search": False,
    }

    t0 = time.time()
    try:
        resp = session.post(
            f"{BASE}/api/v1/query/stream",
            json=payload,
            stream=True,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return result

        current_event = None
        current_data = ""
        for raw_line in resp.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line
            if line.startswith("event:"):
                current_event = line[len("event:") :].strip()
                current_data = ""
            elif line.startswith("data:"):
                current_data = line[len("data:") :].strip()
                if current_event == "token" and current_data:
                    try:
                        tok = json.loads(current_data)
                        result["tokens"] += tok.get("text", "")
                    except json.JSONDecodeError:
                        pass
                elif current_event == "answer" and current_data:
                    try:
                        ans = json.loads(current_data)
                        result["answer"] = ans.get("answer")
                        result["raw_answer"] = str(ans.get("answer", ""))
                        result["sources"] = ans.get("sources", [])
                        result["confidence"] = ans.get("confidence")
                        result["latency_ms"] = ans.get("latency_ms", 0)
                    except json.JSONDecodeError:
                        pass
                elif current_event == "status" and current_data:
                    try:
                        st = json.loads(current_data)
                        status_val = st.get("status", "")
                        if "web" in status_val.lower() or "search" in status_val.lower():
                            result["used_web_search"] = True
                    except json.JSONDecodeError:
                        pass
                elif current_event == "error" and current_data:
                    result["error"] = current_data
                current_event = None
            elif line == "":
                # SSE event boundary
                pass
    except requests.exceptions.Timeout:
        result["timed_out"] = True
        result["error"] = "timeout"
    except Exception as e:
        result["error"] = str(e)

    result["wall_time_s"] = round(time.time() - t0, 1)

    # If raw_answer is empty but we got tokens, use tokens as fallback
    if not result["raw_answer"] and result["tokens"]:
        result["raw_answer"] = result["tokens"]
        result["answer"] = result["tokens"]

    return result


# ── Scoring ──────────────────────────────────────────────────────────────────


def score_result(result: dict, test: dict) -> dict:
    """Score a single result against expected values."""
    if result["timed_out"] or result["error"]:
        return {"citation": 0, "correctness": 0, "grounding": 0}

    answer_text = str(result.get("answer", "") or "")
    # Also check token stream for content
    full_text = answer_text + " " + str(result.get("tokens", ""))

    # 1. Citation accuracy: does the answer mention the expected section?
    expected_section = test["expected_section"]
    citation_hit = 0
    # Check in answer text
    if re.search(re.escape(expected_section), full_text, re.IGNORECASE):
        citation_hit = 1
    else:
        # Also check source doc_ids
        for src in result.get("sources", []):
            doc_id = str(src.get("doc_id", ""))
            src_text = str(src.get("text", "") or "")
            if re.search(re.escape(expected_section), doc_id + " " + src_text, re.IGNORECASE):
                citation_hit = 1
                break

    # 2. Answer correctness: does the answer contain the expected keyword?
    expected_keyword = test["expected_answer_contains"]
    correctness_hit = 1 if re.search(re.escape(expected_keyword), full_text, re.IGNORECASE) else 0

    # 3. Grounding: does the answer contain [DOC-N] citations?
    grounding_hit = 1 if re.search(r"\[DOC-\d+\]", full_text) else 0

    return {"citation": citation_hit, "correctness": correctness_hit, "grounding": grounding_hit}


# ── Run benchmarks ───────────────────────────────────────────────────────────


def run_benchmark(name: str, tests: list, corpus: str):
    """Run a full benchmark suite and print results."""
    print(f"\n{'=' * 80}")
    print(f"  BENCHMARK: {name} ({len(tests)} questions, corpus={corpus})")
    print(f"{'=' * 80}\n")

    results = []
    total_citation = 0
    total_correctness = 0
    total_grounding = 0
    web_search_count = 0
    corpus_start = time.time()

    for i, test in enumerate(tests, 1):
        q = test["q"]
        short_q = q[:60] + "..." if len(q) > 60 else q
        print(f"[{i:02d}/{len(tests)}] {short_q}")
        sys.stdout.flush()

        res = run_question_sse(q, corpus)
        scores = score_result(res, test)

        total_citation += scores["citation"]
        total_correctness += scores["correctness"]
        total_grounding += scores["grounding"]
        if res.get("used_web_search"):
            web_search_count += 1

        status = "OK" if not res["error"] else f"ERR: {res['error'][:40]}"
        if res["timed_out"]:
            status = "TIMEOUT"

        answer_preview = str(res.get("answer", ""))[:80]
        print(
            f"       Citation={scores['citation']} Correct={scores['correctness']} "
            f"Grounded={scores['grounding']} | {res.get('wall_time_s', 0)}s | {status}"
        )
        if scores["citation"] == 0:
            print(f"       MISS citation: expected '{test['expected_section']}' not found")
        if scores["correctness"] == 0:
            print(f"       MISS keyword: expected '{test['expected_answer_contains']}' not found")
        if scores["grounding"] == 0:
            print("       MISS grounding: no [DOC-N] citations found")
        print(f"       Answer: {answer_preview}...")
        print()

        results.append(
            {
                "question": q,
                "expected_section": test["expected_section"],
                "expected_keyword": test["expected_answer_contains"],
                "citation_score": scores["citation"],
                "correctness_score": scores["correctness"],
                "grounding_score": scores["grounding"],
                "wall_time_s": res.get("wall_time_s", 0),
                "confidence": res.get("confidence"),
                "error": res.get("error"),
                "timed_out": res.get("timed_out", False),
                "used_web_search": res.get("used_web_search", False),
                "answer_preview": str(res.get("answer", ""))[:200],
                "sources_count": len(res.get("sources", [])),
            }
        )

    corpus_time = round(time.time() - corpus_start, 1)
    n = len(tests)

    # ── Summary table ────────────────────────────────────────────────
    print(f"\n{'─' * 80}")
    print(f"  RESULTS: {name}")
    print(f"{'─' * 80}")
    print(f"{'#':<4} {'Citation':<10} {'Correct':<10} {'Grounded':<10} {'Time':<8} {'Question':<40}")
    print(f"{'─' * 4} {'─' * 9} {'─' * 9} {'─' * 9} {'─' * 7} {'─' * 40}")
    for i, r in enumerate(results, 1):
        c = "Y" if r["citation_score"] else "N"
        a = "Y" if r["correctness_score"] else "N"
        g = "Y" if r["grounding_score"] else "N"
        t = f"{r['wall_time_s']}s"
        q = r["question"][:40]
        err = " [TIMEOUT]" if r["timed_out"] else (" [ERR]" if r["error"] else "")
        web = " [WEB]" if r["used_web_search"] else ""
        print(f"{i:<4} {c:<10} {a:<10} {g:<10} {t:<8} {q}{err}{web}")

    print(f"\n{'─' * 80}")
    print(f"  AGGREGATE: {name}")
    print(f"{'─' * 80}")
    print(f"  Citation accuracy:  {total_citation}/{n} = {total_citation / n * 100:.1f}%")
    print(f"  Answer correctness: {total_correctness}/{n} = {total_correctness / n * 100:.1f}%")
    print(f"  Grounding (DOC-N):  {total_grounding}/{n} = {total_grounding / n * 100:.1f}%")
    print(f"  Total time:         {corpus_time}s ({corpus_time / n:.1f}s avg)")
    print(f"  Web search used:    {web_search_count}/{n}")
    print(f"  Timeouts:           {sum(1 for r in results if r['timed_out'])}/{n}")
    print(f"  Errors:             {sum(1 for r in results if r['error'] and not r['timed_out'])}/{n}")
    print()

    return {
        "name": name,
        "corpus": corpus,
        "n": n,
        "citation_pct": round(total_citation / n * 100, 1),
        "correctness_pct": round(total_correctness / n * 100, 1),
        "grounding_pct": round(total_grounding / n * 100, 1),
        "total_time_s": corpus_time,
        "avg_time_s": round(corpus_time / n, 1),
        "web_search_count": web_search_count,
        "results": results,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    all_results = {}

    difc_summary = run_benchmark("DIFC Corpus", difc_tests, "difc")
    all_results["difc"] = difc_summary

    czech_summary = run_benchmark("Czech Corpus", czech_tests, "czech")
    all_results["czech"] = czech_summary

    # ── Final comparison ─────────────────────────────────────────────
    print(f"\n{'=' * 80}")
    print("  FINAL COMPARISON")
    print(f"{'=' * 80}")
    print(f"{'Metric':<25} {'DIFC':<15} {'Czech':<15}")
    print(f"{'─' * 25} {'─' * 14} {'─' * 14}")
    print(f"{'Citation accuracy':<25} {difc_summary['citation_pct']:.1f}%{'':<9} {czech_summary['citation_pct']:.1f}%")
    print(
        f"{'Answer correctness':<25} {difc_summary['correctness_pct']:.1f}%{'':<9} {czech_summary['correctness_pct']:.1f}%"
    )
    print(
        f"{'Grounding (DOC-N)':<25} {difc_summary['grounding_pct']:.1f}%{'':<9} {czech_summary['grounding_pct']:.1f}%"
    )
    print(f"{'Avg time/question':<25} {difc_summary['avg_time_s']}s{'':<10} {czech_summary['avg_time_s']}s")
    print(f"{'Total time':<25} {difc_summary['total_time_s']}s{'':<10} {czech_summary['total_time_s']}s")
    print(
        f"{'Web search used':<25} {difc_summary['web_search_count']}/{difc_summary['n']}{'':<10} {czech_summary['web_search_count']}/{czech_summary['n']}"
    )
    print()

    # Save JSON results
    with open(
        "/Users/viacheslavivannikov/projects/ai-challenge-legal/scripts/benchmark_accuracy_results.json", "w"
    ) as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print("Results saved to scripts/benchmark_accuracy_results.json")
