"""Retrieve relevant document chunks for a question using hybrid search."""

import re
import os
import json
import threading
from dataclasses import dataclass
import numpy as np
import anthropic
import chromadb
import bm25s
from arlc.indexing.legal_tokenizer import legal_tokenize_corpus, legal_tokenize_queries
import pymupdf
from dotenv import load_dotenv
from sentence_transformers import CrossEncoder, SentenceTransformer

load_dotenv()

_HAIKU_MODEL = "claude-haiku-4-5"  # short ID required for direct Vertex AI (no date suffix)

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

CHROMA_DIR = "data/chroma_db"  # Fallback ChromaDB path
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

# Embedding backend. Default: llama-server (Qwen3-Embedding-8B Q4_K_M via llama.cpp).
# Requires llama-server running on LLAMA_SERVER_URL (default http://localhost:8088).
# Fallback: set EMBEDDING_MODEL=snowflake to use Snowflake Arctic Embed L v2.0 (no server needed).
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "llama-server")
# FAISS: pure vector math, no SQLite overhead — faster search, lower memory than ChromaDB
# Credit: FAISS backend choice inspired by IAS Partners (guy4)
# Default index path matches the active embedding backend.
# Rebuild with: EMBEDDING_MODEL=llama-server python3 -m neolex.embeddings.build_index \
#     --corpus data/chunks/ --output data/faiss_llama-server.bin
FAISS_INDEX_PATH = os.environ.get("FAISS_INDEX_PATH", "data/faiss_llama-server.bin")
FAISS_METADATA_PATH = os.environ.get("FAISS_METADATA_PATH", "data/faiss_metadata.json")
# VECTOR_BACKEND: "faiss" (default, preferred) or "chroma" (fallback)
VECTOR_BACKEND = os.environ.get("VECTOR_BACKEND", "faiss")
# Embedding prefixes: Arctic uses "query: " for queries, "" for documents
# BGE uses "Represent this sentence for searching relevant passages: " for queries
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
BM25_CACHE_DIR = "data/bm25_cache"  # Must match CHROMA_DIR corpus
BM25_IDS_PATH = "data/bm25_cache/corpus_ids.json"

# Multi-signal fusion BM25 index variants
# Credit: Multi-signal fusion architecture from IAS Partners (guy4, Ivanov/Agishev/Sadchikov)
BM25_PAGE1_CACHE_DIR = "data/bm25_page1_cache"
BM25_PAGE1_IDS_PATH = "data/bm25_page1_cache/corpus_ids.json"
BM25_DOC_CACHE_DIR = "data/bm25_doc_cache"
BM25_DOC_IDS_PATH = "data/bm25_doc_cache/corpus_ids.json"

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
        print(f"[retriever] Warning: could not load date pages: {e}")

_load_doc_date_pages()

# Module-level caches
_doc_index = None         # pdf_id -> full text (for keyword matching)
_chunks_by_doc = None     # pdf_id -> list[dict] (for fast page retrieval, replaces collection.get())
_bm25_index = None
_bm25_corpus_ids = None
_bm25_page1_index = None
_bm25_page1_ids = None
_bm25_doc_index = None
_bm25_doc_ids = None
_collection = None
_reranker = None
_embedding_model = None
_faiss_index = None       # FAISS index (loaded lazily)
_faiss_metadata = None    # FAISS metadata list (loaded lazily)

# Locks for thread-safe lazy initialization
_bm25_lock = threading.Lock()
_bm25_page1_lock = threading.Lock()
_bm25_doc_lock = threading.Lock()
_collection_lock = threading.Lock()
_reranker_lock = threading.Lock()
_embedding_lock = threading.Lock()
_doc_index_lock = threading.Lock()
_faiss_lock = threading.Lock()


@dataclass
class PageResult:
    """A single page retrieved for answering a question."""
    doc_id: str
    page_number: int
    score: float
    text: str


def _is_qwen_reranker() -> bool:
    return "qwen" in RERANKER_MODEL.lower()


def _format_reranker_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Prepend instruction to query for Qwen3-Reranker; passthrough for others."""
    if not _is_qwen_reranker():
        return pairs
    prefix = f"Instruct: {RERANKER_INSTRUCTION}\nQuery: "
    return [(prefix + q, doc) for q, doc in pairs]


def get_reranker():
    """Get reranker (cached, thread-safe).

    Model is controlled by RERANKER_MODEL env var (default: Qwen/Qwen3-Reranker-0.6B).
    Returns Qwen3Reranker for Qwen models (correct causal-LM inference via yes/no
    token probabilities) or CrossEncoder for standard models (BGE, MiniLM, etc.).
    Both expose the same predict() interface.
    """
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                if _is_qwen_reranker():
                    from arlc.qwen3_reranker import Qwen3Reranker
                    _reranker = Qwen3Reranker(
                        model_name=RERANKER_MODEL,
                        instruction=RERANKER_INSTRUCTION,
                    )
                else:
                    import torch
                    device = (
                        'cuda' if torch.cuda.is_available()
                        else 'mps' if torch.backends.mps.is_available()
                        else 'cpu'
                    )
                    _reranker = CrossEncoder(RERANKER_MODEL, max_length=1024, device=device)
    return _reranker


def rerank_chunks(question: str, chunks: list[dict], top_k: int = 15) -> list[dict]:
    """Rerank chunks by relevance to question using cross-encoder. Returns top_k."""
    if len(chunks) <= top_k:
        return chunks
    ranker = get_reranker()
    # 2000 chars ≈ 500-700 tokens — within CrossEncoder's max_length=1024 token budget.
    # SAC adds ~150-char [DOCUMENT: ...] prefix to each chunk. Legal provisions can span
    # multiple sub-clauses; 2000 chars captures full articles for better ranking precision.
    pairs = _format_reranker_pairs([(question, chunk["text"][:2000]) for chunk in chunks])
    with _reranker_lock:  # tokenizer is not thread-safe
        scores = ranker.predict(pairs)
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [chunks[i] for i, _ in indexed[:top_k]]


def _is_arctic_model() -> bool:
    """Check if the configured embedding model is Snowflake Arctic Embed."""
    return "arctic" in EMBEDDING_MODEL.lower()


def _is_llama_server() -> bool:
    """Check if llama-server HTTP backend is configured (default)."""
    return EMBEDDING_MODEL.lower() == "llama-server"


def get_embedding_model():
    """Get embedding model (cached, thread-safe).

    Returns LlamaServerEmbedder for llama-server (default),
    or SentenceTransformer for snowflake (fallback).
    """
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                if _is_llama_server():
                    from neolex.embeddings.llama_embedder import LlamaServerEmbedder
                    _embedding_model = LlamaServerEmbedder()
                else:
                    import torch
                    device = (
                        'mps' if torch.backends.mps.is_available()
                        else 'cuda' if torch.cuda.is_available()
                        else 'cpu'
                    )
                    model_kwargs = {"trust_remote_code": True} if _is_arctic_model() else {}
                    _embedding_model = SentenceTransformer(
                        EMBEDDING_MODEL, device=device, **model_kwargs
                    )
    return _embedding_model


def embed_query(question: str) -> list[float]:
    """Embed a query for asymmetric retrieval.

    llama-server: LlamaServerEmbedder.encode(prompt_name='query') applies instruction prefix.
    Arctic:       prompt_name='query' prepends the Arctic 'query: ' prefix.
    BGE fallback: manual BGE_QUERY_PREFIX prepend.
    """
    model = get_embedding_model()
    with _embedding_lock:  # tokenizer is not thread-safe
        if _is_llama_server() or _is_arctic_model():
            embedding = model.encode(question, prompt_name='query', normalize_embeddings=True)
        else:
            embedding = model.encode(BGE_QUERY_PREFIX + question, normalize_embeddings=True)
    return embedding.tolist()


def _load_faiss():
    """Load FAISS index and metadata from disk (cached, thread-safe)."""
    global _faiss_index, _faiss_metadata
    if _faiss_index is None:
        with _faiss_lock:
            if _faiss_index is None:
                import faiss
                print(f"Loading FAISS index from {FAISS_INDEX_PATH}...")
                _faiss_index = faiss.read_index(FAISS_INDEX_PATH)
                with open(FAISS_METADATA_PATH) as f:
                    _faiss_metadata = json.load(f)
                print(f"FAISS index loaded: {_faiss_index.ntotal} vectors, dim={_faiss_index.d}")

                # Validate dimension matches query embedder to catch mismatches early.
                # Probe with a dummy query — this is cheaper than a silent FAISS crash later.
                try:
                    probe = embed_query("dimension check")
                    if len(probe) != _faiss_index.d:
                        raise RuntimeError(
                            f"FAISS index dim ({_faiss_index.d}) != "
                            f"query embedding dim ({len(probe)}) for "
                            f"EMBEDDING_MODEL={EMBEDDING_MODEL!r}. "
                            f"Rebuild the index with the same backend:\n"
                            f"  EMBEDDING_MODEL={EMBEDDING_MODEL} python3 -m neolex.embeddings.build_index "
                            f"--corpus data/chunks/ --output {FAISS_INDEX_PATH}"
                        )
                except Exception as e:
                    if "dim" in str(e).lower() or "FAISS index dim" in str(e):
                        raise
                    # embed_query errors (e.g. server not running) surface here — re-raise clearly
                    raise RuntimeError(
                        f"Embedding backend check failed for EMBEDDING_MODEL={EMBEDDING_MODEL!r}: {e}"
                    ) from e

    return _faiss_index, _faiss_metadata


def _search_faiss(query_embedding: list[float], top_k: int = 50) -> dict:
    """Search FAISS index, returning results in ChromaDB-compatible format.

    Returns dict with keys: ids, documents, metadatas, distances
    Each is a list-of-lists (matching ChromaDB's batch format).
    Distances are cosine distances (1 - similarity) for ChromaDB compatibility.
    """
    index, metadata = _load_faiss()
    query_np = np.array([query_embedding], dtype='float32')
    import faiss
    faiss.normalize_L2(query_np)  # normalize query for cosine similarity
    top_k = min(top_k, index.ntotal)
    D, I = index.search(query_np, top_k)  # D=similarities (inner product), I=indices

    ids = []
    documents = []
    metadatas = []
    distances = []
    for i in range(top_k):
        idx = int(I[0][i])
        if idx < 0:  # FAISS returns -1 for unfilled slots
            continue
        entry = metadata[idx]
        ids.append(entry["chunk_id"])
        documents.append(entry["text"])
        metadatas.append({
            "pdf_id": entry["pdf_id"],
            "page": entry["page"],
            "source_file": entry["source_file"],
        })
        # Convert inner product similarity to cosine distance for ChromaDB compat
        distances.append(1.0 - float(D[0][i]))

    return {
        "ids": [ids],
        "documents": [documents],
        "metadatas": [metadatas],
        "distances": [distances],
    }


def _faiss_count() -> int:
    """Return total number of vectors in FAISS index."""
    index, _ = _load_faiss()
    return index.ntotal


def _faiss_get_all() -> dict:
    """Get all documents and metadata from FAISS (equivalent to collection.get())."""
    _, metadata = _load_faiss()
    ids = [entry["chunk_id"] for entry in metadata]
    documents = [entry["text"] for entry in metadata]
    metadatas = [
        {
            "pdf_id": entry["pdf_id"],
            "page": entry["page"],
            "source_file": entry["source_file"],
            # entities field added at index time (CPBD-inspired); may be absent in old indexes
            **({"entities": entry["entities"]} if entry.get("entities") else {}),
        }
        for entry in metadata
    ]
    return {"ids": ids, "documents": documents, "metadatas": metadatas}


def _faiss_get_by_ids(chunk_ids: list[str]) -> dict:
    """Get specific chunks by ID from FAISS metadata."""
    _, metadata = _load_faiss()
    # Build lookup on first call (O(n) once, then O(1) per lookup)
    if not hasattr(_faiss_get_by_ids, "_id_map"):
        _faiss_get_by_ids._id_map = {entry["chunk_id"]: entry for entry in metadata}
    id_map = _faiss_get_by_ids._id_map

    ids = []
    documents = []
    metadatas = []
    for cid in chunk_ids:
        entry = id_map.get(cid)
        if entry:
            ids.append(entry["chunk_id"])
            documents.append(entry["text"])
            meta = {"pdf_id": entry["pdf_id"], "page": entry["page"],
                    "source_file": entry["source_file"]}
            if entry.get("entities"):
                meta["entities"] = entry["entities"]
            metadatas.append(meta)
    return {"ids": ids, "documents": documents, "metadatas": metadatas}


def _use_faiss() -> bool:
    """Check if FAISS backend should be used (preferred when available)."""
    if VECTOR_BACKEND != "faiss":
        return False
    return os.path.exists(FAISS_INDEX_PATH) and os.path.exists(FAISS_METADATA_PATH)


def get_collection():
    """Get the ChromaDB collection (cached, thread-safe).

    No embedding function needed here — we always pass query_embeddings explicitly.
    Avoids loading BGE a second time via SentenceTransformerEmbeddingFunction.
    Used as fallback when FAISS is not available.
    """
    global _collection
    if _collection is None:
        with _collection_lock:
            if _collection is None:
                client = chromadb.PersistentClient(path=CHROMA_DIR)
                _collection = client.get_collection(name="legal_docs")
    return _collection


def _load_all_chunks():
    """Load all chunks from vector store once into memory. Builds both indexes simultaneously.

    Uses FAISS metadata when available (faster, no SQLite), falls back to ChromaDB.
    """
    global _doc_index, _chunks_by_doc
    if _use_faiss():
        all_results = _faiss_get_all()
    else:
        collection = get_collection()
        all_results = collection.get(include=["documents", "metadatas"])

    doc_text_index = {}
    chunks_by_doc = {}
    for chunk_id, text, meta in zip(all_results["ids"], all_results["documents"], all_results["metadatas"]):
        pdf_id = meta["pdf_id"]
        # Build text index for keyword matching
        if pdf_id not in doc_text_index:
            doc_text_index[pdf_id] = ""
        doc_text_index[pdf_id] += text + "\n"
        # Build chunk index for fast page retrieval
        if pdf_id not in chunks_by_doc:
            chunks_by_doc[pdf_id] = []
        chunks_by_doc[pdf_id].append({
            "chunk_id": chunk_id,
            "text": text,
            "metadata": meta,
        })

    _doc_index = doc_text_index
    _chunks_by_doc = chunks_by_doc


def build_doc_index() -> dict[str, str]:
    """Build keyword-matching index from ChromaDB data (includes OCR'd text)."""
    global _doc_index
    if _doc_index is None:
        with _doc_index_lock:
            if _doc_index is None:
                _load_all_chunks()
    return _doc_index


def get_chunks_by_doc() -> dict[str, list[dict]]:
    """Get in-memory chunk index (pdf_id -> list of chunks). Avoids slow collection.get() per doc."""
    global _chunks_by_doc
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
        r'(?:case\s+no\.?\s*|case\s+|no\.\s*)((?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+)',
        # Bare case numbers: direct references in question text (e.g., "What happened in SCT 295/2025?")
        r'(?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+',
        r'Law\s+No\.?\s*\d+\s+of\s+\d+',
        r'DIFC\s+Law\s+No\.?\s*\d+(?:\s+of\s+\d+)?',
        r'Regulation\s+No\.?\s*\d+',
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
    exact_pattern = r'\b' + re.escape(law_lower) + r'\b'

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
        _is_law_no_pattern = bool(re.match(r'(?:DIFC\s+)?Law\s+No\.?\s*\d+', identifier, re.IGNORECASE))
        if _is_law_no_pattern:
            primary_docs = _score_doc_by_law_name(identifier, doc_index)
            if primary_docs:
                matching_pdf_ids.update(primary_docs)
                continue

        normalized = re.sub(r'[\s\-_/\(\)]+', r'[\\s\\-_/]*', identifier.strip())
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
        r'(CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*(\d+)[\s/\-_]*(\d+)',
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
    year_pattern = r'\b(19\d{2}|20\d{2})\b'
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


_STOPWORDS = frozenset({
    'the', 'a', 'an', 'of', 'in', 'is', 'are', 'was', 'were', 'to', 'for',
    'and', 'or', 'by', 'how', 'many', 'what', 'which', 'according', 'under',
    'does', 'did', 'do', 'has', 'have', 'be', 'any', 'if', 'at', 'this',
    'that', 'with', 'from', 'as', 'its', 'it', 'on', 'not', 'no', 'than',
    'such', 'same', 'both', 'also', 'may', 'shall', 'will', 'who',
})


_SCHEDULE_INDICATORS = frozenset({'schedule', 'contravention', 'appendix', 'annex', 'fine', 'penalty table'})


_ENACTMENT_KEYWORDS = frozenset({
    'enacted', 'enact', 'enactment', 'promulgated', 'came into force', 'effective date',
    # V4BH: added phrasing variants found in legal questions (RESEARCH_RETRIEVAL.md)
    'published', 'commencement', 'date of commencement', 'gazetted', 'gazette',
    # Phase 3: 'effective' standalone for "when did X become effective?"
    'effective',
})

# Outcome-related question keywords — used to boost prescore of outcome chunks
# NOTE: 'judgment'/'judgement' intentionally EXCLUDED — questions referencing
# "the appeal judgment" or "what does the judgment say about X" are NOT asking
# about the OUTCOME; they're asking about content within the judgment document.
# Including them caused "claim value in judgment" to trigger outcome boosting,
# promoting wrong chunks (e.g., ordered amount instead of claimed amount).
_OUTCOME_QUESTION_KEYWORDS = frozenset({
    'outcome', 'result', 'ruling', 'decision', 'verdict', 'held', 'ordered',
    'dismissed', 'awarded', 'granted', 'refused', 'conclud', 'final order', 'final ruling',
})
# Outcome keywords that appear IN the actual chunks (order pages, judgment text)
# Broad 'judgment'/'judgement' removed to prevent false-positive boosting on non-outcome chunks.
_OUTCOME_CHUNK_KEYWORDS = frozenset({
    'dismissed', 'awarded', 'granted', 'ordered', 'hereby ordered',
    'it is ordered', 'it is hereby', 'costs awarded', 'claim dismissed',
    'application dismissed', 'claim allowed', 'appeal dismissed', 'appeal allowed',
})


def _clean_query_for_ce(question: str) -> str:
    """Strip long case names from query for cross-encoder scoring in targeted retrieval.

    Questions like "What was X in [LONG PARTY NAME] [YEAR] DIFC TYPE NUM?" cause the CE
    to over-rank title pages: the long case name dominates token budget and CE matching.
    In targeted retrieval (doc already identified), the case name is redundant — removing
    it focuses CE on the semantic "what/why/how" portion of the question.

    Only triggers when party segment is ≥25 chars, avoiding removal of short case refs.
    """
    cleaned = re.sub(
        r'\s+in\s+[A-Z][^?\[\]]{25,}\[\d{4}\]\s+DIFC\s+[A-Z]+\s+\d+[^?]*',
        '',
        question,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned if len(cleaned) >= 20 else question


def _prescore_keyword_chunks(question: str, chunks: list[dict], top_n: int = 25) -> list[dict]:
    """Pre-rank keyword chunks by term overlap with question before cross-encoder reranking.

    Gives 3× weight to specific article references (Article 14(2)(b)), 1× to other terms.
    Penalizes schedule/table chunks that reference articles but don't contain the actual text.
    Always includes page-1 chunks so law title/number is always available.
    Boosts enactment notice chunks when the question asks about enactment dates.
    """
    # Extract exact article references (e.g. "Article 14(2)(b)") — high-value signal
    article_refs = [r.lower() for r in re.findall(r'Article\s+\d+[\w\(\)\.]*', question, re.IGNORECASE)]

    # Extract quoted section phrases (e.g., "IT IS HEREBY ORDERED THAT") — chunks containing
    # these phrases get a strong boost so section-specific questions find the right page
    import re as _re
    _section_quotes = _re.findall(r"'([^']{10,})'|\"([^\"]{10,})\"", question)
    _section_phrase = (_section_quotes[0][0] or _section_quotes[0][1]).strip().lower() if _section_quotes else ""

    # General question terms (stopwords removed)
    q_words = {w.lower() for w in re.findall(r'\w+', question)} - _STOPWORDS

    # Detect enactment-related questions (e.g. "Was X enacted earlier than Y?")
    q_lower = question.lower()
    asks_enactment = any(kw in q_lower for kw in _ENACTMENT_KEYWORDS)

    # Detect outcome/result questions (e.g. "What was the outcome of case X?")
    asks_outcome = any(kw in q_lower for kw in _OUTCOME_QUESTION_KEYWORDS)

    # Page-1 chunk IDs — always include these (law title/number is typically on page 1)
    page1_ids = {c['chunk_id'] for c in chunks if c['metadata'].get('page', 0) == 1}

    # Also extract bare article numbers (legal docs often omit "Article" prefix in body text)
    # e.g. "Article 14(2)(b)" → also check for "14(2)(b)" substring
    bare_art_nums = [re.sub(r'^article\s+', '', ref) for ref in article_refs]
    # Article root numbers for header detection: "14(2)(b)" → "14"
    art_root_nums = list({re.match(r'(\d+)', num).group(1) for num in bare_art_nums if re.match(r'\d+', num)})

    scored = []
    for chunk in chunks:
        text_lower = chunk['text'].lower()
        chunk_text = chunk['text']  # original case for pattern matching

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
        if asks_enactment and 'enactment notice' in text_lower:
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
        page_bonus = 4 if chunk['chunk_id'] in page1_ids else 0

        # General: question term overlap
        chunk_words = set(re.findall(r'\w+', text_lower))
        overlap = len(q_words & chunk_words)

        scored.append((article_score + enactment_bonus + section_boost + outcome_bonus + page_bonus + overlap, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_n]]


def get_all_pages_for_docs(pdf_ids: list[str]) -> list[dict]:
    """Get all indexed chunks for specific documents (in-memory, no ChromaDB query)."""
    chunks_by_doc = get_chunks_by_doc()
    chunks = []
    for pdf_id in pdf_ids:
        chunks.extend(chunks_by_doc.get(pdf_id, []))
    return chunks


def build_bm25_index():
    """Build BM25 index over all ChromaDB chunks (lazy-loaded, disk-cached, thread-safe).

    Saves index to data/bm25_cache/ on first build; loads from disk on subsequent runs.
    Delete data/bm25_cache/ after re-indexing to force a rebuild.
    """
    global _bm25_index, _bm25_corpus_ids
    if _bm25_index is not None:
        return _bm25_index, _bm25_corpus_ids

    with _bm25_lock:
        if _bm25_index is not None:
            return _bm25_index, _bm25_corpus_ids

        # Try loading from disk cache first
        if os.path.exists(BM25_IDS_PATH) and os.path.exists(BM25_CACHE_DIR):
            try:
                print("Loading BM25 index from disk cache...")
                retriever = bm25s.BM25.load(BM25_CACHE_DIR, load_corpus=False)
                with open(BM25_IDS_PATH) as f:
                    corpus_ids = json.load(f)
                _bm25_corpus_ids = corpus_ids
                _bm25_index = retriever
                print("BM25 index loaded from cache.")
                return _bm25_index, _bm25_corpus_ids
            except Exception as e:
                print(f"BM25 cache load failed ({e}), rebuilding...")

        # Build from vector store (FAISS or ChromaDB)
        print("Building BM25 index...")
        if _use_faiss():
            all_results = _faiss_get_all()
        else:
            collection = get_collection()
            all_results = collection.get(include=["documents", "metadatas"])

        corpus_texts = all_results["documents"]
        corpus_ids = all_results["ids"]

        corpus_tokens = legal_tokenize_corpus(corpus_texts)

        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)

        # Save to disk cache
        try:
            os.makedirs(BM25_CACHE_DIR, exist_ok=True)
            retriever.save(BM25_CACHE_DIR)
            with open(BM25_IDS_PATH, "w") as f:
                json.dump(corpus_ids, f)
            print("BM25 index saved to disk cache.")
        except Exception as e:
            print(f"BM25 cache save failed (non-fatal): {e}")

        _bm25_corpus_ids = corpus_ids
        _bm25_index = retriever

    return _bm25_index, _bm25_corpus_ids


def build_bm25_page1_index():
    """Build BM25 index over first-page-only chunks (document identification signal).

    # Multi-signal fusion from IAS Partners (guy4, Ivanov/Agishev/Sadchikov)
    Page 1 typically contains the document title, law number, and preamble — strong
    signal for identifying which document a query refers to.
    """
    global _bm25_page1_index, _bm25_page1_ids
    if _bm25_page1_index is not None:
        return _bm25_page1_index, _bm25_page1_ids

    with _bm25_page1_lock:
        if _bm25_page1_index is not None:
            return _bm25_page1_index, _bm25_page1_ids

        # Try loading from disk cache first
        if os.path.exists(BM25_PAGE1_IDS_PATH) and os.path.exists(BM25_PAGE1_CACHE_DIR):
            try:
                print("Loading BM25 page1 index from disk cache...")
                retriever = bm25s.BM25.load(BM25_PAGE1_CACHE_DIR, load_corpus=False)
                with open(BM25_PAGE1_IDS_PATH) as f:
                    corpus_ids = json.load(f)
                _bm25_page1_ids = corpus_ids
                _bm25_page1_index = retriever
                print("BM25 page1 index loaded from cache.")
                return _bm25_page1_index, _bm25_page1_ids
            except Exception as e:
                print(f"BM25 page1 cache load failed ({e}), rebuilding...")

        # Build from in-memory chunks (page 1 only)
        print("Building BM25 page1 index...")
        chunks_by_doc = get_chunks_by_doc()

        corpus_texts = []
        corpus_ids = []
        for doc_id, chunks in chunks_by_doc.items():
            for chunk in chunks:
                if chunk["metadata"].get("page", 1) == 1:
                    corpus_texts.append(chunk["text"])
                    corpus_ids.append(chunk["chunk_id"])

        if not corpus_texts:
            print("BM25 page1 index: no page-1 chunks found, skipping.")
            return None, None

        corpus_tokens = legal_tokenize_corpus(corpus_texts)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)

        try:
            os.makedirs(BM25_PAGE1_CACHE_DIR, exist_ok=True)
            retriever.save(BM25_PAGE1_CACHE_DIR)
            with open(BM25_PAGE1_IDS_PATH, "w") as f:
                json.dump(corpus_ids, f)
            print("BM25 page1 index saved to disk cache.")
        except Exception as e:
            print(f"BM25 page1 cache save failed (non-fatal): {e}")

        _bm25_page1_ids = corpus_ids
        _bm25_page1_index = retriever

    return _bm25_page1_index, _bm25_page1_ids


def build_bm25_doc_index():
    """Build BM25 index over concatenated document text (one entry per doc).

    # Multi-signal fusion from IAS Partners (guy4, Ivanov/Agishev/Sadchikov)
    Document-level BM25 captures full-document term frequency — strong signal for
    identifying target documents when queries mention law names or case numbers.
    """
    global _bm25_doc_index, _bm25_doc_ids
    if _bm25_doc_index is not None:
        return _bm25_doc_index, _bm25_doc_ids

    with _bm25_doc_lock:
        if _bm25_doc_index is not None:
            return _bm25_doc_index, _bm25_doc_ids

        # Try loading from disk cache first
        if os.path.exists(BM25_DOC_IDS_PATH) and os.path.exists(BM25_DOC_CACHE_DIR):
            try:
                print("Loading BM25 doc-level index from disk cache...")
                retriever = bm25s.BM25.load(BM25_DOC_CACHE_DIR, load_corpus=False)
                with open(BM25_DOC_IDS_PATH) as f:
                    doc_ids = json.load(f)
                _bm25_doc_ids = doc_ids
                _bm25_doc_index = retriever
                print("BM25 doc-level index loaded from cache.")
                return _bm25_doc_index, _bm25_doc_ids
            except Exception as e:
                print(f"BM25 doc-level cache load failed ({e}), rebuilding...")

        # Build from in-memory chunks (concatenate all pages per doc)
        print("Building BM25 doc-level index...")
        chunks_by_doc = get_chunks_by_doc()

        doc_texts = []
        doc_ids = []
        for doc_id, chunks in chunks_by_doc.items():
            # Concatenate all chunk texts for this document
            full_text = "\n".join(chunk["text"] for chunk in chunks)
            doc_texts.append(full_text)
            doc_ids.append(doc_id)

        if not doc_texts:
            print("BM25 doc-level index: no documents found, skipping.")
            return None, None

        corpus_tokens = legal_tokenize_corpus(doc_texts)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)

        try:
            os.makedirs(BM25_DOC_CACHE_DIR, exist_ok=True)
            retriever.save(BM25_DOC_CACHE_DIR)
            with open(BM25_DOC_IDS_PATH, "w") as f:
                json.dump(doc_ids, f)
            print("BM25 doc-level index saved to disk cache.")
        except Exception as e:
            print(f"BM25 doc-level cache save failed (non-fatal): {e}")

        _bm25_doc_ids = doc_ids
        _bm25_doc_index = retriever

    return _bm25_doc_index, _bm25_doc_ids


def generate_hyde_passage(question: str) -> str | None:
    """Generate a hypothetical document passage that would answer the question (HyDE).

    Embeds this passage instead of the raw question for better semantic alignment with
    the document corpus (especially for fact-lookup questions where the question uses
    everyday language but the answer uses specific legal terminology).

    Uses the configured LLM backend (litellm/vertex/anthropic) via arlc.llm.router.
    Returns None silently on any error so HyDE is always best-effort.
    """
    try:
        from arlc.llm.router import _call_backend
        text, *_ = _call_backend(
            system_prompt="You are a legal document writer. Write only document text, no preamble.",
            user_message=(
                f"Write a single concise paragraph (3-4 sentences) from a Victorian "
                f"criminal law document that directly answers this question: {question}"
            ),
            max_tokens=150,
            model=_HAIKU_MODEL,
            system_blocks=None,
        )
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
PAGE_RANK_USE_BM25 = False  # Set True to re-enable BM25 in page ranking

# Per-type configs inspired by IAS Partners dual-pipeline (guy4)
# top_k: retrieval depth — how many candidates to pull before reranking.
# Inspired by CPBD (Azamat Yelmagambetov, 1st place) who swept 22 depth values.
# V5: Increased all top_k values to 200 (was 30-100) based on Legal RAG Bench testing.
# Deeper candidate pool gave +0.10 retrieval accuracy — more candidates before reranking
# means the right page has a higher chance of being in the pool at all.
# NOTE: This is retrieval POOL depth, not output pages. "Extra pages" graveyard entry
# refers to max output pages (max_pages), not the candidate pool. These are different.
RETRIEVAL_CONFIGS = {
    "boolean":   {"top_k": 200, "max_docs": 3, "max_pages": 3},
    "number":    {"top_k": 200, "max_docs": 2, "max_pages": 2},
    "date":      {"top_k": 200, "max_docs": 2, "max_pages": 1},
    "name":      {"top_k": 200, "max_docs": 3, "max_pages": 3},
    "names":     {"top_k": 200, "max_docs": 3, "max_pages": 3},
    "free_text": {"top_k": 200, "max_docs": 4, "max_pages": 5},
}

DOC_FUSION_WEIGHTS = {
    "bm25_std": 0.10,     # standard BM25 page score (max per doc)
    "dense_std": 0.05,    # dense embedding score (max per doc)
    "dense_rrf": 0.20,    # dense RRF rank score
    "bm25_doc": 0.30,     # document-level BM25
    "bm25_page1": 0.30,   # page-1-only BM25
}

DOC_FUSION_GAP_THRESHOLD = 0.15  # Adaptive doc selection gap


def _doc_fusion_select(
    question: str,
    max_docs: int = 3,
    answer_type: str = "",
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

    # Load all required indexes
    bm25_all, bm25_all_ids = build_bm25_index()
    bm25_p1_result = build_bm25_page1_index()
    bm25_doc_result = build_bm25_doc_index()

    if bm25_p1_result is None or bm25_p1_result[0] is None:
        return None
    if bm25_doc_result is None or bm25_doc_result[0] is None:
        return None

    bm25_p1_idx, bm25_p1_ids = bm25_p1_result
    bm25_doc_idx, bm25_doc_doc_ids = bm25_doc_result

    collection = get_collection() if not _use_faiss() else None
    chunks_by_doc_map = get_chunks_by_doc()

    # Map chunk_id -> doc_id for BM25 all-pages index
    chunk_to_doc = {}
    for doc_id, chunks in chunks_by_doc_map.items():
        for chunk in chunks:
            chunk_to_doc[chunk["chunk_id"]] = doc_id

    # Map chunk_id -> doc_id for BM25 page1 index
    chunk_to_doc_p1 = {}
    for doc_id, chunks in chunks_by_doc_map.items():
        for chunk in chunks:
            if chunk["metadata"].get("page", 1) == 1:
                chunk_to_doc_p1[chunk["chunk_id"]] = doc_id

    query_tokens = legal_tokenize_queries(question)

    # --- Signal 1: BM25 standard (max page score per doc) ---
    bm25_results, bm25_scores = bm25_all.retrieve(query_tokens, k=min(fusion_top_k, len(bm25_all_ids)))
    bm25_std_doc_scores: dict[str, float] = {}
    indices = bm25_results[0] if len(bm25_results.shape) > 1 else bm25_results
    scores_arr = bm25_scores[0] if len(bm25_scores.shape) > 1 else bm25_scores
    for idx_i, idx in enumerate(indices):
        if idx < len(bm25_all_ids):
            chunk_id = bm25_all_ids[idx]
            doc_id = chunk_to_doc.get(chunk_id)
            if doc_id:
                score = float(scores_arr[idx_i]) if idx_i < len(scores_arr) else 0.0
                if doc_id not in bm25_std_doc_scores or score > bm25_std_doc_scores[doc_id]:
                    bm25_std_doc_scores[doc_id] = score

    # Normalize BM25 std scores
    max_bm25_std = max(bm25_std_doc_scores.values(), default=1.0) or 1.0
    for d in bm25_std_doc_scores:
        bm25_std_doc_scores[d] /= max_bm25_std

    # --- Signal 2 & 3: Dense embedding scores + RRF ---
    query_emb = embed_query(question)
    if _use_faiss():
        dense_n = min(fusion_top_k, _faiss_count())
        vector_results = _search_faiss(query_emb, top_k=dense_n)
    else:
        dense_n = min(fusion_top_k, collection.count())
        vector_results = collection.query(
            query_embeddings=[query_emb],
            n_results=dense_n,
            include=["metadatas", "distances"],
        )

    dense_std_doc_scores: dict[str, float] = {}
    dense_rrf_doc_scores: dict[str, float] = {}
    k_rrf = 60
    for rank, (meta, dist) in enumerate(
        zip(vector_results["metadatas"][0], vector_results["distances"][0])
    ):
        doc_id = meta["pdf_id"]
        sim = 1.0 - float(dist)  # ChromaDB cosine distance -> similarity
        # Signal 2: max dense score per doc
        if doc_id not in dense_std_doc_scores or sim > dense_std_doc_scores[doc_id]:
            dense_std_doc_scores[doc_id] = sim
        # Signal 3: RRF rank score (accumulate across pages)
        rrf_score = 1.0 / (k_rrf + rank + 1)
        dense_rrf_doc_scores[doc_id] = dense_rrf_doc_scores.get(doc_id, 0.0) + rrf_score

    # Normalize dense scores
    max_dense_std = max(dense_std_doc_scores.values(), default=1.0) or 1.0
    for d in dense_std_doc_scores:
        dense_std_doc_scores[d] /= max_dense_std
    max_dense_rrf = max(dense_rrf_doc_scores.values(), default=1.0) or 1.0
    for d in dense_rrf_doc_scores:
        dense_rrf_doc_scores[d] /= max_dense_rrf

    # --- Signal 4: BM25 doc-level ---
    bm25_doc_results, bm25_doc_scores = bm25_doc_idx.retrieve(query_tokens, k=min(fusion_top_k, len(bm25_doc_doc_ids)))
    bm25_doc_doc_scored: dict[str, float] = {}
    d_indices = bm25_doc_results[0] if len(bm25_doc_results.shape) > 1 else bm25_doc_results
    d_scores = bm25_doc_scores[0] if len(bm25_doc_scores.shape) > 1 else bm25_doc_scores
    for idx_i, idx in enumerate(d_indices):
        if idx < len(bm25_doc_doc_ids):
            doc_id = bm25_doc_doc_ids[idx]
            score = float(d_scores[idx_i]) if idx_i < len(d_scores) else 0.0
            bm25_doc_doc_scored[doc_id] = score

    max_bm25_doc = max(bm25_doc_doc_scored.values(), default=1.0) or 1.0
    for d in bm25_doc_doc_scored:
        bm25_doc_doc_scored[d] /= max_bm25_doc

    # --- Signal 5: BM25 page1 ---
    bm25_p1_results, bm25_p1_scores = bm25_p1_idx.retrieve(query_tokens, k=min(fusion_top_k, len(bm25_p1_ids)))
    bm25_p1_doc_scored: dict[str, float] = {}
    p1_indices = bm25_p1_results[0] if len(bm25_p1_results.shape) > 1 else bm25_p1_results
    p1_scores = bm25_p1_scores[0] if len(bm25_p1_scores.shape) > 1 else bm25_p1_scores
    for idx_i, idx in enumerate(p1_indices):
        if idx < len(bm25_p1_ids):
            chunk_id = bm25_p1_ids[idx]
            doc_id = chunk_to_doc_p1.get(chunk_id)
            if doc_id:
                score = float(p1_scores[idx_i]) if idx_i < len(p1_scores) else 0.0
                if doc_id not in bm25_p1_doc_scored or score > bm25_p1_doc_scored[doc_id]:
                    bm25_p1_doc_scored[doc_id] = score

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
    for scores_dict in [bm25_std_doc_scores, dense_std_doc_scores, dense_rrf_doc_scores,
                        bm25_doc_doc_scored, bm25_p1_doc_scored]:
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

    print(f"[doc_fusion] selected {len(selected)} docs: "
          f"{', '.join(f'{d[:12]}({fused_scores[d]:.3f})' for d in selected)}")

    return selected


def _generate_query_variants(question: str) -> list[str]:
    """Generate 2 alternative query phrasings using Haiku. Returns empty list on failure."""
    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model=_HAIKU_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    f"Generate 2 alternative search queries for this legal question. "
                    f"Use different legal terminology and phrasing. Output ONLY the 2 queries, one per line, no numbering:\n{question}"
                ),
            }],
            max_tokens=100,
            temperature=0.3,
        )
        content = response.content[0].text.strip() if response.content else ""
        variants = [line.strip() for line in content.split("\n") if line.strip()]
        return variants[:2]
    except Exception:
        return []


def prewarm():
    """Pre-warm all caches before parallel processing to avoid race conditions."""
    print("Pre-warming retrieval caches...")
    get_embedding_model()
    get_collection()
    build_doc_index()      # also populates _chunks_by_doc via _load_all_chunks()
    build_bm25_index()
    # Multi-signal fusion indexes (graceful if not yet built)
    if USE_MULTI_SIGNAL_FUSION:
        build_bm25_page1_index()
        build_bm25_doc_index()
    get_reranker()
    print("Caches ready.")


def detect_multi_hop(question: str) -> bool:
    """Detect if question requires multi-hop cross-document retrieval.

    Returns True if:
    - Question contains 2+ case numbers (e.g., "CFI 010/2024 and CFI 016/2025")
    - Question contains cross-document comparison indicators

    Multi-hop questions need to retrieve chunks from multiple documents
    to enable cross-document comparison/synthesis.
    """
    # Count case numbers in the question
    case_pattern = r'(?:SCT|CFI|CA|ARB|ENF|DEC|TCD)\s+\d{3}/\d{4}'
    case_matches = re.findall(case_pattern, question, re.IGNORECASE)
    if len(case_matches) >= 2:
        return True

    # Check for cross-document comparison indicators
    cross_doc_indicators = [
        r'\bboth case(?:s)?\b',
        r'\bany of the same\b',
        r'\bcommon to both\b',
        r'\bbetween\b',
        r'\bwhich case\b',
        r'\bany main party\b',
        r'\bany judge\b',
        r'\bsame judge\b',
        r'\beither\b',
        r'\bacross\b',
    ]

    q_lower = question.lower()
    for indicator in cross_doc_indicators:
        if re.search(indicator, q_lower):
            return True

    return False


def decompose_query(question: str) -> list[str]:
    """Decompose a multi-hop question into 2 independent sub-questions.

    Uses Haiku (fast, ~200ms) to split cross-document questions into
    separate sub-questions that can be answered independently.

    Example:
        Input: "Is there any judge common to CFI 010/2024 and CFI 016/2025?"
        Output: ["Who was the judge in CFI 010/2024?",
                 "Who was the judge in CFI 016/2025?"]

    Returns empty list on failure (timeout, API error, etc.).
    """
    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model=_HAIKU_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    f"Split this legal question into 2 independent sub-questions, "
                    f"one per document/case. Output each on a separate line.\n"
                    f"Question: {question}"
                ),
            }],
            max_tokens=150,
            temperature=0.0,
        )
        content = response.content[0].text.strip() if response.content else ""
        sub_queries = [line.strip() for line in content.split("\n") if line.strip()]
        return sub_queries[:2]  # Return at most 2 sub-queries
    except Exception:
        return []


def _extract_article_filter(question: str) -> str | None:
    """Extract article number for metadata filtering.

    Returns article number string (e.g., "28") if question explicitly mentions
    a specific article like "Article 28" or "Article 14(2)".
    """
    # Match "Article 28", "Article 14(2)", "Article 3(a)"
    article_match = re.search(r'\bArticle\s+(\d+)', question, re.IGNORECASE)
    if article_match:
        return article_match.group(1)
    return None


def retrieve(question: str, n_results: int = 15, use_hyde: bool = True, answer_type: str = "") -> list[dict]:
    """
    Hybrid retrieval: keyword match + BM25 + vector search with RRF.

    For questions with keyword matches (specific case/law): return up to 25 chunks.
    For pure vector questions: return 15 chunks using BM25 + vector RRF (+ HyDE if enabled).

    answer_type: when provided, overrides n_results with per-type top_k from RETRIEVAL_CONFIGS.
    Inspired by CPBD (Azamat Yelmagambetov, 1st place) who swept 22 depth values per type.

    NEW: Metadata-aware filtering when question mentions specific articles.
    NEW: Query decomposition for multi-hop cross-document questions.
    """
    # Per-type retrieval depth: RETRIEVAL_CONFIGS[answer_type]["top_k"] overrides n_results
    if answer_type and answer_type in RETRIEVAL_CONFIGS:
        n_results = RETRIEVAL_CONFIGS[answer_type]["top_k"]
    # Multi-hop query decomposition: disabled for now (causes pipeline hangs in parallel)
    if False and detect_multi_hop(question):
        sub_queries = decompose_query(question)
        if len(sub_queries) >= 2:
            print(f"[MULTI-HOP] Decomposed into {len(sub_queries)} sub-queries")
            # Retrieve chunks for each sub-query
            all_chunks = []
            seen_ids = set()
            for sub_q in sub_queries[:2]:  # Process at most 2 sub-queries
                sub_chunks = retrieve(sub_q, n_results=n_results, use_hyde=use_hyde)
                # Deduplicate by chunk_id (preserve first occurrence)
                for chunk in sub_chunks:
                    if chunk["chunk_id"] not in seen_ids:
                        seen_ids.add(chunk["chunk_id"])
                        all_chunks.append(chunk)
            print(f"[MULTI-HOP] Retrieved {len(all_chunks)} unique chunks from {len(sub_queries)} sub-queries")
            return all_chunks
        # If decomposition failed, fall through to standard retrieval
        print("[MULTI-HOP] Decomposition failed, using standard retrieval")

    collection = get_collection() if not _use_faiss() else None

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
            print(f"[METADATA FILTER] Article {article_filter}: {len(article_chunks)} exact matches promoted to top")

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
        if _use_faiss():
            vector_results = _search_faiss(embed_query(question), top_k=max(n_results, 15))
        else:
            vector_results = collection.query(
                query_embeddings=[embed_query(question)],
                n_results=max(n_results, 15),
                include=["documents", "metadatas", "distances"],
            )

        vector_chunks = []
        for i in range(len(vector_results["ids"][0])):
            vector_chunks.append({
                "chunk_id": vector_results["ids"][0][i],
                "text": vector_results["documents"][0][i],
                "metadata": vector_results["metadatas"][0][i],
                "distance": vector_results["distances"][0][i],
            })

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

        # Cap at 60 chunks before reranking — larger pool for citation coverage
        ranked = rerank_chunks(question, merged[:60], top_k=40)

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

    else:
        # No keyword matches: use BM25 + vector with RRF, augmented by HyDE
        bm25_index, corpus_ids = build_bm25_index()
        query_tokens = legal_tokenize_queries(question)

        # Scale top_k based on metadata filters (need larger pool before filtering)
        # V5: Raised floor from 50 to 200 — deeper pool gives +0.10 retrieval accuracy
        base_top_k = max(n_results, 200)
        top_k = base_top_k * 3 if article_filter else base_top_k

        bm25_results, bm25_scores = bm25_index.retrieve(query_tokens, k=top_k)

        bm25_ranking = []
        if len(bm25_results.shape) > 1:
            for idx in bm25_results[0]:
                if idx < len(corpus_ids):
                    bm25_ranking.append(corpus_ids[idx])
        else:
            for idx in bm25_results:
                if idx < len(corpus_ids):
                    bm25_ranking.append(corpus_ids[idx])

        # Original query embedding
        query_emb = embed_query(question)
        if _use_faiss():
            vector_results = _search_faiss(query_emb, top_k=top_k)
        else:
            vector_results = collection.query(
                query_embeddings=[query_emb],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        vector_ranking = vector_results["ids"][0]

        # HyDE: generate a hypothetical passage and embed it for additional signal
        # Only for free_text questions — adds ~500ms Haiku call overhead, worth it for LLM-judged answers
        hyde_ranking = []
        hyde_passage = generate_hyde_passage(question) if use_hyde else None
        if hyde_passage:
            try:
                hyde_emb = embed_query(hyde_passage)  # uses embed_query prefix internally
                if _use_faiss():
                    hyde_results = _search_faiss(hyde_emb, top_k=top_k)
                else:
                    hyde_results = collection.query(
                        query_embeddings=[hyde_emb],
                        n_results=top_k,
                        include=["documents", "metadatas", "distances"],
                    )
                hyde_ranking = hyde_results["ids"][0]
            except Exception:
                pass

        # Multi-query expansion: generate variant queries for additional BM25 signal
        # Only for free_text (use_hyde=True) to avoid TTFT penalty on deterministic questions
        variant_rankings = []
        if use_hyde:
            variants = _generate_query_variants(question)
            for variant in variants[:2]:
                try:
                    v_tokens = legal_tokenize_queries(variant)
                    v_results, _ = bm25_index.retrieve(v_tokens, k=top_k)
                    v_bm25_ranking = [corpus_ids[idx] for idx in (v_results[0] if len(v_results.shape) > 1 else v_results) if idx < len(corpus_ids)]
                    variant_rankings.append(v_bm25_ranking)
                except Exception:
                    pass

        # RRF over all signals: BM25, vector, HyDE-vector, variant queries
        all_rankings = [r for r in [bm25_ranking, vector_ranking, hyde_ranking] + variant_rankings if r]
        # BM25 gets 2.0x weight — outperforms dense for legal without domain-adapted embeddings (LRAGE 2025)
        # Phase 3: raised 1.5→2.0 for larger 300-doc corpus (more vector noise at scale)
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

        final_chunks = []
        for chunk_id in merged_ranking[:60]:
            if chunk_id in vector_lookup:
                final_chunks.append(vector_lookup[chunk_id])
            else:
                if _use_faiss():
                    chunk_data = _faiss_get_by_ids([chunk_id])
                else:
                    chunk_data = collection.get(
                        ids=[chunk_id],
                        include=["documents", "metadatas"],
                    )
                if len(chunk_data["ids"]) > 0:
                    final_chunks.append({
                        "chunk_id": chunk_data["ids"][0],
                        "text": chunk_data["documents"][0],
                        "metadata": chunk_data["metadatas"][0],
                        "distance": 0.5,
                    })

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
            print(f"[METADATA FILTER] Article {article_filter}: {len(article_chunks)} exact matches promoted (vector path)")

        return rerank_chunks(question, final_chunks[:60], top_k=40)


# ---------------------------------------------------------------------------
# Page-level retrieval (new pipeline)
# ---------------------------------------------------------------------------

def _extract_page_text(doc_id: str, page_number: int) -> str:
    """Extract full text from a specific page of a PDF document.

    page_number is 1-based (matches our grounding convention).
    Returns empty string for missing files or scanned pages with no text.
    """
    pdf_path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.pdf")
    if not os.path.exists(pdf_path):
        return ""
    doc = None
    try:
        doc = pymupdf.open(pdf_path)
        if page_number < 1 or page_number > len(doc):
            return ""
        return doc[page_number - 1].get_text().strip()
    except Exception:
        return ""
    finally:
        if doc is not None:
            doc.close()


_METADATA_QUESTION_PATTERNS = re.compile(
    r'\b(date of issue|issue date|issued|when was .* issued'
    r'|who (?:is|was|are|were) the judge'
    r'|presiding judge|name of.*judge'
    r'|claimants?|defendants?|respondents?|appellants?'
    r'|claim value|amount claimed|value of.*claim'
    r'|title page)\b',
    re.IGNORECASE,
)


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
    """
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
        # For 2-doc name/names comparison questions where the router boosts a specific non-p1 page
        # for EACH doc (e.g., claim value on p2), cap mpd=1 to get exactly 1 boosted page per doc.
        # Without this, mpd=2 selects p1+p2 from each doc, and max_total=3 drops p2 of the 2nd doc.
        effective_mpd = max_per_doc
        if (answer_type in ("name", "names") and boost_pages
                and len(target_doc_ids) == 2
                and all(d in boost_pages for d in target_doc_ids)
                and any(boost_pages[d] != 1 for d in target_doc_ids)):
            effective_mpd = 1
        results = _retrieve_pages_targeted(question, target_doc_ids, effective_mpd, max_total, answer_type, boost_pages=boost_pages, case_doc_groups=case_doc_groups)
        # Low-confidence fallback: if targeted retrieval's best score < 0.4,
        # the router likely pointed to the wrong doc. Supplement with corpus-wide
        # fallback retrieval and merge by score. (Threshold 0.4 vs 0.5: avoids triggering
        # when targeted correctly finds the right doc with a moderate score 0.40-0.50.)
        best_score = max((r.score for r in results), default=0.0)
        if best_score < 0.4:
            print(f"[retriever] low-confidence targeted ({best_score:.3f} < 0.40), adding fallback")
            # Limit fallback to 1 page to rescue routing misses without adding noise
            fb_results = _retrieve_pages_fallback(question, max_per_doc=1, max_total=1, answer_type=answer_type)
            # Merge: deduplicate by (doc_id, page_number), keep highest score
            seen = {}
            for r in results + fb_results:
                key = (r.doc_id, r.page_number)
                if key not in seen or r.score > seen[key].score:
                    seen[key] = r
            results = sorted(seen.values(), key=lambda p: p.score, reverse=True)[:max_total]
    else:
        results = _retrieve_pages_fallback(question, max_per_doc, max_total, answer_type)

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


def _dense_page_scores(question: str, doc_id: str, chunks: list[dict]) -> dict[int, float]:
    """Rank pages within a document using dense embedding similarity only.

    # Dense-only page ranking insight from IAS Partners (guy4)
    Returns dict of page_number -> max_similarity_score.
    """
    if not chunks:
        return {}

    query_emb = embed_query(question)
    model = get_embedding_model()

    # Embed all chunk texts for this doc
    chunk_texts = [BGE_QUERY_PREFIX + chunk["text"][:2000] for chunk in chunks]
    with _embedding_lock:
        chunk_embeddings = model.encode(chunk_texts, normalize_embeddings=True)

    import numpy as np  # noqa: E402 — lazy import to avoid startup cost
    query_arr = np.array(query_emb)
    similarities = chunk_embeddings @ query_arr

    page_scores: dict[int, float] = {}
    for chunk, sim in zip(chunks, similarities):
        page_num = chunk["metadata"].get("page", 1)
        sim_val = float(sim)
        if page_num not in page_scores or sim_val > page_scores[page_num]:
            page_scores[page_num] = sim_val

    return page_scores


def _retrieve_pages_targeted(
    question: str,
    target_doc_ids: list[str],
    max_per_doc: int,
    max_total: int,
    answer_type: str,
    boost_pages: dict[str, int] | None = None,
    case_doc_groups: dict[str, list[str]] | None = None,
) -> list[PageResult]:
    """Retrieve pages by reranking all chunks from target documents."""
    # Small-doc full inclusion: for documents with ≤8 pages, skip reranking and
    # return all pages. Avoids cross-encoder mistakes on short documents where a
    # wrong page choice is particularly costly. (Inspired by Vitaliy Pokrovskiy, 3rd place)
    SMALL_DOC_THRESHOLD = int(os.environ.get("SMALL_DOC_PAGES", "8"))
    chunks_by_doc_map = get_chunks_by_doc()
    ranker = get_reranker()

    # Detect metadata questions (date, judge, claimant) that are answered on page 1
    is_metadata_q = (
        answer_type in ("date", "name")
        and bool(_METADATA_QUESTION_PATTERNS.search(question))
    )

    # Detect date-related questions regardless of answer_type (e.g. "which doc has
    # the earlier issue date?" has answer_type=name but needs the date page).
    _is_date_question = bool(re.search(
        r'\b(date of issue|issue date|issued|earlier.*date|later.*date)\b',
        question, re.IGNORECASE,
    ))

    # Extract article root numbers for content-based definition page boost.
    # Acts as a fallback when the router's article_page_index doesn't have a mapping.
    # Only detects article DEFINITION headers (e.g., "13.\nTitle"), not references.
    # Skip when question asks about fines/penalties — the answer is in a schedule,
    # not the article definition page.
    _asks_fine = bool(re.search(r'\b(fine|penalty|penalt|sanction|contravene|contravention)\b', question, re.IGNORECASE))
    _art_root_nums = list(set(re.findall(r'Article\s+(\d+)', question, re.IGNORECASE))) if not _asks_fine else []

    # Law-title-page boost: "What is the law number / official number of X?"
    # Law numbers (e.g. "DIFC LAW NO. 5 OF 2020") appear on the title page (p1/p2).
    # CE over-ranks body articles (e.g. "cited as 'X Law'") vs the title page.
    # Strong +1.2 boost to p1 overrides CE preference for body text on this pattern.
    _asks_law_number = bool(re.search(
        r'\b(?:law\s+number|official\s+number|law\s+no\.?\s+of|numbered)\b',
        question, re.IGNORECASE,
    ))

    # Detect outcome questions for targeted page boost (mirrors _prescore_keyword_chunks)
    _asks_outcome_q = any(kw in question.lower() for kw in _OUTCOME_QUESTION_KEYWORDS)
    # Award-value detection: comparison questions about arbitral/judgment award amounts
    _asks_award_value = bool(re.search(
        r'\bhigher\b.*\baward\b|\baward\b.*\bvalue\b',
        question, re.IGNORECASE,
    ))
    # Cleaned CE query: strips long case names (≥25 chars before "[YEAR] DIFC TYPE NUM")
    # that bias the cross-encoder toward title pages. In targeted retrieval the doc is
    # already identified so the case name is redundant; removing it lets CE focus on
    # the semantic "what/why" portion of the question.
    _ce_query = _clean_query_for_ce(question)
    if _ce_query != question:
        print(f"[retriever] CE query cleaned: '{_ce_query[:80]}'")

    all_page_scores: list[PageResult] = []

    for doc_id in target_doc_ids:
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
                all_page_scores.append(PageResult(
                    doc_id=doc_id,
                    page_number=pg,
                    score=1.0,  # all pages equally scored for small docs
                    text=best_chunk.get("text", ""),
                ))
            print(f"[retriever] small-doc full inclusion: {doc_id[:12]} ({len(unique_pages)} pages)")
            continue

        # Dense-only page ranking insight from IAS Partners (guy4)
        # When PAGE_RANK_USE_BM25 is False, use dense similarity for initial page
        # scoring, then cross-encoder reranking on top candidates only.
        if not PAGE_RANK_USE_BM25:
            # Phase 1: Dense similarity scoring for all chunks
            dense_scores = _dense_page_scores(question, doc_id, doc_chunks)
            # Phase 2: Select top candidate chunks by dense score, then cross-encoder rerank
            chunk_dense = []
            for chunk in doc_chunks:
                pg = chunk["metadata"].get("page", 1)
                chunk_dense.append((dense_scores.get(pg, 0.0), chunk))
            chunk_dense.sort(key=lambda x: x[0], reverse=True)
            # Take top 50 chunks by dense score for cross-encoder reranking
            # V5: Raised from 20 to 50 — larger pre-filter improves CE recall
            # (not 100 — our BGE reranker-v2-m3 is heavier than benchmark's lighter CE)
            top_chunks = [c for _, c in chunk_dense[:50]]
            pairs = _format_reranker_pairs([(_ce_query, chunk["text"][:2000]) for chunk in top_chunks])
            with _reranker_lock:
                ce_scores = ranker.predict(pairs)
            # Merge: use cross-encoder scores for the top candidates
            page_scores: dict[int, float] = {}
            for chunk, score in zip(top_chunks, ce_scores):
                page_num = chunk["metadata"].get("page", 1)
                score_val = float(score)
                if page_num not in page_scores or score_val > page_scores[page_num]:
                    page_scores[page_num] = score_val
        else:
            # Original: Score all chunks against the question using cross-encoder
            # Use 2000 chars to capture more legal context than the default 1000
            # Use _ce_query (long case names removed) so CE focuses on semantics, not party names
            pairs = _format_reranker_pairs([(_ce_query, chunk["text"][:2000]) for chunk in doc_chunks])
            with _reranker_lock:  # tokenizer is not thread-safe
                scores = ranker.predict(pairs)
            page_scores: dict[int, float] = {}
            for chunk, score in zip(doc_chunks, scores):
                page_num = chunk["metadata"].get("page", 1)
                score_val = float(score)
                if page_num not in page_scores or score_val > page_scores[page_num]:
                    page_scores[page_num] = score_val

        # Track which pages contain article DEFINITION headers.
        _art_def_pages: set[int] = set()
        _has_router_boost = bool(boost_pages and doc_id in boost_pages)
        if _art_root_nums and not _has_router_boost:
            for chunk in doc_chunks:
                page_num = chunk["metadata"].get("page", 1)
                chunk_text = chunk["text"]
                for art_num in _art_root_nums:
                    if re.search(rf'(?:^|\n)\s*{re.escape(art_num)}\.\s*\n', chunk_text):
                        _art_def_pages.add(page_num)
                    elif re.search(rf'(?:^|\n)\s*(?:Article|ARTICLE)\s+{re.escape(art_num)}\s*[\n(]', chunk_text):
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
                if pg not in _award_boosted and re.search(
                    r'(?:EUR|USD|AED|GBP)\s+[\d,]+', chunk["text"]
                ):
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
                _boost_amt = (
                    1.2 if (answer_type in ("name", "names") and boost_pages[doc_id] != 1)
                    else 0.6
                )
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
                            re.search(r'SCHEDULE\s+\d+\s*\n\s*(?:CONTRAVENTIONS\s+AND\s+)?FINES', ct, re.IGNORECASE)
                            or re.search(r'SCHEDULE\s+\d+\s*\n\s*FINES\s+AND\s+FEES', ct, re.IGNORECASE)
                            or (re.search(r'^SCHEDULE\s+\d+', ct, re.IGNORECASE) and re.search(r'\bFINES?\b', ct[:200], re.IGNORECASE))
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
        if answer_type in _demotion_types and not is_metadata_q and not _p1_is_boosted and 1 in page_scores and len(page_scores) > 1:
            p1_score = page_scores[1]
            best_deep = max(
                ((pn, sc) for pn, sc in page_scores.items() if pn > 1),
                key=lambda x: x[1],
                default=None,
            )
            if best_deep and p1_score > best_deep[1] and (p1_score - best_deep[1]) < 0.15:
                # Swap: push page 1 just below the best deep page
                page_scores[1] = best_deep[1] - 0.001
                print(f"[retriever] title-page demotion: p1 ({p1_score:.3f}) demoted below p{best_deep[0]} ({best_deep[1]:.3f})")

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
            all_page_scores.append(PageResult(
                doc_id=doc_id,
                page_number=page_num,
                score=score,
                text=text,
            ))
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
                        print(f"[retriever] post-fusion rescue: injected {doc_id[:12]}:p{candidate.page_number} "
                              f"(score={candidate.score:.3f}) to ensure multi-doc coverage")
                        break
        results.sort(key=lambda p: p.score, reverse=True)
    else:
        results = all_page_scores[:max_total]

    ppq = len(results)
    doc_set = {r.doc_id[:12] for r in results}
    print(f"[retrieve_pages] targeted: {ppq} pages from {len(doc_set)} docs "
          f"({', '.join(f'{r.doc_id[:12]}:p{r.page_number}({r.score:.2f})' for r in results)})")

    return results


def _retrieve_pages_fallback(
    question: str,
    max_per_doc: int,
    max_total: int,
    answer_type: str,
) -> list[PageResult]:
    """Retrieve pages using full-corpus hybrid retrieval when no target docs are known."""
    # Use existing hybrid retrieval to get ranked chunks — pass answer_type for per-type depth
    chunks = retrieve(question, n_results=25, use_hyde=False, answer_type=answer_type)

    if not chunks:
        return []

    # Detect metadata questions
    is_metadata_q = (
        answer_type in ("date", "name")
        and bool(_METADATA_QUESTION_PATTERNS.search(question))
    )
    _is_date_question = bool(re.search(
        r'\b(date of issue|issue date|issued|earlier.*date|later.*date)\b',
        question, re.IGNORECASE,
    ))

    # Group by (doc_id, page_number), take the best chunk position as score
    # Lower position = higher score (first chunk is most relevant)
    page_best: dict[tuple[str, int], float] = {}
    for rank, chunk in enumerate(chunks):
        doc_id = chunk["metadata"]["pdf_id"]
        page_num = chunk["metadata"].get("page", 1)
        key = (doc_id, page_num)
        # Score: inverse rank (first result = highest score)
        score = 1.0 / (rank + 1)
        if key not in page_best or score > page_best[key]:
            page_best[key] = score

    # Apply bonuses — same targeted-page logic as _retrieve_pages_targeted()
    for (doc_id, page_num), score in list(page_best.items()):
        page_best[(doc_id, page_num)] = score + 0.02 / page_num
        if is_metadata_q:
            meta_target_page = (
                _DOC_DATE_PAGES.get(doc_id, 1) if (answer_type == "date" or _is_date_question) else 1
            )
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
        results.append(PageResult(
            doc_id=doc_id,
            page_number=page_num,
            score=score,
            text=text,
        ))
        doc_page_count[doc_id] = count + 1

    ppq = len(results)
    doc_set = {r.doc_id[:12] for r in results}
    print(f"[retrieve_pages] fallback: {ppq} pages from {len(doc_set)} docs "
          f"({', '.join(f'{r.doc_id[:12]}:p{r.page_number}({r.score:.2f})' for r in results)})")

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

        expanded.append(PageResult(
            doc_id=r.doc_id,
            page_number=r.page_number,
            score=r.score,
            text="\n\n".join(context_parts),
        ))
    return expanded
