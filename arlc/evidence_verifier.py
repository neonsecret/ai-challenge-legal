"""3-pass evidence verification for answer-grounded page re-ranking.

After answer generation, re-ranks candidate pages by how well each one supports
the answer text:
  Pass 1: Exact keyword match ratio (lexical signal — fast, always runs)
  Pass 2: Fuzzy sliding-window match (SequenceMatcher — catches paraphrases)
  Pass 3: Semantic cosine similarity via embed_query (free_text/boolean only)

Technique source: RAGnarok (#1 team, 0.779) — post-answer quote matching.
Target metric: G-score. Our finals G=0.797 had ~20% wrong page citations.

Integration point: pipeline.py, after Step 4 (page_verifier), free_text answers.
"""

from __future__ import annotations

import difflib
import logging
import re

import numpy as np

logger = logging.getLogger(__name__)

# Words too common to distinguish which page contains the answer.
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might must shall can cannot of in on at to for with from by "
    "and or but not if as so that this these those it its which who whom whose when "
    "where why how all any each both some no nor more very also just only even still "
    "about after before between through without during because since though although "
    "therefore thus hence moreover furthermore however whereas said states provides "
    "pursuant under section article law regulation court case".split(),
)

_MIN_KW_LEN = 3
_MAX_KEYWORDS = 30


def _extract_keywords(text: str, answer_type: str) -> list[str]:
    """Extract meaningful keywords from an answer string.

    For deterministic types (date/number/name) we use the full answer (≤500 chars).
    For free_text we use only the first 200 chars to keep exact-match scoring fast
    and avoid matching generic legal boilerplate.
    """
    source = str(text)[:200] if answer_type == "free_text" else str(text)[:500]
    tokens = re.findall(r"[a-zA-Z0-9/\-]+", source)
    seen: set[str] = set()
    keywords: list[str] = []
    for tok in tokens:
        low = tok.lower()
        if low not in _STOPWORDS and len(tok) >= _MIN_KW_LEN and low not in seen:
            keywords.append(tok)
            seen.add(low)
    return keywords[:_MAX_KEYWORDS]


def _fuzzy_match_score(answer: str, page_text: str) -> float:
    """Best SequenceMatcher ratio over sliding 200-char windows of page_text.

    We compare the first 300 chars of the answer against windows because the
    answer is typically shorter than a page. autojunk=False is important for
    legal text (many repeated short tokens like 'the').
    """
    answer_clean = answer[:300]
    if not answer_clean or not page_text:
        return 0.0
    window = len(answer_clean) + 100
    best = 0.0
    step = 100
    for i in range(0, max(1, len(page_text) - window + 1), step):
        chunk = page_text[i : i + window]
        ratio = difflib.SequenceMatcher(None, answer_clean, chunk, autojunk=False).ratio()
        if ratio > best:
            best = ratio
        if best > 0.9:
            break
    return best


def _semantic_score(answer: str, page_text: str) -> float:
    """Cosine similarity between answer and page text embeddings.

    Only called for free_text/boolean — adds ~100ms per pair (Qwen3-8B via
    llama-server). Returns 0.0 on any failure so it never blocks the pipeline.
    """
    try:
        from arlc.retriever import embed_query  # lazy import to avoid circular deps

        a_emb = embed_query(answer[:500])
        p_emb = embed_query(page_text[:500])
        if a_emb is None or p_emb is None:
            return 0.0
        a = np.array(a_emb, dtype=np.float32)
        p = np.array(p_emb, dtype=np.float32)
        norm = float(np.linalg.norm(a) * np.linalg.norm(p))
        if norm < 1e-9:
            return 0.0
        return float(np.dot(a, p) / norm)
    except Exception:
        return 0.0


def score_source(answer: str, doc_id: str, page_num: int) -> float:
    """Score a single (doc_id, page) pair against the answer using passes 1 + 2.

    Pass 3 (semantic) is skipped here — it doubles latency and is too expensive
    to call for every source in the agent's accumulated doc list.

    Returns a float in [0, 1].  Falls back to 0.0 on any error.
    """
    if not answer:
        return 0.0
    try:
        from arlc.retriever import _extract_page_text  # lazy import

        page_text = _extract_page_text(doc_id, page_num) or ""
        if not page_text:
            return 0.0
        answer_str = str(answer)
        keywords = _extract_keywords(answer_str, "free_text")
        page_lower = page_text.lower()
        p1 = sum(1 for kw in keywords if kw.lower() in page_lower) / max(len(keywords), 1)
        p2 = _fuzzy_match_score(answer_str, page_text)
        return 0.6 * p1 + 0.4 * p2
    except Exception:
        return 0.0


def rerank_agent_sources(answer: str, sources: list[dict]) -> list[dict]:
    """Re-rank a list of agent source dicts by evidence quality.

    Each source is expected to be ``{"doc_id": str, "page_numbers": [int], ...}``.
    Web sources (``doc_id`` starting with ``"web:"``) are always appended last
    and never re-ranked against corpus sources.

    Non-destructive: never removes sources, only changes order.
    Falls back to the original list on any error.
    """
    if not answer or not sources:
        return sources

    try:
        corpus_srcs = [s for s in sources if not s.get("doc_id", "").startswith("web:")]
        web_srcs = [s for s in sources if s.get("doc_id", "").startswith("web:")]

        scored: list[tuple[float, dict]] = []
        for src in corpus_srcs:
            doc_id = src.get("doc_id", "")
            pns = src.get("page_numbers", [])
            # Score the first (usually only) page for this source entry
            s = score_source(answer, doc_id, pns[0]) if doc_id and pns else 0.0
            scored.append((s, src))

        scored.sort(key=lambda x: x[0], reverse=True)
        result = [s for _, s in scored] + web_srcs

        if result and sources and result[0].get("doc_id") != sources[0].get("doc_id"):
            logger.info(
                "evidence_verifier: agent sources re-ranked — top source %s (was %s)",
                result[0].get("doc_id", "?")[:20],
                sources[0].get("doc_id", "?")[:20],
            )
        return result
    except Exception as exc:
        logger.warning("evidence_verifier: rerank_agent_sources failed: %s", exc)
        return sources


def find_evidence_pages(
    answer: str,
    answer_type: str,
    doc_id: str,
    candidate_page_nums: list[int],
    top_k: int = 2,
) -> list[int]:
    """Re-rank candidate pages by how well each supports the answer.

    Returns candidate_page_nums re-ranked so the highest-evidence pages come
    first, capped at top_k.  Falls back to the original order on any error so
    callers are never blocked.

    Composite score weights:
      date/number/name/names: 0.70 × exact + 0.30 × fuzzy
        (lexical signal dominates for factual extraction)
      free_text/boolean:      0.40 × exact + 0.30 × fuzzy + 0.30 × semantic
        (semantic signal helps for paraphrased/reasoned answers)

    Parameters
    ----------
    answer:
        The generated answer text (or str(answer) for non-string types).
    answer_type:
        One of date/number/name/names/boolean/free_text.
    doc_id:
        Document identifier — used to fetch page text via _extract_page_text.
    candidate_page_nums:
        Pages to re-rank (typically 1–5 pages from the retriever/verifier).
    top_k:
        Maximum pages to return after re-ranking.
    """
    if not answer or not candidate_page_nums:
        return candidate_page_nums

    try:
        from arlc.retriever import _extract_page_text  # lazy import

        answer_str = str(answer)
        keywords = _extract_keywords(answer_str, answer_type)
        use_semantic = answer_type in ("free_text", "boolean") and len(answer_str) > 30
        scores: dict[int, float] = {}

        for page_num in candidate_page_nums:
            page_text = _extract_page_text(doc_id, page_num) or ""
            if not page_text:
                scores[page_num] = 0.0
                continue

            page_lower = page_text.lower()

            # Pass 1: exact keyword presence fraction
            exact_hits = sum(1 for kw in keywords if kw.lower() in page_lower)
            p1 = exact_hits / max(len(keywords), 1)

            # Pass 2: fuzzy sliding-window match
            p2 = _fuzzy_match_score(answer_str, page_text)

            # Pass 3: semantic similarity (costly — gated to free_text/boolean)
            p3 = _semantic_score(answer_str, page_text) if use_semantic else 0.0

            if answer_type in ("date", "number", "name", "names"):
                scores[page_num] = 0.70 * p1 + 0.30 * p2
            else:
                scores[page_num] = 0.40 * p1 + 0.30 * p2 + 0.30 * p3

        # Log a warning when no page has meaningful evidence support
        max_score = max(scores.values(), default=0.0)
        if max_score < 0.05 and len(candidate_page_nums) > 0:
            logger.warning(
                "evidence_verifier: low confidence for %s %s — best page score %.3f "
                "(answer may not be grounded in provided pages)",
                doc_id[:12],
                answer_type,
                max_score,
            )

        re_ranked = sorted(candidate_page_nums, key=lambda p: scores.get(p, 0.0), reverse=True)
        result = re_ranked[:top_k]

        # Log re-ranking changes for observability
        if result and candidate_page_nums and result[0] != candidate_page_nums[0]:
            logger.info(
                "evidence_verifier: page re-ranked for %s %s — top page %d (was %d), scores: %s",
                doc_id[:12],
                answer_type,
                result[0],
                candidate_page_nums[0],
                {p: round(scores.get(p, 0.0), 3) for p in candidate_page_nums[:5]},
            )

        return result

    except Exception as exc:
        logger.warning(
            "evidence_verifier: failed for %s pages=%s: %s",
            doc_id[:12],
            candidate_page_nums,
            exc,
        )
        return candidate_page_nums[:top_k]
