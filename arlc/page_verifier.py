"""Page verification: verify cited pages support the answer, re-select if not.

Two-stage process:
1. Check if the cited page text contains evidence for the answer
2. If NO_SUPPORT, scan adjacent/all pages in the doc and pick the best one

Designed to be called between answer generation (Step 3) and post-processing (Step 5)
in finals.py.
"""

import logging
import os
import re
import unicodedata
from datetime import datetime

import pymupdf

logger = logging.getLogger(__name__)

# LLM page intersection approach inspired by IAS Partners (guy4)
ENABLE_LLM_FALLBACK = os.environ.get("PAGE_VERIFY_LLM", "false").lower() == "true"

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "documents")

# Page text cache: doc_id -> {page_num (int) -> text}
_page_text_cache: dict[str, dict[int, str]] = {}


# ---------------------------------------------------------------------------
# PDF text extraction (with caching)
# ---------------------------------------------------------------------------

def _get_page_text(doc_id: str, page_number: int) -> str:
    """Get text for a specific page (1-based). Cached per doc."""
    if doc_id in _page_text_cache and page_number in _page_text_cache[doc_id]:
        return _page_text_cache[doc_id][page_number]

    pdf_path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.pdf")
    if not os.path.exists(pdf_path):
        return ""

    doc = None
    try:
        doc = pymupdf.open(pdf_path)
        # Cache all pages at once (avoids repeated file opens)
        if doc_id not in _page_text_cache:
            _page_text_cache[doc_id] = {}
        for i in range(len(doc)):
            pnum = i + 1
            if pnum not in _page_text_cache[doc_id]:
                _page_text_cache[doc_id][pnum] = doc[i].get_text().strip()
        return _page_text_cache[doc_id].get(page_number, "")
    except Exception as e:
        logger.warning(f"[page_verifier] Failed to read {doc_id} page {page_number}: {e}")
        return ""
    finally:
        if doc is not None:
            doc.close()


def _get_doc_page_count(doc_id: str) -> int:
    """Get total page count for a document."""
    # Ensure doc is loaded into cache
    _get_page_text(doc_id, 1)
    return len(_page_text_cache.get(doc_id, {}))


def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase, NFKC, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Stage 1: Page verification (deterministic, no LLM)
# ---------------------------------------------------------------------------

CONFIRMED = "CONFIRMED"
WEAK = "WEAK"
NO_SUPPORT = "NO_SUPPORT"


def _extract_answer_keywords(answer, answer_type: str) -> list[str]:
    """Extract searchable keywords from the answer based on type."""
    if answer is None:
        return []

    if answer_type == "boolean":
        # For boolean, we can't verify true/false on the page — need keyword matching
        return []

    if answer_type == "number":
        # Search for the number as string
        s = str(answer).strip()
        keywords = [s]
        # Also try without decimal if it's .0
        if s.endswith(".0"):
            keywords.append(s[:-2])
        # Try with commas for large numbers (e.g., 50000 -> 50,000)
        try:
            num = float(s)
            if num == int(num) and num >= 1000:
                keywords.append(f"{int(num):,}")
        except (ValueError, OverflowError):
            pass
        return keywords

    if answer_type == "date":
        s = str(answer).strip()
        keywords = [s]  # ISO format: 2024-01-15
        # Also try common date formats
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
            keywords.extend([
                dt.strftime("%d %B %Y"),  # 15 January 2024
                dt.strftime("%d %b %Y"),  # 15 Jan 2024
                dt.strftime("%B %d, %Y"),  # January 15, 2024
                dt.strftime("%-d %B %Y"),  # 5 January 2024 (no leading zero)
                dt.strftime("%d/%m/%Y"),  # 15/01/2024
            ])
        except ValueError:
            pass
        return keywords

    if answer_type == "name":
        s = str(answer).strip()
        if not s or s.lower() == "null":
            return []
        return [s]

    if answer_type == "names":
        s = str(answer).strip()
        if not s or s.lower() == "null":
            return []
        # Split comma-separated names
        return [n.strip() for n in s.split(",") if n.strip()]

    if answer_type == "free_text":
        s = str(answer).strip()
        if not s:
            return []
        # Extract key terms: nouns, proper nouns, numbers, legal terms
        # Remove common stop words and short words
        words = re.findall(r"\b[A-Za-z0-9][\w'-]*\b", s)
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "shall",
            "should", "may", "might", "can", "could", "must", "and", "or", "but",
            "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
            "into", "through", "during", "before", "after", "above", "below",
            "between", "under", "about", "not", "no", "nor", "that", "this",
            "these", "those", "it", "its", "they", "them", "their", "we", "our",
            "he", "she", "his", "her", "you", "your", "which", "who", "whom",
            "what", "when", "where", "how", "all", "each", "every", "both",
            "any", "such", "only", "also", "than", "very", "just", "if", "so",
            "because", "while", "however", "therefore", "provided", "unless",
            "according", "based", "per", "within", "regarding", "whether",
            "document", "documents", "provided", "information", "question",
        }
        # Keep words 3+ chars that aren't stop words
        keywords = [w for w in words if len(w) >= 3 and w.lower() not in stop_words]
        # Deduplicate preserving order
        seen = set()
        unique = []
        for kw in keywords:
            low = kw.lower()
            if low not in seen:
                seen.add(low)
                unique.append(kw)
        return unique[:20]  # Cap at 20 keywords

    return []


def _verify_single_page(
        page_text: str,
        answer,
        answer_type: str,
        question: str,
) -> str:
    """Verify whether a single page supports the answer.

    Returns CONFIRMED, WEAK, or NO_SUPPORT.
    """
    if not page_text.strip():
        return NO_SUPPORT

    page_norm = _normalize(page_text)
    q_norm = _normalize(question)

    # For boolean questions, check if question keywords appear on the page
    if answer_type == "boolean":
        # Extract key nouns from the question
        q_words = re.findall(r"\b[a-z][\w'-]*\b", q_norm)
        stop = {"the", "a", "an", "is", "are", "was", "were", "does", "did",
                "do", "in", "of", "for", "to", "and", "or", "by", "this", "that",
                "same", "both", "case", "what", "who", "which", "how", "have",
                "has", "had", "been", "be", "will", "would", "shall", "should",
                "can", "could", "may", "might", "must", "not", "no", "with",
                "from", "at", "on", "as", "if", "but", "so", "than", "then"}
        q_keywords = [w for w in q_words if len(w) >= 3 and w not in stop]
        if not q_keywords:
            return WEAK
        matches = sum(1 for kw in q_keywords if kw in page_norm)
        ratio = matches / len(q_keywords)
        if ratio >= 0.5:
            return CONFIRMED
        elif ratio >= 0.25:
            return WEAK
        return NO_SUPPORT

    # For deterministic types, check if answer value appears on page
    keywords = _extract_answer_keywords(answer, answer_type)
    if not keywords:
        return WEAK  # Can't verify without keywords

    if answer_type in ("number", "date"):
        # Any keyword variant match is enough
        for kw in keywords:
            if _normalize(kw) in page_norm:
                return CONFIRMED
        return NO_SUPPORT

    if answer_type in ("name", "names"):
        # For names, check each name
        matched = 0
        for kw in keywords:
            if _normalize(kw) in page_norm:
                matched += 1
        if not keywords:
            return WEAK
        ratio = matched / len(keywords)
        if ratio >= 0.5:
            return CONFIRMED
        elif ratio > 0:
            return WEAK
        return NO_SUPPORT

    if answer_type == "free_text":
        # Keyword overlap check
        if not keywords:
            return WEAK
        matched = sum(1 for kw in keywords if _normalize(kw) in page_norm)
        ratio = matched / len(keywords)
        if ratio >= 0.4:
            return CONFIRMED
        elif ratio >= 0.2:
            return WEAK
        return NO_SUPPORT

    return WEAK


# ---------------------------------------------------------------------------
# Stage 2: Page re-selection (scan doc pages when verification fails)
# ---------------------------------------------------------------------------

def _find_best_page_in_doc(
        doc_id: str,
        answer,
        answer_type: str,
        question: str,
        current_page: int,
        max_scan: int = 30,
) -> tuple[int | None, str]:
    """Scan pages in a doc to find the best supporting page.

    Search order: adjacent pages first, then all pages.
    Returns (best_page_number, verification_status) or (None, NO_SUPPORT).
    """
    total_pages = _get_doc_page_count(doc_id)
    if total_pages == 0:
        return None, NO_SUPPORT

    # Build scan order: adjacent first, then expanding outward
    scan_order = []
    # Adjacent pages
    for offset in [-1, 1, -2, 2]:
        p = current_page + offset
        if 1 <= p <= total_pages:
            scan_order.append(p)

    # Then all remaining pages
    for p in range(1, min(total_pages + 1, max_scan + 1)):
        if p != current_page and p not in scan_order:
            scan_order.append(p)

    best_page = None
    best_status = NO_SUPPORT
    best_score = 0

    for page_num in scan_order:
        text = _get_page_text(doc_id, page_num)
        if not text.strip():
            continue

        status = _verify_single_page(text, answer, answer_type, question)
        # Score: CONFIRMED=2, WEAK=1, NO_SUPPORT=0
        score = 2 if status == CONFIRMED else (1 if status == WEAK else 0)

        if score > best_score:
            best_score = score
            best_page = page_num
            best_status = status

        # Early exit on CONFIRMED
        if status == CONFIRMED:
            break

    return best_page, best_status


def _find_best_page_llm(
        doc_id: str,
        answer,
        answer_type: str,
        question: str,
        current_page: int,
        max_scan: int = 20,
) -> int | None:
    """Use LLM to pick the best supporting page (fallback when keyword matching fails).

    Only called for free_text and boolean where keyword matching is unreliable.
    Returns page number or None.
    """
    try:
        from arlc.llm import router as llm_router
    except ImportError:
        return None

    total_pages = _get_doc_page_count(doc_id)
    if total_pages == 0:
        return None

    # Collect candidate pages (adjacent + nearby)
    candidates = []
    scan_pages = []
    for offset in range(-2, 3):
        p = current_page + offset
        if 1 <= p <= total_pages:
            scan_pages.append(p)

    # Also add a few more pages for broader coverage
    for p in range(1, min(total_pages + 1, max_scan + 1)):
        if p not in scan_pages:
            scan_pages.append(p)

    for p in scan_pages[:10]:  # Limit to 10 pages for LLM context
        text = _get_page_text(doc_id, p)
        if text.strip():
            candidates.append((p, text[:500]))  # Truncate for efficiency

    if not candidates:
        return None

    # Build prompt
    page_texts = "\n\n".join(
        f"[PAGE {p}]\n{text}" for p, text in candidates
    )

    prompt = (
        f"Question: {question}\n"
        f"Answer: {str(answer)[:400]}\n\n"
        f"Which page below BEST supports this answer? "
        f"Return ONLY the page number as a single integer.\n\n"
        f"{page_texts}"
    )
    system = "You identify which document page best supports an answer. Output only the page number."

    try:
        raw, _, _, _, _, _ = llm_router.call_llm(system, prompt, 10)
        # Extract page number
        nums = re.findall(r"\d+", raw.strip())
        if nums:
            page_num = int(nums[0])
            # Validate it's one of our candidates
            valid_pages = {p for p, _ in candidates}
            if page_num in valid_pages:
                return page_num
    except Exception as e:
        logger.warning(f"[page_verifier] LLM re-selection failed for {doc_id}: {e}")

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def verify_pages(
        question: str,
        answer,
        answer_type: str,
        pages: list[dict],
        use_llm_fallback: bool = False,
) -> list[dict]:
    """Verify that cited pages support the answer. Replace bad pages.

    Args:
        question: The question text
        answer: The generated answer (bool, int, float, str, list, or None)
        answer_type: boolean/number/date/name/names/free_text
        pages: List of {doc_id, page_numbers: [int]} from the pipeline
        use_llm_fallback: Whether to use LLM for re-selection when keyword matching fails

    Returns:
        Updated pages list with verified/corrected page citations.
        Format: [{doc_id: str, page_numbers: [int]}, ...]
    """
    if not pages or answer is None:
        return pages

    updated_pages = []
    any_changed = False

    for entry in pages:
        doc_id = entry.get("doc_id", "")
        page_numbers = entry.get("page_numbers", [])
        if not doc_id or not page_numbers:
            updated_pages.append(entry)
            continue

        new_page_numbers = []
        for page_num in page_numbers:
            page_text = _get_page_text(doc_id, page_num)
            status = _verify_single_page(page_text, answer, answer_type, question)

            if status == CONFIRMED:
                new_page_numbers.append(page_num)
                logger.debug(f"[page_verifier] {doc_id}:p{page_num} CONFIRMED")
            elif status == WEAK:
                # Keep weak pages — they might be correct
                new_page_numbers.append(page_num)
                logger.debug(f"[page_verifier] {doc_id}:p{page_num} WEAK (keeping)")
            else:
                # NO_SUPPORT — try to find a better page
                logger.info(
                    f"[page_verifier] {doc_id}:p{page_num} NO_SUPPORT — scanning for better page"
                )

                # Stage 2a: Keyword-based scan
                best_page, best_status = _find_best_page_in_doc(
                    doc_id, answer, answer_type, question, page_num
                )

                if best_page is not None and best_status in (CONFIRMED, WEAK):
                    logger.info(
                        f"[page_verifier] {doc_id}: replaced p{page_num} -> p{best_page} ({best_status})"
                    )
                    new_page_numbers.append(best_page)
                    any_changed = True
                elif use_llm_fallback and answer_type in ("free_text", "boolean"):
                    # Stage 2b: LLM-based re-selection (expensive, only for hard cases)
                    llm_page = _find_best_page_llm(
                        doc_id, answer, answer_type, question, page_num
                    )
                    if llm_page is not None:
                        logger.info(
                            f"[page_verifier] {doc_id}: LLM replaced p{page_num} -> p{llm_page}"
                        )
                        new_page_numbers.append(llm_page)
                        any_changed = True
                    else:
                        # Keep original page as fallback
                        new_page_numbers.append(page_num)
                        logger.info(
                            f"[page_verifier] {doc_id}:p{page_num} NO_SUPPORT but no better found, keeping"
                        )
                else:
                    # Keep original page as fallback
                    new_page_numbers.append(page_num)
                    logger.info(
                        f"[page_verifier] {doc_id}:p{page_num} NO_SUPPORT but no better found, keeping"
                    )

        # Deduplicate page numbers
        seen = set()
        deduped = []
        for pn in new_page_numbers:
            if pn not in seen:
                seen.add(pn)
                deduped.append(pn)

        updated_pages.append({"doc_id": doc_id, "page_numbers": deduped})

    if any_changed:
        logger.info("[page_verifier] Pages updated for question")

    return updated_pages
