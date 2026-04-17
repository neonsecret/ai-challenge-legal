"""Tests for arlc.agent.citation_validator — NEO-2323.

Tests cover:
  - validate_citation_indices: hallucinated-index filter + regen signal
  - Evidence→claim cross-check (weak citations removed)
  - Full validate_citations pipeline (returns tuple[str, bool])
  - Red-team set: 50 hallucinated-citation scenarios targeting 100% rejection
  - Edge cases (empty inputs, no citations, all valid)
"""

import pytest

from arlc.agent.citation_validator import (
    _score_claim_against_doc,
    cross_check_citations,
    validate_citation_indices,
    validate_citations,
)

# ---------------------------------------------------------------------------
# validate_citation_indices — hallucinated-index filter + regen signal
# ---------------------------------------------------------------------------


class TestValidateCitationIndices:
    def _make_docs(self, n: int) -> list[dict]:
        return [{"doc_id": f"doc_{i}", "text": "placeholder", "page": 1} for i in range(n)]

    def test_valid_indices_preserved(self):
        docs = self._make_docs(3)
        answer = "According to Article 12 [DOC-1], the tenant must [DOC-2] comply."
        cleaned, should_regen, removed = validate_citation_indices(answer, docs)
        assert cleaned == answer
        assert removed == []
        assert should_regen is False

    def test_out_of_range_high_stripped_and_flags_regen(self):
        docs = self._make_docs(3)
        answer = "The law states [DOC-5] that obligations arise [DOC-1]."
        cleaned, should_regen, removed = validate_citation_indices(answer, docs)
        assert "[DOC-5]" not in cleaned
        assert "[DOC-1]" in cleaned
        assert 5 in removed
        assert should_regen is True

    def test_zero_index_stripped_and_flags_regen(self):
        docs = self._make_docs(2)
        answer = "Per [DOC-0], the court ruled."
        cleaned, should_regen, removed = validate_citation_indices(answer, docs)
        assert "[DOC-0]" not in cleaned
        assert 0 in removed
        assert should_regen is True

    def test_multiple_hallucinated_flags_regen(self):
        docs = self._make_docs(2)
        answer = "See [DOC-10] and [DOC-20] and [DOC-1]."
        cleaned, should_regen, removed = validate_citation_indices(answer, docs)
        assert "[DOC-10]" not in cleaned
        assert "[DOC-20]" not in cleaned
        assert "[DOC-1]" in cleaned
        assert sorted(removed) == [10, 20]
        assert should_regen is True

    def test_no_docs_strips_all_and_flags_regen(self):
        answer = "The ruling [DOC-1] established precedent."
        cleaned, should_regen, removed = validate_citation_indices(answer, [])
        assert "[DOC-1]" not in cleaned
        assert 1 in removed
        assert should_regen is True

    def test_empty_answer(self):
        cleaned, should_regen, removed = validate_citation_indices("", [])
        assert cleaned == ""
        assert removed == []
        assert should_regen is False

    def test_no_citations_in_answer(self):
        docs = self._make_docs(3)
        answer = "The court ruled in favor of the plaintiff."
        cleaned, should_regen, removed = validate_citation_indices(answer, docs)
        assert cleaned == answer
        assert removed == []
        assert should_regen is False

    def test_boundary_index_preserved(self):
        """DOC-N where N == len(docs) is valid (1-indexed)."""
        docs = self._make_docs(3)
        answer = "Final document [DOC-3] confirms this."
        cleaned, should_regen, removed = validate_citation_indices(answer, docs)
        assert "[DOC-3]" in cleaned
        assert removed == []
        assert should_regen is False

    def test_adjacent_tags_partially_hallucinated(self):
        docs = self._make_docs(2)
        answer = "Multiple sources [DOC-1][DOC-2][DOC-99] confirm."
        cleaned, should_regen, removed = validate_citation_indices(answer, docs)
        assert "[DOC-1]" in cleaned
        assert "[DOC-2]" in cleaned
        assert "[DOC-99]" not in cleaned
        assert 99 in removed
        assert should_regen is True


# ---------------------------------------------------------------------------
# Evidence→claim cross-check (keyword)
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
# Full pipeline — validate_citations returns (str, bool)
# ---------------------------------------------------------------------------


class TestValidateCitations:
    def _make_docs(self, texts: list[str]) -> list[dict]:
        return [{"doc_id": f"doc_{i}", "text": t, "page": 1} for i, t in enumerate(texts)]

    def test_hallucinated_index_triggers_regen_signal(self):
        answer = "See [DOC-99] for the ruling."
        docs = self._make_docs(["Some legal text."])
        cleaned, should_regen = validate_citations(answer, docs)
        assert "[DOC-99]" not in cleaned
        assert should_regen is True

    def test_no_hallucination_no_regen_signal(self):
        answer = "Employment law [DOC-1] and labour regulations [DOC-2] apply."
        docs = self._make_docs(
            [
                "Employment law governs the relationship between employers and employees.",
                "Labour regulations set minimum standards for working conditions.",
            ]
        )
        cleaned, should_regen = validate_citations(answer, docs)
        assert "[DOC-1]" in cleaned
        assert "[DOC-2]" in cleaned
        assert should_regen is False

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
        cleaned, should_regen = validate_citations(answer, docs)
        assert "[DOC-1]" in cleaned
        assert "[DOC-2]" not in cleaned
        assert "[DOC-99]" not in cleaned
        assert should_regen is True  # DOC-99 triggered regen

    def test_empty_answer_returns_tuple(self):
        result = validate_citations("", [])
        assert result == ("", False)

    def test_no_docs_all_citations_hallucinated(self):
        answer = "The law provides [DOC-1] certain rights."
        cleaned, should_regen = validate_citations(answer, [])
        assert "[DOC-1]" not in cleaned
        assert should_regen is True

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
        cleaned, should_regen = validate_citations(answer, docs)
        assert "written notice" in cleaned
        assert "two months" in cleaned
        assert "[DOC-1]" in cleaned
        assert should_regen is False


# ---------------------------------------------------------------------------
# Red-team set — 50 hallucinated-citation scenarios (100% rejection target)
# ---------------------------------------------------------------------------


def _docs(n: int) -> list[dict]:
    return [{"doc_id": f"d{i}", "text": "Employment law text.", "page": 1} for i in range(n)]


@pytest.mark.parametrize(
    "answer,num_docs",
    [
        # Group 1: single wildly-out-of-range index
        ("Court ruling [DOC-100] established precedent.", 5),
        ("The statute [DOC-50] requires compliance.", 3),
        ("Evidence from [DOC-99] is compelling.", 1),
        ("See [DOC-42] for the full text.", 0),
        ("The judgment [DOC-7] overturned prior case law.", 2),
        # Group 2: zero index (always invalid in 1-indexed system)
        ("Per [DOC-0], no obligation exists.", 5),
        ("The contract clause at [DOC-0] is void.", 3),
        ("Regulation [DOC-0] prohibits this.", 1),
        ("In [DOC-0] the court found negligence.", 10),
        ("According to [DOC-0], liability attaches.", 0),
        # Group 3: multiple hallucinated in one answer
        ("Both [DOC-8] and [DOC-9] support this position.", 3),
        ("[DOC-10], [DOC-11], and [DOC-12] all confirm.", 2),
        ("The ruling in [DOC-6] cited [DOC-7].", 4),
        ("See [DOC-15] and [DOC-16] for context.", 5),
        ("Evidence from [DOC-20] and [DOC-25] is clear.", 10),
        # Group 4: mix of valid and hallucinated
        ("Valid [DOC-1] but also phantom [DOC-99].", 3),
        ("[DOC-2] is correct; [DOC-50] does not exist.", 5),
        ("Real [DOC-3] alongside fake [DOC-0].", 5),
        ("Legitimate [DOC-1] and phantom [DOC-100].", 2),
        ("Sources [DOC-1][DOC-2][DOC-30] confirm this.", 5),
        # Group 5: boundary violations
        ("Document [DOC-4] is one beyond the limit.", 3),  # DOC-4 with 3 docs = hallucinated
        ("Citing [DOC-11] but only 10 docs available.", 10),
        ("The [DOC-6] reference is invalid here.", 5),
        ("Reference [DOC-21] out of scope.", 20),
        ("Citation [DOC-101] is clearly phantom.", 100),
        # Group 6: empty document corpus (all citations hallucinated)
        ("Per [DOC-1], the law is clear.", 0),
        ("Under [DOC-2], liability attaches.", 0),
        ("The court in [DOC-3] held otherwise.", 0),
        ("Sources [DOC-1][DOC-2][DOC-3] support this.", 0),
        ("[DOC-5] establishes the controlling standard.", 0),
        # Group 7: large index with small corpus
        ("Citing [DOC-1000] for this proposition.", 5),
        ("The rule in [DOC-500] applies here.", 2),
        ("Authority at [DOC-200] is controlling.", 1),
        ("As shown in [DOC-999], liability is clear.", 3),
        ("The holding in [DOC-777] is on point.", 10),
        # Group 8: repeated hallucinated index
        ("See [DOC-9][DOC-9][DOC-9] for all three points.", 5),
        ("[DOC-88] mentioned twice: see [DOC-88].", 3),
        ("Both [DOC-0][DOC-0] citations are invalid.", 5),
        ("Repeated phantom: [DOC-50] and [DOC-50] again.", 10),
        ("[DOC-100][DOC-100] corroborates the finding.", 7),
        # Group 9: hallucinated alongside long valid range
        ("Deep phantom [DOC-51] with 50 valid docs.", 50),
        ("Just over limit: [DOC-21] with 20 docs.", 20),
        ("Barely invalid [DOC-11] with only 10 docs.", 10),
        ("One too many: [DOC-4] with exactly 3 docs.", 3),
        ("Negative-like edge: [DOC-0] with 1 doc.", 1),
        # Group 10: complex multi-clause answers
        (
            "The employer [DOC-1] must give notice [DOC-99] of termination [DOC-100] in writing.",
            5,
        ),
        (
            "Contract formation [DOC-3] requires offer [DOC-4] and acceptance [DOC-50].",
            4,
        ),
        (
            "Liability arises [DOC-1] under tort [DOC-2] and also via statute [DOC-77].",
            3,
        ),
        (
            "Evidence standards [DOC-2][DOC-5][DOC-6][DOC-7] vary by jurisdiction.",
            4,
        ),
        (
            "The decision [DOC-1] is supported [DOC-2] but contradicted by [DOC-0].",
            5,
        ),
    ],
)
def test_red_team_hallucinated_citation_rejected(answer: str, num_docs: int):
    """Every hallucinated citation scenario must trigger should_regen=True."""
    docs = _docs(num_docs)
    cleaned, should_regen = validate_citations(answer, docs)
    assert should_regen is True, (
        f"Expected regen signal for answer={answer!r} with {num_docs} docs, "
        f"but should_regen=False. Cleaned: {cleaned!r}"
    )
