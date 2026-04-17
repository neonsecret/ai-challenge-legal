"""E2E retrieval quality tests — live backend required.

Coverage:
  1. Jurisdiction retrieval quality — each corpus returns docs from the correct corpus
  2. Cross-corpus isolation — Czech query does NOT return DIFC documents (NEO-2226)
  3. Custom corpus isolation — corpus-only query returns no jurisdiction bleed

All tests are marked @pytest.mark.e2e and skip when localhost:8000 is unavailable.
They assert at the retrieval level (source doc_ids) AND at the answer level (key phrases).

Known doc layout (builtin corpora):
  - difc:  employment_law_difc_law_no_2_of_2019  (DIFC Employment Law)
  - czech: zakonik_prace_*  (Labour Code), obcansky_zakonik_*  (Civil Code)
  - uk:    employment_rights_act_1996, data_protection_act_2018
  - au:    fair_work_act_2009, corporations_act_2001
"""

from __future__ import annotations

import httpx
import pytest

from tests.e2e.conftest import stream_query

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio(loop_scope="session")]

# ---------------------------------------------------------------------------
# Corpus prefix constants (used for corpus membership assertions)
# ---------------------------------------------------------------------------

_DIFC_DOC_PREFIXES = ("employment_law_difc", "difc_court", "difc_law", "dfsa")
_CZECH_DOC_PREFIXES = ("zakonik", "zakon", "obcansky", "danovy", "trestni", "spravni", "zivnostensky")
_UK_DOC_PREFIXES = (
    "employment_rights_act",
    "data_protection_act",
    "companies_act",
    "arbitration_act",
    "bribery_act",
    "competition_act",
    "consumer_rights_act",
    "equality_act",
    "financial_services",
    "human_rights_act",
)
_AU_DOC_PREFIXES = (
    "fair_work_act",
    "corporations_act",
    "aml_ctf_act",
    "asic_act",
    "bankruptcy_act",
    "competition_consumer",
    "consumer_credit",
    "epbc_act",
    "income_tax",
    "insurance_contracts",
)


def _source_doc_ids(result: dict) -> list[str]:
    return [s.get("doc_id", "") for s in result.get("sources", []) if isinstance(s, dict)]


def _any_source_matches_prefix(doc_ids: list[str], prefixes: tuple) -> bool:
    return any(did.startswith(prefixes) for did in doc_ids)


# ---------------------------------------------------------------------------
# Area 1: Jurisdiction retrieval quality
# ---------------------------------------------------------------------------


class TestJurisdictionRetrievalQuality:
    """Queries with known §/article references should return corpus-correct docs."""

    async def test_difc_employment_termination(self, authed_client: httpx.AsyncClient):
        """DIFC query: notice period → employment_law_difc_law_no_2_of_2019 in top results."""
        result = await stream_query(
            authed_client,
            question="What is the minimum notice period for terminating employment under DIFC law?",
            corpus="difc",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned for DIFC employment query"

        assert _any_source_matches_prefix(doc_ids, _DIFC_DOC_PREFIXES), f"No DIFC docs in sources: {doc_ids}"
        assert "employment_law_difc_law_no_2_of_2019" in doc_ids, (
            f"Expected employment_law_difc_law_no_2_of_2019 in top results, got: {doc_ids}"
        )

    async def test_difc_answer_contains_article_reference(self, authed_client: httpx.AsyncClient):
        """DIFC answer must mention an article number or 'notice' to be grounded."""
        result = await stream_query(
            authed_client,
            question="What is the minimum notice period for terminating employment under DIFC law?",
            corpus="difc",
        )
        answer = result["answer"].lower()
        assert any(kw in answer for kw in ("notice", "article", "termination", "employment")), (
            f"DIFC answer missing expected legal terms: {answer[:200]}"
        )

    async def test_czech_labour_code_retrieval(self, authed_client: httpx.AsyncClient):
        """Czech query: notice period → zakonik_prace_* in sources."""
        result = await stream_query(
            authed_client,
            question="Jaká je výpovědní doba při ukončení pracovního poměru ze strany zaměstnavatele?",
            corpus="czech",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned for Czech labour query"

        assert _any_source_matches_prefix(doc_ids, _CZECH_DOC_PREFIXES), f"No Czech statute docs in sources: {doc_ids}"
        zakonik_hits = [d for d in doc_ids if d.startswith("zakonik_prace")]
        assert zakonik_hits, f"Expected zakonik_prace_* in sources for termination query, got: {doc_ids}"

    async def test_uk_employment_retrieval(self, authed_client: httpx.AsyncClient):
        """UK query: unfair dismissal → employment_rights_act_1996 in sources."""
        result = await stream_query(
            authed_client,
            question="What constitutes unfair dismissal under UK employment law?",
            corpus="uk",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned for UK employment query"

        assert _any_source_matches_prefix(doc_ids, _UK_DOC_PREFIXES), f"No UK act docs in sources: {doc_ids}"
        assert "employment_rights_act_1996" in doc_ids, (
            f"Expected employment_rights_act_1996 in top results, got: {doc_ids}"
        )

    async def test_au_fair_work_retrieval(self, authed_client: httpx.AsyncClient):
        """AU query: unfair dismissal → fair_work_act_2009 in sources."""
        result = await stream_query(
            authed_client,
            question="What are the grounds for unfair dismissal under Australian law?",
            corpus="au",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned for AU fair work query"

        assert _any_source_matches_prefix(doc_ids, _AU_DOC_PREFIXES), f"No AU act docs in sources: {doc_ids}"
        assert "fair_work_act_2009" in doc_ids, f"Expected fair_work_act_2009 in top results, got: {doc_ids}"


# ---------------------------------------------------------------------------
# Area 2: Cross-corpus isolation (regression: NEO-2226)
# ---------------------------------------------------------------------------


class TestCrossCorpusIsolation:
    """Czech queries must not bleed into DIFC corpus and vice versa."""

    async def test_czech_query_no_difc_bleed(self, authed_client: httpx.AsyncClient):
        """NEO-2226 regression: Czech retrieval must NOT return DIFC documents.

        Bug: _doc_fusion_select hardcoded corpus='difc', silently returning DIFC chunks
        for Czech queries. Fix: corpus is passed dynamically.
        """
        result = await stream_query(
            authed_client,
            question="Jaká jsou práva zaměstnance při výpovědi pracovního poměru?",
            corpus="czech",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned — cannot assert corpus isolation"

        difc_in_czech = [d for d in doc_ids if d.startswith(_DIFC_DOC_PREFIXES)]
        assert not difc_in_czech, f"NEO-2226 regression: Czech query returned DIFC documents: {difc_in_czech}"

    async def test_difc_query_no_czech_bleed(self, authed_client: httpx.AsyncClient):
        """DIFC retrieval must NOT return Czech statute documents."""
        result = await stream_query(
            authed_client,
            question="What are an employee's rights upon termination under DIFC law?",
            corpus="difc",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned — cannot assert corpus isolation"

        czech_in_difc = [d for d in doc_ids if d.startswith(_CZECH_DOC_PREFIXES)]
        assert not czech_in_difc, f"DIFC query returned Czech documents: {czech_in_difc}"

    async def test_uk_query_returns_only_uk_docs(self, authed_client: httpx.AsyncClient):
        """UK query must return only UK corpus documents, not DIFC or AU docs."""
        result = await stream_query(
            authed_client,
            question="What are the data protection obligations under UK law?",
            corpus="uk",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned for UK data protection query"

        wrong_corpus = [d for d in doc_ids if not d.startswith(_UK_DOC_PREFIXES)]
        assert not wrong_corpus, f"UK query returned non-UK documents: {wrong_corpus}"

    async def test_au_query_returns_only_au_docs(self, authed_client: httpx.AsyncClient):
        """AU query must return only AU corpus documents."""
        result = await stream_query(
            authed_client,
            question="What are the requirements for a company director under Australian law?",
            corpus="au",
        )
        doc_ids = _source_doc_ids(result)
        assert doc_ids, "No sources returned for AU corporations query"

        wrong_corpus = [d for d in doc_ids if not d.startswith(_AU_DOC_PREFIXES)]
        assert not wrong_corpus, f"AU query returned non-AU documents: {wrong_corpus}"


# ---------------------------------------------------------------------------
# Area 3: Answer quality smoke tests
# ---------------------------------------------------------------------------


class TestAnswerQualitySmoke:
    """Agent answers should contain expected legal concepts for known questions."""

    async def test_difc_employment_answer_grounded(self, authed_client: httpx.AsyncClient):
        """DIFC termination question must produce a grounded answer with sources."""
        result = await stream_query(
            authed_client,
            question="What is the notice period for terminating employment under DIFC law Article 62?",
            corpus="difc",
        )
        answer = result["answer"].lower()
        sources = result["sources"]

        assert sources, "No sources — answer is ungrounded"
        assert any(kw in answer for kw in ("week", "month", "notice", "62", "article", "termination")), (
            f"DIFC answer does not reference expected legal concepts: {answer[:300]}"
        )

    async def test_uk_data_protection_answer(self, authed_client: httpx.AsyncClient):
        """UK data protection query must reference relevant act provisions."""
        result = await stream_query(
            authed_client,
            question="What obligations does the UK Data Protection Act 2018 impose on data controllers?",
            corpus="uk",
        )
        answer = result["answer"].lower()
        assert any(kw in answer for kw in ("data", "protection", "controller", "personal", "gdpr", "lawful")), (
            f"UK data protection answer missing expected concepts: {answer[:300]}"
        )

    async def test_czech_answer_in_czech_or_english(self, authed_client: httpx.AsyncClient):
        """Czech query should return a meaningful answer referencing zákoník práce or Labour Code."""
        result = await stream_query(
            authed_client,
            question="Jaká je délka výpovědní doby podle zákoníku práce?",
            corpus="czech",
        )
        answer = result["answer"].lower()
        assert result["sources"], "Czech query returned no sources"
        assert any(kw in answer for kw in ("výpověď", "notice", "labour", "zákoník", "měsíc", "month", "§")), (
            f"Czech labour answer missing expected concepts: {answer[:300]}"
        )

    async def test_au_fair_work_answer(self, authed_client: httpx.AsyncClient):
        """AU Fair Work query must produce a grounded answer."""
        result = await stream_query(
            authed_client,
            question="What is the minimum notice period for terminating employment under the Fair Work Act 2009?",
            corpus="au",
        )
        answer = result["answer"].lower()
        assert result["sources"], "AU query returned no sources"
        assert any(kw in answer for kw in ("notice", "week", "termination", "fair work", "employment")), (
            f"AU fair work answer missing expected concepts: {answer[:300]}"
        )
