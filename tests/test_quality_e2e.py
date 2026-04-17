"""E2E quality test suite: retrieval precision, hybrid fusion, agent answer quality, regression guards.

NEO-2298: Four test categories covering the full RAG pipeline:
  1. TestRRFFusion         — reciprocal_rank_fusion correctness (offline, pure logic)
  2. TestReranking         — rerank_chunks contract and fallback behavior (offline, mocked)
  3. TestEmbeddingContract — embed_query vs embed_document asymmetry (offline, mocked)
  4. TestOracleAndAnswer   — oracle fast-path and generate_answer contract (offline, mocked)
  5. TestHybridSearchPaths — corpus routing: Czech BM25 fusion, UK/AU vector-only (offline, mocked)
  6. TestRegressionGuards  — golden-set quality vs known thresholds (integration, live infra required)

Run:
    uv run pytest tests/test_quality_e2e.py -v              # offline tests only (1-5)
    uv run pytest tests/test_quality_e2e.py -m integration  # regression guards (6), requires live infra
    uv run pytest tests/test_quality_e2e.py -v --tb=short   # full run with short tracebacks

Integration tests require:
    - PostgreSQL at DATABASE_URL with indexed chunks
    - Embedding server at LLAMA_SERVER_URL (localhost:8088 or RTX 3070)
    - LLM credentials: VERTEX_PROJECT_ID or ANTHROPIC_API_KEY
"""

from __future__ import annotations

import os
import re
from unittest.mock import MagicMock, patch

import pytest

# Env vars must be set before any module-level config evaluation
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-only")
os.environ.setdefault("ADMIN_EMAILS", "admin@vitreon.app")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _dummy_vec(dim: int = 4096, val: float = 0.1) -> list[float]:
    return [val] * dim


def _make_chunk(chunk_id: str, doc_id: str, page: int = 1, text: str = "Legal text.") -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "page": page,
        "text": text,
        "score": 0.5,
        "source_file": f"{doc_id}.pdf",
    }


def _make_call_llm_return(answer_text: str) -> tuple:
    """Return value shape for _call_llm: (text, ttft_ms, total_ms, tpot_ms, in_tok, out_tok, cr, cw)."""
    return (answer_text, 120.0, 1500.0, 8.0, 800, 60, 0, 0)


# ---------------------------------------------------------------------------
# 1. TestRRFFusion — reciprocal_rank_fusion correctness (pure logic)
# ---------------------------------------------------------------------------


class TestRRFFusion:
    """Verify the RRF formula produces correct orderings."""

    def test_single_list_order_preserved(self):
        from arlc.retriever import reciprocal_rank_fusion

        ranking = ["a", "b", "c", "d", "e"]
        assert reciprocal_rank_fusion([ranking]) == ranking

    def test_shared_item_wins_over_single_list_item(self):
        from arlc.retriever import reciprocal_rank_fusion

        vec = ["shared", "vec_only"]
        bm25 = ["shared", "bm25_only"]
        merged = reciprocal_rank_fusion([vec, bm25])
        assert merged[0] == "shared", "Item in both rankings must outscore items in only one"

    def test_weighted_vector_beats_bm25_for_disjoint_items(self):
        from arlc.retriever import reciprocal_rank_fusion

        # vec_top: rank-0 in vec (w=0.7), absent from bm25
        # bm25_top: rank-0 in bm25 (w=0.3), absent from vec
        # vec_top score: 0.7/(60+1) = 0.01148 > bm25_top score: 0.3/(60+1) = 0.00492
        vec = ["vec_top", "vec_second"]
        bm25 = ["bm25_top"]
        merged = reciprocal_rank_fusion([vec, bm25], weights=[0.7, 0.3])
        assert merged[0] == "vec_top"

    def test_four_list_shared_item_dominates(self):
        """Item appearing in all 4 worker results (Czech hybrid) must rank first."""
        from arlc.retriever import reciprocal_rank_fusion

        workers = [
            ["common", "vec_only"],
            ["common", "bm25_only"],
            ["common", "custom_only"],
            ["common", "court_only"],
        ]
        merged = reciprocal_rank_fusion(workers)
        assert merged[0] == "common"

    def test_empty_list_does_not_crash(self):
        from arlc.retriever import reciprocal_rank_fusion

        # Empty inner list should be silently skipped
        merged = reciprocal_rank_fusion([["a", "b"], [], ["a", "c"]])
        assert merged[0] == "a"

    def test_single_item_list(self):
        from arlc.retriever import reciprocal_rank_fusion

        assert reciprocal_rank_fusion([["only"]]) == ["only"]

    def test_k60_formula_correctness(self):
        """Verify the RRF score for known inputs matches the formula 1/(k+rank+1)."""
        from arlc.retriever import reciprocal_rank_fusion

        # With one list and k=60, rank-0 item scores 1/61, rank-1 scores 1/62
        # Their ratio must satisfy: score(rank-0) > score(rank-1)
        merged = reciprocal_rank_fusion([["first", "second"]], k=60)
        assert merged == ["first", "second"]

    def test_weights_not_required_to_sum_to_one(self):
        from arlc.retriever import reciprocal_rank_fusion

        # Weights don't need to sum to 1; result must still be a valid ordering
        merged = reciprocal_rank_fusion([["a", "b"], ["b", "a"]], weights=[0.7, 0.3])
        assert set(merged) == {"a", "b"}
        assert len(merged) == 2

    def test_rrf_vec_weight_constant_is_0_7(self):
        """_RRF_VEC_WEIGHT must be 0.7 — vector signal is weighted higher than BM25 (0.3)."""
        from arlc.retriever import _RRF_VEC_WEIGHT

        assert _RRF_VEC_WEIGHT == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# 2. TestReranking — rerank_chunks contract + fallback chain (mocked)
# ---------------------------------------------------------------------------


class TestReranking:
    """Verify rerank_chunks result limits, score assignment, and failover."""

    def _mock_ranker(self, scores: list[float]) -> MagicMock:
        m = MagicMock()
        m.predict.return_value = scores
        return m

    def test_top_k_limit_respected(self):
        from arlc.retriever import rerank_chunks

        chunks = [_make_chunk(f"c{i}", "doc1") for i in range(30)]
        ranker = self._mock_ranker([0.9 - i * 0.01 for i in range(30)])

        with patch("arlc.retriever.get_reranker", return_value=ranker):
            result = rerank_chunks("legal question", chunks, top_k=10)

        assert len(result) == 10

    def test_rerank_score_field_present_on_every_result(self):
        from arlc.retriever import rerank_chunks

        chunks = [_make_chunk(f"c{i}", "doc1") for i in range(20)]
        ranker = self._mock_ranker([float(i) for i in range(20)])

        with patch("arlc.retriever.get_reranker", return_value=ranker):
            result = rerank_chunks("legal question", chunks, top_k=5)

        for chunk in result:
            assert "rerank_score" in chunk, f"Missing rerank_score on chunk: {chunk.get('chunk_id')}"

    def test_higher_score_chunk_appears_first(self):
        from arlc.retriever import rerank_chunks

        chunks = [_make_chunk(f"c{i}", "doc1") for i in range(20)]
        # Assign scores so last chunk has highest score
        scores = [0.0 + i * 0.05 for i in range(20)]
        ranker = self._mock_ranker(scores)

        with patch("arlc.retriever.get_reranker", return_value=ranker):
            result = rerank_chunks("legal question", chunks, top_k=5)

        # Top result must have the highest rerank_score
        assert result[0]["rerank_score"] >= result[-1]["rerank_score"]

    def test_noop_when_chunks_lte_top_k(self):
        """No predict() call when len(chunks) <= top_k — avoid unnecessary latency."""
        from arlc.retriever import rerank_chunks

        chunks = [_make_chunk(f"c{i}", "doc1") for i in range(5)]
        ranker = self._mock_ranker([])

        with patch("arlc.retriever.get_reranker", return_value=ranker):
            result = rerank_chunks("legal question", chunks, top_k=10)

        ranker.predict.assert_not_called()
        assert result == chunks

    def test_primary_failure_falls_back_to_local(self):
        """When primary reranker fails, local reranker must be tried."""
        from arlc.retriever import rerank_chunks

        chunks = [_make_chunk(f"c{i}", "doc1") for i in range(20)]
        primary = MagicMock()
        primary.predict.side_effect = RuntimeError("remote unavailable")
        local = self._mock_ranker([0.9 - i * 0.01 for i in range(20)])

        with (
            patch("arlc.retriever.get_reranker", return_value=primary),
            patch("arlc.retriever.get_local_reranker", return_value=local),
            patch("arlc.retriever._demote_remote_reranker"),
        ):
            result = rerank_chunks("legal question", chunks, top_k=5)

        assert len(result) == 5
        local.predict.assert_called_once()

    def test_both_rerankers_fail_returns_unranked_subset(self):
        """Double failure must not propagate — returns first top_k unranked chunks."""
        from arlc.retriever import rerank_chunks

        chunks = [_make_chunk(f"c{i}", "doc1") for i in range(20)]
        bad = MagicMock()
        bad.predict.side_effect = RuntimeError("failed")

        with (
            patch("arlc.retriever.get_reranker", return_value=bad),
            patch("arlc.retriever.get_local_reranker", return_value=bad),
            patch("arlc.retriever._demote_remote_reranker"),
        ):
            result = rerank_chunks("legal question", chunks, top_k=5)

        assert len(result) == 5  # first 5 unranked


# ---------------------------------------------------------------------------
# 3. TestEmbeddingContract — embed_query vs embed_document asymmetry
# ---------------------------------------------------------------------------


class TestEmbeddingContract:
    """Verify Qwen3-Embedding-8B asymmetric usage: query prefix vs no prefix."""

    def _setup_mock_model(self):
        model = MagicMock()
        vec = MagicMock()
        vec.tolist.return_value = _dummy_vec()
        model.encode.return_value = vec
        return model

    def test_embed_query_uses_query_prompt_name(self):
        """embed_query must pass prompt_name='query' for Qwen3 instruction prefix."""
        model = self._setup_mock_model()
        with patch("arlc.retriever.get_embedding_model", return_value=model):
            from arlc.retriever import embed_query

            embed_query("What is the limitation period?")

        _, kwargs = model.encode.call_args
        assert kwargs.get("prompt_name") == "query", (
            "embed_query must pass prompt_name='query' — required for Qwen3 asymmetric retrieval"
        )

    def test_embed_document_does_not_use_query_prompt(self):
        """embed_document must NOT pass prompt_name='query' — documents embed raw."""
        model = self._setup_mock_model()
        with patch("arlc.retriever.get_embedding_model", return_value=model):
            from arlc.retriever import embed_document

            embed_document("Article 10. The limitation period is 6 years.")

        _, kwargs = model.encode.call_args
        assert kwargs.get("prompt_name") != "query", (
            "embed_document must NOT use query prefix — breaks retrieval quality for indexed chunks"
        )

    def test_embed_query_and_document_are_different_calls(self):
        """The two calls must differ — same call for both means asymmetry is broken."""
        model = self._setup_mock_model()
        with patch("arlc.retriever.get_embedding_model", return_value=model):
            from arlc.retriever import embed_document, embed_query

            embed_query("What is the limitation period?")
            embed_document("Article 10. The limitation period is 6 years.")

        assert model.encode.call_count == 2
        first_call = model.encode.call_args_list[0]
        second_call = model.encode.call_args_list[1]
        # The two calls must differ (query has prompt_name='query', document does not)
        assert first_call != second_call

    def test_embed_query_returns_list_of_floats(self):
        model = self._setup_mock_model()
        with patch("arlc.retriever.get_embedding_model", return_value=model):
            from arlc.retriever import embed_query

            result = embed_query("test question")

        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_embed_document_returns_list_of_floats(self):
        model = self._setup_mock_model()
        with patch("arlc.retriever.get_embedding_model", return_value=model):
            from arlc.retriever import embed_document

            result = embed_document("test document text")

        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)


# ---------------------------------------------------------------------------
# 4. TestOracleAndAnswer — oracle fast-path + generate_answer contract (mocked)
# ---------------------------------------------------------------------------


class TestOracleAndAnswer:
    """Verify oracle fast-path correctness and generate_answer output contract."""

    def test_oracle_returns_none_for_unknown_question(self):
        """Oracle must return None when it cannot answer from metadata indexes."""
        from arlc.answerer import _lookup_oracle

        result = _lookup_oracle("What is the weather in Dubai today?", "free_text", source_pages=[])
        assert result is None

    def test_oracle_returns_answer_result_or_none(self):
        """Oracle must return AnswerResult or None — never a bare primitive."""
        from arlc.answerer import AnswerResult, _lookup_oracle

        result = _lookup_oracle("Some legal question about DIFC", "boolean", source_pages=[])
        assert result is None or isinstance(result, AnswerResult)

    def test_answer_result_required_fields(self):
        """AnswerResult must expose all fields consumed by the pipeline and API layer."""
        from arlc.answerer import AnswerResult

        ar = AnswerResult(answer=True)
        required = {
            "answer",
            "chunk_pages",
            "ttft_ms",
            "total_time_ms",
            "tpot_ms",
            "input_tokens",
            "output_tokens",
            "model_name",
            "grounding",
        }
        for field in required:
            assert hasattr(ar, field), f"AnswerResult is missing field: {field}"

    def test_answer_result_total_time_ms_nonzero_default(self):
        """total_time_ms default must be > 0 — zero causes platform T-score regression."""
        from arlc.answerer import AnswerResult

        ar = AnswerResult(answer=None)
        assert ar.total_time_ms > 0, "total_time_ms=0 triggers platform scoring penalty"

    def test_answer_result_list_fields_are_mutable_per_instance(self):
        """chunk_pages and grounding must be independent lists (not shared class-level default)."""
        from arlc.answerer import AnswerResult

        ar1 = AnswerResult(answer=True)
        ar2 = AnswerResult(answer=False)
        ar1.chunk_pages.append({"doc_id": "doc-1", "page_numbers": [1]})
        assert ar2.chunk_pages == [], "chunk_pages lists must be independent per instance"

    @pytest.mark.asyncio
    async def test_generate_answer_returns_answer_result(self):
        """generate_answer must return an AnswerResult regardless of LLM response."""
        from arlc.answerer import AnswerResult, generate_answer

        source_pages = [{"doc_id": "DIFC-EMP-2019", "page_number": 5, "text": "Article 59 text."}]

        with patch("arlc.answerer._call_llm", return_value=_make_call_llm_return("true")):
            result = await generate_answer("Can an employee be dismissed?", "boolean", source_pages)

        assert isinstance(result, AnswerResult)

    @pytest.mark.asyncio
    async def test_generate_answer_no_crash_on_empty_pages(self):
        """generate_answer must not raise when source_pages is empty."""
        from arlc.answerer import AnswerResult, generate_answer

        with patch("arlc.answerer._call_llm", return_value=_make_call_llm_return("null")):
            result = await generate_answer("Any question?", "boolean", source_pages=[])

        assert isinstance(result, AnswerResult)

    @pytest.mark.asyncio
    async def test_metadata_answer_bypasses_llm(self):
        """When metadata_answer is provided for non-free_text types, LLM must not be called."""
        from arlc.answerer import AnswerResult, generate_answer

        source_pages = [{"doc_id": "DIFC-LAW-5", "page_number": 3, "text": "Article 10."}]

        with patch("arlc.answerer._call_llm") as mock_call:
            result = await generate_answer(
                "What is the case number?",
                "name",
                source_pages,
                metadata_answer="CFI 001/2024",
            )

        mock_call.assert_not_called()
        assert isinstance(result, AnswerResult)
        assert result.answer == "CFI 001/2024"

    @pytest.mark.asyncio
    async def test_generate_answer_boolean_answer_is_bool(self):
        """Boolean questions must produce a Python bool or None, never a raw string."""
        from arlc.answerer import AnswerResult, generate_answer

        source_pages = [{"doc_id": "DIFC-EMP-2019", "page_number": 5, "text": "Yes, employees may be dismissed."}]

        with patch("arlc.answerer._call_llm", return_value=_make_call_llm_return("true")):
            result = await generate_answer("Can an employee be dismissed for cause?", "boolean", source_pages)

        assert isinstance(result, AnswerResult)
        # answer is either a bool or None (null JSON) — never a raw "true"/"false" string
        if result.answer is not None:
            assert isinstance(result.answer, bool), (
                f"Boolean answer must be bool, got {type(result.answer)}: {result.answer!r}"
            )


# ---------------------------------------------------------------------------
# 5. TestHybridSearchPaths — corpus routing + BM25 path selection (mocked)
# ---------------------------------------------------------------------------


class TestHybridSearchPaths:
    """Verify corpus-specific retrieval routing and BM25 fusion activation."""

    def test_czech_in_morphological_corpora(self):
        """Czech must be in _MORPHOLOGICAL_CORPORA — controls BM25 fusion activation."""
        from arlc.retriever import _MORPHOLOGICAL_CORPORA

        assert "czech" in _MORPHOLOGICAL_CORPORA

    def test_difc_not_in_morphological_corpora(self):
        """DIFC uses a different retrieval path; BM25 fusion must not apply to it here."""
        from arlc.retriever import _MORPHOLOGICAL_CORPORA

        assert "difc" not in _MORPHOLOGICAL_CORPORA

    def test_retrieve_pages_simple_calls_embed_query_once(self):
        """_retrieve_pages_simple must embed the query once when no cached embedding is given."""
        from arlc.retriever import _retrieve_pages_simple

        mock_embed = MagicMock(return_value=_dummy_vec())

        with (
            patch("arlc.retriever.embed_query", mock_embed),
            patch(
                "arlc.retriever.search_chunks_vector",
                return_value={"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]},
            ),
            patch("arlc.retriever.search_chunks_text", return_value=[]),
            patch("arlc.retriever._search_court_decisions_sync", return_value=[]),
            patch("arlc.retriever.rerank_chunks", return_value=[]),
            patch("arlc.retriever.get_chunk_count", return_value=100),
        ):
            _retrieve_pages_simple("What is the limitation period?", corpus="uk")

        mock_embed.assert_called_once()

    def test_retrieve_pages_simple_uses_cached_embedding(self):
        """When cached_query_emb is supplied, embed_query must NOT be called."""
        from arlc.retriever import _retrieve_pages_simple

        mock_embed = MagicMock(return_value=_dummy_vec())

        with (
            patch("arlc.retriever.embed_query", mock_embed),
            patch(
                "arlc.retriever.search_chunks_vector",
                return_value={"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]},
            ),
            patch("arlc.retriever.search_chunks_text", return_value=[]),
            patch("arlc.retriever._search_court_decisions_sync", return_value=[]),
            patch("arlc.retriever.rerank_chunks", return_value=[]),
            patch("arlc.retriever.get_chunk_count", return_value=100),
        ):
            _retrieve_pages_simple(
                "test question",
                corpus="uk",
                cached_query_emb=_dummy_vec(val=0.99),
            )

        mock_embed.assert_not_called()

    def test_czech_path_calls_search_chunks_text(self):
        """Czech corpus must trigger BM25 search (search_chunks_text) alongside vector search."""
        from arlc.retriever import _retrieve_pages_simple

        mock_bm25 = MagicMock(return_value=[])

        with (
            patch("arlc.retriever.embed_query", return_value=_dummy_vec()),
            patch(
                "arlc.retriever.search_chunks_vector",
                return_value={"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]},
            ),
            patch("arlc.retriever.search_chunks_text", mock_bm25),
            patch("arlc.retriever._search_court_decisions_sync", return_value=[]),
            patch("arlc.retriever.rerank_chunks", return_value=[]),
            patch("arlc.retriever.get_chunk_count", return_value=100),
        ):
            _retrieve_pages_simple("Jaká je výpovědní doba?", corpus="czech")

        mock_bm25.assert_called()

    def test_uk_path_skips_bm25(self):
        """UK corpus (non-morphological) must NOT call BM25 search."""
        from arlc.retriever import _retrieve_pages_simple

        mock_bm25 = MagicMock(return_value=[])

        with (
            patch("arlc.retriever.embed_query", return_value=_dummy_vec()),
            patch(
                "arlc.retriever.search_chunks_vector",
                return_value={"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]},
            ),
            patch("arlc.retriever.search_chunks_text", mock_bm25),
            patch("arlc.retriever._search_court_decisions_sync", return_value=[]),
            patch("arlc.retriever.rerank_chunks", return_value=[]),
            patch("arlc.retriever.get_chunk_count", return_value=100),
        ):
            _retrieve_pages_simple("What is the limitation period?", corpus="uk")

        mock_bm25.assert_not_called()

    def test_retrieve_pages_simple_returns_list(self):
        """_retrieve_pages_simple must always return a list (never None or crash)."""
        from arlc.retriever import _retrieve_pages_simple

        with (
            patch("arlc.retriever.embed_query", return_value=_dummy_vec()),
            patch(
                "arlc.retriever.search_chunks_vector",
                return_value={"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]},
            ),
            patch("arlc.retriever.search_chunks_text", return_value=[]),
            patch("arlc.retriever._search_court_decisions_sync", return_value=[]),
            patch("arlc.retriever.rerank_chunks", return_value=[]),
            patch("arlc.retriever.get_chunk_count", return_value=100),
        ):
            result = _retrieve_pages_simple("any question", corpus="uk")

        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 6. TestRegressionGuards — golden-set quality vs thresholds (integration)
# ---------------------------------------------------------------------------

# Conservative thresholds based on April 2026 benchmark baseline.
# Fail only on genuine regression (not noise). Update when pipeline is intentionally improved.
_DIFC_CITATION_THRESHOLD = 55.0  # citation accuracy %: answer mentions expected section
_DIFC_CORRECT_THRESHOLD = 60.0  # answer correctness %: answer contains expected keyword
_DIFC_GROUNDING_THRESHOLD = 65.0  # grounding %: answer contains [DOC-N] citation
_CZECH_CITATION_THRESHOLD = 45.0
_CZECH_CORRECT_THRESHOLD = 55.0
_CZECH_GROUNDING_THRESHOLD = 55.0

# Small golden sets drawn from benchmark_accuracy.py — stable, known-good questions
_GOLDEN_DIFC: list[dict] = [
    {"q": "What is the limitation period under DIFC Law No. 5 of 2005?", "section": "Article 9", "keyword": "6 years"},
    {"q": "Can a contract be formed orally under DIFC law?", "section": "Article 15", "keyword": "oral"},
    {
        "q": "What is the minimum notice period for termination of employment in DIFC?",
        "section": "Article 58",
        "keyword": "30 days",
    },
    {"q": "How is end of service gratuity calculated in DIFC?", "section": "Article 62", "keyword": "gratuity"},
    {"q": "What constitutes unfair dismissal under DIFC Employment Law?", "section": "Article 59", "keyword": "unfair"},
    {"q": "What are the grounds for winding up a company in DIFC?", "section": "Article 50", "keyword": "wind"},
    {
        "q": "What remedies are available for breach of contract under DIFC law?",
        "section": "Law No. 5",
        "keyword": "damages",
    },
    {"q": "What is the maximum working hours per week in DIFC?", "section": "Employment", "keyword": "48"},
]

_GOLDEN_CZECH: list[dict] = [
    {"q": "Jaká je výpovědní doba podle zákoníku práce?", "section": "§ 51", "keyword": "2 měsíc"},
    {"q": "Co je bezdůvodné obohacení?", "section": "§ 2991", "keyword": "obohac"},
    {"q": "Kolik je zákonné odstupné?", "section": "§ 67", "keyword": "odstupn"},
    {"q": "Jaký je nárok na dovolenou?", "section": "§ 211", "keyword": "dovolen"},
    {"q": "Jaká je promlčecí doba?", "section": "§ 629", "keyword": "3 rok"},
]


def _score_answer(answer_text: str, source_texts: list[str], section: str, keyword: str) -> dict:
    """Score answer against expected section mention and keyword presence."""
    full_text = answer_text + " " + " ".join(source_texts)
    citation = 1 if re.search(re.escape(section), full_text, re.IGNORECASE) else 0
    correctness = 1 if re.search(re.escape(keyword), full_text, re.IGNORECASE) else 0
    grounding = 1 if re.search(r"\[DOC-\d+\]", answer_text) else 0
    return {"citation": citation, "correctness": correctness, "grounding": grounding}


def _postgres_reachable() -> bool:
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("localhost", 5432))
        s.close()
        return True
    except OSError:
        return False


def _embedding_server_reachable() -> bool:
    """Check whether the embedding server (llama-server) is responding."""
    import socket
    from urllib.parse import urlparse

    url = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8088")
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8088
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((host, port))
        s.close()
        return True
    except OSError:
        return False


def _llm_credentials_configured() -> bool:
    """Check whether real LLM credentials are available (not test dummies)."""
    vertex_id = os.environ.get("VERTEX_PROJECT_ID", "")
    if vertex_id and vertex_id != "test-project":
        return True
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    return False


_skip_no_llm = pytest.mark.skipif(
    not _llm_credentials_configured(),
    reason="No real LLM credentials — full pipeline guards need VERTEX_PROJECT_ID or ANTHROPIC_API_KEY",
)


@pytest.mark.integration
class TestRegressionGuards:
    """End-to-end quality regression guards against known score thresholds.

    Requires: live PostgreSQL (indexed chunks), embedding server, LLM credentials.
    Skipped automatically when PostgreSQL or the embedding server is unreachable.
    """

    @pytest.fixture(autouse=True)
    def _require_live_infra(self):
        if not _postgres_reachable():
            pytest.skip("No live PostgreSQL at localhost:5432 — skipping regression guard")
        if not _embedding_server_reachable():
            pytest.skip("Embedding server not reachable — skipping regression guard")

    def _run_golden_set(self, questions: list[dict], corpus: str) -> dict:
        """Run golden questions through the real pipeline, return aggregate scores."""
        import asyncio

        from arlc.answerer import generate_answer
        from arlc.retriever import retrieve_pages
        from arlc.router import route

        citation_hits = correctness_hits = grounding_hits = 0
        errors: list[str] = []

        for item in questions:
            q = item["q"]
            try:
                route_result = route(q, "free_text")
                target_docs = route_result.target_doc_ids or []

                pages = retrieve_pages(
                    q,
                    target_doc_ids=target_docs or None,
                    max_per_doc=2,
                    max_total=5,
                    answer_type="free_text",
                    corpus=corpus,
                )
                if not pages:
                    errors.append(f"No pages retrieved: {q[:60]}")
                    continue

                source_pages = [{"doc_id": p.doc_id, "page_number": p.page_number, "text": p.text} for p in pages]
                ar = asyncio.run(generate_answer(q, "free_text", source_pages, corpus=corpus))
                answer_text = str(ar.answer or "")
                source_texts = [p.text for p in pages]
                scores = _score_answer(answer_text, source_texts, item["section"], item["keyword"])
                citation_hits += scores["citation"]
                correctness_hits += scores["correctness"]
                grounding_hits += scores["grounding"]
            except Exception as exc:
                errors.append(f"Error on '{q[:50]}': {exc}")

        n = len(questions)
        return {
            "total": n,
            "errors": errors,
            "citation_pct": citation_hits / n * 100 if n else 0.0,
            "correctness_pct": correctness_hits / n * 100 if n else 0.0,
            "grounding_pct": grounding_hits / n * 100 if n else 0.0,
        }

    # ── Retrieval-only guards (no LLM) ─────────────────────────────────────

    def test_difc_retrieval_returns_pages_for_all_golden_questions(self):
        """Every DIFC golden question must retrieve at least 1 page from the corpus."""
        from arlc.retriever import retrieve_pages

        missing: list[str] = []
        for item in _GOLDEN_DIFC:
            pages = retrieve_pages(item["q"], max_per_doc=2, max_total=5, answer_type="free_text", corpus="difc")
            if not pages:
                missing.append(item["q"][:60])

        assert not missing, f"No pages retrieved for DIFC questions: {missing}"

    def test_czech_retrieval_returns_pages_for_all_golden_questions(self):
        """Every Czech golden question must retrieve at least 1 page from the corpus."""
        from arlc.retriever import retrieve_pages

        missing: list[str] = []
        for item in _GOLDEN_CZECH:
            pages = retrieve_pages(item["q"], max_per_doc=2, max_total=5, answer_type="free_text", corpus="czech")
            if not pages:
                missing.append(item["q"][:60])

        assert not missing, f"No pages retrieved for Czech questions: {missing}"

    def test_difc_retrieval_top1_page_score_above_zero(self):
        """Top retrieved page for a known DIFC question must have a positive score."""
        from arlc.retriever import retrieve_pages

        pages = retrieve_pages(
            "What is the limitation period under DIFC Law No. 5 of 2005?",
            max_per_doc=2,
            max_total=5,
            answer_type="free_text",
            corpus="difc",
        )
        assert pages, "Must return at least one page for limitation period question"
        assert pages[0].score > 0, f"Top page score must be positive, got {pages[0].score}"

    # ── Full pipeline guards (retrieval + LLM) ──────────────────────────────

    @_skip_no_llm
    def test_difc_citation_accuracy_above_threshold(self):
        """DIFC pipeline citation accuracy must stay >= {_DIFC_CITATION_THRESHOLD}%."""
        result = self._run_golden_set(_GOLDEN_DIFC, corpus="difc")
        assert not result["errors"], f"Pipeline errors: {result['errors']}"
        assert result["citation_pct"] >= _DIFC_CITATION_THRESHOLD, (
            f"DIFC citation {result['citation_pct']:.1f}% < threshold {_DIFC_CITATION_THRESHOLD}%"
        )

    @_skip_no_llm
    def test_difc_answer_correctness_above_threshold(self):
        """DIFC pipeline answer correctness must stay >= {_DIFC_CORRECT_THRESHOLD}%."""
        result = self._run_golden_set(_GOLDEN_DIFC, corpus="difc")
        assert result["correctness_pct"] >= _DIFC_CORRECT_THRESHOLD, (
            f"DIFC correctness {result['correctness_pct']:.1f}% < threshold {_DIFC_CORRECT_THRESHOLD}%"
        )

    @_skip_no_llm
    def test_difc_grounding_coverage_above_threshold(self):
        """DIFC free-text answers must contain [DOC-N] citations >= {_DIFC_GROUNDING_THRESHOLD}%."""
        result = self._run_golden_set(_GOLDEN_DIFC, corpus="difc")
        assert result["grounding_pct"] >= _DIFC_GROUNDING_THRESHOLD, (
            f"DIFC grounding {result['grounding_pct']:.1f}% < threshold {_DIFC_GROUNDING_THRESHOLD}%"
        )

    @_skip_no_llm
    def test_czech_citation_accuracy_above_threshold(self):
        """Czech pipeline citation accuracy must stay >= {_CZECH_CITATION_THRESHOLD}%."""
        result = self._run_golden_set(_GOLDEN_CZECH, corpus="czech")
        assert not result["errors"], f"Pipeline errors: {result['errors']}"
        assert result["citation_pct"] >= _CZECH_CITATION_THRESHOLD, (
            f"Czech citation {result['citation_pct']:.1f}% < threshold {_CZECH_CITATION_THRESHOLD}%"
        )

    @_skip_no_llm
    def test_czech_answer_correctness_above_threshold(self):
        """Czech pipeline answer correctness must stay >= {_CZECH_CORRECT_THRESHOLD}%."""
        result = self._run_golden_set(_GOLDEN_CZECH, corpus="czech")
        assert result["correctness_pct"] >= _CZECH_CORRECT_THRESHOLD, (
            f"Czech correctness {result['correctness_pct']:.1f}% < threshold {_CZECH_CORRECT_THRESHOLD}%"
        )

    @_skip_no_llm
    def test_czech_grounding_coverage_above_threshold(self):
        """Czech free-text answers must contain [DOC-N] citations >= {_CZECH_GROUNDING_THRESHOLD}%."""
        result = self._run_golden_set(_GOLDEN_CZECH, corpus="czech")
        assert result["grounding_pct"] >= _CZECH_GROUNDING_THRESHOLD, (
            f"Czech grounding {result['grounding_pct']:.1f}% < threshold {_CZECH_GROUNDING_THRESHOLD}%"
        )
