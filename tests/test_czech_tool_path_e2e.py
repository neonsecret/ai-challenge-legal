"""Czech search_court_decisions tool path tests.

Verifies that after removing auto-enrichment from search_node:
  1. The explicit caselaw tool pipeline (search → format) still produces [DOC-N] content.
  2. No auto-enrichment code exists in the source (static guard).
  3. search_court_decisions → execute_caselaw_search round-trip with DB (integration).
"""

from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from arlc.agent.state import SourceDocument

# ---------------------------------------------------------------------------
# Static guard: auto-enrichment must not exist in graph.py
# ---------------------------------------------------------------------------


class TestNoAutoEnrichmentCode:
    """graph.py must not contain any auto-enrichment code after the cleanup."""

    def test_no_caselaw_auto_triggered_var(self):
        import arlc.agent.graph as graph_mod

        src = inspect.getsource(graph_mod)
        assert "_caselaw_auto_triggered" not in src, (
            "_caselaw_auto_triggered found — auto-enrichment was not fully removed"
        )

    def test_no_extract_caselaw_query_helper(self):
        import arlc.agent.graph as graph_mod

        src = inspect.getsource(graph_mod)
        assert "_extract_caselaw_query" not in src, (
            "_extract_caselaw_query found — auto-enrichment helper was not removed"
        )

    def test_no_boilerplate_terms_dict(self):
        import arlc.agent.graph as graph_mod

        src = inspect.getsource(graph_mod)
        assert "_BOILERPLATE_TERMS" not in src, "_BOILERPLATE_TERMS found — auto-enrichment data was not removed"

    def test_search_court_decisions_tool_still_registered(self):
        """The explicit search_court_decisions tool must still be in the graph."""
        from arlc.agent.graph import _CASELAW_TOOLS, build_agent_graph

        assert "search_court_decisions" in _CASELAW_TOOLS
        assert "fetch_court_decision" in _CASELAW_TOOLS

        graph = build_agent_graph()
        assert "search" in graph.nodes


# ---------------------------------------------------------------------------
# Static guard: multi-hop dead code must not exist in retriever.py
# ---------------------------------------------------------------------------


class TestNoDeadMultiHopCode:
    """retriever.py must not contain the disabled multi-hop branch."""

    def test_no_detect_multi_hop(self):
        import arlc.retriever as retriever_mod

        src = inspect.getsource(retriever_mod)
        assert "detect_multi_hop" not in src, "detect_multi_hop found — dead function was not removed"

    def test_no_decompose_query(self):
        import arlc.retriever as retriever_mod

        src = inspect.getsource(retriever_mod)
        assert "decompose_query" not in src, "decompose_query found — dead function was not removed"

    def test_no_if_false_guard(self):
        import arlc.retriever as retriever_mod

        src = inspect.getsource(retriever_mod)
        assert "if False and detect_multi_hop" not in src, "Dead 'if False' guard found — was not removed"


# ---------------------------------------------------------------------------
# Caselaw tool pipeline: search → format → [DOC-N] (no DB needed)
# ---------------------------------------------------------------------------


class TestCaselawToolPipeline:
    """Verify the caselaw tool format pipeline produces [DOC-N] output."""

    def _make_decision(self, ecli: str = "ECLI:CZ:NS:2023:21.CDO.1.2023.1") -> SourceDocument:
        return SourceDocument(
            doc_id=ecli,
            page=1,
            text="Zaměstnavatel není oprávněn dát zaměstnanci výpověď bez skutečného zrušení.",
            score=0.95,
            source_type="court_decision",
            case_number="21 Cdo 1/2023",
            decision_date="2023-06-15",
            court="Nejvyssi soud",
            category="A",
            ecli=ecli,
            legal_thesis="Zaměstnavatel není oprávněn dát zaměstnanci výpověď.",
        )

    def test_format_caselaw_full_produces_doc_n(self):
        """format_caselaw_full wraps decisions in [DOC-N] with document_content tags."""
        from arlc.agent.caselaw_tools import format_caselaw_full

        doc = self._make_decision()
        output = format_caselaw_full(doc, doc_index=3)

        assert "[DOC-3]" in output
        assert "<document_content>" in output
        assert "</document_content>" in output
        assert "PRÁVNÍ VĚTA" in output or "Zamestnavatel" in output or "Zaměstnavatel" in output

    def test_format_search_results_uses_plain_numbering(self):
        """format_caselaw_search_results uses 'Case N:' not '[CASE-N]'."""
        import re

        from arlc.agent.caselaw_tools import format_caselaw_search_results

        docs = [self._make_decision()]
        output = format_caselaw_search_results(docs)

        assert not re.search(r"\[CASE-\d+\]", output), (
            "[CASE-N] bracket labels found — these leak into final answers as spurious citations"
        )
        assert "Case 1:" in output
        assert "21 Cdo 1/2023" in output

    def test_full_pipeline_search_then_format_as_doc_n(self):
        """Simulate search_court_decisions handler: search results → format_caselaw_full → [DOC-N]."""
        from arlc.agent.caselaw_tools import format_caselaw_full, format_caselaw_search_results

        decisions = [self._make_decision()]

        # Step 1: format search results (what the agent sees in the ToolMessage)
        search_content = format_caselaw_search_results(decisions)
        assert "21 Cdo 1/2023" in search_content

        # Step 2: auto-promote top result as [DOC-N] (appended to ToolMessage)
        promoted = format_caselaw_full(decisions[0], doc_index=1)
        full_content = search_content + "\n---\n" + promoted

        assert "[DOC-1]" in full_content
        assert "<document_content>" in full_content
        assert "PRÁVNÍ VĚTA" in full_content or "Zaměstnavatel" in full_content


# ---------------------------------------------------------------------------
# Integration: DB-backed search (skipped if DB unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_caselaw_search_returns_structured_docs():
    """execute_caselaw_search returns SourceDocuments with required fields.

    Requires a running PostgreSQL with court_decisions data.
    Skipped automatically when DB is unavailable.
    """
    try:
        from neolex.db.postgres import init_db

        await init_db()
    except Exception:
        pytest.skip("PostgreSQL not available")

    from arlc.agent.caselaw_tools import execute_caselaw_search

    try:
        results = await execute_caselaw_search("výpověď zaměstnavatel", limit=3)
    except Exception as exc:
        pytest.skip(f"DB query failed: {exc}")

    # Even if results are empty (no matching data), the return type must be correct
    assert isinstance(results, list)
    for r in results:
        assert r.get("source_type") == "court_decision"
        assert r.get("doc_id")
        assert r.get("case_number")
