"""LLM-based page reranking using Anthropic SDK (Haiku).

Implements the Enterprise RAG Challenge winner's core strategy:
  - Cross-encoder scores provide fast initial ranking (30% weight)
  - Haiku judges each page's relevance to the question (70% weight)
  - Weighted combination gives the final ranking

Why this matters for legal RAG:
  Cross-encoders are trained on general text and may miss legal-domain nuances.
  An LLM reranker understands the specific legal question intent — "what does
  Article 14(2)(b) require?" vs "does Article 14 apply here?" — and can score
  pages accordingly, especially for multi-clause legal provisions.

Reference: https://abdullin.com/ilya/how-to-build-best-rag/
  "Weighted scoring: vector 30% + LLM reranker 70%"
"""

import json
import logging
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (all overridable via environment)
# ---------------------------------------------------------------------------

LLM_RERANK_MODEL = os.environ.get("LLM_RERANK_MODEL", "claude-haiku-4-5-20251001")

# Enterprise RAG winner used 70% LLM / 30% vector. We inherit cross-encoder
# scores instead of raw vector scores, which are already stronger than pure vector.
LLM_WEIGHT = float(os.environ.get("LLM_RERANK_WEIGHT", "0.70"))
CROSS_ENCODER_WEIGHT = 1.0 - LLM_WEIGHT

# Max characters of page text sent to Haiku per candidate (controls cost/latency).
# 1500 chars ≈ 375 tokens. At 3 candidates: ~1125 tokens input.
MAX_PAGE_TEXT_CHARS = int(os.environ.get("LLM_RERANK_MAX_CHARS", "1500"))

MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# LLM client — uses llm_router for backend selection
# ---------------------------------------------------------------------------

def _get_llm_fn():
    """Get the best available LLM call function."""
    try:
        from arlc.llm import router as llm_router
        return llm_router.call_llm
    except ImportError:
        from arlc.llm import anthropic_backend as llm_anthropic
        return llm_anthropic.call_llm


# ---------------------------------------------------------------------------
# Score normalization
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    """Map a cross-encoder logit to (0, 1) via sigmoid.

    Cross-encoders like bge-reranker-v2-m3 output raw logit scores (can be
    negative or large positive). Sigmoid maps them to a comparable [0, 1]
    range without needing batch statistics.
    """
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# Core reranking function
# ---------------------------------------------------------------------------

def llm_rerank_pages(
    question: str,
    pages: list,  # list[PageResult] — avoid circular import, duck-typed
    llm_weight: float = LLM_WEIGHT,
    model: str = LLM_RERANK_MODEL,
    max_retries: int = MAX_RETRIES,
) -> list:
    """Rerank page results using LLM relevance scoring (Enterprise RAG winner approach).

    Parameters
    ----------
    question : str
        The legal question being answered.
    pages : list[PageResult]
        Candidate pages from cross-encoder retrieval, pre-sorted by cross-encoder score.
    llm_weight : float
        Weight for LLM score in the weighted combination (default 0.70).
    model : str
        Anthropic model to use for reranking (default: claude-haiku-4-5).
    max_retries : int
        Number of retries on API errors (with exponential backoff).

    Returns
    -------
    list[PageResult]
        Pages reranked by the weighted LLM + cross-encoder score.
        Falls back to original cross-encoder order on any failure.

    Notes
    -----
    - All candidates are scored in a SINGLE Haiku call (efficient batching).
    - Cross-encoder logit scores are normalized via sigmoid before weighting.
    - LLM scores are clamped to [0, 1].
    - Final score = llm_weight * llm_score + (1 - llm_weight) * ce_norm_score
    """
    if not pages:
        return pages

    # Single page: no reranking needed, return immediately
    if len(pages) == 1:
        logger.debug("[llm_rerank] Single candidate, skipping LLM call")
        return pages

    ce_weight = 1.0 - llm_weight

    # Normalize cross-encoder scores (logits -> [0, 1]) via sigmoid
    ce_norm = {i: _sigmoid(float(p.score)) for i, p in enumerate(pages)}

    # Build candidate text blocks for the prompt
    candidate_blocks = []
    for i, page in enumerate(pages):
        # Truncate to control cost; strip leading whitespace from page text
        text_preview = page.text[:MAX_PAGE_TEXT_CHARS].strip()
        # Add ellipsis if truncated
        if len(page.text) > MAX_PAGE_TEXT_CHARS:
            text_preview += "…"
        candidate_blocks.append(
            f"[CANDIDATE {i + 1}]\n"
            f"Document: {page.doc_id} | Page {page.page_number}\n\n"
            f"{text_preview}"
        )

    candidates_block = "\n\n---\n\n".join(candidate_blocks)

    # Recall-biased LLM reranker prompt — inspired by CPBD (1st place, G=0.990).
    # Key insight: "Missing a gold page is ~6x worse than including a marginally
    # relevant page" (F-beta 2.5 scoring). Bias scoring toward INCLUSION.
    prompt = (
        f"You are a legal document relevance expert.\n\n"
        f"QUESTION: {question}\n\n"
        f"Rate each candidate page's relevance to answering the question above.\n"
        f"Score 0.0 (not relevant) to 1.0 (directly answers the question).\n\n"
        f"CRITICAL BIAS: When uncertain whether a page is relevant, ROUND UP.\n"
        f"Missing a relevant page is approximately 6x worse than including a\n"
        f"marginally relevant one. When in doubt, score higher.\n\n"
        f"Scoring guide:\n"
        f"  1.0 — Page directly and completely answers the question\n"
        f"  0.8 — Page contains the key legal provision or fact asked about\n"
        f"  0.6 — Page contains related information or supporting context\n"
        f"  0.4 — Page is possibly relevant — score here when UNCERTAIN\n"
        f"  0.1 — Page is very unlikely to be relevant\n"
        f"  0.0 — Page is clearly not relevant to this question\n\n"
        f"CANDIDATE PAGES:\n\n"
        f"{candidates_block}\n\n"
        f"Output ONLY a valid JSON object mapping candidate number strings to float scores.\n"
        f"Example for {len(pages)} candidates: "
        f"{{{', '.join(f'\"{i+1}\": 0.5' for i in range(len(pages)))}}}\n\n"
        f"JSON scores:"
    )

    for attempt in range(max_retries + 1):
        try:
            t0 = time.monotonic()
            llm_fn = _get_llm_fn()
            content, _, elapsed_ms, _, _, _ = llm_fn(
                "", prompt, max_tokens=128, model=model,
            )
            content = content.strip()

            # Parse JSON scores — robust extraction handles surrounding text
            llm_scores = _parse_scores(content, n_candidates=len(pages))

            # Compute weighted combined scores
            scored = []
            for i, page in enumerate(pages):
                ce_score_norm = ce_norm[i]
                llm_score = llm_scores.get(i + 1, 0.5)  # 1-indexed from prompt
                llm_score = max(0.0, min(1.0, llm_score))
                combined = llm_weight * llm_score + ce_weight * ce_score_norm
                scored.append((page, combined, ce_score_norm, llm_score))

            scored.sort(key=lambda x: x[1], reverse=True)

            # Rebuild PageResult list with updated combined scores
            # We import PageResult here to avoid circular imports at module level
            from arlc.retriever import PageResult
            result = [
                PageResult(
                    doc_id=page.doc_id,
                    page_number=page.page_number,
                    score=combined,
                    text=page.text,
                )
                for page, combined, _, _ in scored
            ]

            # Detailed log for debugging
            ranking_summary = " | ".join(
                f"{page.doc_id[:12]}:p{page.page_number} "
                f"(ce={ce:.2f} llm={llm:.2f} comb={comb:.2f})"
                for page, comb, ce, llm in scored
            )
            logger.info(
                "[llm_rerank] %.0fms | %d candidates | %s",
                elapsed_ms, len(pages), ranking_summary,
            )
            print(
                f"[llm_rerank] {elapsed_ms:.0f}ms | "
                f"top: {result[0].doc_id[:12]}:p{result[0].page_number} "
                f"(combined={scored[0][1]:.2f})"
            )

            return result

        except json.JSONDecodeError as e:
            logger.warning(
                "[llm_rerank] JSON parse error (attempt %d/%d): %s",
                attempt + 1, max_retries + 1, e,
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)

        except anthropic.RateLimitError:
            wait = 2 ** attempt * 3
            logger.warning(
                "[llm_rerank] Rate limit (attempt %d/%d), waiting %ds",
                attempt + 1, max_retries + 1, wait,
            )
            if attempt < max_retries:
                time.sleep(wait)

        except anthropic.APIStatusError as e:
            logger.warning(
                "[llm_rerank] API status error (attempt %d/%d): %s",
                attempt + 1, max_retries + 1, e,
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)

        except Exception as e:
            logger.warning("[llm_rerank] Unexpected error: %s", e, exc_info=True)
            break

    # Fallback: return original cross-encoder order (no-op for the caller)
    logger.warning("[llm_rerank] All attempts failed, falling back to cross-encoder ranking")
    print("[llm_rerank] FALLBACK: using cross-encoder ranking")
    return pages


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _parse_scores(content: str, n_candidates: int) -> dict[int, float]:
    """Parse LLM score output into {1-indexed candidate: float} dict.

    Robust to common LLM formatting quirks:
      - Trailing commas in JSON ("1": 0.9,}  -> fixed)
      - Extra prose before/after the JSON object
      - String values instead of floats ("0.9" -> 0.9)
      - Missing candidates (filled with 0.5 default)
    """
    # Extract JSON object from possibly verbose response
    json_match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
    if not json_match:
        raise json.JSONDecodeError("No JSON object found", content, 0)

    raw_json = json_match.group()

    # Fix trailing commas (common LLM mistake: {"1": 0.9, "2": 0.3,})
    raw_json = re.sub(r',\s*([}\]])', r'\1', raw_json)

    parsed = json.loads(raw_json)

    scores: dict[int, float] = {}
    for k, v in parsed.items():
        try:
            candidate_idx = int(k)
            score = float(v)
            if 1 <= candidate_idx <= n_candidates:
                scores[candidate_idx] = score
        except (ValueError, TypeError):
            continue

    # Fill missing candidates with neutral score
    for i in range(1, n_candidates + 1):
        if i not in scores:
            logger.debug("[llm_rerank] Missing score for candidate %d, using 0.5", i)
            scores[i] = 0.5

    return scores
