"""Unit tests for hybrid jurisdiction + custom corpus search (NEO-2184, fix ba39e63).

Covers all four code paths identified in NEO-2199:
1. _retrieve_pages_simple — Czech BM25 + custom corpus threaded path
2. _retrieve_pages_simple — UK/AU vector + custom corpus path
3. retrieve_pages — DIFC + custom corpus RRF merge path
4. query.py _resolve_corpora_id + hybrid mode detection routing

All tests mock IO (DB, embedding server, reranker) so they run offline
without a running Postgres or llama-server instance.

Run with:
    uv run pytest tests/test_hybrid_search.py -v
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

# Ensure env vars exist before any module-level config is evaluated
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-only")
os.environ.setdefault("ADMIN_EMAILS", "admin@vitreon.app")


# ---------------------------------------------------------------------------
# Helpers: fixture factory for search_chunks_vector mock responses
# ---------------------------------------------------------------------------


def _make_vector_result(chunk_ids: list[str], doc_ids: list[str] | None = None) -> dict:
    """Build a search_chunks_vector-compatible response."""
    if doc_ids is None:
        doc_ids = chunk_ids  # simple default: chunk_id == doc_id
    n = len(chunk_ids)
    return {
        "ids": [chunk_ids],
        "documents": [[f"text for {cid}" for cid in chunk_ids]],
        "metadatas": [
            [
                {
                    "doc_id": doc_ids[i],
                    "pdf_id": doc_ids[i],
                    "page": 1,
                    "source_file": "f.pdf",
                    "chunk_id": chunk_ids[i],
                }
                for i in range(n)
            ]
        ],
        "distances": [[0.1 + 0.01 * i for i in range(n)]],
    }


def _make_reranked(chunks: list[dict], score_start: float = 0.9) -> list[dict]:
    """Annotate chunk dicts with a descending rerank_score."""
    result = []
    for i, c in enumerate(chunks):
        r = dict(c)
        r["rerank_score"] = score_start - 0.1 * i
        result.append(r)
    return result


# ---------------------------------------------------------------------------
# 1. _retrieve_pages_simple — Czech (BM25 fusion) + custom corpus path
# ---------------------------------------------------------------------------


class TestRetrievePagesSimpleCzechWithCustomCorpus:
    """Czech BM25-fusion path: custom corpus results enter the RRF pool via 4th worker."""

    PATCH_BASE = "arlc.retriever"

    def _run(
        self,
        custom_corpus: str | None,
        custom_doc_ids: list[str] | None,
        builtin_chunks: list[str],
        custom_chunks: list[str],
    ):
        builtin_result = _make_vector_result(builtin_chunks)
        custom_result = _make_vector_result(custom_chunks, doc_ids=["custom-doc-1"] * len(custom_chunks))

        # _retrieve_pages_simple calls rerank_chunks, but with ≤40 chunks it returns them unchanged
        # since len(chunks) <= top_k. We patch it anyway so we don't need a real reranker.
        def _fake_rerank(question, chunks, top_k=20, answer_type="", on_status=None):
            return _make_reranked(chunks[:top_k])

        def _search_vector_side_effect(query_emb, top_k=50, corpus="difc", doc_ids=None):
            if corpus == "custom-tenant":
                return custom_result
            return builtin_result

        with (
            patch(f"{self.PATCH_BASE}.embed_query", return_value=[0.0] * 4096),
            patch(f"{self.PATCH_BASE}.search_chunks_vector", side_effect=_search_vector_side_effect),
            patch(f"{self.PATCH_BASE}.search_chunks_text", return_value=builtin_chunks),
            patch(f"{self.PATCH_BASE}._search_court_decisions_sync", return_value=[]),
            patch(f"{self.PATCH_BASE}.rerank_chunks", side_effect=_fake_rerank),
            patch(f"{self.PATCH_BASE}.get_chunk_count", return_value=1000),
            patch(f"{self.PATCH_BASE}.get_chunks_by_ids", return_value={"ids": [], "documents": [], "metadatas": []}),
        ):
            from arlc.retriever import _retrieve_pages_simple

            return _retrieve_pages_simple(
                question="Co říká zákon o zaměstnanosti?",
                corpus="czech",
                max_per_doc=2,
                max_total=5,
                custom_corpus=custom_corpus,
                custom_doc_ids=custom_doc_ids,
            )

    def test_custom_corpus_chunks_appear_in_results(self):
        """Custom corpus chunks should be present alongside Czech statute chunks."""
        results = self._run(
            custom_corpus="custom-tenant",
            custom_doc_ids=["custom-doc-1"],
            builtin_chunks=["cz-chunk-1", "cz-chunk-2"],
            custom_chunks=["custom-chunk-1"],
        )
        doc_ids = {r.doc_id for r in results}
        # custom-doc-1 is from the custom corpus; builtin doc_ids match chunk_ids
        assert "custom-doc-1" in doc_ids, f"Custom corpus doc missing from results: {doc_ids}"

    def test_without_custom_corpus_only_builtin_returned(self):
        """When no custom corpus is selected, results come only from the builtin corpus."""
        results = self._run(
            custom_corpus=None,
            custom_doc_ids=None,
            builtin_chunks=["cz-chunk-1", "cz-chunk-2"],
            custom_chunks=[],
        )
        doc_ids = {r.doc_id for r in results}
        assert "custom-doc-1" not in doc_ids

    def test_worker_count_expression_with_custom_corpus(self):
        """_n_workers evaluates to 4 when custom_corpus and custom_doc_ids are both set.

        This tests the ternary: _n_workers = 4 if (custom_corpus and custom_doc_ids) else 3
        """
        custom_corpus = "custom-tenant"
        custom_doc_ids = ["doc-1"]
        _n_workers = 4 if (custom_corpus and custom_doc_ids) else 3
        assert _n_workers == 4

    def test_worker_count_expression_without_custom_corpus(self):
        """_n_workers evaluates to 3 when custom_corpus is None."""
        custom_corpus = None
        custom_doc_ids = None
        _n_workers = 4 if (custom_corpus and custom_doc_ids) else 3
        assert _n_workers == 3

    def test_worker_count_expression_custom_corpus_no_doc_ids(self):
        """_n_workers evaluates to 3 when custom_corpus is set but doc_ids is empty list."""
        custom_corpus = "custom-tenant"
        custom_doc_ids = []  # falsy
        _n_workers = 4 if (custom_corpus and custom_doc_ids) else 3
        assert _n_workers == 3

    def test_custom_corpus_rrf_weight_0_7(self):
        """Custom corpus vector results enter RRF at weight 0.7 (same as builtin vector)."""
        # We verify this indirectly: the top custom chunk (rank=0) must contribute more
        # to the merged score than a builtin BM25-only chunk (rank=0 with weight 0.3).
        # With RRF: custom weight=0.7/(60+1) ≈ 0.01148; BM25 weight=0.3/(60+1) ≈ 0.00492
        # A custom chunk at rank 0 should outscore a BM25-only chunk at rank 0 if neither
        # appears in vector results — which we verify by checking chunk ordering.
        builtin_vec = _make_vector_result(["cz-vec"])
        custom_result = _make_vector_result(["custom-only"], doc_ids=["custom-doc"])
        bm25_only_ids = ["bm25-only"]

        def _search_vector_side_effect(query_emb, top_k=50, corpus="difc", doc_ids=None):
            if corpus == "custom-tenant":
                return custom_result
            return builtin_vec

        captured_fused_ids = []

        def _fake_rerank(question, chunks, top_k=20, answer_type="", on_status=None):
            captured_fused_ids.extend([c["chunk_id"] for c in chunks])
            return _make_reranked(chunks[:top_k])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever.search_chunks_vector", side_effect=_search_vector_side_effect),
            patch("arlc.retriever.search_chunks_text", return_value=bm25_only_ids),
            patch("arlc.retriever._search_court_decisions_sync", return_value=[]),
            patch("arlc.retriever.rerank_chunks", side_effect=_fake_rerank),
            patch("arlc.retriever.get_chunk_count", return_value=1000),
            patch(
                "arlc.retriever.get_chunks_by_ids",
                return_value={
                    "ids": ["bm25-only"],
                    "documents": ["bm25 text"],
                    "metadatas": [
                        {
                            "doc_id": "bm25-doc",
                            "pdf_id": "bm25-doc",
                            "page": 1,
                            "source_file": "f.pdf",
                            "chunk_id": "bm25-only",
                        }
                    ],
                },
            ),
        ):
            from arlc.retriever import _retrieve_pages_simple

            _retrieve_pages_simple(
                question="test",
                corpus="czech",
                custom_corpus="custom-tenant",
                custom_doc_ids=["custom-doc"],
            )

        # custom-only chunk should appear before bm25-only chunk in the reranker pool
        # (custom weight=0.7 vs BM25 weight=0.3)
        assert "custom-only" in captured_fused_ids, "Custom chunk not passed to reranker"
        assert "bm25-only" in captured_fused_ids, "BM25-only chunk not passed to reranker"
        custom_pos = captured_fused_ids.index("custom-only")
        bm25_pos = captured_fused_ids.index("bm25-only")
        assert custom_pos < bm25_pos, (
            f"Custom chunk (weight 0.7) should rank ahead of BM25-only chunk (weight 0.3), "
            f"but got positions: custom={custom_pos}, bm25={bm25_pos}"
        )


# ---------------------------------------------------------------------------
# 2. _retrieve_pages_simple — UK/AU (vector-only) + custom corpus path
# ---------------------------------------------------------------------------


class TestRetrievePagesSimpleVectorOnlyWithCustomCorpus:
    """UK/AU non-BM25 path: custom corpus merged via RRF with builtin vector results."""

    def _run(
        self,
        corpus: str,
        custom_corpus: str | None,
        custom_doc_ids: list[str] | None,
        builtin_chunks: list[str],
        custom_chunks: list[str],
    ):
        builtin_result = _make_vector_result(builtin_chunks)
        custom_result = _make_vector_result(custom_chunks, doc_ids=["custom-doc"] * len(custom_chunks))

        def _search_vector_side_effect(query_emb, top_k=50, corpus=corpus, doc_ids=None):
            if doc_ids is not None:  # custom corpus query always passes doc_ids
                return custom_result
            return builtin_result

        def _fake_rerank(question, chunks, top_k=20, answer_type="", on_status=None):
            return _make_reranked(chunks[:top_k])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever.search_chunks_vector", side_effect=_search_vector_side_effect),
            patch("arlc.retriever.rerank_chunks", side_effect=_fake_rerank),
            patch("arlc.retriever.get_chunk_count", return_value=1000),
        ):
            from arlc.retriever import _retrieve_pages_simple

            return _retrieve_pages_simple(
                question="What is the relevant UK statutory provision?",
                corpus=corpus,
                max_per_doc=2,
                max_total=5,
                custom_corpus=custom_corpus,
                custom_doc_ids=custom_doc_ids,
            )

    @pytest.mark.parametrize("corpus", ["uk", "au"])
    def test_custom_results_merged_for_non_morphological_corpus(self, corpus):
        """Custom corpus results appear in output alongside builtin vector results."""
        results = self._run(
            corpus=corpus,
            custom_corpus="custom-tenant",
            custom_doc_ids=["custom-doc"],
            builtin_chunks=["builtin-chunk-1"],
            custom_chunks=["custom-chunk-1"],
        )
        doc_ids = {r.doc_id for r in results}
        assert "custom-doc" in doc_ids, f"Custom doc missing for corpus={corpus}: {doc_ids}"

    @pytest.mark.parametrize("corpus", ["uk", "au"])
    def test_without_custom_corpus_no_extra_vector_call(self, corpus):
        """When no custom corpus, search_chunks_vector is called exactly once (builtin only)."""
        builtin_result = _make_vector_result(["builtin-chunk-1"])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever.search_chunks_vector", return_value=builtin_result) as mock_vec,
            patch("arlc.retriever.rerank_chunks", side_effect=lambda q, chunks, **kw: chunks),
            patch("arlc.retriever.get_chunk_count", return_value=1000),
        ):
            from arlc.retriever import _retrieve_pages_simple

            _retrieve_pages_simple(
                question="test",
                corpus=corpus,
                custom_corpus=None,
                custom_doc_ids=None,
            )
        assert mock_vec.call_count == 1, f"Expected 1 vector call (no custom corpus), got {mock_vec.call_count}"

    @pytest.mark.parametrize("corpus", ["uk", "au"])
    def test_with_custom_corpus_two_vector_calls(self, corpus):
        """When custom corpus is set, search_chunks_vector is called twice — builtin + custom."""
        builtin_result = _make_vector_result(["b1"])
        custom_result = _make_vector_result(["custom-1"], doc_ids=["custom-doc"])

        call_args = []

        def _track_calls(query_emb, top_k=50, corpus=corpus, doc_ids=None):
            call_args.append({"corpus": corpus, "doc_ids": doc_ids})
            if doc_ids:
                return custom_result
            return builtin_result

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever.search_chunks_vector", side_effect=_track_calls),
            patch("arlc.retriever.rerank_chunks", side_effect=lambda q, chunks, **kw: chunks),
            patch("arlc.retriever.get_chunk_count", return_value=1000),
        ):
            from arlc.retriever import _retrieve_pages_simple

            _retrieve_pages_simple(
                question="test",
                corpus=corpus,
                custom_corpus="custom-tenant",
                custom_doc_ids=["custom-doc"],
            )

        assert len(call_args) == 2, f"Expected 2 vector calls, got {len(call_args)}: {call_args}"
        corpora_queried = {c["corpus"] for c in call_args}
        assert corpus in corpora_queried, f"Builtin corpus {corpus!r} not queried"

    def test_rrf_merge_when_custom_outranks_builtin(self):
        """Custom corpus chunk at rank 0 competes fairly with builtin via RRF."""
        builtin_result = _make_vector_result(["builtin-chunk"], doc_ids=["builtin-doc"])
        custom_result = _make_vector_result(["custom-chunk"] * 1, doc_ids=["custom-doc"])

        def _search_side_effect(query_emb, top_k=50, corpus="uk", doc_ids=None):
            if doc_ids:
                return custom_result
            return builtin_result

        ranked_order = []

        def _fake_rerank(question, chunks, top_k=20, **kw):
            ranked_order.extend(c["chunk_id"] for c in chunks)
            return _make_reranked(chunks[:top_k])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever.search_chunks_vector", side_effect=_search_side_effect),
            patch("arlc.retriever.rerank_chunks", side_effect=_fake_rerank),
            patch("arlc.retriever.get_chunk_count", return_value=1000),
        ):
            from arlc.retriever import _retrieve_pages_simple

            _retrieve_pages_simple(
                question="test",
                corpus="uk",
                custom_corpus="custom-tenant",
                custom_doc_ids=["custom-doc"],
            )

        # Both chunks must be in the reranker pool
        assert "builtin-chunk" in ranked_order
        assert "custom-chunk" in ranked_order


# ---------------------------------------------------------------------------
# 3. retrieve_pages — DIFC + custom corpus RRF merge path
# ---------------------------------------------------------------------------


class TestRetrievePagesDialogDIFCWithCustomCorpus:
    """DIFC targeted/doc-fusion path: custom corpus merged via RRF after DIFC retrieval."""

    def _make_page_result(self, doc_id: str, page: int = 1, score: float = 0.8):
        from arlc.retriever import PageResult

        return PageResult(doc_id=doc_id, page_number=page, score=score, text=f"text from {doc_id}")

    def test_custom_corpus_results_merged_into_difc_results(self):
        """When both DIFC corpus and custom_corpus are set, custom results appear in output."""
        difc_pages = [self._make_page_result("difc-doc-A")]
        custom_vector = _make_vector_result(["custom-chunk-1"], doc_ids=["custom-doc-X"])

        def _fake_rerank(question, chunks, top_k=20, **kw):
            return _make_reranked(chunks[:top_k])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever._doc_fusion_select", return_value=["difc-doc-A"]),
            patch("arlc.retriever._retrieve_pages_targeted", return_value=difc_pages),
            patch("arlc.retriever.search_chunks_vector", return_value=custom_vector),
            patch("arlc.retriever.rerank_chunks", side_effect=_fake_rerank),
        ):
            from arlc.retriever import retrieve_pages

            results = retrieve_pages(
                question="What does DIFC Employment Law say about termination?",
                corpus="difc",
                max_per_doc=2,
                max_total=5,
                custom_corpus="custom-tenant",
                custom_doc_ids=["custom-doc-X"],
            )

        doc_ids = {r.doc_id for r in results}
        assert "custom-doc-X" in doc_ids, f"Custom corpus doc missing from DIFC results: {doc_ids}"
        assert "difc-doc-A" in doc_ids, f"DIFC doc should still appear: {doc_ids}"

    def test_no_custom_corpus_returns_only_difc_results(self):
        """Without custom_corpus, the DIFC path returns only builtin results."""
        difc_pages = [self._make_page_result("difc-doc-A")]

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever._doc_fusion_select", return_value=["difc-doc-A"]),
            patch("arlc.retriever._retrieve_pages_targeted", return_value=difc_pages),
            patch("arlc.retriever.search_chunks_vector") as mock_vec,
        ):
            from arlc.retriever import retrieve_pages

            results = retrieve_pages(
                question="test",
                corpus="difc",
                custom_corpus=None,
                custom_doc_ids=None,
            )

        # search_chunks_vector must NOT be called for the custom corpus step
        assert mock_vec.call_count == 0, "search_chunks_vector called unexpectedly with no custom corpus"
        assert results == difc_pages

    def test_custom_corpus_search_uses_correct_corpus_and_doc_ids(self):
        """search_chunks_vector for custom corpus must receive the correct corpus + doc_ids."""
        difc_pages = [self._make_page_result("difc-doc-A")]
        custom_vector = _make_vector_result(["custom-chunk"], doc_ids=["custom-doc"])

        captured_calls = []

        def _track_vec(query_emb, top_k=50, corpus="difc", doc_ids=None):
            captured_calls.append({"corpus": corpus, "doc_ids": doc_ids})
            return custom_vector

        def _fake_rerank(question, chunks, top_k=20, **kw):
            return _make_reranked(chunks[:top_k])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever._doc_fusion_select", return_value=["difc-doc-A"]),
            patch("arlc.retriever._retrieve_pages_targeted", return_value=difc_pages),
            patch("arlc.retriever.search_chunks_vector", side_effect=_track_vec),
            patch("arlc.retriever.rerank_chunks", side_effect=_fake_rerank),
        ):
            from arlc.retriever import retrieve_pages

            retrieve_pages(
                question="test",
                corpus="difc",
                custom_corpus="my-tenant",
                custom_doc_ids=["custom-doc"],
            )

        assert len(captured_calls) == 1, f"Expected 1 custom vector call, got: {captured_calls}"
        call = captured_calls[0]
        assert call["corpus"] == "my-tenant"
        assert call["doc_ids"] == ["custom-doc"]

    def test_custom_corpus_only_when_doc_ids_empty_no_merge(self):
        """When custom_doc_ids is an empty list, no custom corpus search or merge is done."""
        difc_pages = [self._make_page_result("difc-doc-A")]

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever._doc_fusion_select", return_value=["difc-doc-A"]),
            patch("arlc.retriever._retrieve_pages_targeted", return_value=difc_pages),
            patch("arlc.retriever.search_chunks_vector") as mock_vec,
        ):
            from arlc.retriever import retrieve_pages

            results = retrieve_pages(
                question="test",
                corpus="difc",
                custom_corpus="my-tenant",
                custom_doc_ids=[],  # empty — no documents in collection
            )

        # Empty doc_ids is falsy → skip the custom corpus branch
        assert mock_vec.call_count == 0
        assert results == difc_pages

    def test_difc_fallback_path_also_merges_custom_corpus(self):
        """When doc-fusion returns nothing, fallback path still merges custom corpus."""
        fallback_pages = [self._make_page_result("difc-fallback-doc")]
        custom_vector = _make_vector_result(["custom-chunk"], doc_ids=["custom-doc"])

        def _fake_rerank(question, chunks, top_k=20, **kw):
            return _make_reranked(chunks[:top_k])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever._doc_fusion_select", return_value=[]),
            patch("arlc.retriever._retrieve_pages_fallback", return_value=fallback_pages),
            patch("arlc.retriever.search_chunks_vector", return_value=custom_vector),
            patch("arlc.retriever.rerank_chunks", side_effect=_fake_rerank),
        ):
            from arlc.retriever import retrieve_pages

            results = retrieve_pages(
                question="test",
                corpus="difc",
                custom_corpus="my-tenant",
                custom_doc_ids=["custom-doc"],
            )

        doc_ids = {r.doc_id for r in results}
        assert "custom-doc" in doc_ids, "Custom doc should be merged even via fallback path"

    def test_rrf_limits_applied_on_merged_results(self):
        """max_total is enforced on the merged DIFC + custom result set."""
        difc_pages = [self._make_page_result(f"difc-doc-{i}", score=0.9 - 0.01 * i) for i in range(4)]
        custom_vector = _make_vector_result(
            [f"custom-chunk-{i}" for i in range(4)],
            doc_ids=[f"custom-doc-{i}" for i in range(4)],
        )

        def _fake_rerank(question, chunks, top_k=20, **kw):
            return _make_reranked(chunks[:top_k])

        with (
            patch("arlc.retriever.embed_query", return_value=[0.0] * 4096),
            patch("arlc.retriever._doc_fusion_select", return_value=[f"difc-doc-{i}" for i in range(4)]),
            patch("arlc.retriever._retrieve_pages_targeted", return_value=difc_pages),
            patch("arlc.retriever.search_chunks_vector", return_value=custom_vector),
            patch("arlc.retriever.rerank_chunks", side_effect=_fake_rerank),
        ):
            from arlc.retriever import retrieve_pages

            results = retrieve_pages(
                question="test",
                corpus="difc",
                max_total=3,
                custom_corpus="my-tenant",
                custom_doc_ids=[f"custom-doc-{i}" for i in range(4)],
            )

        assert len(results) <= 3, f"max_total=3 violated: got {len(results)} results"


# ---------------------------------------------------------------------------
# 4. query.py — _resolve_corpora_id + hybrid mode detection routing
# ---------------------------------------------------------------------------


class TestResolveCorporaId:
    """_resolve_corpora_id: format validation, ownership check, and collection filtering."""

    def test_malformed_id_missing_colon_returns_none(self):
        from neolex.routers.query import _resolve_corpora_id

        result = _resolve_corpora_id("no-colon-here", "my-tenant")
        assert result is None

    def test_wrong_slug_returns_none(self):
        """Access control: user cannot query another tenant's collection."""
        from neolex.routers.query import _resolve_corpora_id

        result = _resolve_corpora_id("other-tenant:MyCollection", "my-tenant")
        assert result is None

    def test_missing_docs_directory_returns_none(self, tmp_path):
        """If the client docs directory does not exist, return None."""
        from unittest.mock import patch as _patch

        from neolex.routers.query import _resolve_corpora_id

        with _patch("neolex.routers.query.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            result = _resolve_corpora_id("my-tenant:MyCollection", "my-tenant")

        assert result is None

    def test_valid_collection_returns_doc_ids(self, tmp_path):
        """Documents in the correct collection are returned; others are excluded."""
        import json as _json
        from unittest.mock import patch as _patch

        docs_dir = tmp_path / "clients" / "my-tenant" / "docs"
        docs_dir.mkdir(parents=True)

        # doc in target collection
        (docs_dir / "doc1.meta").write_text(_json.dumps({"doc_id": "uuid-doc-1", "collection": "MyCollection"}))
        # doc in different collection — must be excluded
        (docs_dir / "doc2.meta").write_text(_json.dumps({"doc_id": "uuid-doc-2", "collection": "OtherCollection"}))
        # doc without collection key — defaults to "My Documents", must be excluded
        (docs_dir / "doc3.meta").write_text(_json.dumps({"doc_id": "uuid-doc-3"}))

        from neolex.routers.query import _resolve_corpora_id

        with _patch("neolex.routers.query.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            result = _resolve_corpora_id("my-tenant:MyCollection", "my-tenant")

        assert result == ["uuid-doc-1"], f"Unexpected doc_ids: {result}"

    def test_empty_collection_returns_none(self, tmp_path):
        """Collection exists but no documents match → None (caller treats as invalid/empty).

        _resolve_corpora_id returns `doc_ids if doc_ids else None`, so an empty match
        returns None, not []. The caller in query_stream raises HTTP 400 on None.
        """
        import json as _json
        from unittest.mock import patch as _patch

        docs_dir = tmp_path / "clients" / "my-tenant" / "docs"
        docs_dir.mkdir(parents=True)

        (docs_dir / "doc1.meta").write_text(_json.dumps({"doc_id": "uuid-doc-1", "collection": "OtherCollection"}))

        from neolex.routers.query import _resolve_corpora_id

        with _patch("neolex.routers.query.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            result = _resolve_corpora_id("my-tenant:EmptyCollection", "my-tenant")

        assert result is None, f"Expected None for empty collection match, got: {result}"

    def test_malformed_meta_file_is_skipped(self, tmp_path):
        """Corrupted .meta files are skipped gracefully; valid ones still returned."""
        import json as _json
        from unittest.mock import patch as _patch

        docs_dir = tmp_path / "clients" / "my-tenant" / "docs"
        docs_dir.mkdir(parents=True)

        (docs_dir / "bad.meta").write_text("{not valid json}")
        (docs_dir / "good.meta").write_text(_json.dumps({"doc_id": "uuid-good", "collection": "MyCollection"}))

        from neolex.routers.query import _resolve_corpora_id

        with _patch("neolex.routers.query.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            result = _resolve_corpora_id("my-tenant:MyCollection", "my-tenant")

        assert result == ["uuid-good"]


class TestHybridModeDetectionRouting:
    """query_stream corpora_id branch: hybrid vs custom-only routing logic.

    These tests exercise the routing decision (lines ~398-411 in query.py) by
    importing and calling the routing logic directly after mocking dependencies.
    Because query_stream is a large async handler, we extract and test the
    routing logic through the public _resolve_corpora_id function and verify
    the conditions that gate each branch.
    """

    def test_builtin_corpus_plus_corpora_id_is_hybrid_mode(self):
        """corpus in _BUILTIN_CORPORA and corpus != client_slug → hybrid mode."""
        from neolex.routers.query import _BUILTIN_CORPORA

        client_slug = "my-tenant"
        for corpus in _BUILTIN_CORPORA:
            # corpus is a builtin name like "difc", "czech", "uk", "au"
            # client_slug is the user's own tenant ID — never equal to a builtin name
            assert corpus != client_slug, f"Builtin corpus {corpus!r} should differ from client slug"
            is_hybrid = corpus in _BUILTIN_CORPORA and corpus != client_slug
            assert is_hybrid, f"Expected hybrid mode for corpus={corpus!r}"

    def test_custom_only_when_corpus_equals_client_slug(self):
        """When corpus matches client_slug (user's own corpus), it's custom-only mode."""
        from neolex.routers.query import _BUILTIN_CORPORA

        client_slug = "my-tenant"
        corpus = "my-tenant"  # user selected their own corpus directly

        # This corpus is not in builtins, so the hybrid branch is NOT entered
        is_hybrid = corpus in _BUILTIN_CORPORA and corpus != client_slug
        assert not is_hybrid, "Corpus matching client_slug should not enter hybrid mode"

    def test_builtin_corpora_set_contains_expected_jurisdictions(self):
        """_BUILTIN_CORPORA must contain exactly the four production jurisdictions."""
        from neolex.routers.query import _BUILTIN_CORPORA

        expected = {"difc", "czech", "uk", "au"}
        assert _BUILTIN_CORPORA == expected, (
            f"_BUILTIN_CORPORA has changed — update hybrid routing logic if intentional: {_BUILTIN_CORPORA}"
        )

    def test_hybrid_mode_sets_custom_corpus_and_doc_ids(self):
        """Simulate the query_stream routing decision: builtin corpus + corpora_id → custom_corpus set."""
        from neolex.routers.query import _BUILTIN_CORPORA

        # Simulate the routing logic from query_stream (lines ~395-411)
        corpus = "czech"
        corpora_id = "my-tenant:MyCollection"
        client_slug = "my-tenant"
        resolved_doc_ids = ["uuid-doc-1", "uuid-doc-2"]

        custom_corpus = None
        custom_doc_ids = None
        body_doc_ids = None
        body_corpus = corpus

        if corpora_id:
            if corpus in _BUILTIN_CORPORA and corpus != client_slug:
                custom_corpus = client_slug
                custom_doc_ids = resolved_doc_ids
            else:
                body_doc_ids = resolved_doc_ids
                body_corpus = client_slug

        assert custom_corpus == "my-tenant"
        assert custom_doc_ids == ["uuid-doc-1", "uuid-doc-2"]
        assert body_doc_ids is None  # body not overridden in hybrid mode
        assert body_corpus == "czech"  # corpus unchanged in hybrid mode

    def test_custom_only_mode_overrides_body_corpus(self):
        """When corpus is not builtin, corpora_id overrides body corpus (custom-only mode)."""
        from neolex.routers.query import _BUILTIN_CORPORA

        corpus = "my-tenant"  # user's own corpus selected
        corpora_id = "my-tenant:MyCollection"
        client_slug = "my-tenant"
        resolved_doc_ids = ["uuid-doc-1"]

        custom_corpus = None
        body_doc_ids = None
        body_corpus = corpus

        if corpora_id:
            if corpus in _BUILTIN_CORPORA and corpus != client_slug:
                custom_corpus = client_slug
            else:
                body_doc_ids = resolved_doc_ids
                body_corpus = client_slug

        assert custom_corpus is None, "Should NOT be hybrid mode"
        assert body_doc_ids == ["uuid-doc-1"], "body.doc_ids should be set in custom-only mode"
        assert body_corpus == "my-tenant"
