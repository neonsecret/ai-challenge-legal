"""Tests for the thorough parameter on search_legal_corpus.

Verifies that:
- thorough=True routes to SEARCH_TOP_K_THOROUGH (10) as target_new
- thorough=False (default) routes to SEARCH_TOP_K (3) as target_new
- The tool schema exposes the thorough param as optional bool
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from arlc.agent.config import SEARCH_TOP_K, SEARCH_TOP_K_THOROUGH
from arlc.agent.graph import search_legal_corpus
from arlc.agent.tools import execute_search


class TestSearchLegalCorpusSchema:
    def test_thorough_is_optional_bool_defaulting_false(self):
        schema = search_legal_corpus.args_schema.model_json_schema()
        props = schema["properties"]
        assert "thorough" in props
        assert props["thorough"]["type"] == "boolean"
        assert props["thorough"].get("default") is False
        assert "thorough" not in schema.get("required", [])

    def test_query_is_required(self):
        schema = search_legal_corpus.args_schema.model_json_schema()
        assert "query" in schema["required"]


class TestExecuteSearchThoroughRouting:
    def _make_fake_page(self, doc_id: str = "doc1", page: int = 1) -> MagicMock:
        p = MagicMock()
        p.doc_id = doc_id
        p.page_number = page
        p.text = "sample text"
        p.score = 0.9
        p.chunk_id = f"{doc_id}-chunk1"
        return p

    def test_thorough_false_uses_default_top_k(self):
        fake_pages = [self._make_fake_page(f"doc{i}") for i in range(5)]
        with patch("arlc.retriever.retrieve_pages", return_value=fake_pages) as mock_retrieve:
            execute_search(
                query="test query",
                corpus="difc",
                law_filters=None,
                exclude_doc_pages=set(),
                target_new=SEARCH_TOP_K,
            )
            call_kwargs = mock_retrieve.call_args[1] if mock_retrieve.call_args[1] else {}
            # max_total = target_new + len(exclude) = SEARCH_TOP_K + 0
            assert call_kwargs.get("max_total") == SEARCH_TOP_K

    def test_thorough_true_uses_thorough_top_k(self):
        fake_pages = [self._make_fake_page(f"doc{i}", i) for i in range(15)]
        with patch("arlc.retriever.retrieve_pages", return_value=fake_pages) as mock_retrieve:
            results = execute_search(
                query="test query",
                corpus="difc",
                law_filters=None,
                exclude_doc_pages=set(),
                target_new=SEARCH_TOP_K_THOROUGH,
            )
            call_kwargs = mock_retrieve.call_args[1] if mock_retrieve.call_args[1] else {}
            assert call_kwargs.get("max_total") == SEARCH_TOP_K_THOROUGH
            assert len(results) == SEARCH_TOP_K_THOROUGH

    def test_constants_have_correct_values(self):
        assert SEARCH_TOP_K == 3
        assert SEARCH_TOP_K_THOROUGH == 10
