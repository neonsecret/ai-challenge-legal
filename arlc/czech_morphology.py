"""Czech morphological query builder for PostgreSQL full-text search.

Czech is a highly inflected language — a single word can appear in 7+ grammatical
forms (e.g. "smlouva" / "smlouvou" / "smlouvě" / "smlouvy").  PostgreSQL's
``'simple'`` text search dictionary performs no stemming, so exact-token matching
misses most inflected forms.

This module builds a PostgreSQL ``tsquery`` that uses prefix matching (``:*``) to
capture inflected variants without requiring a Czech dictionary in the database.
The strategy:

1.  Lemmatize each query token with ``simplemma`` (Czech language model).
    simplemma maps inflected forms to their nominative/infinitive base form, which
    gives a shorter, more accurate prefix than the raw word.
2.  Only accept the lemma when it is clearly a suffix reduction of the original
    word (same first ≥60 % of characters).  If simplemma maps to an unrelated form
    (e.g. masculine ↔ feminine crossover), fall back to the original word.
3.  Truncate the base form conservatively: remove 2 suffix characters for words ≥ 8
    characters, 1 for 5–7 characters, keep as-is for shorter words.  This yields a
    stem that covers all major Czech paradigms while staying specific enough to
    avoid excessive false positives.
4.  Terms are joined with OR (``|``) so that any matching term returns the document;
    ``ts_rank`` naturally scores multi-term matches higher than single-term ones.

Number tokens (statute section references like "52", "262") get exact matching —
never truncated — because legal section numbers must match precisely.

Example
-------
``build_czech_tsquery("výpověď z pracovního poměru")``
→ ``"výpově:* | z:* | pracov:* | pomě:*"``

This matches documents containing any inflected form of "výpověď" (termination),
"pracovní" (work/labor), or "poměr" (relationship/ratio).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Czech / Latin alphabetic characters including diacritics
_CZECH_WORD_RE = re.compile(r"[a-záčďéěíňóřšťúůýžA-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9]+")

# Czech stop words — high-frequency function words that add noise to BM25 queries.
# Kept intentionally short: stopword removal can hurt recall for short queries.
CZECH_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "i",
        "v",
        "ve",
        "z",
        "ze",
        "k",
        "ke",
        "s",
        "se",
        "o",
        "na",
        "do",
        "od",
        "po",
        "pro",
        "při",
        "je",
        "jsou",
        "byl",
        "byla",
        "bylo",
        "být",
        "to",
        "ten",
        "ta",
        "ti",
        "ty",
        "tím",
        "jeho",
        "její",
        "jejich",
        "který",
        "která",
        "které",
        "nebo",
        "než",
        "jak",
        "jako",
        "že",
        "ale",
        "také",
        "již",
        "jen",
    }
)

# Lazy-loaded simplemma lemmatizer to avoid import overhead when not needed.
_lemmatizer_loaded = False
_simplemma = None


def _load_simplemma() -> None:
    global _lemmatizer_loaded, _simplemma
    if _lemmatizer_loaded:
        return
    try:
        import simplemma as _sm  # type: ignore[import-untyped]

        _simplemma = _sm
    except ImportError:
        logger.warning(
            "simplemma not installed — Czech BM25 will use heuristic prefix stemming only. "
            "Install with: uv add simplemma"
        )
    _lemmatizer_loaded = True


def _lemmatize(word: str) -> str:
    """Return simplemma lemma for a Czech word, or the word itself if unavailable."""
    _load_simplemma()
    if _simplemma is None:
        return word
    try:
        return _simplemma.lemmatize(word, lang="cs").lower()
    except Exception:
        return word


def _czech_stem(word: str) -> str:
    """Compute a stem for a Czech word suitable for PostgreSQL prefix matching.

    Combines simplemma lemmatization (for common inflected forms) with conservative
    suffix truncation (to cover paradigm variants that simplemma doesn't map).

    Returns the stem string WITHOUT the trailing ``:*`` suffix — the caller adds it.
    """
    w = word.lower()
    lemma = _lemmatize(w)

    # Accept the lemma only when it is a clear suffix reduction:
    # the original word and lemma must share a common prefix of at least
    # 60 % of the shorter word (or 4 chars, whichever is larger).
    min_common = max(4, int(0.6 * min(len(w), len(lemma))))
    common_len = 0
    for a, b in zip(w, lemma):
        if a != b:
            break
        common_len += 1

    # Only use lemma if it doesn't go longer than original and shares a good prefix
    base = lemma if (common_len >= min_common and len(lemma) <= len(w)) else w

    # Conservative suffix truncation:
    # >=8 chars → remove last 2 (covers most Czech noun/adj endings: -ou, -ím, -em, -ní, -ný…)
    # 5–7 chars → remove last 1 (covers -a, -e, -í, -u, -y short endings)
    # 3–4 chars → keep as-is (too short to safely truncate)
    n = len(base)
    if n >= 8:
        stem = base[:-2]
    elif n >= 5:
        stem = base[:-1]
    else:
        stem = base

    # Hard floor: stem must be at least 4 characters to avoid over-broad matching
    return stem if len(stem) >= 4 else base


def build_czech_tsquery(query: str, include_stop_words: bool = False) -> str | None:
    """Build a PostgreSQL ``tsquery`` string for a Czech legal query.

    Each non-trivial word is converted to a prefix-matched term (``stem:*``)
    that covers inflected variants.  Number tokens get exact matching.
    Terms are joined with OR so any match returns the document.

    Parameters
    ----------
    query:
        Raw Czech query string (may include diacritics, mixed case, punctuation).
    include_stop_words:
        If ``True``, include Czech stop words in the query (useful when query is
        very short and stop word removal would leave too few terms).

    Returns
    -------
    str | None
        A ``tsquery`` string suitable for ``to_tsquery('simple', ...)``::

            'výpově:* | pracov:* | pomě:*'

        Returns ``None`` when no valid terms can be extracted (empty query,
        punctuation-only input, or all tokens filtered).  Callers must fall back
        to ``plainto_tsquery`` or skip BM25 when ``None`` is returned — passing
        ``None`` or an empty string to ``to_tsquery`` raises a PostgreSQL syntax
        error.
    """
    words = _CZECH_WORD_RE.findall(query)
    terms: list[str] = []

    for word in words:
        w = word.lower()
        if len(w) < 2:
            continue

        # Number tokens: exact match (section/article references must be precise)
        if w.isdigit():
            terms.append(w)
            continue

        if len(w) < 3:
            continue

        # Optionally skip stop words
        if not include_stop_words and w in CZECH_STOP_WORDS:
            continue

        stem = _czech_stem(w)
        terms.append(f"{stem}:*")

    if not terms:
        # Fallback: no terms survived (e.g. query was all stop words) — use stop words
        for word in words:
            w = word.lower()
            if len(w) >= 3:
                stem = _czech_stem(w)
                terms.append(f"{stem}:*")

    return " | ".join(terms) if terms else None
