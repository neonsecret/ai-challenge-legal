"""Citation validation: hallucinated-index filter + evidence→claim cross-check.

Two post-processing passes run after the agent produces its final answer:

1. **Hallucinated-index filter** — scans the answer for [DOC-N] references
   where N exceeds the number of accumulated documents. These phantom
   citations are stripped from the answer text so the frontend never
   renders a dangling footnote.

2. **Evidence→claim cross-check** — for each [DOC-N] cited in the answer,
   extracts the surrounding claim text and scores it against the actual
   document content. Citations with near-zero evidence support are
   stripped (the claim remains, only the unsupported tag is removed).

Both passes are non-destructive to the source list — they only modify
the answer text. Source ordering is never changed (rule 16).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_DOC_TAG_RE = re.compile(r"\[DOC-(\d+)\]")

# Context window: chars before/after [DOC-N] to extract as the "claim"
_CLAIM_CONTEXT_CHARS = 200

# Minimum evidence score to keep a citation (0.0–1.0).
# Below this threshold the citation tag is removed from the answer.
_MIN_EVIDENCE_SCORE = 0.04

_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would could should may might must shall can cannot of in on "
    "at to for with from by and or but not if as so that this these "
    "those it its which who whom whose when where why how all any each "
    "both some no nor more very also just only even still about after "
    "before between through without during".split(),
)


def filter_hallucinated_indices(answer: str, num_docs: int) -> tuple[str, list[int]]:
    """Remove [DOC-N] tags where N is outside the valid range [1, num_docs].

    Returns the cleaned answer and a list of removed indices (for logging).
    """
    if not answer or num_docs < 0:
        return answer, []

    removed: list[int] = []

    def _replace(m: re.Match) -> str:
        idx = int(m.group(1))
        if idx < 1 or idx > num_docs:
            removed.append(idx)
            return ""
        return m.group(0)

    cleaned = _DOC_TAG_RE.sub(_replace, answer)

    if removed:
        logger.warning(
            "citation_validator: stripped %d hallucinated index(es) %s (valid range 1–%d)",
            len(removed),
            sorted(set(removed)),
            num_docs,
        )

    return cleaned, removed


def _extract_claim_context(answer: str, match: re.Match) -> str:
    """Extract the text surrounding a [DOC-N] tag as the claim to verify."""
    start = max(0, match.start() - _CLAIM_CONTEXT_CHARS)
    end = min(len(answer), match.end() + _CLAIM_CONTEXT_CHARS)
    context = answer[start:end]
    # Strip other [DOC-N] tags from the context to get pure claim text
    return _DOC_TAG_RE.sub("", context).strip()


def _score_claim_against_doc(claim: str, doc_text: str) -> float:
    """Score how well a document supports a claim using keyword overlap.

    Simple but effective: extracts non-stopword tokens from the claim and
    checks what fraction appear in the document text. This catches the
    common hallucination pattern where the LLM cites a document that
    discusses an entirely different topic.

    Returns a float in [0.0, 1.0].
    """
    if not claim or not doc_text:
        return 0.0

    claim_tokens = re.findall(r"[a-zA-Z0-9\u00c0-\u024f]+", claim.lower())
    keywords = [t for t in claim_tokens if t not in _STOPWORDS and len(t) >= 3]

    if not keywords:
        return 0.0

    doc_lower = doc_text.lower()
    hits = sum(1 for kw in keywords if kw in doc_lower)
    return hits / len(keywords)


def cross_check_citations(
    answer: str,
    docs: list[dict],
) -> tuple[str, list[int]]:
    """Verify each [DOC-N] citation against its document's content.

    For each [DOC-N] in the answer:
    - Extract the surrounding claim text (~200 chars each side)
    - Score the claim against the cited document's text
    - If the score is below _MIN_EVIDENCE_SCORE, strip the tag

    Args:
        answer: The agent's final answer text with [DOC-N] citations.
        docs: Accumulated documents list (0-indexed; DOC-1 = docs[0]).
              Each doc must have a "text" key.

    Returns:
        Tuple of (cleaned answer, list of removed DOC indices).
    """
    if not answer or not docs:
        return answer, []

    tags_to_remove: set[int] = set()

    for m in _DOC_TAG_RE.finditer(answer):
        idx = int(m.group(1))
        if idx < 1 or idx > len(docs):
            continue  # already handled by filter_hallucinated_indices

        doc = docs[idx - 1]
        doc_text = doc.get("text", "")
        if not doc_text:
            continue  # no text to verify against — keep the citation

        claim = _extract_claim_context(answer, m)
        if not claim:
            continue

        score = _score_claim_against_doc(claim, doc_text)
        if score < _MIN_EVIDENCE_SCORE:
            tags_to_remove.add(idx)
            logger.info(
                "citation_validator: DOC-%d evidence score %.3f < %.3f — removing (claim: '%.60s…', doc: '%.40s…')",
                idx,
                score,
                _MIN_EVIDENCE_SCORE,
                claim,
                doc_text[:40],
            )

    if not tags_to_remove:
        return answer, []

    def _remove_weak(m: re.Match) -> str:
        return "" if int(m.group(1)) in tags_to_remove else m.group(0)

    cleaned = _DOC_TAG_RE.sub(_remove_weak, answer)
    removed = sorted(tags_to_remove)

    logger.warning(
        "citation_validator: cross-check removed %d weak citation(s): DOC-%s",
        len(removed),
        removed,
    )

    return cleaned, removed


def validate_citations(
    answer: str,
    accumulated_docs: list[dict],
) -> str:
    """Run full citation validation pipeline on an agent answer.

    Combines both passes:
    1. filter_hallucinated_indices — remove out-of-range [DOC-N]
    2. cross_check_citations — remove unsupported [DOC-N]

    Returns the cleaned answer text.
    """
    if not answer:
        return answer

    num_docs = len(accumulated_docs)

    # Pass 1: strip out-of-range indices
    answer, hallucinated = filter_hallucinated_indices(answer, num_docs)

    # Pass 2: evidence cross-check (only if we have docs with text)
    if accumulated_docs:
        answer, weak = cross_check_citations(answer, accumulated_docs)
    else:
        weak = []

    total_removed = len(hallucinated) + len(weak)
    if total_removed:
        logger.info(
            "citation_validator: total %d citation(s) removed (hallucinated=%d, weak_evidence=%d)",
            total_removed,
            len(hallucinated),
            len(weak),
        )

    return answer
