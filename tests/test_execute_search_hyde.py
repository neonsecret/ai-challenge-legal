"""Tests for execute_search HyDE control.

Verifies that:
- execute_search calls retrieve_pages with use_hyde=False
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from arlc.agent.tools import execute_search


class TestExecuteSearchHydeControl:
    def _make_fake_page(self, doc_id: str = "doc1", page: int = 1) -> MagicMock:
        p = MagicMock()
        p.doc_id = doc_id
        p.page_number = page
        p.text = "sample text"
        p.score = 0.9
        p.chunk_id = f"{doc_id}-chunk1"
        return p

    def test_execute_search_calls_retrieve_pages_with_use_hyde_false(self):
        """execute_search must call retrieve_pages with use_hyde=False."""
        fake_pages = [self._make_fake_page(f"doc{i}") for i in range(3)]

        with patch("arlc.retriever.retrieve_pages", return_value=fake_pages) as mock_retrieve:
            execute_search(
                query="test query",
                corpus="difc",
                law_filters=None,
                exclude_doc_pages=set(),
                target_new=3,
            )

            call_kwargs = mock_retrieve.call_args.kwargs if mock_retrieve.call_args else {}

            assert "use_hyde" in call_kwargs, "retrieve_pages must be called with use_hyde parameter"
            assert call_kwargs["use_hyde"] is False, "use_hyde must be False"
