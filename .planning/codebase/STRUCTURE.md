# Codebase Structure

**Analysis Date:** 2026-03-23

## Directory Layout

```
ai-challenge-legal/
├── finals.py                  # Pipeline orchestrator (entry point)
├── router.py                  # Deterministic document routing (regex)
├── retriever.py               # Hybrid BM25 + vector + cross-encoder retrieval
├── answerer_v3.py             # LLM answer generation (Sonnet/Opus)
├── llm_router.py              # LLM call wrapper with retry logic
├── llm_anthropic.py           # Anthropic SDK streaming client
├── llm_reranker.py            # Haiku-based LLM reranking (70/30 weighting)
├── page_verifier.py           # Post-answer page verification and re-selection
├── format_guardian.py         # Answer format validation and correction
├── indexer.py                 # ChromaDB vector index builder
├── prepare_corpus.py          # End-to-end corpus preparation script
├── build_article_index.py     # Article-to-page mapping builder
├── build_case_index.py        # Case metadata extractor (Haiku-based)
├── build_case_metadata_auto.py # Automated case metadata for 300+ docs
├── build_law_index_v2.py      # Law name/edition index builder
├── conftest.py                # Pytest root config (adds project to sys.path)
├── Makefile                   # Build/run targets
├── pyproject.toml             # Project config and dependencies (uv)
├── CLAUDE.md                  # Project instructions for Claude Code
├── README.md                  # Project documentation
├── data/
│   ├── documents/             # Source PDF documents (legal corpus)
│   ├── chroma_db/             # ChromaDB persistent vector index
│   ├── bm25_cache/            # BM25 index cache
│   ├── bm25_cache_hierarchical/ # Hierarchical BM25 variant
│   ├── case_metadata_index.json  # Case metadata (judges, dates, parties, claims)
│   ├── article_page_index.json   # Article -> page number mappings
│   ├── law_name_index.json       # Law name variants -> doc IDs
│   ├── latest_edition_index.json # Latest edition per law
│   ├── consultation_paper_index.json  # CP number -> doc ID
│   ├── court_order_index.json    # Court order number -> doc ID
│   ├── appeal_index.json         # Appeal chain mappings
│   └── questions.json            # Input questions (from platform)
├── tests/
│   ├── test_law_index_v2.py   # Law index tests
│   ├── test_case_index.py     # Case index tests
│   ├── test_agent_tools.py    # Agent tools tests
│   └── test_agent_v2.py       # Agent v2 tests
├── speed_agent/
│   ├── fast_pipeline.py       # Speed-optimized pipeline (PyPy3, Gemini Flash)
│   ├── build_page_cache.py    # Pre-extract PDF text to JSON cache
│   ├── run_pipeline.sh        # Shell wrapper for speed pipeline
│   └── README.md              # Speed agent documentation
├── output/                    # Pipeline output directory
│   └── competitor_analysis.md # Analysis notes
├── .planning/
│   └── codebase/              # Architecture documentation (this file)
├── .chroma/                   # ChromaDB metadata
├── .flashrank_cache/          # FlashRank model cache
└── other_people/              # Competitor analysis notes
```

## Directory Purposes

**Root directory:**
- Purpose: All core pipeline Python modules live at project root (flat structure, no `src/` directory)
- Contains: 16 Python files, config files, documentation
- Key files: `finals.py` (orchestrator), `router.py`, `retriever.py`, `answerer_v3.py`

**`data/`:**
- Purpose: All data artifacts — source documents, vector indexes, metadata indexes
- Contains: PDFs in `documents/`, ChromaDB in `chroma_db/`, BM25 cache, 7+ JSON index files
- Key files: `case_metadata_index.json` (oracle source), `article_page_index.json` (article-to-page), `law_name_index.json` (law routing)
- Generated: Yes (by `prepare_corpus.py` and `build_*` scripts)
- Committed: Index JSON files are committed; `chroma_db/` and `bm25_cache/` are generated

**`tests/`:**
- Purpose: Pytest test files for index builders and agent tools
- Contains: 4 test files
- Key files: `test_law_index_v2.py`, `test_case_index.py`

**`speed_agent/`:**
- Purpose: Alternative speed-optimized pipeline using PyPy3 + Gemini Flash Lite
- Contains: Standalone pipeline that pre-caches PDF text and uses stdlib HTTP (no C extensions)
- Key files: `fast_pipeline.py` (main entry), `build_page_cache.py` (one-time PDF extraction)

**`output/`:**
- Purpose: Pipeline run outputs (results JSON, submission JSON)
- Generated: Yes (by `finals.py`)
- Committed: No (except analysis notes)

## Key File Locations

**Entry Points:**
- `finals.py`: Main pipeline entry — `uv run python finals.py --questions data/questions.json --workers 5`
- `prepare_corpus.py`: Corpus preparation — `uv run python prepare_corpus.py`
- `speed_agent/fast_pipeline.py`: Speed pipeline — `pypy3 speed_agent/fast_pipeline.py`

**Configuration:**
- `pyproject.toml`: Python dependencies, project metadata
- `Makefile`: Build/run targets (`make setup`, `make run`, `make index`, `make test`)
- `CLAUDE.md`: Pipeline architecture rules and constraints for Claude Code
- `.env`: API keys (not committed, existence noted only)

**Core Pipeline (in execution order):**
- `router.py`: Stage 1 — regex-based document routing, `RouteResult` dataclass
- `retriever.py`: Stage 2 — hybrid search (BM25 + vector + cross-encoder + LLM reranker)
- `answerer_v3.py`: Stage 3 — LLM answer generation with oracle fast-path and type-specific prompts

**Supporting Modules:**
- `llm_router.py`: LLM call dispatcher with retry logic (rate-limit backoff)
- `llm_anthropic.py`: Anthropic SDK streaming client (singleton, 120s timeout)
- `llm_reranker.py`: Haiku-based LLM reranking (weighted 70% LLM / 30% cross-encoder)
- `page_verifier.py`: Deterministic page verification + optional LLM re-selection
- `format_guardian.py`: Answer format fixer (string->bool, date normalization, etc.)
- `indexer.py`: ChromaDB index builder with SAC (Summary-Augmented Context)

**Index Builders:**
- `build_article_index.py`: Scans PDFs, maps articles/rules/sections to page numbers -> `data/article_page_index.json`
- `build_case_index.py`: Extracts case metadata (judge, date, parties, claims) via Haiku -> `data/case_metadata_index.json`
- `build_case_metadata_auto.py`: Automated version for 300+ docs (async, batched Haiku calls)
- `build_law_index_v2.py`: Builds law name variants and latest edition tracking -> `data/law_name_index.json`, `data/latest_edition_index.json`

**Testing:**
- `conftest.py`: Root pytest config (adds project root to `sys.path`)
- `tests/test_law_index_v2.py`: Tests for law name extraction and index building
- `tests/test_case_index.py`: Tests for case metadata extraction
- `tests/test_agent_tools.py`: Tests for agent tool functions
- `tests/test_agent_v2.py`: Tests for agent v2 functionality

## Naming Conventions

**Files:**
- Snake_case for all Python modules: `finals.py`, `answerer_v3.py`, `build_case_index.py`
- `llm_` prefix for LLM interaction modules: `llm_router.py`, `llm_anthropic.py`, `llm_reranker.py`
- `build_` prefix for index builder scripts: `build_article_index.py`, `build_case_index.py`
- `test_` prefix for test files: `test_law_index_v2.py`

**Directories:**
- Lowercase, underscore-separated: `speed_agent/`, `bm25_cache/`
- Dot-prefixed for hidden/tool directories: `.planning/`, `.chroma/`, `.flashrank_cache/`

**Data Files:**
- JSON index files use `_index.json` suffix: `case_metadata_index.json`, `article_page_index.json`
- PDF documents use their platform-assigned hash IDs: `{hex_id}.pdf`

## Where to Add New Code

**New Pipeline Stage:**
- Create a new Python module at project root: `my_stage.py`
- Define a main function and a result dataclass
- Import lazily in `finals.py::_import_pipeline_modules()`
- Wire into `_process_question_inner()` at the appropriate step

**New Data Index:**
- Create `build_my_index.py` at project root
- Output to `data/my_index.json`
- Add to `Makefile` `index` target
- Load in the module that needs it (router, retriever, or answerer)

**New Answer Type or LLM Prompt:**
- Add system prompt constant in `answerer_v3.py` (follow `_SYSTEM_*` naming pattern)
- Wire into `generate_answer()` type dispatch

**New Post-Processing Step:**
- Add in `finals.py::_process_question_inner()` after Step 3 (answer generation)
- Keep it deterministic (no LLM) if possible to avoid PPQ increase
- Gate behind answer_type if only applicable to certain types

**New Test:**
- Create `tests/test_my_module.py`
- Run with `make test` or `uv run pytest tests/ -v`

**Utilities / Helpers:**
- Add to the module that uses them (no shared `utils.py` exists)
- LLM utilities go in `llm_router.py` or `llm_anthropic.py`

## Special Directories

**`data/chroma_db/`:**
- Purpose: ChromaDB persistent vector index (BGE-large embeddings, cosine similarity)
- Generated: Yes (by `indexer.py` / `prepare_corpus.py`)
- Committed: No (too large, rebuild from PDFs)

**`data/bm25_cache/`:**
- Purpose: Pre-computed BM25 index for fast keyword search
- Generated: Yes (by retriever on first run, or cleared by indexer)
- Committed: No

**`.flashrank_cache/`:**
- Purpose: Cached FlashRank MiniLM model weights (ONNX format)
- Generated: Yes (downloaded on first use)
- Committed: No

**`speed_agent/`:**
- Purpose: Standalone speed-optimized pipeline (separate from main pipeline)
- Generated: No (hand-written)
- Committed: Yes

## Module Dependency Graph

```
finals.py (orchestrator)
├── router.py
│   └── data/*.json (7 index files)
├── retriever.py
│   ├── chromadb (data/chroma_db)
│   ├── bm25s (data/bm25_cache)
│   ├── sentence_transformers (BGE embeddings, cross-encoder)
│   ├── llm_reranker.py
│   │   └── anthropic SDK (Haiku)
│   └── pymupdf (PDF reading)
├── answerer_v3.py
│   ├── anthropic SDK (Sonnet/Opus, direct client)
│   ├── pymupdf (PDF reading for mega-context)
│   └── data/*.json (case_metadata, article_page, appeal indexes)
├── page_verifier.py
│   ├── pymupdf (PDF reading, cached)
│   └── llm_router.py (optional LLM fallback)
│       └── llm_anthropic.py
│           └── anthropic SDK
├── format_guardian.py (no dependencies)
├── indexer.py
│   ├── pymupdf
│   ├── chromadb
│   ├── anthropic SDK (SAC generation)
│   └── sentence_transformers (BGE embeddings)
└── grounding_verifier (imported dynamically, file not present in repo)
```

---

*Structure analysis: 2026-03-23*
