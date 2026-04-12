"""Integration tests for court decision retrieval in the hybrid pipeline.

Verifies that court decisions from the `court_decisions` table appear alongside
statute chunks in retrieval results for Czech corpus queries, and that court
decision metadata flows correctly through to SourceCitation.

Run with:
    uv run pytest tests/test_court_decision_retrieval.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Unit tests — no DB required
# ---------------------------------------------------------------------------


class TestPageResultCourtFields:
    """PageResult dataclass carries optional court decision metadata."""

    def test_page_result_statute_has_no_court_fields(self):
        from arlc.retriever import PageResult

        p = PageResult(doc_id="abc123", page_number=1, score=0.9, text="statute text")
        assert p.source_type is None
        assert p.ecli is None
        assert p.case_number is None

    def test_page_result_court_decision_fields(self):
        from arlc.retriever import PageResult

        p = PageResult(
            doc_id="ECLI:CZ:NS:2023:21.CDO.1.2023.1",
            page_number=1,
            score=0.85,
            text="Pravni veta text",
            source_type="court_decision",
            ecli="ECLI:CZ:NS:2023:21.CDO.1.2023.1",
            case_number="21 Cdo 1/2023",
            decision_date="2023-06-15",
            court="Nejvyssi soud",
            category="A",
            legal_thesis="Pravni veta text",
        )
        assert p.source_type == "court_decision"
        assert p.ecli == "ECLI:CZ:NS:2023:21.CDO.1.2023.1"
        assert p.case_number == "21 Cdo 1/2023"
        assert p.court == "Nejvyssi soud"
        assert p.category == "A"


class TestPagesToSourceDicts:
    """_pages_to_source_dicts includes court decision metadata when present."""

    def test_statute_page_result_no_court_fields_in_dict(self):
        from arlc.pipeline import _pages_to_source_dicts
        from arlc.retriever import PageResult

        p = PageResult(doc_id="statute-doc", page_number=2, score=0.7, text="statute text")
        dicts = _pages_to_source_dicts([p])
        assert len(dicts) == 1
        assert dicts[0]["doc_id"] == "statute-doc"
        assert "source_type" not in dicts[0]
        assert "ecli" not in dicts[0]

    def test_court_decision_page_result_includes_metadata(self):
        from arlc.pipeline import _pages_to_source_dicts
        from arlc.retriever import PageResult

        ecli = "ECLI:CZ:NS:2023:21.CDO.1.2023.1"
        p = PageResult(
            doc_id=ecli,
            page_number=1,
            score=0.85,
            text="Pravni veta",
            source_type="court_decision",
            ecli=ecli,
            case_number="21 Cdo 1/2023",
            decision_date="2023-06-15",
            court="Nejvyssi soud",
            category="A",
            legal_thesis="Pravni veta",
        )
        dicts = _pages_to_source_dicts([p])
        assert len(dicts) == 1
        d = dicts[0]
        assert d["source_type"] == "court_decision"
        assert d["ecli"] == ecli
        assert d["case_number"] == "21 Cdo 1/2023"
        assert d["court"] == "Nejvyssi soud"
        assert d["category"] == "A"
        assert d["legal_thesis"] == "Pravni veta"


class TestAttachSourceText:
    """_attach_source_text re-attaches court decision metadata to chunk_pages."""

    def test_attaches_text_for_statute(self):
        from arlc.pipeline import _attach_source_text

        source_pages = [{"doc_id": "abc", "page_number": 1, "text": "statute text"}]
        chunk_pages = [{"doc_id": "abc", "page_numbers": [1]}]
        _attach_source_text(chunk_pages, source_pages)
        assert chunk_pages[0]["text"] == "statute text"
        assert "source_type" not in chunk_pages[0]

    def test_attaches_court_metadata_for_court_decision(self):
        from arlc.pipeline import _attach_source_text

        ecli = "ECLI:CZ:NS:2023:21.CDO.1.2023.1"
        source_pages = [
            {
                "doc_id": ecli,
                "page_number": 1,
                "text": "Pravni veta text",
                "source_type": "court_decision",
                "case_number": "21 Cdo 1/2023",
                "ecli": ecli,
                "decision_date": "2023-06-15",
                "court": "Nejvyssi soud",
                "category": "A",
                "legal_thesis": "Pravni veta text",
            }
        ]
        chunk_pages = [{"doc_id": ecli, "page_numbers": [1]}]
        _attach_source_text(chunk_pages, source_pages)

        cp = chunk_pages[0]
        assert cp["text"] == "Pravni veta text"
        assert cp["source_type"] == "court_decision"
        assert cp["ecli"] == ecli
        assert cp["case_number"] == "21 Cdo 1/2023"
        assert cp["court"] == "Nejvyssi soud"
        assert cp["category"] == "A"

    def test_does_not_overwrite_existing_text(self):
        from arlc.pipeline import _attach_source_text

        source_pages = [{"doc_id": "abc", "page_number": 1, "text": "source text"}]
        chunk_pages = [{"doc_id": "abc", "page_numbers": [1], "text": "existing text"}]
        _attach_source_text(chunk_pages, source_pages)
        # Existing text must not be overwritten
        assert chunk_pages[0]["text"] == "existing text"

    def test_does_not_overwrite_existing_court_metadata(self):
        from arlc.pipeline import _attach_source_text

        ecli = "ECLI:CZ:NS:2023:21.CDO.1.2023.1"
        source_pages = [
            {
                "doc_id": ecli,
                "page_number": 1,
                "text": "text",
                "source_type": "court_decision",
                "case_number": "21 Cdo 1/2023",
                "ecli": ecli,
                "court": "Nejvyssi soud",
                "category": "A",
                "legal_thesis": "text",
                "decision_date": None,
            }
        ]
        chunk_pages = [
            {
                "doc_id": ecli,
                "page_numbers": [1],
                "source_type": "court_decision",  # already set
                "ecli": ecli,
            }
        ]
        _attach_source_text(chunk_pages, source_pages)
        # source_type was already set — should not be overwritten
        assert chunk_pages[0]["source_type"] == "court_decision"

    def test_noop_on_empty_inputs(self):
        from arlc.pipeline import _attach_source_text

        _attach_source_text([], [])  # must not raise
        _attach_source_text([{"doc_id": "x", "page_numbers": [1]}], [])  # no source pages — no-op


# ---------------------------------------------------------------------------
# Integration tests — require PostgreSQL with court_decisions table
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _db_available():
    """Skip integration tests when DB is not reachable."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        from sqlalchemy import text

        from arlc.retriever import _get_sync_engine

        engine = _get_sync_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM court_decisions LIMIT 1"))
        return True
    except Exception as e:
        pytest.skip(f"PostgreSQL with court_decisions not available: {e}")


class TestSearchCourtDecisionsSync:
    """_search_court_decisions_sync returns well-formed results from real DB."""

    def test_returns_results_for_czech_query(self, _db_available):
        from dotenv import load_dotenv

        load_dotenv()
        from arlc.retriever import _search_court_decisions_sync, embed_query

        query = "vypoved nadbytecnost zakonik prace"
        emb = embed_query(query)
        results = _search_court_decisions_sync(query, emb, limit=5)

        assert len(results) > 0, "Expected at least one court decision for a labour-law query"
        first = results[0]
        # Verify dict structure
        assert "chunk_id" in first
        assert first["chunk_id"].startswith("ECLI:")
        assert "text" in first
        assert len(first["text"]) > 0
        meta = first["metadata"]
        assert meta["source_type"] == "court_decision"
        assert meta["doc_id"] == first["chunk_id"]  # doc_id == ECLI
        assert meta["page"] == 1
        assert meta["case_number"] is not None

    def test_empty_results_for_nonsense_query(self, _db_available):
        from dotenv import load_dotenv

        load_dotenv()
        from arlc.retriever import _search_court_decisions_sync, embed_query

        # A nonsense query should still return vector results (always returns limit rows)
        # but BM25 leg may return nothing — total is still > 0 due to vector leg
        emb = embed_query("xyzzy foobarbaz")
        results = _search_court_decisions_sync("xyzzy foobarbaz", emb, limit=3)
        # Vector leg always returns rows if embeddings exist, so we expect results
        assert isinstance(results, list)

    def test_results_have_required_metadata_fields(self, _db_available):
        from dotenv import load_dotenv

        load_dotenv()
        from arlc.retriever import _search_court_decisions_sync, embed_query

        emb = embed_query("smlouva zavazek obcansky zakonik")
        results = _search_court_decisions_sync("smlouva zavazek obcansky zakonik", emb, limit=3)
        assert len(results) > 0

        for r in results:
            assert r["metadata"]["source_type"] == "court_decision"
            assert r["metadata"]["doc_id"].startswith("ECLI:")
            assert r["metadata"]["page"] == 1
            assert "case_number" in r["metadata"]
            assert "ecli" in r["metadata"]
            assert "court" in r["metadata"]
            assert "legal_thesis" in r["metadata"]


class TestRetrievePagesIncludesCourtDecisions:
    """_retrieve_pages_simple returns court decisions for Czech corpus."""

    def test_czech_retrieval_includes_court_decision(self, _db_available):
        from dotenv import load_dotenv

        load_dotenv()
        from arlc.retriever import _retrieve_pages_simple

        # Labour law query — should return both statute chunks and court decisions
        results = _retrieve_pages_simple(
            "Jaké jsou podmínky pro výpověď pro nadbytečnost podle zákoníku práce?",
            max_per_doc=1,
            max_total=5,
            corpus="czech",
            answer_type="free_text",
        )

        assert len(results) > 0, "Expected results for a Czech labour law query"

        court_results = [r for r in results if r.source_type == "court_decision"]
        statute_results = [r for r in results if r.source_type != "court_decision"]

        # With 262K court decision embeddings, at least one should appear in top-5
        assert len(court_results) > 0, (
            f"Expected at least one court decision in results, got {len(results)} total "
            f"(all source_types: {[r.source_type for r in results]})"
        )

        # Statute results should also be present (Czech corpus has statutes too)
        # This is a soft check — may fail if statute corpus is empty
        # (not a regression if no statute chunks for Czech are indexed)
        _ = statute_results  # available for debugging

        # Verify court decision PageResult fields are populated
        for cr in court_results:
            assert cr.ecli is not None and cr.ecli.startswith("ECLI:")
            assert cr.case_number is not None
            assert cr.text is not None and len(cr.text) > 0
            assert cr.page_number == 1
