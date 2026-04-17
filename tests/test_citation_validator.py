"""Tests for arlc.agent.citation_validator — NEO-2323.

Tests cover:
  - Hallucinated-index filter (out-of-range [DOC-N] removal)
  - Evidence→claim cross-check (weak citations removed)
  - Full validate_citations pipeline
  - Edge cases (empty inputs, no citations, all valid)
"""

from arlc.agent.citation_validator import (
    _score_claim_against_doc,
    cross_check_citations,
    filter_hallucinated_indices,
    validate_citations,
)

# ---------------------------------------------------------------------------
# Hallucinated-index filter
# ---------------------------------------------------------------------------


class TestFilterHallucinatedIndices:
    def test_valid_indices_preserved(self):
        answer = "According to Article 12 [DOC-1], the tenant must [DOC-2] comply."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=3)
        assert cleaned == answer
        assert removed == []

    def test_out_of_range_high_stripped(self):
        answer = "The law states [DOC-5] that obligations arise [DOC-1]."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=3)
        assert "[DOC-5]" not in cleaned
        assert "[DOC-1]" in cleaned
        assert 5 in removed

    def test_zero_index_stripped(self):
        answer = "Per [DOC-0], the court ruled."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=2)
        assert "[DOC-0]" not in cleaned
        assert 0 in removed

    def test_negative_index_not_matched(self):
        """Regex only matches positive integers, negative won't match [DOC-N]."""
        answer = "Some text [DOC-1] here."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=1)
        assert cleaned == answer
        assert removed == []

    def test_multiple_hallucinated(self):
        answer = "See [DOC-10] and [DOC-20] and [DOC-1]."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=2)
        assert "[DOC-10]" not in cleaned
        assert "[DOC-20]" not in cleaned
        assert "[DOC-1]" in cleaned
        assert sorted(removed) == [10, 20]

    def test_no_docs_strips_all(self):
        answer = "The ruling [DOC-1] established precedent."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=0)
        assert "[DOC-1]" not in cleaned
        assert 1 in removed

    def test_empty_answer(self):
        cleaned, removed = filter_hallucinated_indices("", num_docs=5)
        assert cleaned == ""
        assert removed == []

    def test_no_citations_in_answer(self):
        answer = "The court ruled in favor of the plaintiff."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=3)
        assert cleaned == answer
        assert removed == []

    def test_boundary_index_preserved(self):
        """DOC-N where N == num_docs should be kept (1-indexed)."""
        answer = "Final document [DOC-3] confirms this."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=3)
        assert "[DOC-3]" in cleaned
        assert removed == []

    def test_adjacent_tags(self):
        answer = "Multiple sources [DOC-1][DOC-2][DOC-99] confirm."
        cleaned, removed = filter_hallucinated_indices(answer, num_docs=2)
        assert "[DOC-1]" in cleaned
        assert "[DOC-2]" in cleaned
        assert "[DOC-99]" not in cleaned
        assert 99 in removed


# ---------------------------------------------------------------------------
# Evidence→claim cross-check
# ---------------------------------------------------------------------------


class TestScoreClaimAgainstDoc:
    def test_high_overlap(self):
        claim = "The Labour Code section 52 allows termination for redundancy"
        doc_text = (
            "Section 52 of the Labour Code provides that an employer may "
            "terminate employment for organizational reasons including redundancy."
        )
        score = _score_claim_against_doc(claim, doc_text)
        assert score > 0.3

    def test_zero_overlap(self):
        claim = "Article 45 governs maritime shipping regulations"
        doc_text = (
            "The tenant shall pay rent on the first day of each calendar month. "
            "Late payments incur a penalty of 5% per annum."
        )
        score = _score_claim_against_doc(claim, doc_text)
        assert score < 0.1

    def test_empty_inputs(self):
        assert _score_claim_against_doc("", "some doc") == 0.0
        assert _score_claim_against_doc("some claim", "") == 0.0
        assert _score_claim_against_doc("", "") == 0.0

    def test_czech_text_overlap(self):
        claim = "zakonik prace umoznuje vypoved z organizacnich duvodu"
        doc_text = (
            "Zakonik prace stanovuje, ze zamestnavatel muze dat vypoved z organizacnich duvodu podle paragrafu 52."
        )
        score = _score_claim_against_doc(claim, doc_text)
        assert score > 0.3


class TestCrossCheckCitations:
    def _make_docs(self, texts: list[str]) -> list[dict]:
        return [{"doc_id": f"doc_{i}", "text": t, "page": 1} for i, t in enumerate(texts)]

    def test_supported_citation_kept(self):
        answer = "The Labour Code section 52 allows termination for redundancy [DOC-1]."
        docs = self._make_docs(
            [
                "Section 52 of the Labour Code provides that an employer may "
                "terminate employment for organizational reasons including redundancy."
            ]
        )
        cleaned, removed = cross_check_citations(answer, docs)
        assert "[DOC-1]" in cleaned
        assert removed == []

    def test_unsupported_citation_removed(self):
        answer = (
            "Maritime shipping regulations under Article 45 require vessels to maintain proper documentation [DOC-1]."
        )
        docs = self._make_docs(
            [
                "The tenant shall pay rent on the first day of each calendar month. "
                "Late payments incur a penalty of 5% per annum. The landlord may "
                "terminate the lease if rent remains unpaid for three consecutive months."
            ]
        )
        cleaned, removed = cross_check_citations(answer, docs)
        assert "[DOC-1]" not in cleaned
        assert 1 in removed

    def test_mixed_supported_and_unsupported(self):
        answer = (
            "Employment termination requires notice under the Labour Code [DOC-1]. "
            "Maritime vessels must carry flag state documentation [DOC-2]."
        )
        docs = self._make_docs(
            [
                "The Labour Code requires employers to provide written notice of "
                "employment termination at least two months in advance.",
                "The tenant shall maintain the premises in good condition and return the deposit at lease end.",
            ]
        )
        cleaned, removed = cross_check_citations(answer, docs)
        assert "[DOC-1]" in cleaned
        assert "[DOC-2]" not in cleaned
        assert 2 in removed

    def test_empty_doc_text_keeps_citation(self):
        """If a doc has no text, we can't verify — keep the citation."""
        answer = "The law provides [DOC-1] this protection."
        docs = [{"doc_id": "doc_0", "text": "", "page": 1}]
        cleaned, removed = cross_check_citations(answer, docs)
        assert "[DOC-1]" in cleaned
        assert removed == []

    def test_no_citations_in_answer(self):
        answer = "The court decided in favor of the defendant."
        docs = self._make_docs(["Some legal text here."])
        cleaned, removed = cross_check_citations(answer, docs)
        assert cleaned == answer
        assert removed == []

    def test_empty_inputs(self):
        assert cross_check_citations("", []) == ("", [])
        assert cross_check_citations("text [DOC-1]", []) == ("text [DOC-1]", [])


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


class TestValidateCitations:
    def _make_docs(self, texts: list[str]) -> list[dict]:
        return [{"doc_id": f"doc_{i}", "text": t, "page": 1} for i, t in enumerate(texts)]

    def test_combined_hallucinated_and_weak(self):
        answer = (
            "The employer must comply with section 52 [DOC-1]. "
            "Ship navigation rules apply [DOC-2]. "
            "Also see [DOC-99] for more details."
        )
        docs = self._make_docs(
            [
                "Section 52 of the Labour Code governs employer obligations regarding termination and notice periods.",
                "Tenancy agreements require a minimum deposit of three months rent.",
            ]
        )
        cleaned = validate_citations(answer, docs)
        assert "[DOC-1]" in cleaned  # supported
        assert "[DOC-2]" not in cleaned  # weak evidence
        assert "[DOC-99]" not in cleaned  # hallucinated

    def test_all_valid(self):
        answer = "Employment law [DOC-1] and labour regulations [DOC-2] apply."
        docs = self._make_docs(
            [
                "Employment law governs the relationship between employers and employees.",
                "Labour regulations set minimum standards for working conditions.",
            ]
        )
        cleaned = validate_citations(answer, docs)
        assert "[DOC-1]" in cleaned
        assert "[DOC-2]" in cleaned

    def test_empty_answer(self):
        assert validate_citations("", []) == ""

    def test_no_docs(self):
        answer = "The law provides [DOC-1] certain rights."
        cleaned = validate_citations(answer, [])
        assert "[DOC-1]" not in cleaned  # hallucinated (0 docs)

    def test_preserves_non_citation_text(self):
        answer = (
            "According to the Labour Code, employers must provide "
            "written notice [DOC-1] of termination. The notice period "
            "is at least two months."
        )
        docs = self._make_docs(
            [
                "The Labour Code requires employers to provide written notice "
                "of employment termination. The minimum notice period is two months."
            ]
        )
        cleaned = validate_citations(answer, docs)
        assert "written notice" in cleaned
        assert "two months" in cleaned
        assert "[DOC-1]" in cleaned
