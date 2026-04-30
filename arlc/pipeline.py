"""Finals pipeline: route -> retrieve -> answer -> format check -> output.

Simplified 3-step pipeline replacing the over-engineered 7-step version.
Validated by CRAG winner + Enterprise RAG winner + our own 19-submission data.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Interfaces expected from teammate modules (imported lazily so finals.py
# can be syntax-checked even before the modules exist)
# ---------------------------------------------------------------------------
#
# router.route(question: str, answer_type: str) -> RouteResult
#     RouteResult dataclass with:
#       .target_doc_ids: list[str] | None  (None = full corpus search)
#       .metadata_answer: Any              (pre-computed answer from index)
#       .metadata_pages: dict[str, int] | None  (doc_id -> page for metadata shortcuts)
#       .is_cross_case: bool
#       .case_ids, .law_names, .article_numbers: list[str]
#
# retriever.retrieve_pages(question, target_doc_ids, max_per_doc, max_total, answer_type)
#     -> list[PageResult]
#     PageResult dataclass: .doc_id, .page_number, .score, .text
#
# answerer_v3.generate_answer(question: str, answer_type: str,
#                             source_pages: list[dict]) -> dict
#     Returns {"answer": ..., "ttft_ms": int, "tpot_ms": int,
#              "total_time_ms": int, "input_tokens": int, "output_tokens": int,
#              "model_name": str}

from arlc.format_guardian import FormatGuardian

# Case metadata for cross-case oracle citation expansion
_CASE_META_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "case_metadata_index.json")
_case_meta_for_oracle: dict = {}
if os.path.exists(_CASE_META_PATH):
    with open(_CASE_META_PATH) as _cmf:
        _raw_cm = json.load(_cmf)
        for _cid, _cinfo in _raw_cm.items():
            _case_meta_for_oracle[_cid.upper()] = _cinfo

# Cross-reference graph for IndexRAG (guy2) + ontology traversal (guy1)
_XREF_GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cross_reference_graph.json")
_xref_graph: dict = {}
if os.path.exists(_XREF_GRAPH_PATH):
    try:
        with open(_XREF_GRAPH_PATH) as _xf:
            _xref_graph = json.load(_xf)
    except (json.JSONDecodeError, OSError):
        _xref_graph = {}

# Comparison keywords for cross-ref expansion
_COMPARISON_RE = re.compile(r"\b(compar|differ|both|earlier|later|versus|vs\.?|distinguish|contrast)\b", re.IGNORECASE)

# Architecture summary for submission
ARCHITECTURE_SUMMARY = (
    "Simplified RAG: deterministic document routing (regex case/law extraction) "
    "-> hybrid tsvector+pgvector retrieval scoped to target docs -> Qwen3-Reranker reranking "
    "-> top-1 page per doc (max 3 total) -> single Sonnet 4.6 call with type-specific "
    "prompts -> Opus 4.6 extended-thinking citation page selection (post-processing). PPQ < 1.3."
)


def _import_pipeline_modules():
    """Import pipeline modules. Fails fast with clear error if missing."""
    route_fn = None
    retrieve_fn = None
    answer_fn = None

    try:
        from arlc.router import route as _route

        route_fn = _route
        print("  router.route: OK")
    except ImportError:
        print("  WARNING: router.py not found, using fallback routing", file=sys.stderr)

    try:
        from arlc.retriever import retrieve_pages as _retrieve_pages

        retrieve_fn = _retrieve_pages
        print("  retriever.retrieve_pages: OK")
    except (ImportError, AttributeError):
        print("  WARNING: retriever.retrieve_pages not found, using fallback", file=sys.stderr)

    try:
        from arlc.answerer import generate_answer as _generate_answer

        answer_fn = _generate_answer
        print("  answerer_v3.generate_answer: OK")
    except ImportError:
        print("  WARNING: answerer_v3.py not found, using fallback answerer", file=sys.stderr)

    return route_fn, retrieve_fn, answer_fn


# ---------------------------------------------------------------------------
# Fallback implementations (used when teammate modules aren't ready yet)
# ---------------------------------------------------------------------------


def _fallback_route(question: str, answer_type: str) -> list[str]:
    """Fallback: return empty list (retriever will do corpus-wide search)."""
    return []


def _fallback_retrieve_pages(
    question: str,
    target_doc_ids: list[str] | None = None,
    max_per_doc: int = 1,
    max_total: int = 3,
    answer_type: str = "",
    include_context_pages: bool = False,
    use_llm_rerank: bool = False,
    boost_pages: dict | None = None,
    case_doc_groups: dict | None = None,
    corpus: str = "difc",
) -> list[dict]:
    """Fallback: use existing retriever.retrieve() and convert format."""
    from arlc.retriever import retrieve

    chunks = retrieve(question, n_results=25)

    # Group by doc_id, take top-1 page per doc
    seen_docs = {}
    for chunk in chunks:
        doc_id = chunk.get("pdf_id", chunk.get("doc_id", ""))
        if not doc_id or doc_id in seen_docs:
            continue
        page = chunk.get("page", chunk.get("page_number", 1))
        seen_docs[doc_id] = {
            "doc_id": doc_id,
            "page_number": page,
            "page_numbers": [page],
            "text": chunk.get("text", ""),
            "score": chunk.get("score", 0.0),
        }
        if len(seen_docs) >= max_total:
            break

    return list(seen_docs.values())


def _fallback_generate_answer(question: str, answer_type: str, source_pages: list[dict]) -> dict:
    """Fallback: use existing answerer.answer_question()."""
    from arlc.answerer import answer_question
    from arlc.retriever import retrieve

    chunks = retrieve(question, n_results=25)
    result = answer_question(question, answer_type, chunks)
    return result


# ---------------------------------------------------------------------------
# Format checking (inline from FormatGuardian — key checks only)
# ---------------------------------------------------------------------------


def _format_check(result: dict) -> dict:
    """Run programmatic format checks on a single result. No LLM calls."""
    guardian = FormatGuardian()
    return guardian.guard_result(result)


# ---------------------------------------------------------------------------
# Trick question detection
# ---------------------------------------------------------------------------

# These concepts do not exist in DIFC law (civil/commercial jurisdiction only).
# For questions about them, gold G-score expects EMPTY pages [] (any citation = G=0.0).
# free_text answer must start: "There is no information on this question in the provided documents."
#
# Level 1: Known exact-match keywords (all warmup trick questions matched here).
# Level 2: Semantic concepts — any "criminal X" phrase where X suggests criminal law.
# Level 3: Source text check — if concept not in retrieved text, likely trick.
#
# Finals may introduce NEW criminal-law concepts not in the warmup list, so we
# cast a wider net than the warmup-era 28-keyword list.
_TRICK_KEYWORDS = [
    # Miranda rights
    "miranda",
    "miranda rights",
    "miranda warning",
    # Jury system (NOTE: bare "jury" omitted — it matches "injury"; use regex Level 2 instead)
    "grand jury",
    "trial by jury",
    "jury trial",
    "jury system",
    "jury decide",
    "did the jury",
    "what did the jury",
    "jury verdict",
    "jury deliberat",
    # Plea
    "plea bargain",
    "plea deal",
    "plea guilty",
    "guilty plea",
    "plea agreement",
    "no contest plea",
    "nolo contendere",
    # Parole (avoid bare "probation" — matches "probation period" in employment law)
    "parole",
    "parole board",
    "parole officer",
    "criminal probation",
    "probation order",
    "on probation",
    "community service order",
    # Bail / bond (avoid bare "bail" — matches "bailment" in property law)
    "bail bond",
    "post bail",
    "bail hearing",
    "bail application",
    "granted bail",
    "denied bail",
    "release on bail",
    "bail amount",
    "bail conditions",
    # Criminal procedure concepts
    "criminal jurisdiction",
    "criminal law",
    "criminal case",
    "criminal charge",
    "criminal prosecution",
    "criminal conviction",
    "criminal sentencing",
    "criminal proceeding",
    "criminal court",
    "criminal trial",
    "criminal matter",
    "criminal record",
    "criminal defendant",
    "criminal liability",
    "criminal penalty",
    "criminal sanction",
    "criminal fine",
    # Habeas corpus
    "habeas corpus",
    # Arraignment / indictment
    "arraignment",
    "indictment",
    "grand jury indictment",
    # Felony / misdemeanor
    "felony",
    "misdemeanor",
    "petty crime",
    # Acquittal
    "acquittal",
    "criminal acquittal",
    "not guilty verdict",
    # Criminal appeal
    "criminal appeal",
    # Police powers
    "police caution",
    "police custody",
    "right to remain silent",
    "right to silence",
    "police arrest",
    "search warrant",
    "arrest warrant",
    # Constitutional protections (US/UK specific)
    "fifth amendment",
    "fourth amendment",
    "sixth amendment",
    "double jeopardy",
    "self-incrimination",
    # Prison / custody
    "prison sentence",
    "jail sentence",
    "imprisonment",
    "incarceration",
    "prison term",
    "custodial sentence",
    # Extradition
    "extradition",
    # Death penalty
    "death penalty",
    "capital punishment",
    # Prosecution
    "district attorney",
    "prosecutor",
    "prosecution witness",
    "beyond reasonable doubt",
    "prosecution case",
]

# Level 2 regex: catch "criminal X", "convicted of", "jury" as whole word, etc.
# Using word boundaries avoids false positives like "injury" matching "jury".
_CRIMINAL_PREFIX_RE = re.compile(
    r"\bcriminal\s+\w+"  # "criminal law", "criminal charge", etc.
    r"|\b\w+\s+crime\b"  # "war crime", "organized crime", etc.
    r"|\bconvicted\s+of\b"  # "convicted of fraud"
    r"|\bsentenced\s+to\b"  # "sentenced to prison"
    r"|\bjury\b"  # "use a jury", "a jury of peers" (avoids "injury")
    r"|\bprosecutor\b"  # "the prosecutor argued"
    r"|\bprison\b"  # "prison sentence", "prison term"
    r"|\bjail\b",  # "jail time", "post bail/jail"
    re.IGNORECASE,
)


def _is_trick_question(question: str, source_text: str = "") -> bool:
    """Detect questions about concepts that don't exist in DIFC jurisdiction.

    Args:
        question: The question text.
        source_text: Combined retrieved page text (optional). If provided,
            performs Level 3 check: concept in question but not in source
            strongly implies trick question.
    """
    q = question.lower()

    # Level 1: Exact keyword match — ALWAYS triggers, even with case ID.
    # These keywords are inherently criminal/non-DIFC concepts (e.g. "miranda rights").
    if any(kw in q for kw in _TRICK_KEYWORDS):
        return True

    # Safety guard: questions referencing a specific case ID are real case questions,
    # not trick questions (e.g., "Was imprisonment discussed in CFI 123/2024?" is real).
    # Only applies to Level 2 (regex) and Level 3 (source text) checks.
    if re.search(r"(?:CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)\s*[\-]?\s*\d+\s*(?:/|\s+of\s+)\d{4}", question, re.IGNORECASE):
        return False

    # Level 2: Regex for "criminal X" patterns not already in keyword list
    if _CRIMINAL_PREFIX_RE.search(question):
        return True

    # Level 3: Source text doesn't address the concept (only for free_text).
    # If the question asks about "prison" but no retrieved page mentions it,
    # the concept almost certainly doesn't exist in the DIFC documents.
    if source_text:
        src_lower = source_text.lower()
        # Use specific criminal phrases to avoid false positives on civil terms
        # "custody" removed — appears in family law, corporate custody contexts
        # "sentence" removed — common English word in legal writing
        # "bail" removed — appears in bailment, property law
        # "probation" removed — appears in employment probation periods
        CONCEPT_MARKERS = [
            "prison",
            "jail",
            "criminal",
            "prosecution",
            "conviction",
            "verdict",
            "jury",
            "plea",
            "parole",
            "arraign",
            "indictment",
            "felony",
            "misdemeanor",
            "acquittal",
            "habeas",
            "extradition",
            "criminal jurisdiction",
        ]
        q_has_concept = any(m in q for m in CONCEPT_MARKERS)
        src_has_concept = any(m in src_lower for m in CONCEPT_MARKERS)
        if q_has_concept and not src_has_concept:
            return True

    return False


def _get_all_case_doc_pages(route_result, meta_pages: dict | None = None, max_per_case: int = 1) -> list[dict]:
    """Get page 1 (or metadata page) from docs for ALL cases in the question.

    Cross-case questions (e.g. 'judges in common: DEC 001/2025 and TCD 001/2024?')
    cite max_per_case docs per case. Default 1 per case matches gold scoring:
    citing extra docs from the same case hurts precision in F-beta(2.5).
    """
    pages = []
    seen: set[str] = set()
    case_ids = getattr(route_result, "case_ids", [])
    for case_id in case_ids:
        case_upper = case_id.upper().strip()
        case_info = _case_meta_for_oracle.get(case_upper, {})
        case_count = 0
        for doc in case_info.get("docs", []):
            if case_count >= max_per_case:
                break
            doc_id = doc.get("doc_id", "")
            if doc_id and doc_id not in seen:
                page = (meta_pages or {}).get(doc_id, 1)
                pages.append({"doc_id": doc_id, "page_numbers": [page]})
                seen.add(doc_id)
                case_count += 1
    return pages


# ---------------------------------------------------------------------------
# Single question processor
# ---------------------------------------------------------------------------


def _pages_to_chunk_pages(pages) -> list[dict]:
    """Convert PageResult list to chunk_pages format, grouping by doc_id.

    Carries the chunk_id of the first (highest-scored) page seen per doc,
    since callers typically pass pages already sorted by descending score.
    Also carries start_line/end_line for TXT sources (first page wins, same as
    chunk_id).
    """
    from collections import defaultdict

    by_doc: dict[str, list[int]] = defaultdict(list)
    # Track the first chunk_id / line range seen per doc (highest-scored when pre-sorted).
    doc_chunk_id: dict[str, str] = {}
    doc_start_line: dict[str, int] = {}
    doc_end_line: dict[str, int] = {}

    for p in pages:
        # Handle both PageResult dataclass and dict
        doc_id = p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", "")
        page_num = p.page_number if hasattr(p, "page_number") else p.get("page_number", p.get("page", 1))
        chunk_id = (p.chunk_id if hasattr(p, "chunk_id") else p.get("chunk_id", "")) or ""
        start_line = (
            (p.start_line if hasattr(p, "start_line") else p.get("start_line"))
            if doc_id not in doc_start_line
            else None
        )
        end_line = (p.end_line if hasattr(p, "end_line") else p.get("end_line")) if doc_id not in doc_end_line else None
        if doc_id:
            by_doc[doc_id].append(page_num)
            if doc_id not in doc_chunk_id and chunk_id:
                doc_chunk_id[doc_id] = chunk_id
            if start_line is not None:
                doc_start_line[doc_id] = start_line
            if end_line is not None:
                doc_end_line[doc_id] = end_line

    result = []
    for doc_id, pns in by_doc.items():
        entry: dict = {"doc_id": doc_id, "page_numbers": sorted(set(pns)), "chunk_id": doc_chunk_id.get(doc_id, "")}
        if doc_id in doc_start_line:
            entry["start_line"] = doc_start_line[doc_id]
        if doc_id in doc_end_line:
            entry["end_line"] = doc_end_line[doc_id]
        result.append(entry)
    return result


def _validate_chunk_pages(answer_result: dict, retrieved_pages) -> list[dict]:
    """Remove hallucinated page citations not in retrieved set (Ilya Rice technique).

    The answerer sometimes cites page numbers that weren't in the retrieved context.
    This filters them out, protecting G score from hallucinated references.
    Falls back to retrieved pages if validation removes everything.
    """
    retrieved_set = set()
    for p in retrieved_pages:
        # Handle both PageResult dataclass and dict
        doc_id = p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", "")
        page_num = p.page_number if hasattr(p, "page_number") else p.get("page_number", p.get("page", 1))
        if doc_id:
            retrieved_set.add((doc_id, page_num))

    valid_chunks = []
    for cp in answer_result.get("chunk_pages", []):
        doc_id = cp.get("doc_id", "")
        valid_pages = [pn for pn in cp.get("page_numbers", []) if (doc_id, pn) in retrieved_set]
        if valid_pages:
            valid_chunks.append({"doc_id": doc_id, "page_numbers": valid_pages})

    # If validation removed everything, fall back to retrieved pages
    if not valid_chunks and retrieved_pages:
        return _pages_to_chunk_pages(retrieved_pages)
    return valid_chunks


def _enforce_page_limit(chunk_pages: list[dict], max_pages: int = 3) -> list[dict]:
    """Enforce hard cap on total cited pages (max 1 page per doc, max_pages docs).

    Cross-case questions with many associated documents (e.g., TCD cases with 4+
    docs) can exceed the 3-page limit. This truncates to the first max_pages docs,
    keeping only the first page_number per doc.
    """
    total = sum(len(cp.get("page_numbers", [])) for cp in chunk_pages)
    if total <= max_pages:
        return chunk_pages

    # Keep first page per doc, truncate to max_pages docs
    result = []
    count = 0
    for cp in chunk_pages:
        if count >= max_pages:
            break
        pns = cp.get("page_numbers", [])
        if not pns:
            continue
        result.append({"doc_id": cp["doc_id"], "page_numbers": [pns[0]]})
        count += 1
    return result


def _attach_source_text(chunk_pages: list[dict], source_pages: list[dict]) -> None:
    """Enrich chunk_pages dicts with source text and court decision metadata (in-place).

    The page verifier and LLM page verification steps create new chunk_pages dicts
    that lack the 'text' field. This function copies text from source_pages back onto
    chunk_pages so downstream consumers (e.g. the web frontend) have source text.

    Also copies court decision metadata fields (source_type, case_number, ecli, etc.)
    when the source page is a court decision — these are not present in the LLM-generated
    chunk_pages and must be re-attached so SourceCitation is populated correctly.

    Lookup priority: exact (doc_id, page_number) match first, then any entry for doc_id.
    """
    if not source_pages or not chunk_pages:
        return
    # Build lookups keyed by (doc_id, page_number) and by doc_id alone
    sp_by_page: dict[tuple[str, int], dict] = {(sp["doc_id"], sp.get("page_number", 0)): sp for sp in source_pages}
    sp_by_doc: dict[str, dict] = {}
    for sp in source_pages:
        sp_by_doc.setdefault(sp["doc_id"], sp)

    _court_fields = ("source_type", "case_number", "ecli", "decision_date", "court", "category", "legal_thesis")

    for cp in chunk_pages:
        doc_id = cp.get("doc_id", "")
        for pn in cp.get("page_numbers", []):
            sp = sp_by_page.get((doc_id, pn)) or sp_by_doc.get(doc_id)
            if not sp:
                continue
            if not cp.get("text") and sp.get("text"):
                cp["text"] = sp["text"]
            # Re-attach source_type for all non-default types (court_decision, txt)
            if sp.get("source_type") and not cp.get("source_type"):
                if sp["source_type"] == "court_decision":
                    for field in _court_fields:
                        cp[field] = sp.get(field)
                else:
                    cp["source_type"] = sp["source_type"]
            break


def _boost_cross_references(pages, question: str):
    """Add cross-referenced pages from the graph when targets are resolved.

    # Cross-reference retrieval from IndexRAG (guy2) + ontology traversal (guy1)

    For comparison questions, always include referenced doc pages.
    Cap: max 1 cross-ref page per 3 existing pages.
    Returns the (possibly extended) pages list.
    """
    if not _xref_graph or not pages:
        return pages

    is_comparison = bool(_COMPARISON_RE.search(question))

    # Collect existing (doc_id, page_number) pairs
    existing = set()
    for p in pages:
        doc_id = p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", "")
        page_num = p.page_number if hasattr(p, "page_number") else p.get("page_number", 1)
        existing.add((doc_id, page_num))

    # Max cross-ref additions
    max_additions = max(1, len(pages) // 3)
    additions = []

    for p in pages:
        if len(additions) >= max_additions:
            break
        doc_id = p.doc_id if hasattr(p, "doc_id") else p.get("doc_id", "")
        page_num = str(p.page_number if hasattr(p, "page_number") else p.get("page_number", 1))

        doc_refs = _xref_graph.get(doc_id, {})
        page_refs = doc_refs.get(page_num, [])

        for ref in page_refs:
            if len(additions) >= max_additions:
                break
            target_doc = ref.get("target_doc")
            target_page = ref.get("target_page")
            if target_doc is None or target_page is None:
                continue
            # For non-comparison questions, only add if target is a different doc
            if not is_comparison and target_doc == doc_id:
                continue
            if (target_doc, target_page) in existing:
                continue
            # Create a lightweight PageResult-like object
            from types import SimpleNamespace

            additions.append(
                SimpleNamespace(
                    doc_id=target_doc,
                    page_number=target_page,
                    score=0.3,  # low score — cross-ref supplement
                    text="",  # text will be empty; answerer handles gracefully
                ),
            )
            existing.add((target_doc, target_page))
            print(f"  [cross-ref] Added {target_doc}:p{target_page} from ref in {doc_id}:p{page_num}")

    if additions:
        return list(pages) + additions
    return pages


def _pages_to_source_dicts(pages) -> list[dict]:
    """Convert PageResult objects to dicts for the answerer.

    Court decision metadata (source_type, ecli, case_number, etc.) is included
    when present so it flows through to source_pages and ultimately chunk_pages,
    where _attach_source_text re-attaches it after LLM citation generation.
    """
    result = []
    for p in pages:
        if hasattr(p, "doc_id"):
            d: dict = {
                "doc_id": p.doc_id,
                "page_number": p.page_number,
                "page_numbers": [p.page_number],
                "score": p.score,
                "text": p.text,
            }
            # Propagate source_type for all non-default source types
            src_type = getattr(p, "source_type", None)
            if src_type:
                d["source_type"] = src_type
            # Include court decision metadata when present
            if src_type == "court_decision":
                d["case_number"] = p.case_number
                d["ecli"] = p.ecli
                d["decision_date"] = p.decision_date
                d["court"] = p.court
                d["category"] = p.category
                d["legal_thesis"] = p.legal_thesis
            result.append(d)
        else:
            result.append(p)
    return result


async def _process_question(
    question_data: dict,
    route_fn,
    retrieve_fn,
    answer_fn,
    semaphore: asyncio.Semaphore,
    on_status=None,
    on_token=None,
    corpus: str = "difc",
    web_mode: bool = False,
) -> dict:
    """Process a single question through the pipeline.

    on_status: optional async or sync callback(stage: str) called at each stage transition.
    """
    question = question_data["question"]
    answer_type = question_data["answer_type"]
    question_id = question_data["id"]
    laws = question_data.get("laws")

    def _emit(stage: str):
        if on_status is not None:
            on_status(stage)

    async with semaphore:
        # Route first (fast, deterministic, no LLM) — outside timeout so we
        # always have doc IDs available for fallback citations if retrieval hangs.
        _emit("routing")
        route_result = await asyncio.to_thread(route_fn, question, answer_type)
        if hasattr(route_result, "target_doc_ids"):
            _fallback_docs = route_result.target_doc_ids or []
        elif isinstance(route_result, (list, tuple)):
            _fallback_docs = list(route_result)
        else:
            _fallback_docs = []

        MAX_QUESTION_RETRIES = 2
        _retrieval_cache: dict = {}  # survives timeouts so Sonnet fallback can reuse pages
        for _q_attempt in range(1 + MAX_QUESTION_RETRIES):
            try:
                # Wrap retrieval + answering in a timeout to prevent hangs.
                # 600s: worst case = lock_wait(120s) + cross_encoder(60s) + LLM retries(100s) + LLM(90s)
                result = await asyncio.wait_for(
                    _process_question_inner(
                        question,
                        answer_type,
                        question_id,
                        route_result,
                        retrieve_fn,
                        answer_fn,
                        _retrieval_cache=_retrieval_cache,
                        on_status=on_status,
                        on_token=on_token,
                        corpus=corpus,
                        web_mode=web_mode,
                        laws=laws,
                    ),
                    timeout=600,  # 10 min max per question (allows for rate limit retries)
                )
                break  # success — exit retry loop

            except asyncio.TimeoutError:
                if _q_attempt < MAX_QUESTION_RETRIES:
                    print(
                        f"  TIMEOUT processing {question_id[:16]} (>600s), retry {_q_attempt + 1}/{MAX_QUESTION_RETRIES}",
                        file=sys.stderr,
                    )
                    await asyncio.sleep(10)  # brief pause before retry
                    continue

                # All retries exhausted — try Sonnet fallback if we have cached retrieval pages
                print(f"  TIMEOUT processing {question_id[:16]} (>600s), all retries exhausted", file=sys.stderr)
                cached_pages = _retrieval_cache.get("source_pages")
                if cached_pages:
                    print(
                        f"  SONNET FALLBACK: {question_id[:16]} using {len(cached_pages)} cached pages",
                        file=sys.stderr,
                    )
                    try:
                        from arlc.answerer import generate_answer as _gen_answer_fallback

                        t_fb_start = time.monotonic()
                        fb_result = await asyncio.wait_for(
                            _gen_answer_fallback(
                                question,
                                answer_type,
                                cached_pages,
                                question_id,
                                metadata_answer=_retrieval_cache.get("metadata_answer"),
                                force_model="claude-sonnet-4-6",
                            ),
                            timeout=120,  # Sonnet is fast — 120s is generous
                        )
                        t_fb_total = time.monotonic() - t_fb_start
                        result = {
                            "answer": fb_result.answer,
                            "chunk_pages": getattr(fb_result, "chunk_pages", []),
                            "ttft_ms": getattr(fb_result, "ttft_ms", 1),
                            "tpot_ms": getattr(fb_result, "tpot_ms", 0),
                            "total_time_ms": max(1, int(t_fb_total * 1000)),
                            "input_tokens": getattr(fb_result, "input_tokens", 0),
                            "output_tokens": getattr(fb_result, "output_tokens", 0),
                            "model_name": "sonnet-fallback",
                        }
                        print(
                            f"  SONNET FALLBACK OK: {question_id[:16]} answer={str(fb_result.answer)[:60]}",
                            file=sys.stderr,
                        )
                        break
                    except Exception as fb_exc:
                        print(f"  SONNET FALLBACK FAILED: {question_id[:16]} {fb_exc}", file=sys.stderr)

                # Final fallback: null/False answer
                fallback_answer = False if answer_type == "boolean" else None
                fallback_pages = [{"doc_id": d, "page_numbers": [1]} for d in _fallback_docs]
                result = {
                    "answer": fallback_answer,
                    "ttft_ms": 1,
                    "tpot_ms": 0,
                    "total_time_ms": 600000,
                    "chunk_pages": fallback_pages,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "model_name": "timeout",
                }

            except Exception as e:
                if _q_attempt < MAX_QUESTION_RETRIES:
                    print(f"  ERROR processing {question_id[:16]}: {e}, retry {_q_attempt + 1}", file=sys.stderr)
                    await asyncio.sleep(5)
                    continue
                print(f"  ERROR processing {question_id[:16]}: {e}", file=sys.stderr)
                import traceback

                traceback.print_exc(file=sys.stderr)
                result = {
                    "answer": None,
                    "ttft_ms": 1,
                    "tpot_ms": 0,
                    "total_time_ms": 0,
                    "chunk_pages": [],
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "model_name": "error",
                }

        # Add question metadata
        result["id"] = question_id
        result["question"] = question
        result["answer_type"] = answer_type

        # Step 4: Format check (programmatic, no LLM).
        # Skip in web_mode — FormatGuardian strips markdown and enforces char limits.
        if not web_mode:
            result = _format_check(result)

        return result


async def _process_question_inner(
    question: str,
    answer_type: str,
    question_id: str,
    route_result,
    retrieve_fn,
    answer_fn,
    _retrieval_cache: dict | None = None,
    on_status=None,
    on_token=None,
    corpus: str = "difc",
    web_mode: bool = False,
    laws: list[str] | None = None,
) -> dict:
    """Inner pipeline logic (retrieval + answering), wrapped in timeout by caller.

    route_result is pre-computed by the caller so doc IDs survive a timeout.
    _retrieval_cache: if provided, populated with source_pages after retrieval for fallback use.
    web_mode: passed through to answer_fn (generate_answer) for markdown formatting.
        Also controls source text attachment to chunk_pages for the web frontend.
    """
    t_start = time.monotonic()

    # Extract target_doc_ids from RouteResult (or plain list)
    if hasattr(route_result, "target_doc_ids"):
        target_docs = route_result.target_doc_ids
        metadata_answer = route_result.metadata_answer
        boost_pages = getattr(route_result, "metadata_pages", None)
        # Suppress parties page boost for free_text questions.
        # "parties" metadata_type triggers on any mention of "defendant"/"claimant",
        # but free_text questions mentioning parties (e.g. "what did the Defendant's
        # representative assert") are NOT asking "who is the defendant" — the boost
        # to page 1 overrides the cross-encoder's correct deeper-page selection.
        _meta_type = getattr(route_result, "metadata_type", None)
        if _meta_type == "parties" and answer_type not in ("name", "names"):
            boost_pages = None
    elif isinstance(route_result, (list, tuple)):
        target_docs = list(route_result)
        metadata_answer = None
        boost_pages = None
    else:
        target_docs = None
        metadata_answer = None
        boost_pages = None

    # Step 2: Fast-path oracle checks BEFORE retrieval.
    # The answerer's oracle can answer judge/party/date/claim comparisons
    # directly from case_metadata_index — no retrieval needed.
    # Skipping retrieval avoids 60-300s cross-encoder scoring for cross-case queries.
    from arlc.answerer import _lookup_oracle

    # Fast path A: router pre-computed the answer (date/claim comparisons)
    # Guard: skip if answer is a list of dicts (router bug for list-format parties) or
    # if it's a free_text question (parties metadata is never a valid free_text answer).
    if (
        metadata_answer is not None
        and answer_type != "free_text"
        and not (isinstance(metadata_answer, list) and metadata_answer and isinstance(metadata_answer[0], dict))
    ):
        t_total = time.monotonic() - t_start
        # Use metadata_pages from router for correct data page citations (e.g. date=p.2, claim=p.5)
        meta_pages = boost_pages or {}
        # Cite ALL docs from ALL cases (not just target_docs primary docs).
        # Platform gold for cross-case questions expects p.1 from every document in both cases.
        fallback_pages = _get_all_case_doc_pages(route_result, meta_pages)
        if not fallback_pages:
            # Fallback to target_docs if no case metadata found
            fallback_pages = [{"doc_id": d, "page_numbers": [meta_pages.get(d, 1)]} for d in (target_docs or [])]
        return {
            "answer": metadata_answer,
            "chunk_pages": _enforce_page_limit(fallback_pages),
            "ttft_ms": 1,
            "tpot_ms": 0,
            "total_time_ms": max(1, int(t_total * 1000)),
            "input_tokens": 0,
            "output_tokens": 0,
            "model_name": "oracle",
        }

    # Fast path B: answerer oracle can answer from case metadata (judge/party booleans)
    oracle_result = _lookup_oracle(question, answer_type, [])
    if oracle_result is not None:
        t_total = time.monotonic() - t_start
        # For cross-case questions, expand to ALL docs from ALL cases (oracle only
        # cites primary docs). For single-case questions (e.g. judge-change), the
        # oracle already returns the correct specific docs — don't override them.
        case_ids = getattr(route_result, "case_ids", [])
        if len(case_ids) >= 2:
            # Pass boost_pages so expansion uses metadata page numbers (e.g. date=p.2)
            # instead of defaulting to page 1 for all docs.
            all_case_pages = _get_all_case_doc_pages(route_result, boost_pages)
            chunk_pages = all_case_pages or oracle_result.chunk_pages
        else:
            chunk_pages = oracle_result.chunk_pages
        # Cap oracle pages at 3 (matching pipeline constraints).
        # Even if oracle knows 5 judges, citing 5 pages hurts precision.
        chunk_pages = _enforce_page_limit(chunk_pages, max_pages=3)
        return {
            "answer": oracle_result.answer,
            "chunk_pages": chunk_pages,
            "ttft_ms": 1,
            "tpot_ms": 0,
            "total_time_ms": max(1, int(t_total * 1000)),
            "input_tokens": 0,
            "output_tokens": 0,
            "model_name": "oracle",
        }

    # Fast path C: Trick questions — DIFC has no criminal jurisdiction.
    # Gold G-score expects EMPTY chunk_pages []. Any page citation = G=0.0.
    # Skip retrieval entirely to save time and avoid wrong citations.
    # Handles ALL answer types: free_text returns "There is no information...",
    # deterministic types (boolean/number/name/names/date) return None.
    # Only for DIFC corpus — other jurisdictions (Czech, UK, AU) have criminal law.
    if corpus == "difc" and _is_trick_question(question):
        t_total = time.monotonic() - t_start
        if answer_type == "free_text":
            trick_answer = "There is no information on this question in the provided documents. The DIFC Courts operate exclusively as a civil and commercial jurisdiction and do not have criminal jurisdiction."
        else:
            trick_answer = None  # deterministic trick answers return null
        return {
            "answer": trick_answer,
            "chunk_pages": [],  # MUST be empty — gold expects no pages for trick questions
            "ttft_ms": 1,
            "tpot_ms": 0,
            "total_time_ms": max(1, int(t_total * 1000)),
            "input_tokens": 0,
            "output_tokens": 0,
            "model_name": "rule-based",
        }

    # Step 2b: Retrieve pages from target documents (normal path)
    if on_status is not None:
        on_status("retrieving")
    is_free_text = answer_type == "free_text"
    # Adaptive max_per_doc by answer type (verified against gold distribution):
    # - free_text: 33% need 2+ pages from same doc → mpd=2
    # - boolean: 22% need 2+ pages → mpd=2 (appeals span pages)
    # - name: 76% need 2 docs (cross-case comparisons like "which case earlier") → mpd=2
    # - number/names/date: 90-96% need only 1 page → mpd=1
    _mpd = 2 if answer_type in ("free_text", "boolean", "name") else 1
    _n_target = len(target_docs) if target_docs else 0
    # Only expand max_total for free_text (summaries needing all CPs).
    # Boolean/deterministic with many routed docs (e.g., TCD 8 docs) should stay at 3
    # — gold for boolean is almost always 1-2 pages.
    _max_total = max(3, _n_target) if (_n_target > 3 and answer_type == "free_text") else 3

    # Build cross-case fair representation groups: for questions spanning 2+ cases,
    # ensures at least 1 page per case even when one case's docs score much higher.
    # (93 gold questions span 2+ cases; without fairness, case B can get 0 pages.)
    _case_doc_groups: dict[str, list[str]] | None = None
    _route_case_ids = getattr(route_result, "case_ids", [])
    if len(_route_case_ids) >= 2 and target_docs:
        _target_set = set(target_docs)
        _groups: dict[str, list[str]] = {}
        for _cid in _route_case_ids:
            _cinfo = _case_meta_for_oracle.get(_cid.upper().strip(), {})
            _cdocs = [d.get("doc_id", "") for d in _cinfo.get("docs", []) if d.get("doc_id", "") in _target_set]
            if _cdocs:
                _groups[_cid] = _cdocs
        if len(_groups) >= 2:
            _case_doc_groups = _groups

    pages = await asyncio.to_thread(
        retrieve_fn,
        question,
        target_docs,
        _mpd,
        _max_total,
        answer_type,
        include_context_pages=is_free_text,
        use_llm_rerank=is_free_text,  # re-enabled: now uses llm_router (working endpoints)
        boost_pages=boost_pages,
        case_doc_groups=_case_doc_groups,
        corpus=corpus,
        on_status=on_status,
        laws=laws,
    )

    # Low-confidence fallback is handled in retriever.py (threshold 0.5)

    # Cross-reference boosting: add pages from linked docs (comparison questions benefit most)
    pages = _boost_cross_references(pages, question)

    # Convert PageResult objects to dicts for the answerer
    source_pages = _pages_to_source_dicts(pages)

    # Cache source_pages so the outer retry loop can reuse them for Sonnet fallback
    if _retrieval_cache is not None:
        _retrieval_cache["source_pages"] = source_pages
        _retrieval_cache["metadata_answer"] = metadata_answer

    # Level 3 trick detection: concept in question but absent from retrieved source text.
    # This catches trick questions that use novel phrasing not in _TRICK_KEYWORDS.
    # Only for DIFC corpus — other jurisdictions (Czech, UK, AU) have criminal law.
    if corpus == "difc" and source_pages:
        combined_src = " ".join(p.get("text", "") for p in source_pages)
        if _is_trick_question(question, source_text=combined_src):
            t_total = time.monotonic() - t_start
            if answer_type == "free_text":
                trick_answer = "There is no information on this question in the provided documents. The DIFC Courts operate exclusively as a civil and commercial jurisdiction and do not have criminal jurisdiction."
            else:
                trick_answer = None
            return {
                "answer": trick_answer,
                "chunk_pages": [],
                "ttft_ms": 1,
                "tpot_ms": 0,
                "total_time_ms": max(1, int(t_total * 1000)),
                "input_tokens": 0,
                "output_tokens": 0,
                "model_name": "rule-based",
            }

    # Step 3: Generate answer using source page text (300s inner timeout)
    # 300s allows for rate-limit retries (10s+30s+60s=100s backoff + actual LLM time)
    if on_status is not None:
        n_pages = len(source_pages) if source_pages else 0
        on_status(f"answering:{n_pages}")
    try:
        if asyncio.iscoroutinefunction(answer_fn):
            answer_result = await asyncio.wait_for(
                answer_fn(
                    question,
                    answer_type,
                    source_pages,
                    question_id,
                    metadata_answer=metadata_answer,
                    on_token=on_token,
                    web_mode=web_mode,
                ),
                timeout=300.0,
            )
        else:
            answer_result = await asyncio.wait_for(
                asyncio.to_thread(answer_fn, question, answer_type, source_pages),
                timeout=300.0,
            )
    except asyncio.TimeoutError:
        print(f"  INNER TIMEOUT: {question_id[:12]} answer_fn >300s", file=sys.stderr)
        from arlc.answerer import AnswerResult

        answer_result = AnswerResult(answer=None, chunk_pages=[])

    t_total = time.monotonic() - t_start

    # Convert AnswerResult dataclass to dict if needed
    if hasattr(answer_result, "answer"):
        result = {
            "answer": answer_result.answer,
            "chunk_pages": getattr(answer_result, "chunk_pages", []),
            "ttft_ms": getattr(answer_result, "ttft_ms", 1),
            "tpot_ms": getattr(answer_result, "tpot_ms", 0),
            "total_time_ms": getattr(answer_result, "total_time_ms", 0),
            "input_tokens": getattr(answer_result, "input_tokens", 0),
            "output_tokens": getattr(answer_result, "output_tokens", 0),
            "cache_read_tokens": getattr(answer_result, "cache_read_tokens", 0),
            "cache_write_tokens": getattr(answer_result, "cache_write_tokens", 0),
            "model_name": getattr(answer_result, "model_name", "claude-sonnet-4-6"),
        }
    else:
        result = answer_result

    # Attach source text to chunk_pages for non-PDF corpora (e.g. Czech corpus).
    # This is called again after each verification step that may replace chunk_pages.
    _attach_source_text(result.get("chunk_pages", []), source_pages)

    # Step 4: Answer-grounded page verification.
    # Checks if cited pages actually contain evidence for the answer.
    # If not, scans adjacent/all pages in the doc to find the correct one.
    # This is deterministic (no LLM) so it adds 0 PPQ.
    if result.get("answer") is not None and result.get("model_name") != "oracle":
        try:
            from arlc.page_verifier import verify_pages as _verify_pages

            _chunk_pages = result.get("chunk_pages", [])
            if _chunk_pages:
                _verified_pages = _verify_pages(
                    question,
                    result["answer"],
                    answer_type,
                    _chunk_pages,
                    # Enable LLM fallback for free_text and boolean — keyword matching is
                    # unreliable for paraphrased answers. Exact-match types (date/number/name)
                    # have strong keyword signals and don't benefit from an extra LLM call.
                    use_llm_fallback=(answer_type in ("free_text", "boolean")),
                )
                _step4_changed = str(_chunk_pages) != str(_verified_pages)
                if _step4_changed:
                    print(
                        f"  [page-verify-v2] {question_id[:12]}... pages updated: {_chunk_pages} -> {_verified_pages}",
                        file=sys.stderr,
                    )
                result["chunk_pages"] = _verified_pages
                # Verifier returns new dicts without text — re-attach from source_pages
                _attach_source_text(result["chunk_pages"], source_pages)
        except Exception as _pv2_err:
            _step4_changed = False
            print(f"  [page-verify-v2] {question_id[:12]}... error: {_pv2_err}", file=sys.stderr)
    else:
        _step4_changed = False

    # Step 3.5: Second-pass LLM page verification.
    # SKIP if Step 4 already corrected pages — Step 3.5 uses original retriever pages
    # as its reference set, so it would silently undo Step 4's corrections.
    # The first-pass answer cites up to 3 pages; this verifier checks which of the
    # top-5 retrieved pages genuinely support the answer, filtering over-citations.
    # Gated to free_text/boolean (highest page-error rates) with 2+ retrieved pages.
    # Uses lightweight LLM call (max_tokens=20 — just page numbers) to stay lightweight.
    # PPQ impact: ~60% of questions have 2+ pages, so average PPQ rises ~0.6 * 1 = +0.6
    # PPQ but the gating keeps it well under 1.3 total.
    if (
        not _step4_changed  # Don't undo Step 4's corrections
        and answer_type in ("free_text", "boolean")
        and len(pages) >= 2
        and result.get("answer") is not None
    ):
        try:
            from arlc.answerer import _extract_pages_used as _extract_vp
            from arlc.llm import router as _verify_router

            # Build numbered page list from top-5 retrieved pages.
            # Track (doc_id, page_num) pairs so verification is unambiguous
            # when multiple docs share the same page number.
            _verify_page_texts = []
            _retrieved_pairs: set[tuple[str, int]] = set()
            for _vp in pages[:5]:
                _vp_doc = _vp.doc_id if hasattr(_vp, "doc_id") else _vp.get("doc_id", "")
                _vp_num = _vp.page_number if hasattr(_vp, "page_number") else _vp.get("page_number", 1)
                _vp_text = _vp.text if hasattr(_vp, "text") else _vp.get("text", "")
                _retrieved_pairs.add((_vp_doc, _vp_num))
                _verify_page_texts.append(f"[PAGE {_vp_num}] {_vp_text[:400]}")
            _verify_prompt = (
                f"Question: {question}\n"
                f"Answer: {str(result.get('answer', ''))[:300]}\n\n"
                f"Which pages below directly support this answer? "
                f'Return ONLY page numbers as comma-separated integers (e.g. "3, 7"). '
                f'If none are relevant, return "none".\n\n' + "\n\n".join(_verify_page_texts)
            )
            _verify_system = "You identify which pages directly support an answer. Be concise."
            _verify_raw, _, _, _, _, _ = await asyncio.to_thread(
                _verify_router.call_llm,
                _verify_system,
                _verify_prompt,
                20,  # max_tokens — just page numbers
            )
            _verified_page_nums = _extract_vp(f"PAGES_USED: {_verify_raw}")
            # Also try plain integer extraction if PAGES_USED pattern didn't match
            if not _verified_page_nums:
                _verified_page_nums = [int(t) for t in re.split(r"[,\s]+", _verify_raw.strip()) if t.strip().isdigit()]
            if _verified_page_nums:
                _verified_set = set(_verified_page_nums)
                # Filter chunk_pages to verified page numbers, but only for (doc_id, page_num)
                # pairs that were actually in the retrieved context (pages[:5]).
                # Without this, two docs sharing the same page number would both be "verified"
                # even though the LLM only saw one of them.
                _new_chunk_pages = []
                for _cp in result.get("chunk_pages", []):
                    _cp_doc = _cp.get("doc_id", "")
                    _kept = [
                        pn
                        for pn in _cp.get("page_numbers", [])
                        if pn in _verified_set and (_cp_doc, pn) in _retrieved_pairs
                    ]
                    if _kept:
                        _new_chunk_pages.append({"doc_id": _cp_doc, "page_numbers": _kept})
                # Only apply if verifier returned a non-empty subset (don't wipe everything)
                if _new_chunk_pages:
                    _before = sum(len(c.get("page_numbers", [])) for c in result.get("chunk_pages", []))
                    _after = sum(len(c.get("page_numbers", [])) for c in _new_chunk_pages)
                    if _after < _before:
                        print(
                            f"  [page-verify] {question_id[:12]}... "
                            f"pages {_before}->{_after} verified={sorted(_verified_set)}",
                            file=sys.stderr,
                        )
                    result["chunk_pages"] = _new_chunk_pages
                    # Verifier returns new dicts without text — re-attach from source_pages
                    _attach_source_text(result["chunk_pages"], source_pages)
        except Exception as _pv_err:
            print(f"  [page-verify] {question_id[:12]}... error: {_pv_err}", file=sys.stderr)

    # Step 4.5: Grounding verification (free_text only, non-trick, graceful fallback)
    # Checks every claim is grounded in source pages; adds missing conditions if found.
    # Only rewrites the answer text — page citations are never changed.
    # Skipped for Opus inline answers that already contain verbatim quotes (good quality).
    if answer_type == "free_text" and isinstance(result.get("answer"), str):
        _ans_text = result.get("answer", "")
        _model_used = result.get("model_name", "")
        # Skip grounding check if the LLM produced a quality answer (has quotes, ≥300 chars).
        # The grounding verifier checks against source_pages (1 page), but mega-context
        # answers cite articles from across the FULL law PDF. Haiku incorrectly flags these
        # as "ungrounded" and rewrites them, destroying correct answers.
        _has_leaked_cot = (
            _ans_text.lstrip().startswith("1.") or "QUESTION PARSE" in _ans_text or "KEY PROVISIONS" in _ans_text
        )
        _skip_grounding = ("'" in _ans_text or '"' in _ans_text) and len(_ans_text) >= 300 and not _has_leaked_cot
        if _skip_grounding:
            print(
                f"  [grounding] {question_id[:12]}... skip (Opus inline, {len(_ans_text)} chars)",
                file=sys.stderr,
            )
        else:
            try:
                from grounding_verifier import verify_grounding

                verification = await asyncio.to_thread(verify_grounding, question, result["answer"], source_pages)
                if verification.get("needs_rewrite"):
                    rewritten = verification.get("rewritten_answer", "").strip()
                    if rewritten and 100 <= len(rewritten) <= 900:
                        print(
                            f"  [grounding] {question_id[:12]}... rewrite: "
                            f"{len(result['answer'])}→{len(rewritten)} chars | "
                            f"ungrounded={len(verification.get('ungrounded_claims', []))} "
                            f"missing={len(verification.get('missing_conditions', []))}",
                            file=sys.stderr,
                        )
                        result["answer"] = rewritten
            except Exception as _gv_err:
                print(f"  [grounding] {question_id[:12]}... error: {_gv_err}", file=sys.stderr)

    # Step T-01: Evidence-grounded page re-ranking (free_text only, multiple pages only).
    # Re-ranks page_numbers within each chunk_page entry using 3-pass evidence matching
    # so the best-supported page comes first. pns[0] is the primary citation — this
    # directly improves G-score when multiple pages were retrieved and the second page
    # is actually the evidence page. Non-destructive: never removes pages, only reorders.
    if answer_type == "free_text" and result.get("answer") and result.get("chunk_pages"):
        try:
            from arlc.evidence_verifier import find_evidence_pages as _find_ev_pages

            def _run_evidence_verifier():
                _ev_chunk_pages = []
                for _cp in result["chunk_pages"]:
                    _cp_doc = _cp.get("doc_id", "")
                    _cp_pages = _cp.get("page_numbers", [])
                    # Only re-rank when there are multiple candidate pages — single page is a no-op
                    if _cp_doc and len(_cp_pages) > 1:
                        _reranked = _find_ev_pages(
                            result["answer"],
                            answer_type,
                            _cp_doc,
                            _cp_pages,
                            top_k=len(_cp_pages),  # keep all, just re-order
                        )
                        _ev_chunk_pages.append({**_cp, "page_numbers": _reranked})
                    else:
                        _ev_chunk_pages.append(_cp)
                return _ev_chunk_pages

            # Run in thread to avoid blocking the event loop with sync embed_query() calls
            result["chunk_pages"] = await asyncio.to_thread(_run_evidence_verifier)
            _attach_source_text(result["chunk_pages"], source_pages)
        except Exception as _ev_err:
            print(f"  [evidence-verifier] {question_id[:12]}... error: {_ev_err}", file=sys.stderr)

    # Absence classifier: clear pages when BOTH question pattern AND answer text confirm absence.
    # Conservative — "Does X address Y?" (no case ID) + answer explicitly states absence.
    # Tested against gold: 3 correct clears, 0 false positives.
    if answer_type == "free_text" and isinstance(result.get("answer"), str):
        _q_low = question.lower()
        _a_low = result["answer"].lower()[:150]
        _has_case_id = bool(re.search(r"(?:SCT|CFI|CA|ARB|ENF|DEC|TCD|ACT)\s+\d+/\d{4}", question, re.IGNORECASE))
        # Question must be "Does X address Y?" with no case ID reference
        _q_absence = _q_low.startswith("does") and "address" in _q_low and not _has_case_id
        _absence_markers = [
            "do not address",
            "does not address",
            "do not contain",
            "does not contain",
            "not address or specify",
            "no information about",
            "no information on",
            "cannot be determined from the provided",
        ]
        _a_absence = any(m in _a_low for m in _absence_markers)
        if _q_absence and _a_absence:
            result["chunk_pages"] = []
            print(f"  [absence] {question_id[:12]}... cleared pages (Q+A both signal absence)", file=sys.stderr)

    # Build chunk_pages from retrieved pages if answerer didn't set them
    if not result.get("chunk_pages"):
        result["chunk_pages"] = _pages_to_chunk_pages(pages)

    # Validate chunk_pages: remove hallucinated page references not in retrieved set.
    # SKIP for mega-context (cached) answers: the LLM sees the full PDF and may correctly
    # cite page 46, but the retriever only had pages 1-3 — so validation would strip the
    # correct page. The LLM's PAGES_USED is more authoritative for full-PDF questions.
    _model_used = result.get("model_name", "")
    if "cached" not in _model_used:
        result["chunk_pages"] = _validate_chunk_pages(result, pages)

    # Smart doc cap: limit citations to router's target doc count.
    # Brainstorm analysis confirmed this HELPS G by +0.04 (reduces wrong extra docs).
    if target_docs and result.get("chunk_pages"):
        max_docs = len(target_docs)
        if len(result["chunk_pages"]) > max_docs:
            result["chunk_pages"] = result["chunk_pages"][:max_docs]

    # Hard cap: max pages = max(3, number of target docs).
    # Multi-doc questions (e.g. Consultation Papers) need all docs cited.
    _page_cap = max(3, len(target_docs)) if target_docs else 3
    result["chunk_pages"] = _enforce_page_limit(result["chunk_pages"], max_pages=_page_cap)

    # Ensure timing fields exist (use _ms internal format)
    result.setdefault("ttft_ms", 1)
    result.setdefault("tpot_ms", 0)
    result.setdefault("total_time_ms", int(t_total * 1000))
    result.setdefault("input_tokens", 0)
    result.setdefault("output_tokens", 0)
    result.setdefault("model_name", "claude-sonnet-4-6")

    # Final: attach source text to chunk_pages for the web frontend.
    # Multiple post-processing steps (page verifier, _validate_chunk_pages,
    # _enforce_page_limit) rebuild chunk_pages dicts without text.
    # We do this once at the very end to avoid patching each step.
    if web_mode and source_pages and result.get("chunk_pages"):
        _txt_by_key = {(sp["doc_id"], sp.get("page_number", 0)): sp.get("text", "") for sp in source_pages}
        _txt_by_doc = {sp["doc_id"]: sp.get("text", "") for sp in source_pages if sp.get("text")}
        for cp in result["chunk_pages"]:
            if not cp.get("text"):
                for pn in cp.get("page_numbers", []):
                    t = _txt_by_key.get((cp["doc_id"], pn))
                    if t:
                        cp["text"] = t
                        break
                if not cp.get("text"):
                    cp["text"] = _txt_by_doc.get(cp["doc_id"])

    return result


# ---------------------------------------------------------------------------
# Unicode / Cyrillic normalization helpers
# ---------------------------------------------------------------------------

# Common Cyrillic lookalikes → Latin equivalents.
# These characters are visually identical but different Unicode codepoints,
# causing exact-match failures when the platform compares against gold answers.
_CYRILLIC_TO_LATIN: dict[str, str] = {
    # Uppercase
    "\u0410": "A",  # А → A
    "\u0412": "B",  # В → B
    "\u0421": "C",  # С → C
    "\u0415": "E",  # Е → E
    "\u041d": "H",  # Н → H
    "\u0406": "I",  # І → I
    "\u041a": "K",  # К → K
    "\u041c": "M",  # М → M
    "\u041e": "O",  # О → O
    "\u0420": "P",  # Р → P
    "\u0422": "T",  # Т → T
    "\u0425": "X",  # Х → X
    "\u0423": "Y",  # У → Y
    # Lowercase
    "\u0430": "a",  # а → a
    "\u0435": "e",  # е → e
    "\u043e": "o",  # о → o
    "\u0440": "p",  # р → p
    "\u0441": "c",  # с → c
    "\u0443": "y",  # у → y
    "\u0445": "x",  # х → x
    "\u0456": "i",  # і → i
}


def _check_homoglyphs(text: str) -> str:
    """Replace Cyrillic lookalike characters with their Latin equivalents."""
    return "".join(_CYRILLIC_TO_LATIN.get(c, c) for c in text)


def _normalize_answer(answer: object) -> object:
    """Apply NFKC normalization and homoglyph cleanup to a submission answer.

    Only acts on string and list-of-string answers (name, names, free_text).
    Numeric and boolean answers are returned unchanged.
    """
    if isinstance(answer, str):
        normalized = unicodedata.normalize("NFKC", answer)
        return _check_homoglyphs(normalized)
    if isinstance(answer, list):
        return [
            _check_homoglyphs(unicodedata.normalize("NFKC", item)) if isinstance(item, str) else item for item in answer
        ]
    return answer


# ---------------------------------------------------------------------------
# Submission format validation
# ---------------------------------------------------------------------------


def validate_submission(submission: dict) -> list[str]:
    """Validate a submission dict against the platform API spec.

    Returns a list of error strings. Empty list means the submission is valid.
    Call this BEFORE every submission attempt — if any errors are returned,
    do NOT submit; fix the errors first.
    """
    errors: list[str] = []

    # Top-level structure
    if not isinstance(submission, dict):
        return ["submission is not a dict"]

    if "architecture_summary" not in submission:
        errors.append("missing top-level 'architecture_summary'")
    elif not isinstance(submission["architecture_summary"], str):
        errors.append("'architecture_summary' must be a string")

    if "answers" not in submission:
        errors.append("missing top-level 'answers'")
        return errors  # can't validate further

    answers = submission["answers"]
    if not isinstance(answers, list):
        errors.append("'answers' must be a list")
        return errors

    if len(answers) == 0:
        errors.append("'answers' is empty")

    # Check for duplicate question_ids
    question_ids_seen: set = set()

    for i, ans in enumerate(answers):
        prefix = f"answers[{i}]"

        if not isinstance(ans, dict):
            errors.append(f"{prefix} is not a dict")
            continue

        # question_id
        qid = ans.get("question_id")
        if qid is None:
            errors.append(f"{prefix}: missing 'question_id'")
        elif not isinstance(qid, str):
            errors.append(f"{prefix}: 'question_id' must be a string, got {type(qid).__name__}")
        elif qid in question_ids_seen:
            errors.append(f"{prefix}: duplicate question_id '{qid}'")
        else:
            question_ids_seen.add(qid)

        # answer field
        if "answer" not in ans:
            errors.append(f"{prefix}: missing 'answer' field")
        else:
            a = ans["answer"]
            # answer must be: bool, int, float, str, list[str], or None
            if a is not None and not isinstance(a, (bool, int, float, str, list)):
                errors.append(f"{prefix}: 'answer' has invalid type {type(a).__name__}")
            if isinstance(a, list):
                for j, item in enumerate(a):
                    if not isinstance(item, str):
                        errors.append(f"{prefix}: 'answer[{j}]' must be str, got {type(item).__name__}")

        # telemetry
        tel = ans.get("telemetry")
        if tel is None:
            errors.append(f"{prefix}: missing 'telemetry'")
            continue
        if not isinstance(tel, dict):
            errors.append(f"{prefix}: 'telemetry' must be a dict")
            continue

        # telemetry.timing
        timing = tel.get("timing")
        if timing is None:
            errors.append(f"{prefix}.telemetry: missing 'timing'")
        elif not isinstance(timing, dict):
            errors.append(f"{prefix}.telemetry: 'timing' must be a dict")
        else:
            for field in ("ttft_ms", "tpot_ms", "total_time_ms"):
                v = timing.get(field)
                if v is None:
                    errors.append(f"{prefix}.telemetry.timing: missing '{field}'")
                elif not isinstance(v, (int, float)):
                    errors.append(f"{prefix}.telemetry.timing.{field}: must be numeric, got {type(v).__name__}")
                elif v < 0:
                    errors.append(f"{prefix}.telemetry.timing.{field}: must be >= 0, got {v}")
            # total_time_ms must be >= ttft_ms
            ttft = timing.get("ttft_ms", 0) or 0
            total = timing.get("total_time_ms", 0) or 0
            if isinstance(ttft, (int, float)) and isinstance(total, (int, float)):
                if total < ttft:
                    errors.append(f"{prefix}.telemetry.timing: total_time_ms ({total}) < ttft_ms ({ttft})")
            # total_time_ms must be > 0 (platform penalises total_ms=0)
            if total == 0:
                errors.append(f"{prefix}.telemetry.timing: total_time_ms is 0 (platform flags as invalid telemetry)")

        # telemetry.usage
        usage = tel.get("usage")
        if usage is None:
            errors.append(f"{prefix}.telemetry: missing 'usage'")
        elif not isinstance(usage, dict):
            errors.append(f"{prefix}.telemetry: 'usage' must be a dict")
        else:
            for field in ("input_tokens", "output_tokens"):
                v = usage.get(field)
                if v is None:
                    errors.append(f"{prefix}.telemetry.usage: missing '{field}'")
                elif not isinstance(v, (int, float)):
                    errors.append(f"{prefix}.telemetry.usage.{field}: must be numeric")
                elif v < 0:
                    errors.append(f"{prefix}.telemetry.usage.{field}: must be >= 0")

        # telemetry.retrieval
        retrieval = tel.get("retrieval")
        if retrieval is None:
            errors.append(f"{prefix}.telemetry: missing 'retrieval'")
        elif not isinstance(retrieval, dict):
            errors.append(f"{prefix}.telemetry: 'retrieval' must be a dict")
        else:
            chunk_pages = retrieval.get("retrieved_chunk_pages")
            if chunk_pages is None:
                errors.append(f"{prefix}.telemetry.retrieval: missing 'retrieved_chunk_pages'")
            elif not isinstance(chunk_pages, list):
                errors.append(f"{prefix}.telemetry.retrieval: 'retrieved_chunk_pages' must be a list")
            else:
                for k, cp in enumerate(chunk_pages):
                    cp_prefix = f"{prefix}.retrieved_chunk_pages[{k}]"
                    if not isinstance(cp, dict):
                        errors.append(f"{cp_prefix}: must be a dict")
                        continue
                    if "doc_id" not in cp:
                        errors.append(f"{cp_prefix}: missing 'doc_id'")
                    elif not isinstance(cp["doc_id"], str):
                        errors.append(f"{cp_prefix}: 'doc_id' must be a string")
                    if "page_numbers" not in cp:
                        errors.append(f"{cp_prefix}: missing 'page_numbers'")
                    else:
                        pns = cp["page_numbers"]
                        if not isinstance(pns, list):
                            errors.append(f"{cp_prefix}: 'page_numbers' must be a list")
                        else:
                            for m, pn in enumerate(pns):
                                if not isinstance(pn, int):
                                    errors.append(
                                        f"{cp_prefix}.page_numbers[{m}]: must be int, got {type(pn).__name__}",
                                    )
                                elif pn < 1:
                                    errors.append(f"{cp_prefix}.page_numbers[{m}]: must be >= 1, got {pn}")

        # telemetry.model_name
        model_name = tel.get("model_name")
        if model_name is None:
            errors.append(f"{prefix}.telemetry: missing 'model_name'")
        elif not isinstance(model_name, str):
            errors.append(f"{prefix}.telemetry: 'model_name' must be a string")
        elif not model_name.strip():
            errors.append(f"{prefix}.telemetry: 'model_name' is empty")

    return errors


# ---------------------------------------------------------------------------
# Results -> submission format conversion
# ---------------------------------------------------------------------------


def _to_submission_format(results: list[dict]) -> dict:
    """Convert internal results to platform submission format.

    Reports actual measured TTFT values honestly. No clamping — competition
    rules prohibit manually editing telemetry.
    """
    answers = []
    for r in results:
        ttft_ms = max(1, int(r.get("ttft_ms", 0) or 0))
        tpot_ms = max(0, int(r.get("tpot_ms", 0) or 0))
        total_ms = max(1, int(r.get("total_time_ms", 0) or 0))

        if total_ms < ttft_ms:
            total_ms = ttft_ms

        chunk_pages = r.get("chunk_pages", [])
        if chunk_pages is None:
            chunk_pages = []
        # Validate structure
        valid_pages = []
        for cp in chunk_pages:
            if isinstance(cp, dict) and "doc_id" in cp and "page_numbers" in cp:
                pns = cp["page_numbers"]
                if isinstance(pns, list) and all(isinstance(p, int) for p in pns):
                    valid_pages.append({"doc_id": str(cp["doc_id"]), "page_numbers": pns})
        chunk_pages = valid_pages

        model_name = r.get("model_name", "claude-sonnet-4-6")
        inp = max(1, int(r.get("input_tokens", 0) or 0))
        out = max(1, int(r.get("output_tokens", 0) or 0))

        # NFKC normalization + homoglyph cleanup on string answers.
        # Finals may have Cyrillic or Arabic party names; normalization prevents
        # Cyrillic lookalikes (е/o/р/с/x) from breaking exact-match scoring.
        answer = r["answer"]
        answer = _normalize_answer(answer)

        answers.append(
            {
                "question_id": r["id"],
                "answer": answer,
                "telemetry": {
                    "timing": {
                        "ttft_ms": ttft_ms,
                        "tpot_ms": tpot_ms,
                        "total_time_ms": total_ms,
                    },
                    "retrieval": {
                        "retrieved_chunk_pages": chunk_pages,
                    },
                    "usage": {
                        "input_tokens": inp,
                        "output_tokens": out,
                    },
                    "model_name": model_name,
                },
            },
        )

    return {
        "architecture_summary": ARCHITECTURE_SUMMARY,
        "answers": answers,
    }


# ---------------------------------------------------------------------------
# Stats printer
# ---------------------------------------------------------------------------


def _print_stats(results: list[dict]):
    """Print sanity statistics after pipeline run."""
    n = len(results)
    if n == 0:
        print("No results to analyze.")
        return

    # Answer type distribution
    type_counts = {}
    for r in results:
        t = r.get("answer_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Null answers
    null_count = sum(1 for r in results if r.get("answer") is None)

    # Pages per question
    ppq_values = []
    for r in results:
        pages = r.get("chunk_pages", [])
        total_pages = sum(len(cp.get("page_numbers", [])) for cp in pages)
        ppq_values.append(total_pages)
    avg_ppq = sum(ppq_values) / n if n else 0
    zero_page = sum(1 for v in ppq_values if v == 0)

    # TTFT stats
    ttfts = [r.get("ttft_ms", 0) for r in results if r.get("ttft_ms", 0) > 0]
    avg_ttft = sum(ttfts) / len(ttfts) if ttfts else 0
    max_ttft = max(ttfts) if ttfts else 0

    # Total tokens
    total_input = sum(r.get("input_tokens", 0) for r in results)
    total_output = sum(r.get("output_tokens", 0) for r in results)

    print("\n" + "=" * 60)
    print("PIPELINE RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Questions processed: {n}")
    print(f"  Null answers:        {null_count}")
    print()
    print("  Answer types:")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")
    print()
    print(f"  PPQ (pages/question): {avg_ppq:.2f} (target < 1.3)")
    print(f"  Zero-page questions:  {zero_page}")
    print()
    if ttfts:
        sorted_ttfts = sorted(ttfts)
        p50 = sorted_ttfts[len(sorted_ttfts) // 2]
        p95_idx = min(int(len(sorted_ttfts) * 0.95), len(sorted_ttfts) - 1)
        p95 = sorted_ttfts[p95_idx]
        print(f"  TTFT avg:  {avg_ttft:.0f}ms ({avg_ttft / 1000:.2f}s)")
        print(f"  TTFT p50:  {p50:.0f}ms")
        print(f"  TTFT p95:  {p95:.0f}ms")
        print(f"  TTFT max:  {max_ttft:.0f}ms")
    else:
        print("  TTFT: no data")
    print()
    print(f"  Total tokens: {total_input:,} in / {total_output:,} out")
    est_cost = (total_input * 3 / 1_000_000) + (total_output * 15 / 1_000_000)
    print(f"  Estimated cost: ~${est_cost:.2f} (Sonnet pricing)")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def run_pipeline(
    questions_path: str = "data/questions.json",
    output_dir: str = "output",
    workers: int = 10,
    skip_indexing: bool = False,
    verify_numbers: bool = False,
):
    """Run the full finals pipeline."""
    # Resolve paths
    questions_path = Path(questions_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results_raw.json"
    submission_path = output_dir / "submission_raw.json"

    # Step 0: Check for questions file
    if not questions_path.exists():
        # Try fallback paths
        fallbacks = [
            Path("data/public_dataset.json"),
            Path("data/questions.json"),
            Path("starter_kit/questions.json"),
        ]
        for fb in fallbacks:
            if fb.exists():
                questions_path = fb
                break
        else:
            print(f"ERROR: Questions file not found: {questions_path}")
            print("  Try: uv run python finals.py --questions data/public_dataset.json")
            sys.exit(1)

    # Step 1: Index documents (if needed)
    if not skip_indexing:
        from arlc.retriever import get_chunk_count

        if get_chunk_count("difc") == 0:
            print("=== Step 1: Indexing documents ===")
            from arlc.indexing.indexer import build_index

            build_index()
        else:
            print("=== Step 1: Skipping indexing (chunks already in PostgreSQL) ===")
    else:
        print("=== Step 1: Skipping indexing (--skip-indexing) ===")

    # Step 2: Load questions
    print("=== Step 2: Loading questions ===")
    with open(questions_path) as f:
        questions = json.load(f)
    print(f"Loaded {len(questions)} questions from {questions_path}")

    # Step 3: Import pipeline modules
    print("=== Step 3: Loading pipeline modules ===")
    route_fn, retrieve_fn, answer_fn = _import_pipeline_modules()

    # Use fallbacks for missing modules
    if route_fn is None:
        route_fn = _fallback_route
    if retrieve_fn is None:
        retrieve_fn = _fallback_retrieve_pages
    if answer_fn is None:
        answer_fn = _fallback_generate_answer

    # Validate LLM credentials before doing any work.
    # Skip if using vertex or litellm backends (they have their own auth).
    _backend = os.environ.get("LLM_BACKEND", "litellm")
    if _backend not in ("vertex", "litellm", "auto") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set. Pipeline cannot call LLM.", file=sys.stderr)
        sys.exit(1)

    # Step 3b: Pre-warm retriever caches synchronously.
    # First retrieval loads chunks + cross-encoder into memory.
    # Without pre-warming, parallel workers race for _reranker_lock on cold start,
    # causing a deadlock when asyncio.wait_for cancels the asyncio wrapper but the
    # OS thread keeps holding the lock.
    print("=== Step 3b: Pre-warming retriever (loads chunks + cross-encoder) ===")
    try:
        # Import lazy loaders directly — much faster than a full retrieval warmup.
        # These are thread-safe singletons; calling them now means concurrent workers
        # never race to initialize them.
        import arlc.retriever as _ret_mod

        _ret_mod.get_chunks_by_doc()  # load all chunks from PostgreSQL into memory
        _ret_mod.get_reranker()  # load cross-encoder model onto MPS/CPU
        _ret_mod.get_embedding_model()  # validate OpenRouter API key + init embedder
        print("  Retriever warmed up (chunks, reranker, embeddings all loaded).")
    except Exception as e:
        print(f"  Warmup warning (non-fatal): {e}")

    # Step 3c: Sort questions by target law doc_id for prompt cache efficiency.
    # The answerer_v3 now uses multi-block system prompts where the law context
    # is in a separate cached block. When consecutive questions reference the same
    # law document AND use the same model, the Anthropic API can reuse the cached
    # law context (26K+ tokens), reducing API cost by ~90%.
    #
    # NOTE: Prompt caching primarily reduces COST, not TTFT. TTFT is dominated by
    # network latency + model sampling time, which caching does not affect. The
    # sorting still helps with cost savings.
    print("=== Step 3c: Sorting questions for prompt cache efficiency ===")
    try:
        from arlc.router import get_router

        _sort_router = get_router()

        def _get_sort_key(q):
            r = _sort_router.route(q["question"], q.get("answer_type", "free_text"))
            if r.target_doc_ids:
                # Sort by (doc_id, model_order) to group same-law same-model questions
                model_order = 0 if q.get("answer_type", "") != "free_text" else 1
                return (0, r.target_doc_ids[0], model_order)
            return (1, q.get("id", ""), 0)

        questions.sort(key=_get_sort_key)
        print(f"  Sorted {len(questions)} questions by target doc_id + model type")
    except Exception as _sort_err:
        print(f"  WARNING: Question sorting failed (non-fatal): {_sort_err}", file=sys.stderr)

    # Step 4: Process all questions
    print(f"=== Step 4: Processing {len(questions)} questions ({workers} workers) ===")
    semaphore = asyncio.Semaphore(workers)

    tasks = [_process_question(q, route_fn, retrieve_fn, answer_fn, semaphore) for q in questions]

    results = []
    completed = 0
    run_start = time.monotonic()
    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)
        completed += 1
        elapsed = int(time.monotonic() - run_start)

        # Progress output
        answer_display = str(result["answer"])[:60] if result["answer"] is not None else "null"
        pages_count = sum(len(cp.get("page_numbers", [])) for cp in result.get("chunk_pages", []))
        ttft_ms = result.get("ttft_ms", 0)
        print(
            f"  [{completed}/{len(questions)}] "
            f"type={result['answer_type']} "
            f"pages={pages_count} "
            f"ttft={ttft_ms}ms "
            f"(elapsed: {elapsed}s) "
            f"| {answer_display}",
        )

    # Sort results by original question order
    question_order = {q["id"]: i for i, q in enumerate(questions)}
    results.sort(key=lambda r: question_order.get(r["id"], 999999))

    # Step 5: Save results
    print("\n=== Step 5: Saving results ===")

    # Full results (internal format)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Results: {results_path}")

    # Platform submission format
    submission = _to_submission_format(results)
    with open(submission_path, "w") as f:
        json.dump(submission, f, indent=2)
    print(f"  Submission: {submission_path} ({len(submission['answers'])} answers)")

    # Step 5b: DISABLED — opus_page_select proven to hurt G in 31 warmup submissions
    # (CLAUDE.md Rule #1: NEVER use opus_page_select)
    print("\n=== Step 5b: Opus page selection DISABLED (Rule #1) ===")
    _working_results = results

    # Step 5b.3: Article page restoration — ensure article start pages are used
    # When an article spans a page boundary (heading on page N, content on page N+1),
    # opus_page_select or cross-encoder may select page N+1 (content). Platform gold
    # uses page N (where the article NUMBER appears). This general step restores the
    # correct article start page from article_page_index for all law questions.
    print("\n=== Step 5b.3: Article page restoration (general) ===")
    try:
        _art_index_path = Path("data/article_page_index.json")
        with open(_art_index_path) as f:
            _art_index = json.load(f)
        from arlc.router import get_router

        _router_inst = get_router()
        _art_restored = 0
        for _r in _working_results:
            _question = _r.get("question", "")
            _answer_type = _r.get("answer_type", "")
            _chunks = _r.get("chunk_pages", [])
            if not _chunks:
                continue
            # Re-route to get article and law info
            _rr = _router_inst.route(_question, _answer_type)
            if not _rr.article_numbers or not _rr.law_names:
                continue
            # For each law doc in the results, check if article page needs restoration
            for _law_name in _rr.law_names:
                _law_doc_id = _router_inst._get_law_doc_id(_law_name)
                if not _law_doc_id or _law_doc_id not in _art_index:
                    continue
                _doc_articles = _art_index[_law_doc_id].get("articles", {})
                for _art_key in _rr.article_numbers:
                    if _art_key not in _doc_articles:
                        continue
                    _art_pages = _doc_articles[_art_key]
                    if not _art_pages:
                        continue
                    _correct_page = _art_pages[0]  # First page = article start
                    # Check if any chunk for this doc_id has a page adjacent to but
                    # different from the correct article start page
                    for _cp in _chunks:
                        if _cp.get("doc_id") != _law_doc_id:
                            continue
                        _current_pages = _cp.get("page_numbers", [])
                        # If current page is the adjacent page (correct+1), restore
                        # to the article start page
                        _new_pages = []
                        _changed = False
                        for _pg in _current_pages:
                            if _pg == _correct_page + 1 and _pg != _correct_page:
                                _new_pages.append(_correct_page)
                                _changed = True
                            else:
                                _new_pages.append(_pg)
                        if _changed:
                            _cp["page_numbers"] = sorted(set(_new_pages))
                            _art_restored += 1
                            print(
                                f"  Restored: {_r.get('id', '')[:16]} "
                                f"doc={_law_doc_id[:8]} {_art_key} "
                                f"p{_current_pages}→p{_cp['page_numbers']}",
                            )
        print(f"  Article pages restored: {_art_restored}")
    except Exception as _art_err:
        print(f"  WARNING: Article page restoration failed: {_art_err}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)

    # Step 5c: DISABLED — Opus S_asst rewrite requires Anthropic credits (all calls fail)
    print("\n=== Step 5c: Opus S_asst DISABLED (no Anthropic credits) ===")

    # Step 5c.2: Normalize names answers — list-of-dicts → list-of-strings
    # Router/oracle can return [{"name": "X", ...}] instead of ["X"] for names questions.
    print("\n=== Step 5c.2: Normalizing names answers (list-of-dicts → list-of-strings) ===")
    _names_normalized = 0
    for _r in _working_results:
        if isinstance(_r.get("answer"), list):
            _old = _r["answer"]
            _new = [item.get("name", str(item)) if isinstance(item, dict) else item for item in _old]
            if _new != _old:
                _r["answer"] = _new
                _names_normalized += 1
                print(f"  Normalized: {_r.get('id', '')[:16]} {_old!r} → {_new!r}")
    print(f"  Names normalized: {_names_normalized}")

    # Step 5c.7: DISABLED — Haiku calibration requires Anthropic credits (all calls fail)
    print("\n=== Step 5c.7: Calibration DISABLED (no Anthropic credits) ===")

    # Step 5d.5: Validate and fix telemetry format in all results
    # Ensures: integer timing, total_time_ms >= ttft_ms >= 1, usage block, model_name.
    # Fixes the T=0.961 regression caused by oracle/rule-based entries with
    # total_time_ms=0 and float timing values.
    print("\n=== Step 5d.5: Validating telemetry format ===")
    _telemetry_fixed = 0
    for _r in _working_results:
        _changed = False
        # Fix total_ms → total_time_ms (old field name from CZ v7)
        if "total_ms" in _r and "total_time_ms" not in _r:
            _r["total_time_ms"] = max(0, int(_r.pop("total_ms") or 0))
            _changed = True
        # Ensure integer timing (oracle paths return floats 1.0, 0.0)
        for _key in ["ttft_ms", "tpot_ms", "total_time_ms"]:
            if _key in _r:
                _int_val = int(_r[_key] or 0)
                if _r[_key] != _int_val:
                    _r[_key] = _int_val
                    _changed = True
        # ttft_ms must be >= 1 (platform rejects 0)
        if _r.get("ttft_ms", 0) < 1:
            _r["ttft_ms"] = 1
            _changed = True
        # total_time_ms must be >= ttft_ms
        _ttft = _r.get("ttft_ms", 1)
        _total = _r.get("total_time_ms", 0)
        if _total < _ttft:
            _r["total_time_ms"] = _ttft
            _changed = True
        # Ensure model_name exists
        if not _r.get("model_name"):
            _r["model_name"] = "claude-sonnet-4-6"
            _changed = True
        # Ensure token counts exist (can be 0 for oracle)
        _r.setdefault("input_tokens", 0)
        _r.setdefault("output_tokens", 0)
        if _changed:
            _telemetry_fixed += 1
    print(f"  Telemetry entries fixed: {_telemetry_fixed}")

    # Step 5d.7: Absence-based boolean False → empty pages
    # When a boolean question asks if a law "deals with" / "addresses" a topic and
    # the answer is False, the info is ABSENT — gold expects empty pages [].
    # Confirmed: question 5cb2e9e63192 ("Does DIFC Law No. 7 deal with insolvency?")
    # GUARD: skip if question references a specific article (e.g. "Does Article 5 address X?")
    # — for article-level questions, the article page IS a valid citation even when answer=False.
    print("\n=== Step 5d.7: Absence-based boolean → empty pages ===")
    import re as _re

    # "cover" removed — matches "cover page" in cross-case questions (false positive)
    # "address" guarded by _ARTICLE_RE check below (skipped for article-level questions)
    _ABSENCE_PATTERNS = ["deal with", "relate to", "concern", "pertain to", "address"]
    _ARTICLE_RE = _re.compile(r"\bArticle\s+\d", _re.IGNORECASE)
    _absence_fixed = 0
    for _r in _working_results:
        if _r.get("answer_type") == "boolean" and _r.get("answer") is False:
            _q_text = _r.get("question", "")
            # Skip if the question targets a specific article — page is a valid citation
            if _ARTICLE_RE.search(_q_text):
                continue
            _q_lower = _q_text.lower()
            if any(p in _q_lower for p in _ABSENCE_PATTERNS):
                if _r.get("chunk_pages"):  # only fix if pages were cited
                    _r["chunk_pages"] = []
                    _absence_fixed += 1
                    print(f"  Cleared pages: {_r.get('id', '')[:16]} (absent topic, answer=False)")
    print(f"  Absence-based fixes: {_absence_fixed}")

    # Step 5d.7-null: Null answer → ALWAYS empty pages
    # Gold NEVER has citations for null answers (verified: 0/58 null golds have pages).
    _null_cleared = 0
    for _r in _working_results:
        if _r.get("answer") is None and _r.get("chunk_pages"):
            _r["chunk_pages"] = []
            _null_cleared += 1
    print(f"  Null answer page clearing: {_null_cleared}")

    # Step 5d.7a: Oracle boolean False → always empty pages
    # When the oracle answers False for a cross-case comparison (parties, judges),
    # gold ALWAYS expects empty pages. The oracle only handles comparison questions,
    # so oracle+False = "no overlap" = empty citations. No regex needed.
    # Also catches LLM boolean False when question mentions 2+ case IDs (cross-case).
    _cross_case_fixed = 0
    for _r in _working_results:
        if _r.get("answer_type") == "boolean" and _r.get("answer") is False and _r.get("chunk_pages"):
            # Oracle boolean False → always clear
            if _r.get("model_name") == "oracle":
                _r["chunk_pages"] = []
                _cross_case_fixed += 1
            else:
                # LLM boolean False: clear if question has 2+ case IDs (cross-case)
                _q = _r.get("question", "")
                _case_ids = _re.findall(r"(?:CFI|SCT|CA|ARB|ENF|DEC|TCD)\s+\d+", _q)
                if len(set(_case_ids)) >= 2:
                    _r["chunk_pages"] = []
                    _cross_case_fixed += 1
    print(f"  Cross-case/oracle False fixes: {_cross_case_fixed}")

    # Step 5d.7b-oracle: Oracle comparison answers → empty pages
    # When oracle answers a cross-case comparison (date/claim "which case earlier/larger"),
    # the answer comes from metadata, not from reading a specific page. Gold expects [].
    _oracle_comp_cleared = 0
    for _r in _working_results:
        if _r.get("model_name") == "oracle" and _r.get("answer_type") in ("name", "date") and _r.get("chunk_pages"):
            _q = _r.get("question", "").lower()
            if any(w in _q for w in ["earlier", "later", "higher", "larger", "lower", "first", "most recent"]):
                _r["chunk_pages"] = []
                _oracle_comp_cleared += 1
    print(f"  Oracle comparison page clearing: {_oracle_comp_cleared}")

    # Step 5d.7c: Free-text absent answers → empty pages
    # DISABLED for free_text: many answers say "X does not contain Y, but it DOES say Z"
    # — partially absent but with real content. Clearing pages for these destroys G.
    # Only clear pages for null answers or non-free_text types (handled by Step 5d.7 above).
    print("\n=== Step 5d.7b: Free-text absent answers → empty pages (DISABLED) ===")
    print("  Skipped — free_text answers keep their pages even with absence phrases")

    # Step 5d.7c: REMOVED — boolean null is a valid answer meaning "absent from corpus"
    # Organizer confirmed: null vs null = 1 point, null vs non-null = 0 points.
    # Converting null→False would LOSE points when gold is also null.
    print("\n=== Step 5d.7c: Skipped (null is valid for deterministic types) ===")

    # Step 5d.8: Validate all doc_ids exist as PDF files
    # Confirmed: question 1097af38db84 had non-existent doc_id in sub31.
    print("\n=== Step 5d.8: Doc_id validation ===")
    _doc_dir = Path("data/documents")
    _docid_fixed = 0
    for _r in _working_results:
        _valid_chunks = []
        for _cp in _r.get("chunk_pages", []):
            _did = _cp.get("doc_id", "")
            _pdf_path = _doc_dir / f"{_did}.pdf"
            if _pdf_path.exists():
                _valid_chunks.append(_cp)
            else:
                _docid_fixed += 1
                print(f"  WARNING: {_r.get('id', '')[:16]} has non-existent doc_id {_did[:16]}", file=sys.stderr)
        _r["chunk_pages"] = _valid_chunks
    print(f"  Invalid doc_ids removed: {_docid_fixed}")

    # Step 5e: Save final results + submission
    print("\n=== Step 5e: Saving final results + submission ===")
    results_final_path = output_dir / "results_final.json"
    with open(results_final_path, "w") as f:
        json.dump(_working_results, f, indent=2)
    print(f"  Final results: {results_final_path}")

    # Final submission at output/final_submission.json (per team instructions)
    final_submission_path = (
        Path(output_dir).parent / "final_submission.json"
        if str(output_dir) != "output"
        else Path("output/final_submission.json")
    )
    final_submission = _to_submission_format(_working_results)

    # Run comprehensive validation before writing the submission file.
    # If there are errors, print them but still save (they may be informational only).
    val_errors = validate_submission(final_submission)
    if val_errors:
        print(f"\n  WARNING: {len(val_errors)} submission validation issue(s):", file=sys.stderr)
        for err in val_errors[:20]:
            print(f"    - {err}", file=sys.stderr)
        if len(val_errors) > 20:
            print(f"    ... and {len(val_errors) - 20} more", file=sys.stderr)
    else:
        print("  Submission validation: PASSED (all fields correct)")

    with open(final_submission_path, "w") as f:
        json.dump(final_submission, f, indent=2)
    print(f"  FINAL SUBMISSION: {final_submission_path} ({len(final_submission['answers'])} answers)")

    # Step 6: Print stats
    _print_stats(results)

    # Step 7: Optional number verification
    if verify_numbers:
        print("\n=== Step 7: Verifying number answers ===")
        try:
            from verify_answers import run_verification

            verified_path = results_path.with_stem(results_path.stem + "_verified")
            await run_verification(
                results_path,
                verified_path,
                allowed_types={"number"},
                concurrency=workers,
            )
            # Re-convert to submission format with verified results
            with open(verified_path) as f:
                verified_results = json.load(f)
            verified_submission = _to_submission_format(verified_results)
            verified_sub_path = output_dir / "submission_verified.json"
            with open(verified_sub_path, "w") as f:
                json.dump(verified_submission, f, indent=2)
            print(f"  Verified submission: {verified_sub_path}")
        except Exception as e:
            print(f"  Verification failed: {e}", file=sys.stderr)

    print(f"\nDone! Processed {len(results)} questions.")
    print(f"To evaluate: uv run python eval_dashboard.py --results {results_final_path}")
    print(f"Regression:  uv run python test_regression.py --results {results_final_path}")
    print(f"To submit:   Review results, then: uv run python submit.py --results {final_submission_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(description="Finals pipeline: route -> retrieve -> answer -> format check")
    parser.add_argument(
        "--questions",
        default="data/questions.json",
        help="Path to questions JSON file (default: data/questions.json)",
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of concurrent workers (default: 5, prevents cross-encoder lock contention)",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Skip document indexing step",
    )
    parser.add_argument(
        "--verify-numbers",
        action="store_true",
        help="Run number verification as post-step",
    )
    args = parser.parse_args()

    # Auto-skip indexing if chunks already exist in PostgreSQL
    from arlc.retriever import get_chunk_count

    skip = args.skip_indexing or get_chunk_count("difc") > 0

    asyncio.run(
        run_pipeline(
            questions_path=args.questions,
            output_dir=args.output,
            workers=args.workers,
            skip_indexing=skip,
            verify_numbers=args.verify_numbers,
        ),
    )


if __name__ == "__main__":
    main()
