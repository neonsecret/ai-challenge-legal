"""Citation validation: hallucinated-index filter + evidence→claim cross-check.

Three post-processing passes run after the agent produces its final answer:

1. **Hallucinated-index filter** — scans the answer for [DOC-N] references
   where N is outside the valid range [1, len(docs)]. Any phantom citation
   triggers a full regen of the answer so the model re-answers with only the
   documents it actually retrieved.

2. **Evidence→claim cross-check (keyword)** — for each [DOC-N] cited in the
   answer, extracts the surrounding claim text and scores it against the
   actual document content. Citations with near-zero keyword overlap are
   stripped. This is the sync fallback when no LLM client is available.

3. **Evidence→claim cross-check (LLM)** — async Haiku-based version that
   replaces the keyword scorer when an LLM client is supplied. More accurate
   on short or highly technical claims where keyword overlap is low even for
   genuine citations.

Both cross-check variants are non-destructive to the source list — they only
modify the answer text. Source ordering is never changed (rule 16).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

_DOC_TAG_RE = re.compile(r"\[DOC-(\d+)\]")

# Characters before/after [DOC-N] used as the "claim" context window
_CLAIM_CONTEXT_CHARS = 200

# Minimum keyword-overlap score to keep a citation (0.0–1.0).
_MIN_EVIDENCE_SCORE = 0.04

# Regen is triggered when the model cited a DOC-N outside valid range.
# Even one hallucinated index signals the model was confused about what
# it retrieved — regenerating with a corrected context is safer than
# stripping the phantom references and hoping the rest is accurate.
_REGEN_ON_ANY_HALLUCINATED_INDEX = True

_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would could should may might must shall can cannot of in on "
    "at to for with from by and or but not if as so that this these "
    "those it its which who whom whose when where why how all any each "
    "both some no nor more very also just only even still about after "
    "before between through without during".split(),
)


# ---------------------------------------------------------------------------
# Public names matching the task spec
# ---------------------------------------------------------------------------


def validate_citation_indices(answer: str, docs: list[dict]) -> tuple[str, bool, list[int]]:
    """Synchronous pre-display check for out-of-range [DOC-N] references.

    Scans *answer* for [DOC-N] tags where N is outside [1, len(docs)].
    Strips phantom tags and signals whether the answer should be regenerated.

    Args:
        answer: The agent's final answer text.
        docs: Accumulated documents (0-indexed; DOC-1 = docs[0]).

    Returns:
        Tuple of (cleaned_answer, should_regen, hallucinated_indices).
        ``should_regen`` is True when any hallucinated index was found.
    """
    if not answer:
        return answer, False, []

    num_docs = len(docs)
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
            "citation_validator: %d hallucinated index(es) %s stripped (valid range 1–%d)",
            len(removed),
            sorted(set(removed)),
            num_docs,
        )

    should_regen = bool(removed) and _REGEN_ON_ANY_HALLUCINATED_INDEX
    return cleaned, should_regen, removed


async def verify_claim_evidence(
    sentence: str,
    cited_docs: list[dict],
    llm: BaseChatModel | None = None,
) -> bool:
    """Check whether *cited_docs* support the claim in *sentence*.

    When *llm* is supplied (Haiku recommended for speed), uses an LLM to
    assess evidence quality. Falls back to keyword overlap when *llm* is None.

    Args:
        sentence: The claim sentence extracted from the answer.
        cited_docs: List of doc dicts (each must have a "text" key) that
                    the claim cites.
        llm: Optional language model for evidence scoring.

    Returns:
        True if the evidence supports the claim, False otherwise.
    """
    if not sentence or not cited_docs:
        return True  # no evidence to check → keep citation

    doc_texts = [d.get("text", "") for d in cited_docs if d.get("text")]
    combined_doc = "\n---\n".join(doc_texts[:3])  # cap at 3 docs to limit tokens

    if llm is not None:
        return await _verify_with_llm(sentence, combined_doc, llm)

    # Keyword fallback
    return _verify_with_keywords(sentence, combined_doc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_claim_context(answer: str, match: re.Match) -> str:
    start = max(0, match.start() - _CLAIM_CONTEXT_CHARS)
    end = min(len(answer), match.end() + _CLAIM_CONTEXT_CHARS)
    context = answer[start:end]
    return _DOC_TAG_RE.sub("", context).strip()


def _score_claim_against_doc(claim: str, doc_text: str) -> float:
    if not claim or not doc_text:
        return 0.0
    claim_tokens = re.findall(r"[a-zA-Z0-9\u00c0-\u024f]+", claim.lower())
    keywords = [t for t in claim_tokens if t not in _STOPWORDS and len(t) >= 3]
    if not keywords:
        return 0.0
    doc_lower = doc_text.lower()
    hits = sum(1 for kw in keywords if kw in doc_lower)
    return hits / len(keywords)


def _verify_with_keywords(sentence: str, doc_text: str) -> bool:
    return _score_claim_against_doc(sentence, doc_text) >= _MIN_EVIDENCE_SCORE


async def _verify_with_llm(sentence: str, doc_text: str, llm: BaseChatModel) -> bool:
    """Call the LLM to judge whether *doc_text* supports *sentence*."""
    from langchain_core.messages import HumanMessage, SystemMessage

    system = (
        "You are a citation evidence verifier. "
        "Given a legal claim and a source document excerpt, decide whether "
        "the document actually supports that specific claim. "
        "Reply with exactly one word: YES or NO."
    )
    human = (
        f"CLAIM: {sentence[:400]}\n\n"
        f"DOCUMENT EXCERPT:\n{doc_text[:800]}\n\n"
        "Does this document support the claim? (YES/NO)"
    )
    try:
        response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])
        text = response.content if isinstance(response.content, str) else str(response.content)
        return text.strip().upper().startswith("YES")
    except Exception:
        logger.exception("citation_validator: LLM evidence check failed, falling back to keywords")
        return _verify_with_keywords(sentence, doc_text)


def cross_check_citations(
    answer: str,
    docs: list[dict],
) -> tuple[str, list[int]]:
    """Keyword-based evidence cross-check (sync).

    Strips [DOC-N] tags where the cited document has near-zero keyword
    overlap with the surrounding claim text. This is the sync fallback;
    use the async LLM path for higher accuracy.

    Args:
        answer: Agent answer text with [DOC-N] citations.
        docs: Accumulated documents (0-indexed; DOC-1 = docs[0]).

    Returns:
        Tuple of (cleaned answer, sorted list of removed DOC indices).
    """
    if not answer or not docs:
        return answer, []

    tags_to_remove: set[int] = set()

    for m in _DOC_TAG_RE.finditer(answer):
        idx = int(m.group(1))
        if idx < 1 or idx > len(docs):
            continue  # already handled by validate_citation_indices

        doc = docs[idx - 1]
        doc_text = doc.get("text", "")
        if not doc_text:
            continue

        claim = _extract_claim_context(answer, m)
        if not claim:
            continue

        score = _score_claim_against_doc(claim, doc_text)
        if score < _MIN_EVIDENCE_SCORE:
            tags_to_remove.add(idx)
            logger.info(
                "citation_validator: DOC-%d score=%.3f < %.3f — removing (claim: '%.60s…', doc: '%.40s…')",
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


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def validate_citations(
    answer: str,
    accumulated_docs: list[dict],
) -> tuple[str, bool]:
    """Run full citation validation pipeline on an agent answer.

    Combines:
    1. validate_citation_indices — strip + flag out-of-range [DOC-N]
    2. cross_check_citations — strip keyword-unsupported [DOC-N]

    Returns:
        Tuple of (cleaned_answer, should_regen).
        ``should_regen`` is True when hallucinated indices were found and
        a full regen of the answer is warranted.
    """
    if not answer:
        return answer, False

    # Pass 1: hallucinated-index gate (synchronous, strict)
    answer, should_regen, hallucinated = validate_citation_indices(answer, accumulated_docs)

    # Pass 2: keyword evidence cross-check
    if accumulated_docs:
        answer, weak = cross_check_citations(answer, accumulated_docs)
    else:
        weak = []

    total_removed = len(hallucinated) + len(weak)
    if total_removed:
        logger.info(
            "citation_validator: %d citation(s) removed (hallucinated=%d, weak_evidence=%d, regen=%s)",
            total_removed,
            len(hallucinated),
            len(weak),
            should_regen,
        )

    return answer, should_regen
