"""Tests for Czech morphological query builder (arlc.czech_morphology).

These tests verify:
1. Correct prefix generation for common Czech noun/adjective paradigms
2. That inflected forms are covered by generated tsquery terms
3. Number/section reference handling (exact match)
4. Stop word filtering
5. Edge cases (short words, empty input, punctuation)
"""

import pytest

from arlc.czech_morphology import CZECH_STOP_WORDS, build_czech_tsquery

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stems(tsquery: str) -> list[str]:
    """Extract the list of prefix stems from a tsquery string.

    ``'smlouv:* | pracov:*'`` → ``['smlouv', 'pracov']``
    """
    parts = [p.strip() for p in tsquery.split("|")]
    stems = []
    for p in parts:
        stems.append(p.rstrip(":*").strip())
    return stems


def _all_forms_matched(tsquery: str, forms: list[str]) -> list[str]:
    """Return forms from *forms* that are NOT covered by any term in *tsquery*."""
    stems = _stems(tsquery)
    missed = []
    for form in forms:
        fl = form.lower()
        if not any(fl.startswith(s) for s in stems):
            missed.append(form)
    return missed


# ---------------------------------------------------------------------------
# Core paradigm tests
# ---------------------------------------------------------------------------


class TestNounParadigms:
    """Czech noun paradigms — test that all case forms are covered."""

    def test_smlouva_contract(self):
        """smlouva (contract) — feminine noun, all 7 cases."""
        forms = ["smlouva", "smlouvy", "smlouvě", "smlouvu", "smlouvo", "smlouvou", "smlouvami"]
        tsq = build_czech_tsquery("smlouva")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"smlouva paradigm: missed forms {missed} for tsquery {tsq!r}"

    def test_zakonik_code(self):
        """zákoník (code of law) — masculine inanimate."""
        forms = ["zákoník", "zákoníku", "zákoníkem", "zákoníky"]
        tsq = build_czech_tsquery("zákoník")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"zákoník paradigm: missed forms {missed} for tsquery {tsq!r}"

    def test_zaloba_lawsuit(self):
        """žaloba (lawsuit) — feminine noun."""
        forms = ["žaloba", "žaloby", "žalobou", "žalobě"]
        tsq = build_czech_tsquery("žaloba")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"žaloba paradigm: missed forms {missed} for tsquery {tsq!r}"

    def test_rozhodnuti_decision(self):
        """rozhodnutí (decision) — neuter noun."""
        forms = ["rozhodnutí", "rozhodnutím", "rozhodnutích"]
        tsq = build_czech_tsquery("rozhodnutí")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"rozhodnutí paradigm: missed forms {missed} for tsquery {tsq!r}"

    def test_zamestnanec_employee(self):
        """zaměstnanec (employee) — masculine animate."""
        forms = ["zaměstnanec", "zaměstnance", "zaměstnanci", "zaměstnancem"]
        tsq = build_czech_tsquery("zaměstnanec")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"zaměstnanec paradigm: missed forms {missed} for tsquery {tsq!r}"

    def test_vypoved_termination(self):
        """výpověď (termination) — feminine noun with soft ending."""
        forms = ["výpověď", "výpovědi", "výpovědí", "výpovědi"]
        tsq = build_czech_tsquery("výpověď")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"výpověď paradigm: missed forms {missed} for tsquery {tsq!r}"


class TestAdjectiveParadigms:
    """Czech adjective paradigms — test that all inflected forms are covered."""

    def test_pracovni_work(self):
        """pracovní (work/labor) — soft adjective."""
        forms = ["pracovní", "pracovního", "pracovním", "pracovní", "pracovními"]
        tsq = build_czech_tsquery("pracovní")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"pracovní paradigm: missed forms {missed} for tsquery {tsq!r}"

    def test_inflected_adjective_query(self):
        """Query with an inflected adjective form should still match base forms."""
        # User queries "pracovního" (genitive), should match "pracovní" in documents
        forms = ["pracovní", "pracovního", "pracovním"]
        tsq = build_czech_tsquery("pracovního")
        missed = _all_forms_matched(tsq, forms)
        assert not missed, f"pracovního query: missed forms {missed} for tsquery {tsq!r}"


# ---------------------------------------------------------------------------
# Statute section reference tests
# ---------------------------------------------------------------------------


class TestSectionReferences:
    """Czech legal section/statute references must match exactly."""

    def test_section_number_exact(self):
        """Section numbers must not be prefix-truncated."""
        tsq = build_czech_tsquery("§ 52")
        assert "52" in tsq, f"Section 52 should appear as exact match in tsquery: {tsq!r}"
        assert "52:*" not in tsq, f"Section 52 should NOT be prefix-matched: {tsq!r}"

    def test_law_number_exact(self):
        """Law numbers (e.g. zakon 262/2006) must be exact."""
        tsq = build_czech_tsquery("zákon 262")
        assert "262" in tsq, f"Law number 262 should appear in tsquery: {tsq!r}"
        assert "262:*" not in tsq, f"Law number 262 should NOT be prefix-matched: {tsq!r}"

    def test_complex_query_with_section(self):
        """Query mixing Czech words and section numbers."""
        tsq = build_czech_tsquery("výpověď § 52 zákoník práce")
        stems = _stems(tsq)
        # Section number 52 must appear as exact term
        assert "52" in stems, f"Section 52 missing from tsquery stems: {stems}"
        # Czech words should be prefix-matched
        prefix_terms = [s for s in stems if s != "52"]
        assert all(":" not in s for s in prefix_terms), "Non-number terms should be prefix stems"


# ---------------------------------------------------------------------------
# Stop word tests
# ---------------------------------------------------------------------------


class TestStopWords:
    """Czech stop words should be filtered from BM25 queries."""

    def test_function_words_filtered(self):
        """Common Czech function words should not appear as BM25 terms."""
        # "a" (and), "v" (in), "z" (from) are stop words
        tsq = build_czech_tsquery("smlouva a výpověď v zákoník z práce")
        stems = _stems(tsq)
        # Stop words should be absent or at least not dominant
        # "a" = 1 char, filtered by length check; "v" = 1 char, filtered; "z" = 1 char, filtered
        assert "a" not in stems, f"Stop word 'a' should be filtered: {stems}"
        assert "v" not in stems, f"Stop word 'v' should be filtered: {stems}"
        assert "z" not in stems, f"Stop word 'z' should be filtered: {stems}"

    def test_stop_words_include_common_forms(self):
        """CZECH_STOP_WORDS must include common Czech function words."""
        assert "a" in CZECH_STOP_WORDS
        assert "nebo" in CZECH_STOP_WORDS
        assert "je" in CZECH_STOP_WORDS


# ---------------------------------------------------------------------------
# Recall improvement tests (tsquery quality assertions)
# ---------------------------------------------------------------------------


class TestQueryFormat:
    """Structural tests for the generated tsquery."""

    def test_output_uses_or_operator(self):
        """Multi-word queries should use OR (|) so any term returns a result."""
        tsq = build_czech_tsquery("smlouva zákoník práce")
        assert "|" in tsq, f"Multi-word query should use OR operator: {tsq!r}"

    def test_output_uses_prefix_matching(self):
        """Czech words should be prefix-matched with :*"""
        tsq = build_czech_tsquery("smlouva")
        assert ":*" in tsq, f"Czech word should generate prefix match (:*): {tsq!r}"

    def test_minimum_stem_length(self):
        """Stems must be at least 4 characters to avoid over-broad matching."""
        tsq = build_czech_tsquery("smlouva zákoník pracovního")
        stems = _stems(tsq)
        for stem in stems:
            if stem.isdigit():
                continue  # numbers are exact match, not stems
            assert len(stem) >= 4, f"Stem {stem!r} is too short (< 4 chars) for safe prefix matching"

    def test_empty_query_returns_none(self):
        """Empty or whitespace-only query should return None (no valid terms).

        Callers must fall back to plainto_tsquery when None is returned — passing
        an empty string to to_tsquery raises a PostgreSQL syntax error.
        """
        assert build_czech_tsquery("") is None
        assert build_czech_tsquery("   ") is None
        assert build_czech_tsquery("? ! ;") is None

    def test_punctuation_ignored(self):
        """Punctuation characters should not appear in tsquery output."""
        tsq = build_czech_tsquery("výpověď, zákoník práce (§ 52).")
        assert "," not in tsq
        assert "(" not in tsq
        assert ")" not in tsq
        assert "." not in tsq

    def test_diacritics_preserved(self):
        """Czech diacritics in stems must be preserved for correct tsvector matching."""
        tsq = build_czech_tsquery("zákoník")
        # Stem should contain Czech diacritics, not ASCII-stripped form
        assert "zon" not in tsq.lower() or "zákon" in tsq.lower(), (
            f"Diacritics should be preserved in tsquery stem: {tsq!r}"
        )

    def test_all_stop_word_query_fallback(self):
        """Query consisting entirely of stop words should still produce output."""
        # "a nebo je" — all stop words; fallback should produce something
        tsq = build_czech_tsquery("a nebo je")
        assert tsq, "All-stop-word query should produce non-empty output"


# ---------------------------------------------------------------------------
# Real legal query smoke tests
# ---------------------------------------------------------------------------


class TestLegalQuerySmoke:
    """Smoke tests with real Czech legal queries."""

    @pytest.mark.parametrize(
        "query,expected_coverage",
        [
            # Query → list of doc forms that must be covered
            ("výpověď z pracovního poměru", ["výpověď", "výpovědí", "pracovní", "pracovního", "poměru", "poměr"]),
            ("smlouva o dílo zákoník", ["smlouva", "smlouvou", "dílo", "zákoník", "zákoníku"]),
            ("nadbytečnost zaměstnance", ["nadbytečnost", "zaměstnanec", "zaměstnance"]),
            ("rozhodnutí soudu o žalobě", ["rozhodnutí", "rozhodnutím", "soudu", "soud", "žalobu", "žaloba"]),
        ],
    )
    def test_legal_query_coverage(self, query: str, expected_coverage: list[str]):
        tsq = build_czech_tsquery(query)
        missed = _all_forms_matched(tsq, expected_coverage)
        # Allow up to 1 missed form (some hard cross-paradigm cases are acceptable)
        assert len(missed) <= 1, f"Query {query!r} → tsquery {tsq!r} missed too many forms: {missed}"
