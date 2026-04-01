"""Page verification for the agent pipeline.

Wraps ``arlc.page_verifier`` for use in the agent's post-processing step.
The competition page verifier expects structured answer types (boolean,
number, date, etc.), but the agent produces free-form text answers.  This
module provides a simplified adapter that:

1. Treats every agent answer as ``free_text`` for verification purposes.
2. Runs the keyword-based page verifier (no LLM fallback by default).
3. Replaces NO_SUPPORT pages with better alternatives from the same doc.
4. Is fully non-blocking: any failure preserves the original sources.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def verify_agent_pages(
    question: str,
    answer: str,
    sources: list[dict],
) -> list[dict]:
    """Verify that cited pages support the agent's answer.

    Delegates to :func:`arlc.page_verifier.verify_pages` with
    ``answer_type="free_text"``.  If verification improves a page
    citation (finds a better supporting page in the same document),
    the source entry is updated in place.

    Parameters
    ----------
    question : str
        The user's question.
    answer : str
        The agent's generated answer text.
    sources : list[dict]
        Source entries in the format
        ``[{"doc_id": str, "page_numbers": [int], "text": str}, ...]``.

    Returns
    -------
    list[dict]
        Updated sources list.  Same length as input; only
        ``page_numbers`` may change if a better page was found.
    """
    if not answer or not sources:
        return sources

    try:
        from arlc.page_verifier import verify_pages
    except ImportError:
        logger.debug("[agent] page_verifier not available, skipping verification")
        return sources

    # Build the pages list in the format verify_pages expects:
    # [{doc_id: str, page_numbers: [int]}, ...]
    pages_for_verifier = [{"doc_id": s["doc_id"], "page_numbers": list(s.get("page_numbers", []))} for s in sources]

    try:
        verified = verify_pages(
            question=question,
            answer=answer,
            answer_type="free_text",
            pages=pages_for_verifier,
            use_llm_fallback=False,  # keyword-only, no extra LLM cost
        )
    except Exception:
        logger.exception("[agent] page verification failed, keeping original sources")
        return sources

    # Apply verified page numbers back to sources.
    # The verifier may have swapped a page number if it found a better one.
    changes = 0
    for original, updated in zip(sources, verified):
        old_pages = original.get("page_numbers", [])
        new_pages = updated.get("page_numbers", [])
        if old_pages != new_pages:
            original["page_numbers"] = new_pages
            changes += 1
            logger.info(
                "[agent] page verified: %s pages %s -> %s",
                original["doc_id"],
                old_pages,
                new_pages,
            )

    if changes:
        logger.info("[agent] page verification updated %d/%d sources", changes, len(sources))
    else:
        logger.debug("[agent] page verification: all sources confirmed")

    return sources
