"""Retrieve relevant document chunks for a question using hybrid search."""

import functools
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import anthropic
import numpy as np
import pymupdf
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session as SASession

from arlc.czech_morphology import build_czech_tsquery

# CrossEncoder is used only when RERANKER_MODEL is not a Qwen model (non-default).
# Imported lazily inside its factory function so that the default Qwen3-Reranker
# path has no hard sentence_transformers dependency.

load_dotenv()

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5"  # short ID required for direct Vertex AI (no date suffix)
# Langfuse span payload cap — avoids oversized ingest requests
_LANGFUSE_INPUT_TRUNCATE = 500

# Anthropic client (lazy singleton for HyDE / query variants)
_anthropic_client: anthropic.Anthropic | None = None


def _get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=30.0,
        )
    return _anthropic_client


DOCUMENTS_DIR = "data/documents"
# Reranker model. Default: Qwen3-Reranker-0.6B (instruction-aware, ~2GB VRAM).
# Fallback: BAAI/bge-reranker-v2-m3 (general-purpose, no instruction support).
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "Qwen/Qwen3-Reranker-0.6B")
# Instruction passed to Qwen3-Reranker. Kept intentionally general so it works
# for any customer's legal documents — not domain- or jurisdiction-specific.
RERANKER_INSTRUCTION = os.environ.get(
    "RERANKER_INSTRUCTION",
    "Given a legal question, retrieve the most relevant passage that directly answers it.",
)

# Per-answer-type reranker instructions for Qwen3-Reranker (instruction-aware model).
# Different retrieval objectives per type: factual extraction vs semantic reasoning.
# Falls back to RERANKER_INSTRUCTION for unknown/empty answer types.
RERANKER_INSTRUCTIONS_BY_TYPE: dict[str, str] = {
    "boolean": (
        "Given a yes/no legal question, retrieve the passage that explicitly "
        "states the rule, provision, or prohibition being asked about."
    ),
    "number": (
        "Given a question asking for a numeric value, retrieve the passage "
        "containing the exact number, amount, threshold, or percentage."
    ),
    "date": (
        "Given a question asking for a date or time reference, retrieve the "
        "passage containing the exact date, deadline, or time period."
    ),
    "name": (
        "Given a question asking for a person's name or case identifier, "
        "retrieve the passage where that name or case number explicitly appears."
    ),
    "names": (
        "Given a question asking for multiple names or parties, retrieve the "
        "passage listing all relevant parties, judges, or named individuals."
    ),
    "free_text": (
        "Given a legal question requiring detailed explanation, retrieve the passage "
        "containing the relevant legal provisions, articles, or case holdings that "
        "directly address the question."
    ),
}

# Embedding backend: llama-server (Qwen3-Embedding-8B Q4_K_M via llama.cpp).
# Requires llama-server running on LLAMA_SERVER_URL (default http://localhost:8088).
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "llama-server")

# doc_id -> page where date_of_issue appears (from case_metadata_index.json).
# Judge/claimant/defendant are always page 1 — only dates need a targeted lookup.
# Loaded once at module import (cheap: single JSON read, no ML).
_DOC_DATE_PAGES: dict[str, int] = {}


def _load_doc_date_pages() -> None:
    """Populate _DOC_DATE_PAGES from case_metadata_index.json."""
    global _DOC_DATE_PAGES
    meta_path = os.path.join(os.path.dirname(__file__), "..", "data", "case_metadata_index.json")
    if not os.path.exists(meta_path):
        return
    try:
        with open(meta_path) as f:
            case_meta = json.load(f)
        result: dict[str, int] = {}
        for info in case_meta.values():
            for doc_entry in info.get("docs", []):
                doc_id = doc_entry.get("doc_id", "")
                doi = doc_entry.get("metadata", {}).get("date_of_issue", {})
                if doc_id and doi and "page" in doi:
                    result[doc_id] = int(doi["page"])
        _DOC_DATE_PAGES = result
    except Exception as e:
        logger.warning("[retriever] Warning: could not load date pages: %s", e)


_load_doc_date_pages()

# Module-level caches
_doc_index = None  # pdf_id -> full text (for keyword matching)
_chunks_by_doc = None  # pdf_id -> list[dict] (for fast page retrieval)
_reranker = None  # primary (remote if available, else local)
_local_reranker = None  # always local PyTorch — used as fallback when remote fails mid-query
_embedding_model = None
_sync_engine = None  # Sync SQLAlchemy engine for PostgreSQL (retriever runs in threads)
_sync_engine_lock = threading.Lock()

# Multi-corpus chunk caches: corpus_name -> (doc_index, chunks_by_doc)
_corpus_chunk_cache: dict[str, tuple] = {}

# Locks for thread-safe lazy initialization
_reranker_lock = threading.Lock()
_embedding_lock = threading.Lock()
_doc_index_lock = threading.Lock()


@dataclass
class PageResult:
    """A single page retrieved for answering a question."""

    doc_id: str
    page_number: int
    score: float
    text: str
    chunk_id: str = ""
    # Court decision metadata — populated only when source_type == "court_decision"
    source_type: str | None = None  # "statute" | "court_decision" | "txt"
    case_number: str | None = None  # e.g. "21 Cdo 1234/2023"
    ecli: str | None = None  # ECLI identifier
    decision_date: str | None = None  # ISO date string e.g. "2023-06-15"
    court: str | None = None  # e.g. "Nejvyssi soud"
    category: str | None = None  # A–E
    legal_thesis: str | None = None  # Pravni veta
    # TXT-source line range — populated only when source_type == "txt"
    start_line: int | None = None
    end_line: int | None = None


def _is_qwen_reranker() -> bool:
    return "qwen" in RERANKER_MODEL.lower()


def _format_reranker_pairs(
    pairs: list[tuple[str, str]],
    instruction: str = "",
) -> list[tuple[str, str]]:
    """Prepend instruction to query for Qwen3-Reranker; passthrough for others.

    instruction: when non-empty, overrides the module-level RERANKER_INSTRUCTION.
                 Pass per-answer-type instructions from RERANKER_INSTRUCTIONS_BY_TYPE
                 to improve ranking precision for factual vs semantic questions.
    """
    if not _is_qwen_reranker():
        return pairs
    effective = instruction or RERANKER_INSTRUCTION
    prefix = f"Instruct: {effective}\nQuery: "
    return [(prefix + q, doc) for q, doc in pairs]


def _init_local_reranker():
    """Create the local llama-server reranker (cached).

    Uses llama-server on port 8089 exclusively — no PyTorch fallback.
    llama-server with Metal is ~20x faster than PyTorch MPS.
    If llama-server is unavailable, reranking is skipped (unranked results).
    """
    global _local_reranker
    if _local_reranker is not None:
        return _local_reranker

    local_reranker_url = os.environ.get("RERANKER_LOCAL_URL", "http://localhost:8089")
    from arlc.qwen3_reranker import LlamaServerReranker

    _local_reranker = LlamaServerReranker(url=local_reranker_url)
    logger.info("Using local llama-server reranker at %s", local_reranker_url)
    return _local_reranker


def get_reranker():
    """Get primary reranker (cached, thread-safe).

    Failover chain:
    1. Remote llama-server (RERANKER_SERVER_URL, CUDA on RTX 3070) — ~1.7s for 108 docs
    2. Local llama-server (RERANKER_LOCAL_URL, Metal) — ~2.1s for 40 docs
    """
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                _init_local_reranker()

                remote_url = os.environ.get("RERANKER_SERVER_URL", "")
                if remote_url:
                    try:
                        from arlc.qwen3_reranker import LlamaServerReranker

                        _reranker = LlamaServerReranker(url=remote_url)
                        logger.info("Using remote reranker at %s (local ready as fallback)", remote_url)
                        return _reranker
                    except Exception as e:
                        logger.warning("Remote reranker at %s unavailable (%s), using local", remote_url, e)

                _reranker = _local_reranker
    return _reranker


def _demote_remote_reranker():
    """Circuit breaker: swap primary reranker to local after remote failure.

    Called when the remote reranker fails mid-query. Prevents subsequent
    calls from waiting for TCP timeouts on an unreachable host.
    Uses _reranker_lock to avoid racing with get_reranker() initialization.
    """
    global _reranker
    with _reranker_lock:
        if _local_reranker is not None and _reranker is not _local_reranker:
            logger.warning("Circuit breaker: demoting remote reranker to local for remaining queries")
            _reranker = _local_reranker


def get_local_reranker():
    """Get the local reranker (for mid-query fallback when remote fails)."""
    if _local_reranker is not None:
        return _local_reranker
    with _reranker_lock:
        return _init_local_reranker()


def rerank_chunks(
    question: str,
    chunks: list[dict],
    top_k: int = 15,
    answer_type: str = "",
    on_status=None,
) -> list[dict]:
    """Rerank chunks by relevance to question using cross-encoder. Returns top_k.

    answer_type: when provided, selects a per-type instruction from
                 RERANKER_INSTRUCTIONS_BY_TYPE (date/number/name get exact-match
                 instructions; free_text gets a semantic-relevance instruction).

    Failover chain: primary reranker (remote CUDA if available) → local PyTorch → unranked.
    If remote 3070 goes offline mid-query, falls back to local instantly.
    """
    if len(chunks) <= top_k:
        return chunks

    RERANK_TIMEOUT = 180  # seconds — MPS is slow (~50s/batch for Qwen3-0.6B)
    instruction = RERANKER_INSTRUCTIONS_BY_TYPE.get(answer_type, RERANKER_INSTRUCTION)
    pairs = _format_reranker_pairs([(question, chunk["text"][:1500]) for chunk in chunks], instruction=instruction)

    def _progress(done, total):
        if on_status:
            on_status(f"retrieving:reranking passages ({done}/{total})")

    def _apply_scores(chunk_list: list[dict], score_list) -> list[dict]:
        """Annotate chunks with ``rerank_score`` and return sorted top-k."""
        indexed = sorted(enumerate(score_list), key=lambda x: x[1], reverse=True)
        result = []
        for i, score in indexed[:top_k]:
            c = dict(chunk_list[i])  # shallow copy to avoid mutating the original
            c["rerank_score"] = float(score)
            result.append(c)
        return result

    # Try primary reranker (remote if configured, else local)
    ranker = get_reranker()
    try:
        scores = ranker.predict(pairs, on_progress=_progress, timeout=RERANK_TIMEOUT)
        return _apply_scores(chunks, scores)
    except Exception as e:
        # If primary was remote, try local as fallback + circuit-break for remaining calls
        local = get_local_reranker()
        if local is not ranker:
            _demote_remote_reranker()
            logger.warning("Primary reranker failed (%s), falling back to local", e)
            if on_status:
                on_status("retrieving:reranking passages")
            try:
                scores = local.predict(pairs, on_progress=_progress, timeout=RERANK_TIMEOUT)
                return _apply_scores(chunks, scores)
            except Exception as e2:
                logger.warning("Local reranker also failed (%s), using vector-distance ordering", e2)

        else:
            logger.warning("Reranking failed (%s), using vector-distance ordering", e)

        if on_status:
            on_status("retrieving:scoring results")
        return chunks[:top_k]


def get_embedding_model():
    """Get LlamaServerEmbedder instance (cached, thread-safe)."""
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                from neolex.embeddings.llama_embedder import LlamaServerEmbedder

                _embedding_model = LlamaServerEmbedder()
    return _embedding_model


def embed_query(question: str) -> list[float]:
    """Embed a query for asymmetric retrieval (applies instruction prefix via llama-server).

    LlamaServerEmbedder.encode(prompt_name='query') adds the Qwen3 instruction prefix.
    LlamaServerEmbedder is a stateless HTTP client — safe to call concurrently.
    """
    model = get_embedding_model()
    embedding = model.encode(question, prompt_name="query", normalize_embeddings=True)
    return embedding.tolist()


def embed_document(text: str) -> list[float]:
    """Embed a document/passage for asymmetric retrieval (no instruction prefix).

    Qwen3 is asymmetric: queries get an instruction prefix, documents don't.
    Use this for indexing court decisions, statute chunks, etc.
    Use embed_query() for search queries.
    """
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def _get_sync_engine():
    """Lazy singleton for sync PostgreSQL engine (retriever runs in threads)."""
    global _sync_engine
    if _sync_engine is None:
        with _sync_engine_lock:
            if _sync_engine is None:
                url = os.environ.get("DATABASE_URL", "")
                if "+asyncpg" in url:
                    url = url.replace("+asyncpg", "")
                _sync_engine = create_engine(url, pool_size=10, max_overflow=15, pool_pre_ping=True)
    return _sync_engine


# ---------------------------------------------------------------------------
# PostgreSQL-backed search functions (pgvector + tsvector)
# ---------------------------------------------------------------------------


def _apply_metadata_extra(meta: dict, metadata_extra: dict | None) -> None:
    """Populate *meta* with fields stored in the metadata_extra JSONB column.

    Handles fields written by build_index():
    - entities   : pipe-separated entity string
    - chunk_type : optional structural label
    - source_type: "pdf" | "txt" | "court_decision" (citation rendering hint)
    - start_line : 1-based start line for TXT chunks
    - end_line   : 1-based end line for TXT chunks

    Mutates *meta* in-place; safe to call with metadata_extra=None.
    """
    if not metadata_extra:
        return
    if metadata_extra.get("entities"):
        meta["entities"] = metadata_extra["entities"]
    if metadata_extra.get("chunk_type"):
        meta["chunk_type"] = metadata_extra["chunk_type"]
    if metadata_extra.get("source_type"):
        meta["source_type"] = metadata_extra["source_type"]
    if metadata_extra.get("start_line") is not None:
        meta["start_line"] = metadata_extra["start_line"]
    if metadata_extra.get("end_line") is not None:
        meta["end_line"] = metadata_extra["end_line"]


def search_chunks_vector(
    query_embedding: list[float],
    top_k: int = 50,
    corpus: str = "difc",
    doc_ids: list[str] | None = None,
) -> dict:
    """Search chunks via pgvector inner product, returning legacy-compatible format.

    Returns dict with keys: ids, documents, metadatas, distances
    Each is a list-of-lists (matching legacy batch format).

    Parameters
    ----------
    doc_ids : list[str] | None
        If provided, restrict search to chunks from these specific documents.
        Used when the user selects individual uploaded documents instead of "All".
    """
    engine = _get_sync_engine()
    query_np = np.array(query_embedding, dtype=np.float32)
    norm = np.linalg.norm(query_np)
    if norm > 0:
        query_np = query_np / norm

    vec_literal = "[" + ",".join(str(float(x)) for x in query_np) + "]"

    # Build WHERE clause — optionally filter by specific doc_ids
    where_clause = "WHERE corpus = :corpus"
    params: dict = {"vec": vec_literal, "corpus": corpus, "top_k": top_k}
    if doc_ids:
        where_clause += " AND doc_id = ANY(:doc_ids)"
        params["doc_ids"] = doc_ids

    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT chunk_id, doc_id, pdf_id, page, source_file, text,
                   metadata_extra, (embedding <#> cast(:vec as vector)) AS neg_ip
            FROM chunks
            {where_clause}
            ORDER BY embedding <#> cast(:vec as vector)
            LIMIT :top_k
        """),
            params,
        ).fetchall()

    ids, documents, metadatas, distances = [], [], [], []
    for row in rows:
        ids.append(row.chunk_id)
        documents.append(row.text)
        meta = {
            "doc_id": row.doc_id,
            "pdf_id": row.pdf_id,
            "page": row.page,
            "source_file": row.source_file,
            "chunk_id": row.chunk_id,
        }
        _apply_metadata_extra(meta, row.metadata_extra)
        metadatas.append(meta)
        # neg_ip is negative inner product; convert to cosine distance for compat
        distances.append(1.0 + float(row.neg_ip))

    return {"ids": [ids], "documents": [documents], "metadatas": [metadatas], "distances": [distances]}


# Corpora that require morphological query expansion for BM25 (highly inflected languages).
_MORPHOLOGICAL_CORPORA: frozenset[str] = frozenset({"czech"})

# RRF signal weights used across retrieval paths.
# Vector search gets 0.7 (embedding models handle semantic similarity well),
# BM25 gets 0.3 (keyword match for exact legal terms / section numbers),
# court decisions enter at 0.5 (pre-fused internally from two legs).
_RRF_VEC_WEIGHT: float = 0.7


def _tsquery(query: str, _corpus: str, **extra) -> tuple[str, dict]:
    """Return ``(sql_fn_fragment, bound_params)`` for a tsvector BM25 query.

    For Czech corpora, attempts morphological prefix expansion via
    ``build_czech_tsquery``.  If no valid terms survive (empty query,
    punctuation-only input, or all tokens filtered), falls back to
    ``plainto_tsquery`` so callers never pass an invalid string to
    ``to_tsquery`` — which raises a PostgreSQL syntax error on empty input.

    For all other corpora, ``plainto_tsquery`` is always used (natural-language
    tokenisation, safe for arbitrary input).

    ``_corpus`` is a private positional-only param used for routing logic.
    Callers pass ``corpus=corpus`` in ``**extra`` so it flows through to the
    SQL bound parameters dict (``WHERE corpus = :corpus``).
    """
    if _corpus in _MORPHOLOGICAL_CORPORA:
        tsq = build_czech_tsquery(query)
        if tsq is not None:
            return "to_tsquery('simple', :tsq)", {"tsq": tsq, **extra}
    return "plainto_tsquery('simple', :query)", {"query": query, **extra}


def search_chunks_text(query: str, top_k: int = 200, corpus: str = "difc") -> list[str]:
    """Search chunks via tsvector full-text search, returning ranked chunk_ids."""
    tsfn, tsparams = _tsquery(query, corpus, corpus=corpus, top_k=top_k)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT chunk_id, ts_rank(text_search, {tsfn}) AS rank
            FROM chunks
            WHERE corpus = :corpus AND text_search @@ {tsfn}
            ORDER BY rank DESC
            LIMIT :top_k
        """),
            tsparams,
        ).fetchall()
    return [row.chunk_id for row in rows]


def search_chunks_text_page1(query: str, top_k: int = 200, corpus: str = "difc") -> list[str]:
    """Text search over page-1 chunks only (document identification signal)."""
    tsfn, tsparams = _tsquery(query, corpus, corpus=corpus, top_k=top_k)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT chunk_id, ts_rank(text_search, {tsfn}) AS rank
            FROM chunks
            WHERE corpus = :corpus AND page = 1 AND text_search @@ {tsfn}
            ORDER BY rank DESC
            LIMIT :top_k
        """),
            tsparams,
        ).fetchall()
    return [row.chunk_id for row in rows]


def search_docs_text(query: str, top_k: int = 200, corpus: str = "difc") -> list[str]:
    """Text search aggregated to document level (sum of chunk ranks per doc)."""
    tsfn, tsparams = _tsquery(query, corpus, corpus=corpus, top_k=top_k)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT pdf_id, SUM(ts_rank(text_search, {tsfn})) AS total_rank
            FROM chunks
            WHERE corpus = :corpus AND text_search @@ {tsfn}
            GROUP BY pdf_id
            ORDER BY total_rank DESC
            LIMIT :top_k
        """),
            tsparams,
        ).fetchall()
    return [row.pdf_id for row in rows]


def _search_chunks_text_scored(query: str, top_k: int = 200, corpus: str = "difc") -> list[tuple[str, str, float]]:
    """Text search returning (chunk_id, pdf_id, rank_score) tuples for fusion scoring."""
    tsfn, tsparams = _tsquery(query, corpus, corpus=corpus, top_k=top_k)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT chunk_id, pdf_id, ts_rank(text_search, {tsfn}) AS rank
            FROM chunks
            WHERE corpus = :corpus AND text_search @@ {tsfn}
            ORDER BY rank DESC
            LIMIT :top_k
        """),
            tsparams,
        ).fetchall()
    return [(row.chunk_id, row.pdf_id, float(row.rank)) for row in rows]


def _search_chunks_text_page1_scored(
    query: str,
    top_k: int = 200,
    corpus: str = "difc",
) -> list[tuple[str, str, float]]:
    """Page-1 text search returning (chunk_id, pdf_id, rank_score) tuples for fusion scoring."""
    tsfn, tsparams = _tsquery(query, corpus, corpus=corpus, top_k=top_k)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT chunk_id, pdf_id, ts_rank(text_search, {tsfn}) AS rank
            FROM chunks
            WHERE corpus = :corpus AND page = 1 AND text_search @@ {tsfn}
            ORDER BY rank DESC
            LIMIT :top_k
        """),
            tsparams,
        ).fetchall()
    return [(row.chunk_id, row.pdf_id, float(row.rank)) for row in rows]


def _search_docs_text_scored(query: str, top_k: int = 200, corpus: str = "difc") -> list[tuple[str, float]]:
    """Doc-level text search returning (pdf_id, total_rank) tuples for fusion scoring."""
    tsfn, tsparams = _tsquery(query, corpus, corpus=corpus, top_k=top_k)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT pdf_id, SUM(ts_rank(text_search, {tsfn})) AS total_rank
            FROM chunks
            WHERE corpus = :corpus AND text_search @@ {tsfn}
            GROUP BY pdf_id
            ORDER BY total_rank DESC
            LIMIT :top_k
        """),
            tsparams,
        ).fetchall()
    return [(row.pdf_id, float(row.total_rank)) for row in rows]


def _search_chunks_text_for_doc(query: str, pdf_id: str, corpus: str = "difc", top_k: int = 50) -> list[str]:
    """Text search within a specific document, returning chunk_ids."""
    tsfn, tsparams = _tsquery(query, corpus, corpus=corpus, pdf_id=pdf_id, top_k=top_k)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text(f"""
            SELECT chunk_id, ts_rank(text_search, {tsfn}) AS rank
            FROM chunks
            WHERE corpus = :corpus AND pdf_id = :pdf_id
              AND text_search @@ {tsfn}
            ORDER BY rank DESC
            LIMIT :top_k
        """),
            tsparams,
        ).fetchall()
    return [row.chunk_id for row in rows]


# Common English stop words to strip from queries before OR-mode text search.
_TEXT_SEARCH_STOP_WORDS = frozenset(
    {
        "what",
        "are",
        "the",
        "for",
        "under",
        "which",
        "how",
        "does",
        "do",
        "is",
        "of",
        "in",
        "a",
        "an",
        "that",
        "this",
        "these",
        "those",
        "was",
        "were",
        "has",
        "have",
        "had",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "be",
        "by",
        "at",
        "as",
        "it",
        "its",
        "with",
        "from",
        "to",
        "on",
        "or",
        "and",
        "not",
        "but",
        "if",
        "then",
        "when",
        "where",
        "who",
        "whom",
        "all",
        "any",
        "each",
        "such",
        "no",
        "both",
        "either",
        "neither",
    }
)

# Additional stop words for WITHIN-document OR-mode text search only.
# These terms appear in most chunks of a statute document (e.g. the law's own
# name, jurisdiction, or structural boilerplate) and provide no discriminating
# signal when searching within a single document.  Kept separate so they still
# contribute to cross-document searches elsewhere.
_WITHIN_DOC_STOP_WORDS = _TEXT_SEARCH_STOP_WORDS | frozenset(
    {
        # Jurisdiction / corpus identifiers that appear in every chunk header
        "difc",
        "czech",
        "english",
        "australian",
        "federal",
        "dubai",
        # Generic legal/document terms ubiquitous in statute bodies
        "law",
        "act",
        "regulation",
        "regulations",
        "legal",
        "pursuant",
        "accordance",
        "applicable",
        "provisions",
        "provision",
        # High-frequency substantive words in employment/commercial statutes
        "employment",
        "employee",
        "employer",
        "company",
        "contract",
        "court",
        "tribunal",
        "proceedings",
    }
)


def _extract_search_terms(
    query: str,
    min_len: int = 3,
    max_terms: int = 6,
    stop_words: frozenset[str] | None = None,
) -> list[str]:
    """Extract key non-stop-word terms from a query for OR-mode text search.

    Returns the first ``max_terms`` unique lowercased tokens that are not in
    ``stop_words`` (defaults to ``_TEXT_SEARCH_STOP_WORDS``) and meet the
    minimum length requirement.
    """
    sw = stop_words if stop_words is not None else _TEXT_SEARCH_STOP_WORDS
    tokens = re.findall(r"\b[a-zA-Z]+\b", query.lower())
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t not in sw and len(t) >= min_len and t not in seen:
            seen.add(t)
            result.append(t)
            if len(result) >= max_terms:
                break
    return result


def _search_chunks_text_for_doc_or(query: str, pdf_id: str, corpus: str = "difc", top_k: int = 10) -> list[str]:
    """OR-mode text search within a document — returns chunk_ids ranked by relevance.

    Unlike ``_search_chunks_text_for_doc`` (AND mode), this function extracts
    key terms from the query and uses OR semantics so that pages containing ANY
    relevant term are found.  Uses ``_WITHIN_DOC_STOP_WORDS`` which strips
    terms that are ubiquitous inside a single statute (law name, jurisdiction,
    structural boilerplate) — these add noise within a document even though
    they are useful discriminators for cross-document search.
    """
    terms = _extract_search_terms(query, stop_words=_WITHIN_DOC_STOP_WORDS)
    if not terms:
        return []
    or_tsq = " | ".join(terms)
    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text("""
            SELECT chunk_id,
                   ts_rank(text_search, to_tsquery('simple', :tsq)) AS rank
            FROM chunks
            WHERE corpus = :corpus
              AND pdf_id = :pdf_id
              AND text_search @@ to_tsquery('simple', :tsq)
            ORDER BY rank DESC
            LIMIT :top_k
            """),
            {"tsq": or_tsq, "corpus": corpus, "pdf_id": pdf_id, "top_k": top_k},
        ).fetchall()
    return [row.chunk_id for row in rows]


def get_chunk_count(corpus: str = "difc") -> int:
    """Return total number of chunks in PostgreSQL for a corpus."""
    engine = _get_sync_engine()
    with SASession(engine) as session:
        result = session.execute(
            sa_text("SELECT count(*) FROM chunks WHERE corpus = :corpus"),
            {"corpus": corpus},
        ).scalar()
    return result or 0


# Corpora for which court decisions are included in retrieval results.
# Czech court decisions (Nejvyssi soud judikatura) are stored in a separate
# `court_decisions` table and must be merged with statute chunk results.
_COURT_DECISION_CORPORA: frozenset[str] = frozenset({"czech"})


def _search_court_decisions_sync(
    query: str,
    query_embedding: list[float],
    limit: int = 30,
) -> list[dict]:
    """Sync hybrid BM25 + vector search on the court_decisions table.

    Runs two legs concurrently using a ThreadPoolExecutor, then fuses with RRF
    (vector weight 0.7, BM25 weight 0.3 — matching statute chunk weights).

    Uses the same sync SQLAlchemy engine as the rest of the retriever so no
    additional connection pool is needed.

    Returns a list of chunk-like dicts compatible with the fusion pool in
    ``_retrieve_pages_simple``::

        {
            "chunk_id": ecli,          # ECLI as unique ID
            "text": legal_thesis,      # text used for embedding + reranking
            "metadata": {
                "doc_id": ecli,
                "pdf_id": ecli,
                "page": 1,             # court decisions have no page structure
                "source_file": case_number,
                "source_type": "court_decision",
                "case_number": ...,
                "ecli": ...,
                "decision_date": ...,  # ISO date string or None
                "court": ...,
                "category": ...,
                "legal_thesis": ...,
            },
            "distance": 1.0,           # placeholder; RRF score is used for ranking
        }

    Decisions without legal_thesis (required for meaningful results) are excluded
    from both legs. Decisions without embeddings are excluded from the vector leg
    but remain searchable via BM25.
    """
    engine = _get_sync_engine()

    # Normalise embedding for inner-product search (pgvector needs L2-normalised vectors)
    query_np = np.array(query_embedding, dtype=np.float32)
    norm = np.linalg.norm(query_np)
    if norm > 0:
        query_np = query_np / norm
    vec_literal = "[" + ",".join(str(float(x)) for x in query_np) + "]"

    def _vector_leg() -> list:
        with SASession(engine) as session:
            return session.execute(
                sa_text("""
                SELECT ecli, case_number, court, category, legal_thesis, decision_date
                FROM court_decisions
                WHERE embedding IS NOT NULL
                  AND legal_thesis IS NOT NULL
                  AND legal_thesis != ''
                ORDER BY embedding <#> cast(:vec as vector)
                LIMIT :limit
                """),
                {"vec": vec_literal, "limit": limit},
            ).fetchall()

    def _bm25_leg() -> list:
        if not query or not query.strip():
            return []
        tsq = build_czech_tsquery(query)
        if not tsq:
            return []
        with SASession(engine) as session:
            return session.execute(
                sa_text("""
                SELECT ecli, case_number, court, category, legal_thesis, decision_date
                FROM court_decisions
                WHERE search_vector @@ to_tsquery('simple', :tsq)
                  AND legal_thesis IS NOT NULL
                  AND legal_thesis != ''
                ORDER BY ts_rank(search_vector, to_tsquery('simple', :tsq)) DESC
                LIMIT :limit
                """),
                {"tsq": tsq, "limit": limit},
            ).fetchall()

    with ThreadPoolExecutor(max_workers=2) as executor:
        vec_fut = executor.submit(_vector_leg)
        bm25_fut = executor.submit(_bm25_leg)
        vec_rows = vec_fut.result()
        bm25_rows = bm25_fut.result()

    # RRF fusion: vector weight 0.7, BM25 weight 0.3
    _rrf_k = 60
    rrf_scores: dict[str, float] = {}
    row_by_ecli: dict[str, object] = {}

    for rank, row in enumerate(vec_rows):
        rrf_scores[row.ecli] = rrf_scores.get(row.ecli, 0.0) + _RRF_VEC_WEIGHT / (_rrf_k + rank + 1)
        row_by_ecli.setdefault(row.ecli, row)

    for rank, row in enumerate(bm25_rows):
        rrf_scores[row.ecli] = rrf_scores.get(row.ecli, 0.0) + 0.3 / (_rrf_k + rank + 1)
        row_by_ecli.setdefault(row.ecli, row)

    sorted_eclis = sorted(rrf_scores, key=lambda e: rrf_scores[e], reverse=True)[:limit]

    results = []
    for ecli in sorted_eclis:
        row = row_by_ecli[ecli]
        decision_date_str = str(row.decision_date) if row.decision_date else None
        results.append(
            {
                "chunk_id": ecli,
                "text": row.legal_thesis or "",
                "metadata": {
                    "doc_id": ecli,
                    "pdf_id": ecli,
                    "page": 1,
                    "source_file": row.case_number or ecli,
                    "source_type": "court_decision",
                    "case_number": row.case_number,
                    "ecli": ecli,
                    "decision_date": decision_date_str,
                    "court": row.court,
                    "category": row.category,
                    "legal_thesis": row.legal_thesis,
                },
                "distance": 1.0,
            }
        )
    return results


def get_chunks_by_ids(chunk_ids: list[str], corpus: str | None = None) -> dict:
    """Get specific chunks by ID from PostgreSQL."""
    if not chunk_ids:
        return {"ids": [], "documents": [], "metadatas": []}
    engine = _get_sync_engine()
    sql = "SELECT chunk_id, doc_id, pdf_id, page, source_file, text, metadata_extra FROM chunks WHERE chunk_id = ANY(:ids)"
    params: dict = {"ids": chunk_ids}
    if corpus:
        sql += " AND corpus = :corpus"
        params["corpus"] = corpus
    with SASession(engine) as session:
        rows = session.execute(sa_text(sql), params).fetchall()

    ids, documents, metadatas = [], [], []
    for row in rows:
        ids.append(row.chunk_id)
        documents.append(row.text)
        meta = {"doc_id": row.doc_id, "pdf_id": row.pdf_id, "page": row.page, "source_file": row.source_file}
        _apply_metadata_extra(meta, row.metadata_extra)
        metadatas.append(meta)
    return {"ids": ids, "documents": documents, "metadatas": metadatas}


# ---------------------------------------------------------------------------
# In-memory chunk caches (populated from PostgreSQL on first access)
# ---------------------------------------------------------------------------


def _load_all_chunks(corpus: str = "difc"):
    """Load all chunks from PostgreSQL into memory. Builds both indexes simultaneously."""
    global _doc_index, _chunks_by_doc, _corpus_chunk_cache

    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text("""
            SELECT chunk_id, doc_id, pdf_id, page, source_file, text, metadata_extra
            FROM chunks
            WHERE corpus = :corpus
            ORDER BY pdf_id, page
        """),
            {"corpus": corpus},
        ).fetchall()

    doc_text_index: dict[str, str] = {}
    chunks_by_doc: dict[str, list[dict]] = {}
    for row in rows:
        pdf_id = row.pdf_id
        meta: dict = {
            "doc_id": row.doc_id,  # canonical UUID (may differ from pdf_id for custom corpora)
            "pdf_id": pdf_id,
            "page": row.page,
            "source_file": row.source_file,
        }
        _apply_metadata_extra(meta, row.metadata_extra)

        if pdf_id not in doc_text_index:
            doc_text_index[pdf_id] = ""
        doc_text_index[pdf_id] += row.text + "\n"
        if pdf_id not in chunks_by_doc:
            chunks_by_doc[pdf_id] = []
        chunks_by_doc[pdf_id].append(
            {
                "chunk_id": row.chunk_id,
                "text": row.text,
                "metadata": meta,
            },
        )

    _corpus_chunk_cache[corpus] = (doc_text_index, chunks_by_doc)
    if corpus == "difc":
        _doc_index = doc_text_index
        _chunks_by_doc = chunks_by_doc


def invalidate_corpus_cache(corpus: str) -> None:
    """Remove a corpus from the in-memory chunk cache so the next retrieval reloads it."""
    with _doc_index_lock:
        _corpus_chunk_cache.pop(corpus, None)
    logger.info("Corpus cache invalidated for %s", corpus)


def build_doc_index(corpus: str = "difc") -> dict[str, str]:
    """Build keyword-matching index from PostgreSQL data (includes OCR'd text)."""
    global _doc_index
    if corpus != "difc":
        if corpus not in _corpus_chunk_cache:
            with _doc_index_lock:
                if corpus not in _corpus_chunk_cache:
                    _load_all_chunks(corpus=corpus)
        return _corpus_chunk_cache[corpus][0]
    if _doc_index is None:
        with _doc_index_lock:
            if _doc_index is None:
                _load_all_chunks()
    return _doc_index


def get_chunks_by_doc(corpus: str = "difc") -> dict[str, list[dict]]:
    """Get in-memory chunk index (pdf_id -> list of chunks) from PostgreSQL."""
    global _chunks_by_doc
    if corpus != "difc":
        if corpus not in _corpus_chunk_cache:
            with _doc_index_lock:
                if corpus not in _corpus_chunk_cache:
                    _load_all_chunks(corpus=corpus)
        return _corpus_chunk_cache[corpus][1]
    if _chunks_by_doc is None:
        with _doc_index_lock:
            if _chunks_by_doc is None:
                _load_all_chunks()
    return _chunks_by_doc


# Known DIFC law name patterns — map question phrases to searchable keywords
_DIFC_LAW_NAMES = [
    # Amendment laws must come before their base laws to avoid false shadowing
    "Employment Law Amendment Law",
    "Strata Title Law Amendment Law",
    "Companies Law Amendment Law",
    # Base laws
    "General Partnership Law",
    "Limited Liability Partnership Law",  # LLP Law (b82ac8228e05) — different from Limited Partnership
    "Limited Partnership Law",
    "Employment Law",
    "Data Protection Law",
    "Intellectual Property Law",
    "Real Property Law",
    "Personal Property Law",
    "Strata Title Law",
    "Operating Law",
    "Common Reporting Standard Law",
    "Contract Law",
    "Arbitration Law",
    "Companies Law",
    "Insolvency Law",
    "Regulatory Law",
    "Trust Law",
    "Leasing Law",
    "Collective Investment Law",
    "Digital Assets Law",
    "Foundations Law",  # V4BH: was missing — caused 2 warmup questions to fall through to pure-vector
    "Court Law",
    "Application of Civil and Commercial Laws",  # ff746f7b5834 — not in list before V4BE
    "Companies Regulations",
    "Leasing Regulations",
    "Employment Regulations",
    "Strata Title Regulations",
]


def extract_identifiers(question: str) -> list[str]:
    """Extract case numbers, law references, named laws, etc. from a question.

    Note: Article/Section patterns are intentionally excluded — they match too broadly across
    multiple document versions and inflate the keyword doc set. Articles are handled in
    _prescore_keyword_chunks() instead, which ranks within already-matched docs.
    """
    patterns = [
        # Case numbers with context anchors (Phase 3): "Case No. SCT 295/2025", "Case SCT ...", "No. SCT ..."
        # Capturing group returns just the case number, not the anchor prefix.
        # Reduces false positives at 300-doc scale where bare codes appear in citation text.
        r"(?:case\s+no\.?\s*|case\s+|no\.\s*)((?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+)",
        # Bare case numbers: direct references in question text (e.g., "What happened in SCT 295/2025?")
        r"(?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+",
        r"Law\s+No\.?\s*\d+\s+of\s+\d+",
        r"DIFC\s+Law\s+No\.?\s*\d+(?:\s+of\s+\d+)?",
        r"Regulation\s+No\.?\s*\d+",
        r'"([^"]+)"',  # Party names in quotes
    ]
    identifiers = []
    for pattern in patterns:
        matches = re.findall(pattern, question, re.IGNORECASE)
        identifiers.extend(matches)

    # Also extract known DIFC law names mentioned in the question
    for law_name in _DIFC_LAW_NAMES:
        # Match the law name (case-insensitive, allow "Amendment" variations)
        if re.search(re.escape(law_name), question, re.IGNORECASE):
            identifiers.append(law_name)

    return identifiers


def _score_doc_by_law_name(law_name: str, doc_index: dict) -> list[str]:
    """Return doc IDs ranked by how prominently the law name appears (primary docs first).

    Prefers exact word-boundary matches (10× weight) over substring matches.
    Scales top-K: returns 4-8 docs depending on corpus size (handles 300-doc final phase).
    V4AT: Court cases are penalized when scoring for law-name matches. A court case that
    merely cites "General Partnership Law" in its text should not rank above the actual
    law document. Law docs (SAC prefix: "DIFC Law", "Law/Enactment") get 100× bonus score.
    """
    scored = []
    law_lower = law_name.lower()

    # Exact match pattern: law name with word boundaries
    exact_pattern = r"\b" + re.escape(law_lower) + r"\b"

    for pdf_id, text in doc_index.items():
        text_lower = text.lower()

        # Count exact matches (word boundaries)
        exact_matches = len(re.findall(exact_pattern, text_lower))

        # Count substring matches (includes exact)
        total_count = text_lower.count(law_lower)

        # Score: 10× exact, 1× substring (prevents "Employment Contract" overshadowing "Employment Law")
        score = exact_matches * 10 + (total_count - exact_matches)

        if score > 0:
            # V4AT: Separate law docs from court cases for law-name matching.
            # SAC prefix appears at start of doc_index text (first chunk is page 1).
            # Court cases: "[DOCUMENT: **Court Case | ..." → excluded from law-name matches.
            # A court case citing "General Partnership Law" is NOT the authoritative source
            # for law-content questions. The actual law document must rank first.
            # Fallback: if NO law docs match, return court cases (shouldn't happen).
            sac_prefix = text_lower[:200]
            is_court = "court case" in sac_prefix
            is_law = "[document:" in sac_prefix and (
                "difc law" in sac_prefix
                or "law/enactment" in sac_prefix
                or "enactment" in sac_prefix
                or "regulation" in sac_prefix
            )
            # Law docs get 1000× score boost; court cases marked separately
            boosted_score = score * 1000 if is_law else score
            scored.append((pdf_id, boosted_score, is_court))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Scale top-K with corpus size (300 docs → likely 10+ docs per law family)
    corpus_size = len(doc_index)
    if corpus_size <= 50:
        top_k = 6
    elif corpus_size <= 150:
        top_k = 8
    else:
        top_k = 12

    # Prefer law/enactment docs over court cases for law-name matching.
    # Court cases that cite the law are NOT authoritative sources for law-content questions.
    # Additionally, apply a relative score threshold: only return docs whose score is at
    # least 10% of the top doc's score. This filters out docs that merely mention the law
    # name once (e.g., Operating Law listing all Prescribed Laws at the end) vs. the
    # primary law doc that mentions it hundreds of times.
    # Exception: if NO law docs match, fall back to all matching docs (shouldn't happen
    # in practice since we have law PDFs for all key DIFC laws).
    non_court = [(pdf_id, s) for pdf_id, s, is_court in scored if not is_court]
    if non_court:
        max_score = non_court[0][1]  # highest score (sorted descending)
        min_threshold = max_score * 0.10  # 10% of top score
        # Return law docs that score at least 10% of the top doc (primary relevance)
        primary = [pdf_id for pdf_id, s in non_court if s >= min_threshold]
        if primary:
            return primary[:top_k]
        return [pdf_id for pdf_id, _ in non_court[:top_k]]
    # Fallback: no law docs matched — return all matching docs (court cases as last resort)
    return [pdf_id for pdf_id, _, _ in scored[:top_k]]


def find_docs_by_keyword(question: str) -> list[str]:
    """Find document IDs that contain keywords from the question."""
    doc_index = build_doc_index()
    identifiers = extract_identifiers(question)

    matching_pdf_ids = set()
    for identifier in identifiers:
        # For known law names, use frequency-scoring to find the primary document
        if any(identifier.lower() == law.lower() for law in _DIFC_LAW_NAMES):
            primary_docs = _score_doc_by_law_name(identifier, doc_index)
            matching_pdf_ids.update(primary_docs)
            continue

        # V4BB: For "Law No. N of YEAR" / "DIFC Law No. N" patterns, use frequency scoring.
        # Simple regex matches ALL docs containing the phrase (including 8 amended laws that
        # reference "DIFC Law No. 2 of 2022" once each). Frequency scoring finds the PRIMARY
        # law doc (mentions the number many times in its title/header/body) and applies the
        # 10% relative-threshold filter to exclude docs with rare/incidental mentions.
        _is_law_no_pattern = bool(re.match(r"(?:DIFC\s+)?Law\s+No\.?\s*\d+", identifier, re.IGNORECASE))
        if _is_law_no_pattern:
            primary_docs = _score_doc_by_law_name(identifier, doc_index)
            if primary_docs:
                matching_pdf_ids.update(primary_docs)
                continue

        normalized = re.sub(r"[\s\-_/\(\)]+", r"[\\s\\-_/]*", identifier.strip())
        try:
            pattern = re.compile(normalized, re.IGNORECASE)
            for pdf_id, text in doc_index.items():
                if pattern.search(text):
                    matching_pdf_ids.add(pdf_id)
        except re.error:
            # Fallback to simple substring match if regex fails
            for pdf_id, text in doc_index.items():
                if identifier.lower() in text.lower():
                    matching_pdf_ids.add(pdf_id)

    # Support partial matches: "CFI 10/2024" should match "CFI 010/2024"
    case_patterns = re.findall(
        r"(CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*(\d+)[\s/\-_]*(\d+)",
        question,
        re.IGNORECASE,
    )
    for prefix, num, year in case_patterns:
        num_padded = num.zfill(3)
        search_variants = [
            f"{prefix} {num}/{year}",
            f"{prefix}-{num}-{year}",
            f"{prefix} {num_padded}/{year}",
            f"{prefix}-{num_padded}-{year}",
            f"{prefix}{num}/{year}",
            f"{prefix}{num_padded}/{year}",
        ]
        for pdf_id, text in doc_index.items():
            for variant in search_variants:
                if variant.lower() in text.lower():
                    matching_pdf_ids.add(pdf_id)

    # For enactment-related questions, ensure enactment notice docs are included.
    # _score_doc_by_law_name() returns top-4 by frequency — the enactment notice (which
    # contains fewer mentions of the law name) can fall outside the top-4. Explicitly
    # search for docs that mention the law name AND "enactment notice".
    if any(kw in question.lower() for kw in _ENACTMENT_KEYWORDS):
        for identifier in identifiers:
            if any(identifier.lower() == law.lower() for law in _DIFC_LAW_NAMES):
                law_lower = identifier.lower()
                for pdf_id, text in doc_index.items():
                    text_lower = text.lower()
                    if law_lower in text_lower and "enactment notice" in text_lower:
                        matching_pdf_ids.add(pdf_id)

    # Post-filter: if question mentions a year, only keep docs containing that year.
    # Critical for 300-doc corpus where multiple versions of same law exist (2018, 2019, 2020, etc).
    # Safety: only apply filter if it doesn't eliminate all docs (bad year extraction fallback).
    year_pattern = r"\b(19\d{2}|20\d{2})\b"
    years_in_question = re.findall(year_pattern, question)

    if years_in_question and matching_pdf_ids:
        year_filtered = set()
        for pdf_id in matching_pdf_ids:
            doc_text = doc_index[pdf_id]
            # Keep doc if it contains ANY of the mentioned years
            if any(year in doc_text for year in years_in_question):
                year_filtered.add(pdf_id)

        # Only apply filter if it keeps at least one doc (safety fallback)
        if year_filtered:
            matching_pdf_ids = list(year_filtered)
        else:
            # Year filter too aggressive — keep original matches
            matching_pdf_ids = list(matching_pdf_ids)
    else:
        matching_pdf_ids = list(matching_pdf_ids)

    return matching_pdf_ids


_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "in",
        "is",
        "are",
        "was",
        "were",
        "to",
        "for",
        "and",
        "or",
        "by",
        "how",
        "many",
        "what",
        "which",
        "according",
        "under",
        "does",
        "did",
        "do",
        "has",
        "have",
        "be",
        "any",
        "if",
        "at",
        "this",
        "that",
        "with",
        "from",
        "as",
        "its",
        "it",
        "on",
        "not",
        "no",
        "than",
        "such",
        "same",
        "both",
        "also",
        "may",
        "shall",
        "will",
        "who",
    },
)

_SCHEDULE_INDICATORS = frozenset({"schedule", "contravention", "appendix", "annex", "fine", "penalty table"})

_ENACTMENT_KEYWORDS = frozenset(
    {
        "enacted",
        "enact",
        "enactment",
        "promulgated",
        "came into force",
        "effective date",
        # V4BH: added phrasing variants found in legal questions (RESEARCH_RETRIEVAL.md)
        "published",
        "commencement",
        "date of commencement",
        "gazetted",
        "gazette",
        # Phase 3: 'effective' standalone for "when did X become effective?"
        "effective",
    },
)

# Outcome-related question keywords — used to boost prescore of outcome chunks
# NOTE: 'judgment'/'judgement' intentionally EXCLUDED — questions referencing
# "the appeal judgment" or "what does the judgment say about X" are NOT asking
# about the OUTCOME; they're asking about content within the judgment document.
# Including them caused "claim value in judgment" to trigger outcome boosting,
# promoting wrong chunks (e.g., ordered amount instead of claimed amount).
_OUTCOME_QUESTION_KEYWORDS = frozenset(
    {
        "outcome",
        "result",
        "ruling",
        "decision",
        "verdict",
        "held",
        "ordered",
        "dismissed",
        "awarded",
        "granted",
        "refused",
        "conclud",
        "final order",
        "final ruling",
    },
)
# Outcome keywords that appear IN the actual chunks (order pages, judgment text)
# Broad 'judgment'/'judgement' removed to prevent false-positive boosting on non-outcome chunks.
_OUTCOME_CHUNK_KEYWORDS = frozenset(
    {
        "dismissed",
        "awarded",
        "granted",
        "ordered",
        "hereby ordered",
        "it is ordered",
        "it is hereby",
        "costs awarded",
        "claim dismissed",
        "application dismissed",
        "claim allowed",
        "appeal dismissed",
        "appeal allowed",
    },
)


def _clean_query_for_ce(question: str) -> str:
    """Strip long case names from query for cross-encoder scoring in targeted retrieval.

    Questions like "What was X in [LONG PARTY NAME] [YEAR] DIFC TYPE NUM?" cause the CE
    to over-rank title pages: the long case name dominates token budget and CE matching.
    In targeted retrieval (doc already identified), the case name is redundant — removing
    it focuses CE on the semantic "what/why/how" portion of the question.

    Only triggers when party segment is ≥25 chars, avoiding removal of short case refs.
    """
    cleaned = re.sub(
        r"\s+in\s+[A-Z][^?\[\]]{25,}\[\d{4}\]\s+DIFC\s+[A-Z]+\s+\d+[^?]*",
        "",
        question,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned if len(cleaned) >= 20 else question


# Entity extraction patterns for query-time entity boosting.
# Same patterns as indexer.extract_entities_from_chunk — defined here to avoid
# a cross-module import from the indexer (which has LLM-dependent side effects).
_QUERY_ENTITY_PATTERNS = [
    re.compile(r"\b((?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+)\b", re.IGNORECASE),
    re.compile(r"\b(Article\s+\d+(?:\(\w+\))*)\b", re.IGNORECASE),
    re.compile(r"\b((?:DIFC\s+)?Law\s+No\.?\s*\d+(?:\s+of\s+\d+)?)\b", re.IGNORECASE),
    re.compile(r"\b(Regulation\s+No\.?\s*\d+)\b", re.IGNORECASE),
]


def _extract_query_entities(question: str) -> set[str]:
    """Extract legal entities (case IDs, article refs, law numbers) from the question.

    Used at query time to boost chunks whose stored entities match entities in the question.
    Returns a set of lowercase normalized entity strings.
    """
    entities: set[str] = set()
    for pattern in _QUERY_ENTITY_PATTERNS:
        for match in pattern.findall(question):
            entity = re.sub(r"\s+", " ", match.strip()).lower()
            if entity:
                entities.add(entity)
    return entities


def _prescore_keyword_chunks(question: str, chunks: list[dict], top_n: int = 25) -> list[dict]:
    """Pre-rank keyword chunks by term overlap with question before cross-encoder reranking.

    Gives 3× weight to specific article references (Article 14(2)(b)), 1× to other terms.
    Penalizes schedule/table chunks that reference articles but don't contain the actual text.
    Always includes page-1 chunks so law title/number is always available.
    Boosts enactment notice chunks when the question asks about enactment dates.
    """
    # Extract entities from question for entity-aware chunk boosting (see entity_score below)
    _query_entities = _extract_query_entities(question)

    # Extract exact article references (e.g. "Article 14(2)(b)") — high-value signal
    article_refs = [r.lower() for r in re.findall(r"Article\s+\d+[\w\(\)\.]*", question, re.IGNORECASE)]

    # Extract quoted section phrases (e.g., "IT IS HEREBY ORDERED THAT") — chunks containing
    # these phrases get a strong boost so section-specific questions find the right page
    _section_quotes = re.findall(r"'([^']{10,})'|\"([^\"]{10,})\"", question)
    _section_phrase = (_section_quotes[0][0] or _section_quotes[0][1]).strip().lower() if _section_quotes else ""

    # General question terms (stopwords removed)
    q_words = {w.lower() for w in re.findall(r"\w+", question)} - _STOPWORDS

    # Detect enactment-related questions (e.g. "Was X enacted earlier than Y?")
    q_lower = question.lower()
    asks_enactment = any(kw in q_lower for kw in _ENACTMENT_KEYWORDS)

    # Detect outcome/result questions (e.g. "What was the outcome of case X?")
    asks_outcome = any(kw in q_lower for kw in _OUTCOME_QUESTION_KEYWORDS)

    # Page-1 chunk IDs — always include these (law title/number is typically on page 1)
    page1_ids = {c["chunk_id"] for c in chunks if c["metadata"].get("page", 0) == 1}

    # Also extract bare article numbers (legal docs often omit "Article" prefix in body text)
    # e.g. "Article 14(2)(b)" → also check for "14(2)(b)" substring
    bare_art_nums = [re.sub(r"^article\s+", "", ref) for ref in article_refs]
    # Article root numbers for header detection: "14(2)(b)" → "14"
    art_root_nums = list({re.match(r"(\d+)", num).group(1) for num in bare_art_nums if re.match(r"\d+", num)})

    scored = []
    for chunk in chunks:
        text_lower = chunk["text"].lower()
        chunk_text = chunk["text"]  # original case for pattern matching

        # High-value: article reference with "Article" prefix (title/cross-reference style)
        article_score = sum(3 for ref in article_refs if ref in text_lower)
        # Bare article numbers: "14(2)(b)" as substring (inline body text style)
        article_score += sum(3 for num in bare_art_nums if num and num in text_lower)
        # Article header detection: "14." at start of line = this chunk IS the article
        for root in art_root_nums:
            if chunk_text.startswith(f"{root}.") or f"\n{root}." in chunk_text:
                article_score += 4  # Strongest signal: this chunk DEFINES the article
            elif f"{root}(" in text_lower:
                article_score += 2  # Weaker: chunk contains a sub-clause of this article

        # Penalize schedule/appendix chunks — they reference articles but contain fines, not text
        first_150 = text_lower[:150]
        if any(ind in first_150 for ind in _SCHEDULE_INDICATORS):
            article_score = max(0, article_score - 2)

        # Enactment notice boost: when question asks about enactment dates, chunks from
        # enactment notices are critical (they contain the actual enactment date)
        enactment_bonus = 0
        if asks_enactment and "enactment notice" in text_lower:
            enactment_bonus = 6  # Strong boost — enactment notices have the date we need

        # Quoted section boost: if question quotes a section name (e.g., "IT IS HEREBY ORDERED THAT"),
        # chunks containing that exact phrase get a strong boost regardless of page or article refs.
        # Fixes CFI 092/2024 where page 2 (HEREBY ORDERED) was ranked below page 1 (title page).
        section_boost = 0
        if _section_phrase and _section_phrase in text_lower:
            section_boost = 8  # Strongest signal: this chunk IS the cited section

        # Outcome boost: when question asks about case outcomes, boost chunks with outcome language.
        # Case outcome questions ("What was the result of case X?") need judgment/order pages
        # that contain outcome phrases like "dismissed", "awarded", "IT IS HEREBY ORDERED".
        # Without this boost, page-1 (case header) outranks page-2 (the order itself).
        # Now enhanced with chunk_type metadata for more precise filtering.
        outcome_bonus = 0
        if asks_outcome:
            # Strong boost for chunks classified as "order" type (judgment/order pages)
            if chunk["metadata"].get("chunk_type") == "order":
                outcome_bonus = 7  # Strongest signal: this chunk IS an order/judgment
            elif any(kw in text_lower for kw in _OUTCOME_CHUNK_KEYWORDS):
                outcome_bonus = 5  # Fallback: outcome keywords present

        # Page 1: always boost (contains law title, law number, preamble)
        page_bonus = 4 if chunk["chunk_id"] in page1_ids else 0

        # General: question term overlap
        chunk_words = set(re.findall(r"\w+", text_lower))
        overlap = len(q_words & chunk_words)

        # Entity-aware boost: chunks whose stored entities (case IDs, article refs,
        # law numbers) match entities extracted from the question get +2 per match.
        # This is free signal already in the DB — no extra LLM or regex cost at query time.
        # Case numbers (e.g. "CFI 010/2024") are NOT captured by article_score, so this
        # adds new signal rather than double-counting existing article ref logic.
        chunk_entities = set(chunk["metadata"].get("entities", []))
        entity_score = len(_query_entities & chunk_entities) * 2 if _query_entities else 0

        scored.append(
            (
                article_score + enactment_bonus + section_boost + outcome_bonus + page_bonus + overlap + entity_score,
                chunk,
            ),
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_n]]


def get_all_pages_for_docs(pdf_ids: list[str]) -> list[dict]:
    """Get all indexed chunks for specific documents from PostgreSQL."""
    chunks_by_doc = get_chunks_by_doc()
    chunks = []
    for pdf_id in pdf_ids:
        chunks.extend(chunks_by_doc.get(pdf_id, []))
    return chunks


def generate_hyde_passage(question: str, corpus: str = "difc") -> str | None:
    """Generate a hypothetical document passage that would answer the question (HyDE).

    Embeds this passage instead of the raw question for better semantic alignment with
    the document corpus (especially for fact-lookup questions where the question uses
    everyday language but the answer uses specific legal terminology).

    Uses the configured LLM backend (litellm/vertex/anthropic) via arlc.llm.router.
    Returns None silently on any error so HyDE is always best-effort.

    Parameters
    ----------
    question : str
        The user's legal question.
    corpus : str
        Active corpus identifier. Controls the domain used in the HyDE prompt
        so the generated passage matches the target legal domain.
    """
    # Map corpus to a domain label for the HyDE prompt
    _HYDE_DOMAIN_LABELS = {
        "difc": "DIFC (Dubai International Financial Centre) law",
        "czech": "Czech law",
        "uk": "United Kingdom legislation and case law",
        "au": "Australian Commonwealth legislation and case law",
    }
    domain = _HYDE_DOMAIN_LABELS.get(corpus, "legal")

    try:
        from arlc.llm.router import _call_backend

        text, *rest = _call_backend(
            system_prompt=(
                f"You are a drafter of official {domain} legislative and judicial texts. "
                "Reproduce the exact register, section structure, and terminology of official "
                "legal documents. Output only the document text — no preamble, no metadata, "
                "no explanations."
            ),
            user_message=(
                f"Write 3-4 sentences as they would appear in an official {domain} legal "
                f"document or court judgment that contains the answer to this question: {question}"
            ),
            max_tokens=150,
            model=_HAIKU_MODEL,
            system_blocks=None,
        )
        # Record HyDE generation as an observability span (no-op when trace is None)
        try:
            from neolex.observability import add_generation_span, get_current_trace

            _elapsed_ms = rest[1] if len(rest) > 1 else 0
            _in_tok = rest[3] if len(rest) > 3 else 0
            _out_tok = rest[4] if len(rest) > 4 else 0
            add_generation_span(
                get_current_trace(),
                model=_HAIKU_MODEL,
                input_text=question,
                output_text=text or "",
                duration_ms=_elapsed_ms,
                usage={"input": _in_tok, "output": _out_tok},
                metadata={"name": "hyde", "corpus": corpus},
            )
        except Exception:
            pass
        return text.strip() if text else None
    except Exception:
        return None


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60, weights: list[float] | None = None) -> list[str]:
    """Merge multiple rankings using Reciprocal Rank Fusion with optional weights."""
    scores = {}

    for i, ranking in enumerate(rankings):
        weight = weights[i] if (weights and i < len(weights)) else 1.0
        for rank, chunk_id in enumerate(ranking):
            if chunk_id not in scores:
                scores[chunk_id] = 0.0
            scores[chunk_id] += weight / (k + rank + 1)

    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk_id for chunk_id, score in sorted_ids]


# ---------------------------------------------------------------------------
# Multi-signal document fusion
# Multi-signal fusion from IAS Partners (guy4, Ivanov/Agishev/Sadchikov)
# ---------------------------------------------------------------------------

USE_MULTI_SIGNAL_FUSION = True  # Enable/disable multi-signal document fusion

# Dense-only page ranking insight from IAS Partners (guy4)
# BM25 hurts page-level ranking within a known document — dense similarity only is better
PAGE_RANK_USE_BM25 = (
    True  # Re-enabled: per-type logic in _retrieve_pages_targeted restricts BM25 to exact-match types only
)

# Adaptive CE pre-filter: scale pool size with document size instead of hard-capping at 50.
# Formula: min(100, max(50, n_chunks // 2)) — covers ~half of medium docs,
# caps at 100 to keep Qwen3-Reranker-0.6B latency acceptable.
# Set to False to use fixed-50 fallback.
CE_ADAPTIVE_PREFILTER = os.environ.get("CE_ADAPTIVE_PREFILTER", "1") != "0"

# BM25 injection: inject top BM25-matched chunks from the target doc into the CE pool,
# rescuing pages with strong lexical signal (article numbers, case refs) that dense
# scoring de-prioritised. Distinct from PAGE_RANK_USE_BM25 — BM25 only expands the
# candidate set; the cross-encoder still provides all final scores.
PAGE_RANK_BM25_INJECTION = os.environ.get("PAGE_RANK_BM25_INJECTION", "1") != "0"
BM25_INJECTION_K = 8  # Max BM25 candidates to inject per doc into CE pool

# Per-type configs inspired by IAS Partners dual-pipeline (guy4)
# top_k: retrieval depth — how many candidates to pull before reranking.
# Inspired by CPBD (Azamat Yelmagambetov, 1st place) who swept 22 depth values.
# V5: Increased all top_k values to 200 (was 30-100) based on Legal RAG Bench testing.
# Deeper candidate pool gave +0.10 retrieval accuracy — more candidates before reranking
# means the right page has a higher chance of being in the pool at all.
# NOTE: This is retrieval POOL depth, not output pages. "Extra pages" graveyard entry
# refers to max output pages (max_pages), not the candidate pool. These are different.
RETRIEVAL_CONFIGS = {
    "boolean": {"top_k": 200, "max_docs": 3, "max_pages": 3},
    "number": {"top_k": 200, "max_docs": 2, "max_pages": 2},
    "date": {"top_k": 200, "max_docs": 2, "max_pages": 1},
    "name": {"top_k": 200, "max_docs": 3, "max_pages": 3},
    "names": {"top_k": 200, "max_docs": 3, "max_pages": 3},
    "free_text": {"top_k": 200, "max_docs": 4, "max_pages": 5},
}

DOC_FUSION_WEIGHTS = {
    "bm25_std": 0.10,  # standard BM25 page score (max per doc)
    "dense_std": 0.05,  # dense embedding score (max per doc)
    "dense_rrf": 0.20,  # dense RRF rank score
    "bm25_doc": 0.30,  # document-level BM25
    "bm25_page1": 0.30,  # page-1-only BM25
}

DOC_FUSION_GAP_THRESHOLD = 0.15  # Adaptive doc selection gap


def _doc_fusion_select(
    question: str,
    max_docs: int = 3,
    answer_type: str = "",
    cached_query_emb=None,
    corpus: str = "difc",
) -> list[str] | None:
    """Select target documents using multi-signal fusion.

    Combines 5 signals to identify the most relevant documents before page-level
    ranking. Returns list of doc_ids, or None if fusion indexes are not available.

    Signals:
    1. bm25_std — max BM25 page score per doc (existing all-pages index)
    2. dense_std — max dense embedding score per doc
    3. dense_rrf — dense RRF rank score per doc
    4. bm25_doc — document-level BM25 score
    5. bm25_page1 — page-1-only BM25 score

    Per-type retrieval depth (inspired by CPBD, Azamat Yelmagambetov, 1st place):
    top_k is taken from RETRIEVAL_CONFIGS[answer_type] when available.
    """
    if not USE_MULTI_SIGNAL_FUSION:
        return None

    # Per-type top_k: use answer_type config if available
    type_cfg = RETRIEVAL_CONFIGS.get(answer_type, {})
    fusion_top_k = type_cfg.get("top_k", 128)

    # --- Run all 5 signals in parallel via ThreadPoolExecutor ---
    # Signals are independent: 3 text search queries + 1 embedding + 1 vector query.
    # Parallelizing cuts wall-clock time from sum(all) to max(any).
    query_emb = cached_query_emb if cached_query_emb is not None else embed_query(question)
    dense_n = min(fusion_top_k, get_chunk_count(corpus))

    def _sig_bm25_std():
        return _search_chunks_text_scored(question, top_k=fusion_top_k, corpus=corpus)

    def _sig_vector():
        return search_chunks_vector(query_emb, top_k=dense_n, corpus=corpus)

    def _sig_bm25_doc():
        return _search_docs_text_scored(question, top_k=fusion_top_k, corpus=corpus)

    def _sig_bm25_p1():
        return _search_chunks_text_page1_scored(question, top_k=fusion_top_k, corpus=corpus)

    with ThreadPoolExecutor(max_workers=4) as executor:
        fut_bm25_std = executor.submit(_sig_bm25_std)
        fut_vector = executor.submit(_sig_vector)
        fut_bm25_doc = executor.submit(_sig_bm25_doc)
        fut_bm25_p1 = executor.submit(_sig_bm25_p1)

        bm25_std_results = fut_bm25_std.result()
        vector_results = fut_vector.result()
        bm25_doc_results = fut_bm25_doc.result()
        bm25_p1_results = fut_bm25_p1.result()

    # --- Signal 1: Text search standard (max page score per doc) ---
    bm25_std_doc_scores: dict[str, float] = {}
    for _chunk_id, pdf_id, score in bm25_std_results:
        if pdf_id not in bm25_std_doc_scores or score > bm25_std_doc_scores[pdf_id]:
            bm25_std_doc_scores[pdf_id] = score

    max_bm25_std = max(bm25_std_doc_scores.values(), default=1.0) or 1.0
    for d in bm25_std_doc_scores:
        bm25_std_doc_scores[d] /= max_bm25_std

    # --- Signal 2 & 3: Dense embedding scores + RRF ---
    dense_std_doc_scores: dict[str, float] = {}
    dense_rrf_doc_scores: dict[str, float] = {}
    k_rrf = 60
    for rank, (meta, dist) in enumerate(zip(vector_results["metadatas"][0], vector_results["distances"][0])):
        doc_id = meta["pdf_id"]
        sim = 1.0 - float(dist)  # cosine distance -> similarity
        if doc_id not in dense_std_doc_scores or sim > dense_std_doc_scores[doc_id]:
            dense_std_doc_scores[doc_id] = sim
        rrf_score = 1.0 / (k_rrf + rank + 1)
        dense_rrf_doc_scores[doc_id] = dense_rrf_doc_scores.get(doc_id, 0.0) + rrf_score

    max_dense_std = max(dense_std_doc_scores.values(), default=1.0) or 1.0
    for d in dense_std_doc_scores:
        dense_std_doc_scores[d] /= max_dense_std
    max_dense_rrf = max(dense_rrf_doc_scores.values(), default=1.0) or 1.0
    for d in dense_rrf_doc_scores:
        dense_rrf_doc_scores[d] /= max_dense_rrf

    # --- Signal 4: Text search doc-level ---
    bm25_doc_doc_scored: dict[str, float] = {}
    for pdf_id, score in bm25_doc_results:
        bm25_doc_doc_scored[pdf_id] = score

    max_bm25_doc = max(bm25_doc_doc_scored.values(), default=1.0) or 1.0
    for d in bm25_doc_doc_scored:
        bm25_doc_doc_scored[d] /= max_bm25_doc

    # --- Signal 5: Text search page1 ---
    bm25_p1_doc_scored: dict[str, float] = {}
    for _chunk_id, pdf_id, score in bm25_p1_results:
        if pdf_id not in bm25_p1_doc_scored or score > bm25_p1_doc_scored[pdf_id]:
            bm25_p1_doc_scored[pdf_id] = score

    max_bm25_p1 = max(bm25_p1_doc_scored.values(), default=1.0) or 1.0
    for d in bm25_p1_doc_scored:
        bm25_p1_doc_scored[d] /= max_bm25_p1

    # --- Fuse all signals via RRF (Reciprocal Rank Fusion) ---
    # RRF replaces additive weighted score fusion.
    # Benchmark testing showed additive fusion HURTS recall: vector@3=0.35 but additive@3=0.15
    # because BM25 scores dominate scale and pull vector-dominant hits down.
    # RRF formula: score = sum(weight / (k + rank_i)) for each signal, k=60 (standard).
    # Credit: RRF confirmed by CPBD (1st place) and Legal RAG Bench testing (40% -> 60% recall).
    all_doc_ids = set()
    for scores_dict in [
        bm25_std_doc_scores,
        dense_std_doc_scores,
        dense_rrf_doc_scores,
        bm25_doc_doc_scored,
        bm25_p1_doc_scored,
    ]:
        all_doc_ids.update(scores_dict.keys())

    # Build per-signal rankings (sorted by score descending)
    def _signal_ranking(scores_dict: dict[str, float]) -> list[str]:
        return [d for d, _ in sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)]

    rrf_k = 60
    w = DOC_FUSION_WEIGHTS
    signal_rankings = [
        (_signal_ranking(bm25_std_doc_scores), w["bm25_std"]),
        (_signal_ranking(dense_std_doc_scores), w["dense_std"]),
        (_signal_ranking(dense_rrf_doc_scores), w["dense_rrf"]),
        (_signal_ranking(bm25_doc_doc_scored), w["bm25_doc"]),
        (_signal_ranking(bm25_p1_doc_scored), w["bm25_page1"]),
    ]

    fused_scores: dict[str, float] = {doc_id: 0.0 for doc_id in all_doc_ids}
    for ranking, weight in signal_rankings:
        for rank, doc_id in enumerate(ranking):
            fused_scores[doc_id] += weight / (rrf_k + rank + 1)

    # Sort by fused score descending
    sorted_docs = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

    if not sorted_docs:
        return None

    # Adaptive document selection: select 1-max_docs based on gap threshold
    selected = [sorted_docs[0][0]]
    top_score = sorted_docs[0][1]

    for i in range(1, min(len(sorted_docs), max_docs)):
        doc_id, score = sorted_docs[i]
        # Include doc if its score is within gap threshold of top score
        if top_score > 0 and (top_score - score) / top_score <= DOC_FUSION_GAP_THRESHOLD:
            selected.append(doc_id)
        else:
            break

    logger.debug(
        "[doc_fusion] selected %d docs: %s",
        len(selected),
        ", ".join(f"{d[:12]}({fused_scores[d]:.3f})" for d in selected),
    )

    return selected


# Language names for query variant generation — must match the language of source
# documents so BM25 text search can find relevant chunks.
_CORPUS_LANGUAGE_NAMES: dict[str, str] = {
    "difc": "English",
    "czech": "Czech",
    "uk": "English",
    "au": "English",
    "eu": "English",
    "us": "English",
}


def _generate_query_variants(question: str, corpus: str = "difc") -> list[str]:
    """Generate 2 alternative query phrasings using Haiku. Returns empty list on failure.

    Parameters
    ----------
    question : str
        The original legal question.
    corpus : str
        Active corpus identifier.  Controls the output language so that
        Czech variants are generated in Czech (for BM25 tsvector matching),
        English variants in English, etc.
    """
    corpus_language = _CORPUS_LANGUAGE_NAMES.get(corpus, "English")
    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model=_HAIKU_MODEL,
            system=(
                f"You are a legal search specialist for {corpus_language} legal corpora. "
                "Generate precise alternative search queries using the same language and "
                "legal terminology that would appear in the source documents."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Generate 2 alternative search queries for: {question}\n"
                        f"Requirements: Use {corpus_language}. Use synonymous legal terms, "
                        "article numbers if applicable, or related legal concepts from the same domain. "
                        "Output ONLY the 2 queries, one per line, no numbering."
                    ),
                },
            ],
            max_tokens=100,
            temperature=0.3,
        )
        content = response.content[0].text.strip() if response.content else ""
        variants = [line.strip() for line in content.split("\n") if line.strip()]
        # Record query-variant generation as an observability span (no-op when trace is None)
        try:
            from neolex.observability import add_generation_span, get_current_trace

            _usage = getattr(response, "usage", None)
            add_generation_span(
                get_current_trace(),
                model=_HAIKU_MODEL,
                input_text=question,
                output_text=content,
                usage={
                    "input": getattr(_usage, "input_tokens", 0),
                    "output": getattr(_usage, "output_tokens", 0),
                },
                metadata={"name": "query-variants", "corpus": corpus},
            )
        except Exception:
            pass
        return variants[:2]
    except Exception:
        return []


def prewarm() -> None:
    """Pre-warm all caches before parallel processing to avoid race conditions."""
    logger.info("Pre-warming retrieval caches...")
    get_embedding_model()
    get_chunk_count("difc")  # warm DB connection pool
    get_chunk_count("czech")
    build_doc_index()  # populates in-memory chunk cache from PostgreSQL
    get_reranker()
    logger.info("Caches ready.")


def _extract_article_filter(question: str) -> str | None:
    """Extract article number for metadata filtering.

    Returns article number string (e.g., "28") if question explicitly mentions
    a specific article like "Article 28" or "Article 14(2)".
    """
    # Match "Article 28", "Article 14(2)", "Article 3(a)"
    article_match = re.search(r"\bArticle\s+(\d+)", question, re.IGNORECASE)
    if article_match:
        return article_match.group(1)
    return None


def retrieve(
    question: str,
    n_results: int = 15,
    use_hyde: bool = True,
    answer_type: str = "",
    corpus: str = "difc",
    cached_query_emb=None,
) -> list[dict]:
    """
    Hybrid retrieval: keyword match + BM25 + vector search with RRF.

    For questions with keyword matches (specific case/law): return up to 25 chunks.
    For pure vector questions: return 15 chunks using BM25 + vector RRF (+ HyDE if enabled).

    answer_type: when provided, overrides n_results with per-type top_k from RETRIEVAL_CONFIGS.
    Inspired by CPBD (Azamat Yelmagambetov, 1st place) who swept 22 depth values per type.

    NEW: Metadata-aware filtering when question mentions specific articles.
    """
    # Per-type retrieval depth: RETRIEVAL_CONFIGS[answer_type]["top_k"] overrides n_results
    if answer_type and answer_type in RETRIEVAL_CONFIGS:
        n_results = RETRIEVAL_CONFIGS[answer_type]["top_k"]

    # Step 0: Extract article filter for metadata-aware retrieval
    article_filter = _extract_article_filter(question)

    # Step 1: Check for keyword matches
    keyword_pdf_ids = find_docs_by_keyword(question)

    if keyword_pdf_ids:
        # Keyword match: prioritize chunks from these documents
        keyword_chunks = get_all_pages_for_docs(keyword_pdf_ids)

        # Metadata-aware filtering: if question mentions a specific article, promote chunks with matching article_number
        if article_filter:
            filtered_chunks = []
            article_chunks = []
            for chunk in keyword_chunks:
                if chunk["metadata"].get("article_number") == article_filter:
                    article_chunks.append(chunk)
                else:
                    filtered_chunks.append(chunk)
            # Put article-matching chunks first, then others
            keyword_chunks = article_chunks + filtered_chunks
            logger.debug(
                "[METADATA FILTER] Article %s: %d exact matches promoted to top", article_filter, len(article_chunks)
            )

        # Pre-score keyword chunks by term overlap so article-specific chunks surface first.
        # When multiple docs are retrieved, score per-doc first (top-10 each) to prevent a
        # large doc (e.g., 83-chunk ENF case) from crowding out a smaller companion doc.
        if len(keyword_chunks) > 20:
            if len(keyword_pdf_ids) > 1:
                from collections import defaultdict as _dd

                _by_doc: dict[str, list] = _dd(list)
                for c in keyword_chunks:
                    _by_doc[c["metadata"]["pdf_id"]].append(c)
                # Interleave top chunks from each doc (round-robin) to prevent
                # large docs from crowding out small ones in the keyword_chunks list.
                per_doc_ranked = [_prescore_keyword_chunks(question, dc, top_n=15) for dc in _by_doc.values()]
                keyword_chunks = []
                max_len = max(len(ranked) for ranked in per_doc_ranked)
                for i in range(max_len):
                    for ranked in per_doc_ranked:
                        if i < len(ranked):
                            keyword_chunks.append(ranked[i])
            else:
                keyword_chunks = _prescore_keyword_chunks(question, keyword_chunks, top_n=30)

        # Also get vector search results to supplement
        _kw_query_emb = cached_query_emb if cached_query_emb is not None else embed_query(question)
        vector_results = search_chunks_vector(_kw_query_emb, top_k=max(n_results, 15), corpus=corpus)

        vector_chunks = []
        for i in range(len(vector_results["ids"][0])):
            vector_chunks.append(
                {
                    "chunk_id": vector_results["ids"][0][i],
                    "text": vector_results["documents"][0][i],
                    "metadata": vector_results["metadatas"][0][i],
                    "distance": vector_results["distances"][0][i],
                },
            )

        # Merge: pre-scored keyword matches first, then vector matches
        seen_ids = set()
        merged = []

        for chunk in keyword_chunks:
            if chunk["chunk_id"] not in seen_ids:
                seen_ids.add(chunk["chunk_id"])
                merged.append(chunk)

        for chunk in vector_chunks:
            if chunk["chunk_id"] not in seen_ids:
                seen_ids.add(chunk["chunk_id"])
                merged.append(chunk)

        # Cap at 30 chunks before reranking — balances citation coverage with latency
        ranked = rerank_chunks(question, merged[:30], top_k=20, answer_type=answer_type)

        # Guarantee each keyword-matched doc has at least 1 chunk in the result.
        # CrossEncoder can rank one doc's chunks so highly that another keyword doc disappears
        # entirely — this breaks "compare two cases" questions where both docs are needed.
        if len(keyword_pdf_ids) > 1:
            ranked_doc_ids = {c["metadata"]["pdf_id"] for c in ranked}
            chunks_by_doc_kw = get_chunks_by_doc()
            for pdf_id in keyword_pdf_ids:
                if pdf_id not in ranked_doc_ids:
                    # Add the page-1 chunk (most informative) from the missing doc
                    doc_chunks = chunks_by_doc_kw.get(pdf_id, [])
                    page1 = [c for c in doc_chunks if c["metadata"].get("page") == 1]
                    if page1:
                        ranked.append(page1[0])
                    elif doc_chunks:
                        ranked.append(doc_chunks[0])

        return ranked

    # No keyword matches: use text search + vector with RRF, augmented by HyDE

    # Scale top_k based on metadata filters (need larger pool before filtering)
    # V5: Raised floor from 50 to 200 — deeper pool gives +0.10 retrieval accuracy
    base_top_k = max(n_results, 200)
    top_k = base_top_k * 3 if article_filter else base_top_k

    # --- Parallel Phase 1: Run BM25 + vector search + HyDE generation + query variant generation ---
    # All are independent: BM25 and vector are DB queries; HyDE and variants are LLM calls.
    # Running in parallel saves ~500-1000ms (HyDE Haiku call ~500ms, variant call ~300ms).
    query_emb = cached_query_emb if cached_query_emb is not None else embed_query(question)

    with ThreadPoolExecutor(max_workers=4) as executor:
        fut_bm25 = executor.submit(search_chunks_text, question, top_k, corpus)
        fut_vector = executor.submit(search_chunks_vector, query_emb, top_k, corpus)
        # Start LLM calls in parallel with DB queries
        fut_hyde = executor.submit(generate_hyde_passage, question, corpus) if use_hyde else None
        fut_variants = executor.submit(_generate_query_variants, question, corpus) if use_hyde else None

        bm25_ranking = fut_bm25.result()
        vector_results = fut_vector.result()
        hyde_passage = fut_hyde.result() if fut_hyde else None
        variants = fut_variants.result() if fut_variants else []

    vector_ranking = vector_results["ids"][0]

    # --- Parallel Phase 2: HyDE embedding+search + variant text searches ---
    # These depend on Phase 1 results (hyde_passage, variants).
    hyde_ranking: list[str] = []
    variant_rankings: list[list[str]] = []

    phase2_futures = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        if hyde_passage:

            def _hyde_search():
                hyde_emb = embed_query(hyde_passage)
                hyde_results = search_chunks_vector(hyde_emb, top_k=top_k, corpus=corpus)
                return hyde_results["ids"][0]

            phase2_futures["hyde"] = executor.submit(_hyde_search)

        for i, variant in enumerate(variants[:2]):
            phase2_futures[f"variant_{i}"] = executor.submit(
                search_chunks_text,
                variant,
                top_k,
                corpus,
            )

        for key, fut in phase2_futures.items():
            try:
                result = fut.result()
                if key == "hyde":
                    hyde_ranking = result
                else:
                    variant_rankings.append(result)
            except Exception:  # nosec B110
                pass

    # RRF over all signals: text search, vector, HyDE-vector, variant queries
    all_rankings = [r for r in [bm25_ranking, vector_ranking, hyde_ranking] + variant_rankings if r]
    # Text search gets 2.0x weight — outperforms dense for legal without domain-adapted embeddings (LRAGE 2025)
    # Phase 3: raised 1.5->2.0 for larger 300-doc corpus (more vector noise at scale)
    weights = [2.0] + [1.0] * (len(all_rankings) - 1)
    merged_ranking = reciprocal_rank_fusion(all_rankings, k=60, weights=weights)

    # Build lookup from vector results
    vector_lookup = {}
    for i in range(len(vector_results["ids"][0])):
        chunk_id = vector_results["ids"][0][i]
        vector_lookup[chunk_id] = {
            "chunk_id": chunk_id,
            "text": vector_results["documents"][0][i],
            "metadata": vector_results["metadatas"][0][i],
            "distance": vector_results["distances"][0][i],
        }

    # Batch-fetch missing chunks instead of one-by-one DB queries
    missing_ids = [cid for cid in merged_ranking[:60] if cid not in vector_lookup]
    missing_lookup: dict[str, dict] = {}
    if missing_ids:
        chunk_data = get_chunks_by_ids(missing_ids, corpus=corpus)
        for i, cid in enumerate(chunk_data["ids"]):
            missing_lookup[cid] = {
                "chunk_id": cid,
                "text": chunk_data["documents"][i],
                "metadata": chunk_data["metadatas"][i],
                "distance": 0.5,
            }

    final_chunks = []
    for chunk_id in merged_ranking[:60]:
        if chunk_id in vector_lookup:
            final_chunks.append(vector_lookup[chunk_id])
        elif chunk_id in missing_lookup:
            final_chunks.append(missing_lookup[chunk_id])

    # Metadata-aware filtering: promote article-matching chunks to the top
    if article_filter:
        article_chunks = []
        other_chunks = []
        for chunk in final_chunks:
            if chunk["metadata"].get("article_number") == article_filter:
                article_chunks.append(chunk)
            else:
                other_chunks.append(chunk)
        final_chunks = article_chunks + other_chunks
        logger.debug(
            "[METADATA FILTER] Article %s: %d exact matches promoted (vector path)",
            article_filter,
            len(article_chunks),
        )

    return rerank_chunks(question, final_chunks[:30], top_k=20, answer_type=answer_type)


# ---------------------------------------------------------------------------
# Page-level retrieval (new pipeline)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=20)
def _open_pdf_cached(pdf_path: str):
    """Cache open pymupdf Document handles to avoid repeated open/close.

    With 4-15 page extractions per query from the same PDF, caching avoids
    4-15 redundant open/close cycles per document.
    """
    return pymupdf.open(pdf_path)


def _extract_page_text(doc_id: str, page_number: int) -> str:
    """Extract full text from a specific page of a document.

    page_number is 1-based (matches our grounding convention).
    Tries PDF first, then falls back to chunk text from the database
    (for TXT-based judgment documents that have no PDF).
    """
    # Try PDF extraction first (law documents)
    pdf_path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.pdf")
    if os.path.exists(pdf_path):
        try:
            doc = _open_pdf_cached(pdf_path)
            if 1 <= page_number <= len(doc):
                return doc[page_number - 1].get_text().strip()
        except Exception:  # nosec B110
            pass

    # Fallback: concatenate chunk texts for this page from the in-memory index.
    # This handles TXT-based judgments and any docs without PDFs.
    try:
        chunks_by_doc = get_chunks_by_doc()
        doc_chunks = chunks_by_doc.get(doc_id, [])
        page_texts = [
            c["text"] for c in doc_chunks if c.get("metadata", {}).get("page", c.get("page", 0)) == page_number
        ]
        if page_texts:
            return "\n".join(page_texts)
    except Exception:  # nosec B110
        pass

    return ""


_METADATA_QUESTION_PATTERNS = re.compile(
    r"\b(date of issue|issue date|issued|when was .* issued"
    r"|who (?:is|was|are|were) the judge"
    r"|presiding judge|name of.*judge"
    r"|claimants?|defendants?|respondents?|appellants?"
    r"|claim value|amount claimed|value of.*claim"
    r"|title page)\b",
    re.IGNORECASE,
)


def _retrieve_pages_simple(
    question: str,
    max_per_doc: int = 1,
    max_total: int = 3,
    corpus: str = "czech",
    answer_type: str = "",
    on_status=None,
    laws: list[str] | None = None,
    cached_query_emb=None,
    doc_ids: list[str] | None = None,
    custom_corpus: str | None = None,
    custom_doc_ids: list[str] | None = None,
) -> list[PageResult]:
    """Simplified retrieval for non-DIFC corpora: hybrid search + cross-encoder reranking.

    For morphologically rich corpora (Czech), BM25 is fused with vector search
    via RRF before cross-encoder reranking.  BM25 uses prefix-based morphological
    query expansion (``build_czech_tsquery``) to capture inflected forms.  For
    other non-DIFC corpora, only vector search is performed.

    answer_type: used for per-type vector candidate pool depth (T-03) and per-type
                 reranker instructions (T-04). Falls back to defaults for unknown types.
    No routing metadata, no DIFC-specific heuristics.
    """
    use_bm25_fusion = corpus in _MORPHOLOGICAL_CORPORA
    logger.debug(
        "[retriever] simple retrieval for corpus=%r answer_type=%r bm25_fusion=%s",
        corpus,
        answer_type,
        use_bm25_fusion,
    )
    if on_status:
        on_status("retrieving:searching corpus")
    query_emb = cached_query_emb if cached_query_emb is not None else embed_query(question)
    # Per-type candidate pool depth for the non-DIFC simple path (T-03).
    # This path only reranks chunks[:40], so fetching >100 candidates is wasteful.
    # Exact-match types (date/number/name) are served well by a tighter pool; the
    # right chunk is almost always in the top-50 by embedding similarity.
    # free_text benefits from broader coverage to catch paraphrased provisions.
    _SIMPLE_TOP_K_BY_TYPE: dict[str, int] = {
        "date": 50,
        "number": 50,
        "name": 50,
        "names": 60,
        "boolean": 75,
        "free_text": 100,
    }
    top_k = min(_SIMPLE_TOP_K_BY_TYPE.get(answer_type, 100), get_chunk_count(corpus=corpus))
    if on_status:
        on_status("retrieving:searching corpus")

    if use_bm25_fusion:
        # Czech: run vector + BM25 (statute chunks) + court decisions concurrently,
        # fuse with RRF for better recall on exact legal terms and court holdings.
        # Each closure creates its own Langfuse child span so timing reflects the
        # actual search duration, not a post-hoc 0ms recording.
        try:
            from neolex.observability import get_current_span
            from neolex.observability import is_enabled as _lf_enabled

            _lf_parent = get_current_span() if _lf_enabled() else None
        except Exception:
            _lf_parent = None

        def _vec():
            try:
                _s = (
                    _lf_parent.start_observation(
                        name="vector-retrieval",
                        as_type="span",
                        input={"corpus": corpus, "top_k": top_k},
                    )
                    if _lf_parent
                    else None
                )
            except Exception:
                _s = None
            result = search_chunks_vector(query_emb, top_k=top_k, corpus=corpus, doc_ids=doc_ids)
            if _s:
                try:
                    _s.update(output={"num_results": len(result["ids"][0]) if result.get("ids") else 0})
                    _s.end()
                except Exception:
                    pass
            return result

        def _bm25():
            try:
                _s = (
                    _lf_parent.start_observation(
                        name="bm25-retrieval",
                        as_type="span",
                        input={"query": question[:_LANGFUSE_INPUT_TRUNCATE], "corpus": corpus, "top_k": top_k},
                    )
                    if _lf_parent
                    else None
                )
            except Exception:
                _s = None
            result = search_chunks_text(question, top_k=top_k, corpus=corpus)
            if _s:
                try:
                    _s.update(output={"num_results": len(result)})
                    _s.end()
                except Exception:
                    pass
            return result

        def _court():
            # Only search court decisions for corpora that have them
            if corpus not in _COURT_DECISION_CORPORA:
                return []
            return _search_court_decisions_sync(question, query_emb, limit=top_k)

        def _custom_vec():
            if not custom_corpus or not custom_doc_ids:
                return None
            return search_chunks_vector(query_emb, top_k=top_k, corpus=custom_corpus, doc_ids=custom_doc_ids)

        _n_workers = 4 if (custom_corpus and custom_doc_ids) else 3
        with ThreadPoolExecutor(max_workers=_n_workers) as executor:
            vec_fut = executor.submit(_vec)
            bm25_fut = executor.submit(_bm25)
            court_fut = executor.submit(_court)
            custom_vec_fut = executor.submit(_custom_vec)
            vector_results = vec_fut.result()
            bm25_chunk_ids = bm25_fut.result()
            court_chunks = court_fut.result()
            custom_vector_results = custom_vec_fut.result()

        # Build chunk lookup from statute vector results (already has text + metadata)
        chunk_by_id: dict[str, dict] = {}
        for i in range(len(vector_results["ids"][0])):
            cid = vector_results["ids"][0][i]
            chunk_by_id[cid] = {
                "chunk_id": cid,
                "text": vector_results["documents"][0][i],
                "metadata": vector_results["metadatas"][0][i],
                "distance": vector_results["distances"][0][i],
            }

        # Add court decisions to chunk lookup (fully populated from _search_court_decisions_sync)
        for cd in court_chunks:
            chunk_by_id[cd["chunk_id"]] = cd

        # RRF fusion: combine statute BM25 + vector signals + court decisions
        # RRF constant k=60 (Cormack et al. 2009)
        _rrf_k = 60
        rrf_scores: dict[str, float] = {}

        # Statute vector signal (weight 0.7 — embedding model handles Czech semantics well)
        for rank, cid in enumerate(vector_results["ids"][0]):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + _RRF_VEC_WEIGHT / (_rrf_k + rank + 1)

        # Statute BM25 signal (weight 0.3 — keyword match for exact legal terms / §-numbers)
        for rank, cid in enumerate(bm25_chunk_ids):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 0.3 / (_rrf_k + rank + 1)

        # Court decisions enter as pre-fused (weight 0.5 — between BM25 and vector weights).
        # Their internal RRF already combines vector + BM25 signals from court_decisions table.
        for rank, cd in enumerate(court_chunks):
            ecli = cd["chunk_id"]
            rrf_scores[ecli] = rrf_scores.get(ecli, 0.0) + 0.5 / (_rrf_k + rank + 1)

        # Custom corpus vector signal (weight 0.7 — same as builtin vector signal).
        # Merges custom corpus documents into the same RRF ranking so they compete
        # uniformly with builtin corpus results through reranking and page assembly.
        if custom_vector_results is not None:
            for i in range(len(custom_vector_results["ids"][0])):
                cid = custom_vector_results["ids"][0][i]
                if cid not in chunk_by_id:
                    chunk_by_id[cid] = {
                        "chunk_id": cid,
                        "text": custom_vector_results["documents"][0][i],
                        "metadata": custom_vector_results["metadatas"][0][i],
                        "distance": custom_vector_results["distances"][0][i],
                    }
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + _RRF_VEC_WEIGHT / (_rrf_k + i + 1)

        # Fetch text/metadata for BM25-only statute hits not in vector results
        bm25_only_ids = [cid for cid in bm25_chunk_ids if cid not in chunk_by_id]
        if bm25_only_ids:
            extra = get_chunks_by_ids(bm25_only_ids, corpus=corpus)
            for cid, text, meta in zip(
                extra.get("ids", []),
                extra.get("documents", []),
                extra.get("metadatas", []),
            ):
                if cid not in chunk_by_id:
                    chunk_by_id[cid] = {"chunk_id": cid, "text": text, "metadata": meta, "distance": 1.0}

        # Sort all candidates by RRF score descending
        fused_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
        chunks = [chunk_by_id[cid] for cid in fused_ids if cid in chunk_by_id]
    else:
        try:
            from neolex.observability import get_current_span
            from neolex.observability import is_enabled as _lf_enabled

            _lf_parent_vec = get_current_span() if _lf_enabled() else None
        except Exception:
            _lf_parent_vec = None

        _vec_span = (
            _lf_parent_vec.start_observation(
                name="vector-retrieval",
                as_type="span",
                input={"corpus": corpus, "top_k": top_k, "mode": "vector-only"},
            )
            if _lf_parent_vec
            else None
        )
        vector_results = search_chunks_vector(query_emb, top_k=top_k, corpus=corpus, doc_ids=doc_ids)
        if _vec_span:
            _vec_span.update(output={"num_results": len(vector_results["ids"][0]) if vector_results.get("ids") else 0})
            _vec_span.end()

        # Hybrid: run custom corpus vector search if present
        custom_vector_results = None
        if custom_corpus and custom_doc_ids:
            custom_vector_results = search_chunks_vector(
                query_emb, top_k=top_k, corpus=custom_corpus, doc_ids=custom_doc_ids
            )

        if custom_vector_results is not None:
            # Merge builtin + custom via RRF (same weights as BM25 fusion path)
            _rrf_k = 60
            rrf_scores: dict[str, float] = {}
            chunk_by_id: dict[str, dict] = {}

            for i in range(len(vector_results["ids"][0])):
                cid = vector_results["ids"][0][i]
                chunk_by_id[cid] = {
                    "chunk_id": cid,
                    "text": vector_results["documents"][0][i],
                    "metadata": vector_results["metadatas"][0][i],
                    "distance": vector_results["distances"][0][i],
                }
                rrf_scores[cid] = _RRF_VEC_WEIGHT / (_rrf_k + i + 1)

            for i in range(len(custom_vector_results["ids"][0])):
                cid = custom_vector_results["ids"][0][i]
                if cid not in chunk_by_id:
                    chunk_by_id[cid] = {
                        "chunk_id": cid,
                        "text": custom_vector_results["documents"][0][i],
                        "metadata": custom_vector_results["metadatas"][0][i],
                        "distance": custom_vector_results["distances"][0][i],
                    }
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + _RRF_VEC_WEIGHT / (_rrf_k + i + 1)

            fused_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
            chunks = [chunk_by_id[cid] for cid in fused_ids if cid in chunk_by_id]
        else:
            chunks = []
            for i in range(len(vector_results["ids"][0])):
                chunks.append(
                    {
                        "chunk_id": vector_results["ids"][0][i],
                        "text": vector_results["documents"][0][i],
                        "metadata": vector_results["metadatas"][0][i],
                        "distance": vector_results["distances"][0][i],
                    }
                )

    # Filter by law prefixes if specified (Czech corpus law selector).
    # Court decisions (source_type == "court_decision") bypass the statute prefix filter —
    # they are indexed by ECLI, not by law doc_id prefix, and are always included.
    if laws:
        law_prefixes = set(laws)
        chunks = [
            c
            for c in chunks
            if c["metadata"].get("source_type") == "court_decision"
            or any(c["metadata"].get("doc_id", "").startswith(p) for p in law_prefixes)
        ]

    # Preserve top fused result before reranking — embedding models handle
    # cross-language queries better than the reranker for non-DIFC corpora.
    vector_top = chunks[0] if chunks else None

    # Build reranking pool (40 chunks max): explicitly mix court decisions with statute
    # chunks so the cross-encoder evaluates both types.  Without this, statute chunks
    # dominate the RRF ranking (they receive contributions from two legs — vector + BM25)
    # and court decisions are never examined by the reranker.
    # Reserve up to 10 of the 40 reranker slots for court decisions.
    _court_chunks = [c for c in chunks if c["metadata"].get("source_type") == "court_decision"]
    _statute_chunks = [c for c in chunks if c["metadata"].get("source_type") != "court_decision"]
    _court_slots = min(10, len(_court_chunks))
    _statute_slots = min(40 - _court_slots, len(_statute_chunks))
    rerank_pool = _statute_chunks[:_statute_slots] + _court_chunks[:_court_slots]

    # Cross-encoder reranking — span wraps actual call for correct timing
    if on_status:
        on_status(f"retrieving:reranking {len(rerank_pool)} passages")
    try:
        from neolex.observability import get_current_span
        from neolex.observability import is_enabled as _lf_enabled

        _lf_rerank_parent = get_current_span() if _lf_enabled() else None
    except Exception:
        _lf_rerank_parent = None

    try:
        _rerank_span = (
            _lf_rerank_parent.start_observation(
                name="reranking",
                as_type="span",
                input={"num_candidates": len(rerank_pool), "answer_type": answer_type},
            )
            if _lf_rerank_parent
            else None
        )
    except Exception:
        _rerank_span = None
    ranked = rerank_chunks(question, rerank_pool, top_k=20, answer_type=answer_type, on_status=on_status)
    if _rerank_span:
        try:
            _rerank_span.update(output={"num_results": len(ranked)})
            _rerank_span.end()
        except Exception:
            pass

    # Aggregate chunks to pages, pick best per (doc_id, page).
    # Value tuple: (score, text, chunk_id, court_meta_dict, start_line, end_line)
    # court_meta_dict is non-empty only for court_decision source_type.
    # start_line/end_line are non-None only for txt source_type.
    page_scores: dict[tuple[str, int], tuple[float, str, str, dict, int | None, int | None]] = {}
    for chunk in ranked:
        doc_id = chunk["metadata"].get("doc_id", chunk["metadata"]["pdf_id"])
        page = int(chunk["metadata"]["page"])
        score = chunk.get("rerank_score", 0.5)
        key = (doc_id, page)
        if key not in page_scores or score > page_scores[key][0]:
            court_meta: dict = {}
            _src = chunk["metadata"].get("source_type")
            if _src == "court_decision":
                court_meta = {
                    k: chunk["metadata"].get(k)
                    for k in (
                        "source_type",
                        "case_number",
                        "ecli",
                        "decision_date",
                        "court",
                        "category",
                        "legal_thesis",
                    )
                }
            elif _src is not None:
                court_meta = {"source_type": _src}
            sl = chunk["metadata"].get("start_line")
            el = chunk["metadata"].get("end_line")
            page_scores[key] = (score, chunk["text"], chunk["metadata"].get("chunk_id", ""), court_meta, sl, el)

    # Inject top fused result if the reranker dropped it — the embedding model's
    # best pick often outperforms the reranker on cross-language queries.
    if vector_top:
        ft_doc = vector_top["metadata"].get("doc_id", vector_top["metadata"]["pdf_id"])
        ft_page = int(vector_top["metadata"]["page"])
        ft_key = (ft_doc, ft_page)
        if ft_key not in page_scores:
            ft_court_meta: dict = {}
            _ft_src = vector_top["metadata"].get("source_type")
            if _ft_src == "court_decision":
                ft_court_meta = {
                    k: vector_top["metadata"].get(k)
                    for k in (
                        "source_type",
                        "case_number",
                        "ecli",
                        "decision_date",
                        "court",
                        "category",
                        "legal_thesis",
                    )
                }
            elif _ft_src is not None:
                ft_court_meta = {"source_type": _ft_src}
            ft_sl = vector_top["metadata"].get("start_line")
            ft_el = vector_top["metadata"].get("end_line")
            page_scores[ft_key] = (
                0.5,
                vector_top["text"],
                vector_top["metadata"].get("chunk_id", ""),
                ft_court_meta,
                ft_sl,
                ft_el,
            )

    # Sort by score descending, apply per-doc and total limits
    sorted_pages = sorted(page_scores.items(), key=lambda x: x[1][0], reverse=True)
    doc_counts: dict[str, int] = {}
    results: list[PageResult] = []
    for (doc_id, page), (score, text, chunk_id, court_meta, start_line, end_line) in sorted_pages:
        if len(results) >= max_total:
            break
        if doc_counts.get(doc_id, 0) >= max_per_doc:
            continue
        doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
        results.append(
            PageResult(
                doc_id=doc_id,
                page_number=page,
                score=score,
                text=text,
                chunk_id=chunk_id,
                source_type=court_meta.get("source_type"),
                case_number=court_meta.get("case_number"),
                ecli=court_meta.get("ecli"),
                decision_date=court_meta.get("decision_date"),
                court=court_meta.get("court"),
                category=court_meta.get("category"),
                legal_thesis=court_meta.get("legal_thesis"),
                start_line=start_line,
                end_line=end_line,
            )
        )

    return results


def retrieve_pages(
    question: str,
    target_doc_ids: list[str] | None = None,
    max_per_doc: int = 1,
    max_total: int = 3,
    answer_type: str = "",
    include_context_pages: bool = False,
    use_llm_rerank: bool = False,
    boost_pages: dict[str, int] | None = None,
    case_doc_groups: dict[str, list[str]] | None = None,
    corpus: str = "difc",
    on_status=None,
    laws: list[str] | None = None,
    doc_ids: list[str] | None = None,
    custom_corpus: str | None = None,
    custom_doc_ids: list[str] | None = None,
) -> list[PageResult]:
    """Retrieve the best pages for answering a question.

    Pipeline (when all features enabled):
      1. Targeted cross-encoder ranking over all chunks in target docs (in-memory)
         OR full-corpus hybrid BM25 + vector retrieval for unknown target docs
      2. [Optional] LLM reranking: Haiku judges each candidate page's relevance
         (Enterprise RAG winner: 70% LLM + 30% cross-encoder weighted score)
      3. [Optional] Adjacent page expansion: add N-1 and N+1 page context text
         (CRAG winner's parent-child chunk concept applied to pages)

    Parameters
    ----------
    target_doc_ids : list[str] | None
        Documents to search within. None triggers full-corpus hybrid retrieval.
    max_per_doc : int
        Maximum pages to return per document.
    max_total : int
        Maximum total pages across all documents.
    answer_type : str
        Question answer type (affects metadata-question heuristics).
    include_context_pages : bool
        If True, expand each page's text with adjacent pages for completeness.
    use_llm_rerank : bool
        If True, apply LLM reranking after cross-encoder (adds one Haiku call).
        Enterprise RAG winner used this as their highest-impact strategy.
    corpus : str
        Corpus to search. "difc" (default) or "czech".
    """
    # Pre-compute query embedding ONCE to avoid redundant HTTP calls to
    # the embedding server (~3s each). Threaded to all sub-functions.
    # HyDE and query variant embeddings use different text — not cached here.
    _question_emb = embed_query(question)

    # ── Non-DIFC corpus: simplified vector-only retrieval path ──
    # Czech and other non-DIFC corpora use pgvector search + cross-encoder reranking.
    # They don't have routing metadata or DIFC-specific heuristics.
    if corpus != "difc":
        return _retrieve_pages_simple(
            question,
            max_per_doc,
            max_total,
            corpus=corpus,
            answer_type=answer_type,
            on_status=on_status,
            laws=laws,
            cached_query_emb=_question_emb,
            doc_ids=doc_ids,
            custom_corpus=custom_corpus,
            custom_doc_ids=custom_doc_ids,
        )

    # Per-type configs inspired by IAS Partners dual-pipeline (guy4)
    # Apply per-answer-type retrieval config if available, using caller's values as overrides
    type_cfg = RETRIEVAL_CONFIGS.get(answer_type, {})
    if type_cfg:
        # Only apply config defaults when caller used the function defaults
        if max_per_doc == 1 and "max_docs" in type_cfg:
            pass  # max_per_doc is per-doc pages, not max_docs — leave as caller set
        if max_total == 3 and "max_pages" in type_cfg:
            max_total = type_cfg["max_pages"]

    if target_doc_ids:
        if on_status:
            on_status(f"retrieving:searching {len(target_doc_ids)} target docs")
        effective_mpd = max_per_doc
        if (
            answer_type in ("name", "names")
            and boost_pages
            and len(target_doc_ids) == 2
            and all(d in boost_pages for d in target_doc_ids)
            and any(boost_pages[d] != 1 for d in target_doc_ids)
        ):
            effective_mpd = 1
        results = _retrieve_pages_targeted(
            question,
            target_doc_ids,
            effective_mpd,
            max_total,
            answer_type,
            boost_pages=boost_pages,
            case_doc_groups=case_doc_groups,
            on_status=on_status,
            cached_query_emb=_question_emb,
        )
        best_score = max((r.score for r in results), default=0.0)
        if best_score < 0.4:
            if on_status:
                on_status("retrieving:broadening search")
            logger.debug("[retriever] low-confidence targeted (%.3f < 0.40), adding fallback", best_score)
            fb_results = _retrieve_pages_fallback(
                question,
                max_per_doc=1,
                max_total=1,
                answer_type=answer_type,
                cached_query_emb=_question_emb,
            )
            seen = {}
            for r in results + fb_results:
                key = (r.doc_id, r.page_number)
                if key not in seen or r.score > seen[key].score:
                    seen[key] = r
            results = sorted(seen.values(), key=lambda p: p.score, reverse=True)[:max_total]
    else:
        if on_status:
            on_status("retrieving:searching corpus")
        # Multi-signal doc fusion: identify best candidate docs using 5 signals
        # (BM25-std, dense-std, dense-RRF, BM25-doc, BM25-page1) via RRF, then
        # run cross-encoder reranking within the selected docs.
        # This is superior to _retrieve_pages_fallback (inverse-rank scoring, no CE)
        # and recovers the _doc_fusion_select dead code path (disabled since pgvector migration).
        # corpus is forwarded; non-DIFC corpora never reach here (they return early above).
        fusion_docs = _doc_fusion_select(
            question,
            max_docs=type_cfg.get("max_docs", 3),
            answer_type=answer_type,
            cached_query_emb=_question_emb,
            corpus=corpus,
        )
        if fusion_docs:
            if on_status:
                on_status(f"retrieving:doc fusion selected {len(fusion_docs)} docs")
            results = _retrieve_pages_targeted(
                question,
                fusion_docs,
                max_per_doc,
                max_total,
                answer_type,
                on_status=on_status,
                cached_query_emb=_question_emb,
            )
            if not results:
                # Targeted retrieval found nothing — fall back to hybrid
                results = _retrieve_pages_fallback(
                    question,
                    max_per_doc,
                    max_total,
                    answer_type,
                    cached_query_emb=_question_emb,
                )
        else:
            results = _retrieve_pages_fallback(
                question,
                max_per_doc,
                max_total,
                answer_type,
                cached_query_emb=_question_emb,
            )

    # ── Hybrid mode: merge custom corpus results into DIFC results ──
    # When both a builtin DIFC jurisdiction and a custom corpus are selected,
    # the DIFC-specific paths above (targeted / doc-fusion) only search the
    # builtin corpus.  Search the custom corpus separately and merge via RRF
    # so custom documents compete fairly with DIFC results through reranking.
    # Non-DIFC corpora handle this inside _retrieve_pages_simple.
    if custom_corpus and custom_doc_ids:
        if on_status:
            on_status("retrieving:searching custom corpus")
        # top_k=50: conservative candidate pool for custom corpus — matches the lower
        # bound of _SIMPLE_TOP_K_BY_TYPE (date/number/name types); we don't have
        # answer_type-specific tuning for custom corpora yet so a single conservative
        # value is used to cap reranker latency without sacrificing recall.
        custom_vector = search_chunks_vector(_question_emb, top_k=50, corpus=custom_corpus, doc_ids=custom_doc_ids)
        if custom_vector and custom_vector.get("ids") and custom_vector["ids"][0]:
            custom_chunks = [
                {
                    "chunk_id": custom_vector["ids"][0][i],
                    "text": custom_vector["documents"][0][i],
                    "metadata": custom_vector["metadatas"][0][i],
                    "distance": custom_vector["distances"][0][i],
                }
                for i in range(len(custom_vector["ids"][0]))
            ]
            # 40 chunks: reranker pool cap, same as _retrieve_pages_simple; fetching
            # more candidates yields diminishing returns at significant latency cost.
            custom_ranked = rerank_chunks(
                question, custom_chunks[:40], top_k=20, answer_type=answer_type, on_status=on_status
            )
            # Convert custom ranked chunks to PageResults
            custom_page_map: dict[tuple[str, int], tuple[float, str, str, str | None, int | None, int | None]] = {}
            for chunk in custom_ranked:
                doc_id = chunk["metadata"].get("doc_id", chunk["metadata"].get("pdf_id", ""))
                page = int(chunk["metadata"]["page"])
                score = chunk.get("rerank_score", 0.5)
                key = (doc_id, page)
                if key not in custom_page_map or score > custom_page_map[key][0]:
                    custom_page_map[key] = (
                        score,
                        chunk["text"],
                        chunk["metadata"].get("chunk_id", ""),
                        chunk["metadata"].get("source_type"),
                        chunk["metadata"].get("start_line"),
                        chunk["metadata"].get("end_line"),
                    )
            custom_page_results = [
                PageResult(
                    doc_id=did,
                    page_number=pg,
                    score=sc,
                    text=tx,
                    chunk_id=cid,
                    source_type=st,
                    start_line=sl,
                    end_line=el,
                )
                for (did, pg), (sc, tx, cid, st, sl, el) in sorted(
                    custom_page_map.items(), key=lambda x: x[1][0], reverse=True
                )
            ]
            # Merge DIFC + custom results via RRF (k=60, equal weight)
            _rrf_k = 60
            merged_scores: dict[tuple[str, int], float] = {}
            all_by_key: dict[tuple[str, int], PageResult] = {}
            for rank, r in enumerate(results):
                key = (r.doc_id, r.page_number)
                merged_scores[key] = merged_scores.get(key, 0.0) + 1.0 / (_rrf_k + rank + 1)
                all_by_key[key] = r
            for rank, r in enumerate(custom_page_results):
                key = (r.doc_id, r.page_number)
                merged_scores[key] = merged_scores.get(key, 0.0) + 1.0 / (_rrf_k + rank + 1)
                if key not in all_by_key:
                    all_by_key[key] = r
            merged_keys = sorted(merged_scores, key=lambda k: merged_scores[k], reverse=True)
            # Apply per-doc and total limits on merged results
            doc_counts: dict[str, int] = {}
            merged_results: list[PageResult] = []
            for k in merged_keys:
                if len(merged_results) >= max_total:
                    break
                r = all_by_key[k]
                if doc_counts.get(r.doc_id, 0) >= max_per_doc:
                    continue
                doc_counts[r.doc_id] = doc_counts.get(r.doc_id, 0) + 1
                merged_results.append(r)
            results = merged_results

    if on_status and results:
        on_status(f"retrieving:found {len(results)} pages")

    if use_llm_rerank and len(results) > 1:
        from arlc.llm.reranker import llm_rerank_pages

        results = llm_rerank_pages(question, results)

    if include_context_pages:
        results = _expand_with_adjacent_pages(results)

    return results


def _fair_case_select(
    pages: list["PageResult"],
    case_doc_groups: dict[str, list[str]],
    max_total: int,
) -> list["PageResult"]:
    """Select pages ensuring at least 1 page per case group.

    Takes top page from each case first (by score), then fills remaining slots
    with highest-scoring remaining pages. Prevents one case's high-scoring docs
    from crowding out the other case entirely.
    """
    # Map doc_id -> case_id
    doc_to_case: dict[str, str] = {}
    for case_id, doc_ids in case_doc_groups.items():
        for doc_id in doc_ids:
            doc_to_case[doc_id] = case_id

    # Group pages by case (already sorted by score descending)
    case_pages: dict[str, list] = {c: [] for c in case_doc_groups}
    unclassified: list = []
    for p in pages:
        case = doc_to_case.get(p.doc_id)
        if case is not None:
            case_pages[case].append(p)
        else:
            unclassified.append(p)

    # Phase 1: take top page from each case
    selected: list = []
    seen: set = set()
    pool: list = []
    for case_id in case_doc_groups:
        if case_pages[case_id] and len(selected) < max_total:
            top = case_pages[case_id][0]
            selected.append(top)
            seen.add((top.doc_id, top.page_number))
            pool.extend(case_pages[case_id][1:])
        else:
            pool.extend(case_pages[case_id])

    # Phase 2: fill remaining slots by score
    pool.extend(unclassified)
    pool.sort(key=lambda p: p.score, reverse=True)
    for p in pool:
        if len(selected) >= max_total:
            break
        key = (p.doc_id, p.page_number)
        if key not in seen:
            selected.append(p)
            seen.add(key)

    selected.sort(key=lambda p: p.score, reverse=True)
    return selected


def _dense_page_scores(
    question: str,
    doc_id: str,
    chunks: list[dict],
    cached_query_emb=None,
    corpus: str = "difc",
) -> dict[int, float]:
    """Rank pages within a document using dense embedding similarity only.

    # Dense-only page ranking insight from IAS Partners (guy4)
    Returns dict of page_number -> max_similarity_score.

    Uses pgvector inner product on pre-stored embeddings instead of
    re-embedding through the model. For a 389-chunk document this
    reduces scoring time from 334+ seconds to <0.1 seconds.

    cached_query_emb: pre-computed query embedding to avoid redundant
    embed_query() calls when scoring multiple documents for the same question.
    """
    if not chunks:
        return {}

    query_emb = cached_query_emb if cached_query_emb is not None else embed_query(question)
    vec_literal = "[" + ",".join(str(float(x)) for x in query_emb) + "]"

    chunk_ids = [c.get("chunk_id") for c in chunks if c.get("chunk_id")]
    if not chunk_ids:
        return {}

    engine = _get_sync_engine()
    with SASession(engine) as session:
        rows = session.execute(
            sa_text("""
            SELECT chunk_id, page, (embedding <#> cast(:vec as vector)) * -1 AS similarity
            FROM chunks
            WHERE chunk_id = ANY(:ids)
        """),
            {"vec": vec_literal, "ids": chunk_ids},
        ).fetchall()

    page_scores: dict[int, float] = {}
    for row in rows:
        if row.page not in page_scores or row.similarity > page_scores[row.page]:
            page_scores[row.page] = float(row.similarity)

    return page_scores


def _retrieve_pages_targeted(
    question: str,
    target_doc_ids: list[str],
    max_per_doc: int,
    max_total: int,
    answer_type: str,
    boost_pages: dict[str, int] | None = None,
    case_doc_groups: dict[str, list[str]] | None = None,
    on_status=None,
    cached_query_emb=None,
) -> list[PageResult]:
    """Retrieve pages by reranking all chunks from target documents."""
    # Small-doc full inclusion: for documents with ≤8 pages, skip reranking and
    # return all pages. Avoids cross-encoder mistakes on short documents where a
    # wrong page choice is particularly costly. (Inspired by Vitaliy Pokrovskiy, 3rd place)
    SMALL_DOC_THRESHOLD = int(os.environ.get("SMALL_DOC_PAGES", "8"))
    chunks_by_doc_map = get_chunks_by_doc()
    ranker = get_reranker()

    # Per-type reranker instruction: use answer-type-specific prefix for Qwen3-Reranker.
    # Computed once here and reused for both dense and BM25 reranking paths below.
    _rr_instruction = RERANKER_INSTRUCTIONS_BY_TYPE.get(answer_type, RERANKER_INSTRUCTION)

    # Detect metadata questions (date, judge, claimant) that are answered on page 1
    is_metadata_q = answer_type in ("date", "name") and bool(_METADATA_QUESTION_PATTERNS.search(question))

    # Detect date-related questions regardless of answer_type (e.g. "which doc has
    # the earlier issue date?" has answer_type=name but needs the date page).
    _is_date_question = bool(
        re.search(
            r"\b(date of issue|issue date|issued|earlier.*date|later.*date)\b",
            question,
            re.IGNORECASE,
        ),
    )

    # Extract article root numbers for content-based definition page boost.
    # Acts as a fallback when the router's article_page_index doesn't have a mapping.
    # Only detects article DEFINITION headers (e.g., "13.\nTitle"), not references.
    # Skip when question asks about fines/penalties — the answer is in a schedule,
    # not the article definition page.
    _asks_fine = bool(
        re.search(r"\b(fine|penalty|penalt|sanction|contravene|contravention)\b", question, re.IGNORECASE),
    )
    _art_root_nums = list(set(re.findall(r"Article\s+(\d+)", question, re.IGNORECASE))) if not _asks_fine else []

    # Law-title-page boost: "What is the law number / official number of X?"
    # Law numbers (e.g. "DIFC LAW NO. 5 OF 2020") appear on the title page (p1/p2).
    # CE over-ranks body articles (e.g. "cited as 'X Law'") vs the title page.
    # Strong +1.2 boost to p1 overrides CE preference for body text on this pattern.
    _asks_law_number = bool(
        re.search(
            r"\b(?:law\s+number|official\s+number|law\s+no\.?\s+of|numbered)\b",
            question,
            re.IGNORECASE,
        ),
    )

    # Detect outcome questions for targeted page boost (mirrors _prescore_keyword_chunks)
    _asks_outcome_q = any(kw in question.lower() for kw in _OUTCOME_QUESTION_KEYWORDS)
    # Award-value detection: comparison questions about arbitral/judgment award amounts
    _asks_award_value = bool(
        re.search(
            r"\bhigher\b.*\baward\b|\baward\b.*\bvalue\b",
            question,
            re.IGNORECASE,
        ),
    )
    # Cleaned CE query: strips long case names (≥25 chars before "[YEAR] DIFC TYPE NUM")
    # that bias the cross-encoder toward title pages. In targeted retrieval the doc is
    # already identified so the case name is redundant; removing it lets CE focus on
    # the semantic "what/why" portion of the question.
    _ce_query = _clean_query_for_ce(question)
    if _ce_query != question:
        logger.debug("[retriever] CE query cleaned: '%s'", _ce_query[:80])

    all_page_scores: list[PageResult] = []

    def _rerank_progress(done, total):
        if on_status:
            on_status(f"retrieving:reranking passages ({done}/{total})")

    # Per-type BM25: use dense-only for free_text/boolean (IAS Partners empirical finding —
    # BM25 hurts page-level ranking for semantic types), BM25 path for exact-match types
    # (date/number/name/names) where lexical signals dominate over semantic similarity.
    _page_rank_bm25 = PAGE_RANK_USE_BM25 and answer_type in ("date", "number", "name", "names")

    # Pre-cache query embedding and BM25 tokenization before the per-document
    # loop. Both are pure functions of `question` — recomputing inside the loop
    # wastes ~200ms per document on embedding and ~50ms on tokenization.
    if not _page_rank_bm25:
        _cached_query_emb = cached_query_emb if cached_query_emb is not None else embed_query(question)
    else:
        _cached_query_emb = None
    # (BM25 tokenization no longer needed — text search runs in PostgreSQL)

    if on_status:
        on_status(f"retrieving:scoring {len(target_doc_ids)} documents")

    for i_doc, doc_id in enumerate(target_doc_ids):
        if on_status:
            on_status(f"retrieving:scoring document {i_doc + 1}/{len(target_doc_ids)}")
        doc_chunks = chunks_by_doc_map.get(doc_id, [])
        if not doc_chunks:
            continue

        # Small-doc full inclusion: return ALL pages for short documents
        # to avoid cross-encoder selection errors on docs where every page matters.
        unique_pages = set(c["metadata"].get("page", 1) for c in doc_chunks)
        if len(unique_pages) <= SMALL_DOC_THRESHOLD:
            for pg in sorted(unique_pages):
                # Find the chunk with most text for this page
                best_chunk = max(
                    (c for c in doc_chunks if c["metadata"].get("page", 1) == pg),
                    key=lambda c: len(c.get("text", "")),
                )
                all_page_scores.append(
                    PageResult(
                        doc_id=doc_id,
                        page_number=pg,
                        score=1.0,  # all pages equally scored for small docs
                        text=best_chunk.get("text", ""),
                        chunk_id=best_chunk.get("chunk_id", ""),
                    ),
                )
            logger.debug("[retriever] small-doc full inclusion: %s (%d pages)", doc_id[:12], len(unique_pages))
            continue

        # Per-type page ranking: dense-only for free_text/boolean (IAS Partners insight),
        # BM25 path for exact-match types (date/number/name/names).
        if not _page_rank_bm25:
            # Phase 1: Dense similarity scoring for all chunks
            dense_scores = _dense_page_scores(question, doc_id, doc_chunks, cached_query_emb=_cached_query_emb)
            # Phase 2: Select top candidate chunks by dense score, then cross-encoder rerank
            chunk_dense = []
            for chunk in doc_chunks:
                pg = chunk["metadata"].get("page", 1)
                chunk_dense.append((dense_scores.get(pg, 0.0), chunk))
            chunk_dense.sort(key=lambda x: x[0], reverse=True)
            # Adaptive CE pre-filter: scale pool with doc size (Technique 5).
            # Formula: min(100, max(50, n_chunks // 2)) — covers ~half of medium docs,
            # caps at 100 to keep Qwen3-Reranker-0.6B latency acceptable.
            if CE_ADAPTIVE_PREFILTER:
                _ce_pool_size = min(100, max(50, len(chunk_dense) // 2))
            else:
                _ce_pool_size = 50
            top_chunks = [c for _, c in chunk_dense[:_ce_pool_size]]

            # Text search injection: rescue pages with strong lexical signal that dense
            # de-ranked (Technique 2). Query PostgreSQL tsvector within this doc,
            # inject up to BM25_INJECTION_K candidates not already in the dense pool.
            # CE still provides all final scores — text search only expands the candidate set.
            # Only run injection when the CE pool doesn't already cover
            # all document chunks — if it does, injection can't add anything new.
            if PAGE_RANK_BM25_INJECTION and _ce_pool_size < len(doc_chunks):
                try:
                    _pool_cid_set = {c["chunk_id"] for c in top_chunks}
                    _cid_to_chunk = {c["chunk_id"]: c for c in doc_chunks}
                    _text_hits = _search_chunks_text_for_doc(
                        question,
                        pdf_id=doc_id,
                        corpus="difc",
                        top_k=BM25_INJECTION_K * 4,
                    )
                    _injected = 0
                    for _cid in _text_hits:
                        if _injected >= BM25_INJECTION_K:
                            break
                        if _cid in _cid_to_chunk and _cid not in _pool_cid_set:
                            top_chunks.append(_cid_to_chunk[_cid])
                            _pool_cid_set.add(_cid)
                            _injected += 1
                except Exception as _inj_err:  # nosec B110
                    pass  # Injection is best-effort; never block page scoring

            pairs = _format_reranker_pairs(
                [(_ce_query, chunk["text"][:1500]) for chunk in top_chunks],
                instruction=_rr_instruction,
            )
            if on_status:
                on_status(f"retrieving:reranking {len(pairs)} passages")
            try:
                ce_scores = ranker.predict(pairs, timeout=180, on_progress=_rerank_progress)
            except Exception as e:
                local = get_local_reranker()
                if local is not ranker:
                    _demote_remote_reranker()
                    logger.warning("Remote reranking failed for %s (%s), falling back to local", doc_id, e)
                    if on_status:
                        on_status("retrieving:reranking passages")
                    try:
                        ce_scores = local.predict(pairs, timeout=180, on_progress=_rerank_progress)
                    except Exception as e2:
                        logger.warning("Local reranking also failed for %s (%s), using dense scores", doc_id, e2)
                        ce_scores = [dense_scores.get(c["metadata"].get("page", 1), 0.0) for c in top_chunks]
                else:
                    logger.warning("Targeted reranking failed for %s: %s, using dense scores only", doc_id, e)
                    if on_status:
                        on_status("retrieving:scoring results")
                    ce_scores = [dense_scores.get(c["metadata"].get("page", 1), 0.0) for c in top_chunks]
            # Merge: use cross-encoder scores for the top candidates
            page_scores: dict[int, float] = {}
            page_chunk_ids: dict[int, str] = {}
            for chunk, score in zip(top_chunks, ce_scores):
                page_num = chunk["metadata"].get("page", 1)
                score_val = float(score)
                if page_num not in page_scores or score_val > page_scores[page_num]:
                    page_scores[page_num] = score_val
                    page_chunk_ids[page_num] = chunk.get("chunk_id", "")
        else:
            # Original: Score all chunks against the question using cross-encoder
            # Use 4000 chars to match reranker context window (-c 4096) and capture full legal context
            # Use _ce_query (long case names removed) so CE focuses on semantics, not party names
            pairs = _format_reranker_pairs(
                [(_ce_query, chunk["text"][:1500]) for chunk in doc_chunks],
                instruction=_rr_instruction,
            )
            if on_status:
                on_status(f"retrieving:reranking {len(pairs)} passages")
            try:
                scores = ranker.predict(pairs, timeout=180, on_progress=_rerank_progress)
            except Exception as e:
                local = get_local_reranker()
                if local is not ranker:
                    _demote_remote_reranker()
                    logger.warning("Remote reranking failed for %s (%s), falling back to local", doc_id, e)
                    if on_status:
                        on_status("retrieving:reranking passages")
                    try:
                        scores = local.predict(pairs, timeout=180, on_progress=_rerank_progress)
                    except Exception as e2:
                        logger.warning("Local reranking also failed for %s (%s), using uniform scores", doc_id, e2)
                        scores = [0.5] * len(doc_chunks)
                else:
                    logger.warning("Targeted reranking failed for %s: %s, using uniform scores", doc_id, e)
                    if on_status:
                        on_status("retrieving:scoring results")
                    scores = [0.5] * len(doc_chunks)
            page_scores: dict[int, float] = {}
            page_chunk_ids: dict[int, str] = {}
            for chunk, score in zip(doc_chunks, scores):
                page_num = chunk["metadata"].get("page", 1)
                score_val = float(score)
                if page_num not in page_scores or score_val > page_scores[page_num]:
                    page_scores[page_num] = score_val
                    page_chunk_ids[page_num] = chunk.get("chunk_id", "")

        # CE cluster guard: when many pages from the same document score within a
        # narrow high band (CE can't discriminate), text search identifies pages
        # that actually contain the query's substantive terms and boosts them above
        # the early-occurrence bonus that otherwise selects title/TOC pages first.
        #
        # Trigger: ≥ (max_per_doc × 2 + 2) pages score within 5% of top CE score.
        # This catches large statute documents where every page mentions the law
        # name, making most CE scores cluster near 0.95–1.0.
        # For case-law documents, CE typically separates 2–3 relevant pages from
        # the rest — the cluster size stays below the threshold, so this guard
        # does not fire and the regular page-gap logic applies undisturbed.
        _ce_top = max(page_scores.values(), default=0.0)
        _CE_CLUSTER_BAND = float(os.environ.get("CE_CLUSTER_BAND", "0.05"))
        _CE_CLUSTER_TRIGGER = max_per_doc * 2 + 2

        _pages_in_band = sum(1 for sc in page_scores.values() if sc >= _ce_top * (1.0 - _CE_CLUSTER_BAND))

        if _pages_in_band >= _CE_CLUSTER_TRIGGER and _ce_top > 0.50:
            logger.debug(
                "[retriever] CE cluster guard triggered for %s: %d pages within %.0f%% of "
                "top score %.4f (threshold %d), applying within-doc text search boost",
                doc_id[:12],
                _pages_in_band,
                _CE_CLUSTER_BAND * 100,
                _ce_top,
                _CE_CLUSTER_TRIGGER,
            )
            try:
                _cid_to_page = {c["chunk_id"]: c["metadata"].get("page", 1) for c in doc_chunks}
                _cluster_hits = _search_chunks_text_for_doc_or(
                    question,
                    pdf_id=doc_id,
                    corpus="difc",
                    top_k=6,
                )
                _cluster_seen: set[int] = set()
                # Boost: text rank 0 → +0.06, rank 1 → +0.055, etc., flooring at 0.02
                # The boost is calibrated to overcome the early-occurrence bonus (+0.02/page_num)
                # that would otherwise always select early pages when CE scores are flat.
                _CLUSTER_BOOST_BASE = 0.06
                _CLUSTER_BOOST_STEP = 0.005
                _CLUSTER_BOOST_MIN = 0.02
                for _cl_rank, _cl_cid in enumerate(_cluster_hits):
                    _cl_pg = _cid_to_page.get(_cl_cid)
                    if _cl_pg is not None and _cl_pg in page_scores and _cl_pg not in _cluster_seen:
                        _boost = max(
                            _CLUSTER_BOOST_MIN,
                            _CLUSTER_BOOST_BASE - _cl_rank * _CLUSTER_BOOST_STEP,
                        )
                        page_scores[_cl_pg] += _boost
                        _cluster_seen.add(_cl_pg)
                        logger.debug(
                            "[retriever] cluster boost: p%d +%.3f (text rank %d)",
                            _cl_pg,
                            _boost,
                            _cl_rank,
                        )
            except Exception as _cl_err:  # nosec B110
                logger.debug("[retriever] CE cluster text boost failed: %s", _cl_err)

        # Track which pages contain article DEFINITION headers.
        _art_def_pages: set[int] = set()
        _has_router_boost = bool(boost_pages and doc_id in boost_pages)
        if _art_root_nums and not _has_router_boost:
            for chunk in doc_chunks:
                page_num = chunk["metadata"].get("page", 1)
                chunk_text = chunk["text"]
                for art_num in _art_root_nums:
                    if re.search(rf"(?:^|\n)\s*{re.escape(art_num)}\.\s*\n", chunk_text):
                        _art_def_pages.add(page_num)
                    elif re.search(rf"(?:^|\n)\s*(?:Article|ARTICLE)\s+{re.escape(art_num)}\s*[\n(]", chunk_text):
                        _art_def_pages.add(page_num)

        # Outcome page boost: when question asks about outcomes, boost pages with outcome
        # language (IT IS HEREBY ORDERED THAT, appeal allowed, etc.).
        # This mirrors _prescore_keyword_chunks logic, which only runs in retrieve() (chunk
        # path) but NOT here in _retrieve_pages_targeted. Without this, the CE over-ranks
        # title pages for outcome questions (e.g. CA 003 page 2 "The Appeal is allowed"
        # ranked #19 while page 1 title scored 0.49).
        if _asks_outcome_q:
            _outcome_boosted: set[int] = set()
            for chunk in doc_chunks:
                pg = chunk["metadata"].get("page", 1)
                if pg in _outcome_boosted:
                    continue
                chunk_lower = chunk["text"].lower()
                if chunk["metadata"].get("chunk_type") == "order":
                    page_scores[pg] = page_scores.get(pg, 0.0) + 0.5
                    _outcome_boosted.add(pg)
                elif any(kw in chunk_lower for kw in _OUTCOME_CHUNK_KEYWORDS):
                    page_scores[pg] = page_scores.get(pg, 0.0) + 0.35
                    _outcome_boosted.add(pg)

        # Award-value boost: comparison questions about arbitral/judgment award amounts
        # need deeper background pages (where the actual monetary figures appear), not the
        # title page. Boost pages with explicit monetary amounts (EUR/USD/AED + digits).
        if _asks_award_value:
            _award_boosted: set[int] = set()
            for chunk in doc_chunks:
                pg = chunk["metadata"].get("page", 1)
                if pg not in _award_boosted and re.search(r"(?:EUR|USD|AED|GBP)\s+[\d,]+", chunk["text"]):
                    page_scores[pg] = page_scores.get(pg, 0.0) + 0.30
                    _award_boosted.add(pg)

        # Apply bonuses
        # For date questions, look up the actual page of date_of_issue from the
        # metadata index (usually page 2, not page 1). Judge/claimant/defendant
        # are almost always page 1, so name questions keep the page-1 boost.
        if is_metadata_q and (answer_type == "date" or _is_date_question):
            meta_target_page = _DOC_DATE_PAGES.get(doc_id, 1)
        else:
            meta_target_page = 1  # safe default for name/other metadata questions

        for page_num in page_scores:
            # Earliest occurrence bonus: slight preference for earlier pages
            # (humans annotate the first sufficient page)
            page_scores[page_num] += 0.02 / page_num

            # Metadata boost: apply to the specific page that holds the
            # requested metadata, not blindly to page 1.
            # +0.8 for date questions (must override strong page-1 cross-encoder bias),
            # +0.6 for other metadata questions.
            if is_metadata_q and page_num == meta_target_page:
                page_scores[page_num] += 0.8 if _is_date_question else 0.6
            # Demote page 1 when we know the date is on a different page
            elif _is_date_question and meta_target_page != 1 and page_num == 1:
                page_scores[page_num] -= 0.3

            # Article page boost: if router identified a specific article page for this doc,
            # apply +0.6 boost. Needs to be strong enough to override cross-encoder preference
            # for nearby pages. +0.6 > delta between p.7 (0.38 raw) and p.29 (0.87) for Art.14.
            # For name/names comparison questions targeting a non-p1 page (e.g. claim value on p2),
            # use a stronger +1.0 boost since p1 (case header) typically scores ~0.85 pts higher.
            if boost_pages and doc_id in boost_pages and page_num == boost_pages[doc_id]:
                _boost_amt = 1.2 if (answer_type in ("name", "names") and boost_pages[doc_id] != 1) else 0.6
                page_scores[page_num] += _boost_amt

            # Content-based article definition boost (fallback only).
            # When the router's article_page_index doesn't cover this doc/article,
            # boost pages where the article header is defined (e.g., "13.\nTitle").
            # Moderate +0.3 so the cross-encoder can still override for edge cases.
            if _art_root_nums and not _has_router_boost and page_num in _art_def_pages:
                page_scores[page_num] += 0.3

            # Law-title-page boost: "law number"/"official number" questions need p1.
            # CE often prefers body pages that cite the law name ("cited as 'X Law'")
            # over the title page which has the actual law number ("DIFC LAW NO. 5 OF 2020").
            # Strong +1.2 on p1 ensures the title page wins for these questions.
            if _asks_law_number and page_num == 1:
                page_scores[page_num] += 1.2

            # Schedule/fines page boost: when the question asks about fines or
            # penalties, boost pages containing the actual SCHEDULE heading with
            # fines table (not pages that merely reference "Schedule 2").
            if _asks_fine:
                for ch in doc_chunks:
                    if ch["metadata"].get("page", 1) == page_num:
                        ct = ch["text"][:300]
                        # Match schedule/appendix headings that contain fines tables.
                        # Pattern expanded to cover variations found in corpus:
                        # - "SCHEDULE 2\nCONTRAVENTIONS AND FINES" (Employment Law)
                        # - "SCHEDULE 3\nFINES AND FEES" (Foundations Law)
                        # - "SCHEDULE 3\nFINES" (IP Law)
                        # - "APPENDIX\nFINES" (other laws)
                        _is_fine_schedule = bool(
                            re.search(r"SCHEDULE\s+\d+\s*\n\s*(?:CONTRAVENTIONS\s+AND\s+)?FINES", ct, re.IGNORECASE)
                            or re.search(r"SCHEDULE\s+\d+\s*\n\s*FINES\s+AND\s+FEES", ct, re.IGNORECASE)
                            or (
                                re.search(r"^SCHEDULE\s+\d+", ct, re.IGNORECASE)
                                and re.search(r"\bFINES?\b", ct[:200], re.IGNORECASE)
                            ),
                        )
                        if _is_fine_schedule:
                            page_scores[page_num] += 0.8  # +0.8 (vs +0.4): must beat router's +0.6 article boost
                            break

        # Title page demotion: page 1 often wins on keywords (case name, parties)
        # but gold answers point to content pages.  If page 1 is top-ranked and a
        # deeper page is within 0.15, demote page 1 below it.
        # Apply to all non-metadata questions EXCEPT when boost_pages explicitly targets p1
        # (e.g. defendants/claimants questions where p1 IS the answer page).
        _p1_is_boosted = bool(boost_pages and doc_id in boost_pages and boost_pages[doc_id] == 1)
        _demotion_types = {"free_text", "number", "date", "name", "names"}
        if (
            answer_type in _demotion_types
            and not is_metadata_q
            and not _p1_is_boosted
            and 1 in page_scores
            and len(page_scores) > 1
        ):
            p1_score = page_scores[1]
            best_deep = max(
                ((pn, sc) for pn, sc in page_scores.items() if pn > 1),
                key=lambda x: x[1],
                default=None,
            )
            if best_deep and p1_score > best_deep[1] and (p1_score - best_deep[1]) < 0.15:
                # Swap: push page 1 just below the best deep page
                page_scores[1] = best_deep[1] - 0.001
                logger.debug(
                    "[retriever] title-page demotion: p1 (%.3f) demoted below p%d (%.3f)",
                    p1_score,
                    best_deep[0],
                    best_deep[1],
                )

        # Skip docs where the best page scores near-zero: routing false-positives
        # that got included (e.g. a law doc cited in the case but not the primary doc).
        # Cross-encoder score < 0.10 on all pages means no relevant content found.
        # Raised from 0.05 → 0.10: companion docs at 0.06 were contaminating results.
        if max(page_scores.values(), default=0.0) < 0.10:
            continue

        # Select top pages using score-gap analysis.
        # Threshold by answer type:
        #   number/name/names: 0.80 — almost always 1 page per doc; tight gap prevents
        #     extra pages (p1 title scores ~65-75% of content page, now filtered out)
        #   boolean: 0.65 — previously 0.45 was too loose, got p1+p2 when gold=p1 only
        #   date: 0.75 — date is on a specific page; second page is nearly always noise
        #   free_text: 0.60 — content may span 2 pages; keep looser threshold
        if answer_type in ("number", "name", "names"):
            _gap_threshold = 0.80
        elif answer_type == "boolean":
            _gap_threshold = 0.65
        elif answer_type == "date":
            _gap_threshold = 0.75
        else:
            _gap_threshold = 0.60  # free_text
        sorted_pages = sorted(page_scores.items(), key=lambda x: x[1], reverse=True)
        _selected_count = 0
        for i, (page_num, score) in enumerate(sorted_pages):
            if _selected_count >= max_per_doc:
                break
            # After first page, only include if score >= threshold of top page.
            # Multi-page answers have similar scores; single-page have a big drop.
            if i > 0 and sorted_pages[0][1] > 0:
                if score / sorted_pages[0][1] < _gap_threshold:
                    break
            text = _extract_page_text(doc_id, page_num)
            all_page_scores.append(
                PageResult(
                    doc_id=doc_id,
                    page_number=page_num,
                    score=score,
                    text=text,
                    chunk_id=page_chunk_ids.get(page_num, ""),
                ),
            )
            _selected_count += 1

    # Sort by score across all documents, then apply fair-case selection or top-k
    all_page_scores.sort(key=lambda p: p.score, reverse=True)
    if case_doc_groups and len(case_doc_groups) >= 2:
        results = _fair_case_select(all_page_scores, case_doc_groups, max_total)
    elif len(target_doc_ids) >= 2:
        # Post-fusion minimum page heuristic: for multi-doc comparison questions,
        # ensure BOTH documents contribute at least 1 page to the final result.
        # Without this, a high-scoring doc can crowd out the second doc entirely.
        # Inspired by CPBD (Azamat Yelmagambetov, 1st place) doc_rescue heuristic.
        doc_represented = {p.doc_id for p in all_page_scores[:max_total]}
        results = list(all_page_scores[:max_total])
        for doc_id in target_doc_ids:
            if doc_id not in doc_represented and len(results) >= 1:
                # Find the best page for this doc from all_page_scores
                for candidate in all_page_scores:
                    if candidate.doc_id == doc_id:
                        # Replace the lowest-scoring result to make room
                        if len(results) >= max_total:
                            results[-1] = candidate
                        else:
                            results.append(candidate)
                        doc_represented.add(doc_id)
                        logger.debug(
                            "[retriever] post-fusion rescue: injected %s:p%d (score=%.3f) to ensure multi-doc coverage",
                            doc_id[:12],
                            candidate.page_number,
                            candidate.score,
                        )
                        break
        results.sort(key=lambda p: p.score, reverse=True)
    else:
        results = all_page_scores[:max_total]

    ppq = len(results)
    doc_set = {r.doc_id[:12] for r in results}
    logger.debug(
        "[retrieve_pages] targeted: %d pages from %d docs (%s)",
        ppq,
        len(doc_set),
        ", ".join(f"{r.doc_id[:12]}:p{r.page_number}({r.score:.2f})" for r in results),
    )

    return results


def _retrieve_pages_fallback(
    question: str,
    max_per_doc: int,
    max_total: int,
    answer_type: str,
    cached_query_emb=None,
) -> list[PageResult]:
    """Retrieve pages using full-corpus hybrid retrieval when no target docs are known."""
    # Use existing hybrid retrieval to get ranked chunks — pass answer_type for per-type depth
    chunks = retrieve(
        question,
        n_results=25,
        # HyDE improves semantic retrieval for free_text by generating a hypothetical
        # legal passage, bridging the vocabulary gap between question and document text.
        # Disabled for exact-match types (date/number/name) where keyword matching suffices.
        use_hyde=(answer_type == "free_text"),
        answer_type=answer_type,
        cached_query_emb=cached_query_emb,
    )

    if not chunks:
        return []

    # Detect metadata questions
    is_metadata_q = answer_type in ("date", "name") and bool(_METADATA_QUESTION_PATTERNS.search(question))
    _is_date_question = bool(
        re.search(
            r"\b(date of issue|issue date|issued|earlier.*date|later.*date)\b",
            question,
            re.IGNORECASE,
        ),
    )

    # Group by (doc_id, page_number), take the best chunk position as score
    # Lower position = higher score (first chunk is most relevant)
    page_best: dict[tuple[str, int], float] = {}
    page_best_chunk_id: dict[tuple[str, int], str] = {}
    for rank, chunk in enumerate(chunks):
        doc_id = chunk["metadata"]["pdf_id"]
        page_num = chunk["metadata"].get("page", 1)
        key = (doc_id, page_num)
        # Score: inverse rank (first result = highest score)
        score = 1.0 / (rank + 1)
        if key not in page_best or score > page_best[key]:
            page_best[key] = score
            page_best_chunk_id[key] = chunk.get("chunk_id", "")

    # Apply bonuses — same targeted-page logic as _retrieve_pages_targeted()
    for (doc_id, page_num), score in list(page_best.items()):
        page_best[(doc_id, page_num)] = score + 0.02 / page_num
        if is_metadata_q:
            meta_target_page = _DOC_DATE_PAGES.get(doc_id, 1) if (answer_type == "date" or _is_date_question) else 1
            if page_num == meta_target_page:
                page_best[(doc_id, page_num)] += 0.5

    # Sort all pages by score
    sorted_pages = sorted(page_best.items(), key=lambda x: x[1], reverse=True)

    # Enforce max_per_doc limit
    doc_page_count: dict[str, int] = {}
    results: list[PageResult] = []
    for (doc_id, page_num), score in sorted_pages:
        if len(results) >= max_total:
            break
        count = doc_page_count.get(doc_id, 0)
        if count >= max_per_doc:
            continue
        text = _extract_page_text(doc_id, page_num)
        results.append(
            PageResult(
                doc_id=doc_id,
                page_number=page_num,
                score=score,
                text=text,
                chunk_id=page_best_chunk_id.get((doc_id, page_num), ""),
            ),
        )
        doc_page_count[doc_id] = count + 1

    ppq = len(results)
    doc_set = {r.doc_id[:12] for r in results}
    logger.debug(
        "[retrieve_pages] fallback: %d pages from %d docs (%s)",
        ppq,
        len(doc_set),
        ", ".join(f"{r.doc_id[:12]}:p{r.page_number}({r.score:.2f})" for r in results),
    )

    return results


def _expand_with_adjacent_pages(results: list[PageResult]) -> list[PageResult]:
    """Expand each page result with text from adjacent pages (N-1 and N+1).

    Implements the CRAG winner's parent-child chunk concept: retrieved page is the
    precise match, adjacent pages provide surrounding context for completeness.
    Text is appended with clear markers so the answerer can distinguish sources.
    Does not add extra PageResult entries — expands the text of existing results.
    """
    expanded = []
    for r in results:
        prev_text = _extract_page_text(r.doc_id, r.page_number - 1) if r.page_number > 1 else ""
        next_text = _extract_page_text(r.doc_id, r.page_number + 1)

        context_parts = [r.text]
        if prev_text:
            context_parts = [f"[PRECEDING PAGE {r.page_number - 1}]\n{prev_text}"] + context_parts
        if next_text:
            context_parts.append(f"[FOLLOWING PAGE {r.page_number + 1}]\n{next_text}")

        expanded.append(
            PageResult(
                doc_id=r.doc_id,
                page_number=r.page_number,
                score=r.score,
                text="\n\n".join(context_parts),
                chunk_id=r.chunk_id,
            ),
        )
    return expanded
