# Custom legal tokenizer inspired by IAS Partners (guy4)
"""
Legal-domain tokenizer that expands compound legal references into
multiple searchable tokens. Used for entity extraction and keyword
matching in queries containing case IDs, article references, law numbers, etc.
"""

import re
from typing import Union

# --- Legal reference patterns ---

# Case IDs: "CFI 057/2025" or "CFI-057-2025"
_CASE_ID_RE = re.compile(r"\b([A-Z]{2,5})[\s\-/](\d{2,4})[\s\-/](\d{4})\b")

# ENF refs: "ENF 022/2023" or "ENF-022-2023"
_ENF_RE = re.compile(r"\b(ENF)[\s\-/](\d{2,4})[\s\-/](\d{4})\b", re.IGNORECASE)

# Article refs: "Article 28(1)" or "Article 28(1)(a)" or "Article 28"
_ARTICLE_RE = re.compile(r"\b(Article|Art\.?)\s+(\d+)(?:\((\w+)\))?(?:\((\w+)\))?", re.IGNORECASE)

# Law numbers: "DIFC Law No. 4 of 2019" or "Law No 4 of 2019"
_LAW_NO_RE = re.compile(r"\b(\w+)\s+Law\s+No\.?\s*(\d+)\s+of\s+(\d{4})\b", re.IGNORECASE)

# Schedule refs: "Schedule 3" or "Schedule 3A"
_SCHEDULE_RE = re.compile(r"\b(Schedule)\s+(\w+)\b", re.IGNORECASE)

# Regulation refs: "Regulation 3.1" or "Regulation 3.1.2"
_REGULATION_RE = re.compile(r"\b(Regulation)\s+(\d+(?:\.\d+)*)\b", re.IGNORECASE)

# Standard word tokenizer (same as sklearn/bm25s default)
_WORD_RE = re.compile(r"(?u)\b\w\w+\b")

# English stopwords (compact set matching bm25s "en")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "if",
        "in",
        "into",
        "is",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "such",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "will",
        "with",
    },
)


def _expand_legal_refs(text: str) -> list[str]:
    """Extract expanded tokens from legal references in text."""
    extra_tokens = []

    # ENF refs (check before generic case ID to avoid double-matching)
    for m in _ENF_RE.finditer(text):
        num, year = m.group(2), m.group(3)
        extra_tokens.extend(
            [
                f"enf_{num}_{year}",
                num,
                year,
            ],
        )

    # Case IDs (skip ENF ones already handled)
    for m in _CASE_ID_RE.finditer(text):
        prefix, num, year = m.group(1), m.group(2), m.group(3)
        if prefix.upper() == "ENF":
            continue
        normalized = f"{prefix.lower()}_{num}_{year}"
        extra_tokens.extend(
            [
                normalized,
                num,
                year,
            ],
        )

    # Article refs
    for m in _ARTICLE_RE.finditer(text):
        art_num = m.group(2)
        sub1 = m.group(3)
        sub2 = m.group(4)
        extra_tokens.append(f"article_{art_num}")
        if sub1:
            extra_tokens.append(f"article_{art_num}_{sub1}")
            extra_tokens.append(sub1)
        if sub2:
            extra_tokens.append(f"article_{art_num}_{sub1}_{sub2}")
            extra_tokens.append(sub2)

    # Law numbers
    for m in _LAW_NO_RE.finditer(text):
        prefix, num, year = m.group(1), m.group(2), m.group(3)
        extra_tokens.append(f"{prefix.lower()}_law_{num}_{year}")

    # Schedule refs
    for m in _SCHEDULE_RE.finditer(text):
        sched_id = m.group(2)
        extra_tokens.append(f"schedule_{sched_id.lower()}")

    # Regulation refs
    for m in _REGULATION_RE.finditer(text):
        reg_parts = m.group(2).split(".")
        extra_tokens.append(f"regulation_{'_'.join(reg_parts)}")
        extra_tokens.extend(reg_parts)

    return extra_tokens


def legal_tokenize(text: str) -> list[str]:
    """Tokenize text with legal reference expansion.

    Combines standard word tokenization with expanded legal reference tokens.
    Applies lowercasing and stopword removal.
    """
    # Standard word tokens (lowercased, stopwords removed)
    words = _WORD_RE.findall(text.lower())
    tokens = [w for w in words if w not in _STOPWORDS]

    # Add expanded legal reference tokens
    tokens.extend(_expand_legal_refs(text))

    return tokens


def legal_tokenize_query(query: str) -> list[str]:
    """Tokenize a query with legal reference expansion.

    Same as legal_tokenize — queries get the same expansion so that
    a query for "Article 28(1)" matches documents containing that reference.
    """
    return legal_tokenize(query)


def legal_tokenize_corpus(texts: list[str]) -> list[list[str]]:
    """Tokenize a corpus of texts with legal reference expansion.

    Returns list-of-lists of tokenized text.
    """
    return [legal_tokenize(text) for text in texts]


def legal_tokenize_queries(queries: Union[str, list[str]]) -> list[list[str]]:
    """Tokenize one or more queries with legal reference expansion.

    Returns list-of-lists of tokenized text. Accepts a single string or list of strings.
    """
    if isinstance(queries, str):
        queries = [queries]
    return [legal_tokenize_query(q) for q in queries]
