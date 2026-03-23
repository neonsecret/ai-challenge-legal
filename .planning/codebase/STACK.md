# Technology Stack

**Analysis Date:** 2026-03-23

## Languages

**Primary:**
- Python 3.13+ - All pipeline code, indexing, retrieval, answer generation

**Secondary:**
- None (pure Python codebase)

## Runtime

**Environment:**
- Python 3.13 (pinned in `.python-version`)
- macOS (Darwin) development; Apple Silicon MPS GPU acceleration used

**Package Manager:**
- `uv` - Fast Python package manager (commands: `uv run python ...`)
- Lockfile: `uv.lock` present

## Frameworks

**Core:**
- No web framework - CLI-based pipeline (`finals.py` is the orchestrator)

**Testing:**
- `pytest` >= 9.0.2 - Test runner (dev dependency)

**Build/Dev:**
- `ruff` >= 0.11.0 - Linter and formatter (dev dependency)
  - Config in `pyproject.toml`: target Python 3.13, line length 120
  - Rules: E, F, I, W (ignores E501 long lines)
- `uv` - Package management and script runner

## Key Dependencies

**Critical (answer generation):**
- `anthropic` >= 0.84.0 - Anthropic SDK for Claude API calls (streaming, tool use, cache control)
  - Used in: `llm_anthropic.py`, `llm_router.py`, `answerer_v3.py`, `retriever.py`, `llm_reranker.py`, `indexer.py`
  - Models: `claude-sonnet-4-6` (main answers), `claude-opus-4-6` (free-text answers), `claude-haiku-4-5-20251001` (reranking, query expansion, metadata extraction)

**Critical (retrieval):**
- `chromadb` >= 1.5.2 - Vector store for document embeddings
  - Used in: `indexer.py` (build index), `retriever.py` (query)
  - Persistent storage at `data/chroma_db/`
  - HNSW index with cosine similarity
- `sentence-transformers` >= 5.2.3 - Embedding models (BGE) and cross-encoder reranking
  - Used in: `retriever.py` (CrossEncoder for reranking, SentenceTransformer for query embedding)
  - Models: `BAAI/bge-large-en-v1.5` (embeddings), `BAAI/bge-reranker-v2-m3` (cross-encoder)
- `bm25s` >= 0.3.2 - BM25 sparse retrieval (hybrid search component)
  - Used in: `retriever.py`
  - Cached at `data/bm25_cache/`
- `flashrank` >= 0.2.10 - Fast initial reranking (declared dependency, used for early-stage filtering)

**Critical (document processing):**
- `pymupdf` >= 1.27.1 - PDF text extraction and OCR rendering
  - Used in: `indexer.py` (build index), `retriever.py` (page text), `answerer_v3.py` (page text), `page_verifier.py`, `build_article_index.py`
  - Also imported as `fitz` in `build_case_metadata_auto.py`

**Infrastructure:**
- `python-dotenv` >= 1.0.0 - Environment variable loading from `.env`
  - Used at top of most modules via `load_dotenv()`
- `requests` >= 2.32.0 - HTTP client (for ARLC platform API in starter kit)
- `openai` >= 2.24.0 - OpenAI SDK (declared dependency; optional, used in speed agent)

**Implicit (pulled by sentence-transformers):**
- `torch` - PyTorch, used for MPS GPU acceleration on Apple Silicon
  - Explicitly checked in `retriever.py` via `torch.backends.mps.is_available()`

## Configuration

**Environment:**
- `.env` file loaded at startup by `python-dotenv`
- `.env.example` documents required/optional vars:
  - `ANTHROPIC_API_KEY` (required) - Claude API access
  - `EVAL_API_KEY` (required for corpus download) - ARLC platform access
  - `GOOGLE_AI_API_KEY` (optional) - Gemini Flash Lite for speed agent
- Additional env vars used in code:
  - `EMBEDDING_MODEL` - Override embedding model (default: `BAAI/bge-large-en-v1.5`)
  - `MODEL_FREE_TEXT` - Override free-text answer model (default: `claude-opus-4-6`)
  - `MODEL_NAME` - OCR model for scanned PDFs
  - `LLM_RERANK_MODEL` - Override reranking model (default: `claude-haiku-4-5-20251001`)
  - `LLM_RERANK_WEIGHT` - LLM vs cross-encoder weight (default: 0.70)
  - `LLM_RERANK_MAX_CHARS` - Max chars per page for LLM reranker (default: 1500)

**Build:**
- `pyproject.toml` - Project metadata, dependencies, ruff config
- No Makefile or CI config detected

## Platform Requirements

**Development:**
- Python 3.13+
- `uv` package manager
- Anthropic API key (for answer generation, reranking, metadata extraction)
- ~4GB disk for ChromaDB index + PDF corpus + model caches
- Apple Silicon recommended (MPS acceleration for cross-encoder and embeddings)

**Production/Submission:**
- Same as development (runs locally, submits JSON to ARLC platform)
- Run command: `uv run python finals.py --workers 5`
- Corpus prep: `uv run python prepare_corpus.py`

## Data Files

**Pre-built indices (JSON, committed or generated):**
- `data/case_metadata_index.json` - Case metadata (judges, dates, parties, claims)
- `data/article_page_index.json` - Article-to-page mappings for law documents
- `data/law_name_index.json` - Law name variants to doc IDs
- `data/latest_edition_index.json` - Latest edition of each law
- `data/appeal_index.json` - Appeal case index

**Generated at index time:**
- `data/chroma_db/` - ChromaDB persistent vector store
- `data/bm25_cache/` - BM25 index cache (corpus_ids.json + index files)

**Input:**
- `data/documents/*.pdf` - Legal document corpus (downloaded from ARLC platform)
- `data/questions.json` - Question set (downloaded from ARLC platform)

---

*Stack analysis: 2026-03-23*
