# Architecture

**Analysis Date:** 2026-03-23

## Pattern Overview

**Overall:** Three-stage RAG pipeline with oracle fast-paths and multi-layer post-processing

**Key Characteristics:**
- Deterministic regex-based routing (no LLM) narrows document scope before retrieval
- Oracle metadata lookups bypass retrieval+LLM for ~40% of questions (judge/party/date comparisons)
- Hybrid BM25 + vector + cross-encoder retrieval scoped to target documents
- Single LLM generation call per non-oracle question (Sonnet for deterministic types, Opus for free_text)
- Extensive post-processing: page verification, grounding verification, absence detection, format guarding
- Async pipeline with semaphore-based concurrency (default 5 workers)

## Layers

**Orchestrator (finals.py):**
- Purpose: End-to-end pipeline coordination, question processing, submission formatting
- Location: `finals.py`
- Contains: `_process_question()` (outer retry/timeout wrapper), `_process_question_inner()` (core pipeline logic), trick question detection, page limit enforcement, submission validation, Unicode normalization
- Depends on: `router.py`, `retriever.py`, `answerer_v3.py`, `page_verifier.py`, `format_guardian.py`, `indexer.py`
- Used by: CLI entry point (`__main__` block)

**Router (router.py):**
- Purpose: Deterministic document routing via regex extraction of case IDs, law names, article numbers
- Location: `router.py`
- Contains: `Router` class, `RouteResult` dataclass, regex patterns for case IDs/law names/articles/consultation papers/court orders
- Depends on: Data indexes (`case_metadata_index.json`, `article_page_index.json`, `law_name_index.json`, `latest_edition_index.json`, `consultation_paper_index.json`, `court_order_index.json`, `appeal_index.json`)
- Used by: `finals.py` (Step 1)

**Retriever (retriever.py):**
- Purpose: Hybrid search combining BM25, vector embeddings, and cross-encoder reranking
- Location: `retriever.py`
- Contains: `retrieve_pages()` (main entry), `PageResult` dataclass, keyword search, embedding search, cross-encoder reranking, LLM reranking
- Depends on: ChromaDB (`data/chroma_db`), BM25 index (`data/bm25_cache`), `llm_reranker.py`, `llm_router.py`
- Used by: `finals.py` (Step 2)

**Answerer (answerer_v3.py):**
- Purpose: LLM-based answer generation with type-specific system prompts and oracle metadata lookup
- Location: `answerer_v3.py`
- Contains: `generate_answer()`, `_lookup_oracle()`, type-specific system prompts, question decomposition, `AnswerResult` dataclass
- Depends on: Anthropic API (via direct SDK), `case_metadata_index.json`, `article_page_index.json`, `appeal_index.json`
- Used by: `finals.py` (Step 3)

**LLM Layer (llm_router.py, llm_anthropic.py):**
- Purpose: Centralized LLM calling with retry logic and rate-limit handling
- Location: `llm_router.py` (retry wrapper), `llm_anthropic.py` (Anthropic SDK streaming client)
- Contains: `call_llm()` with exponential backoff (10s/30s/60s), streaming response collection, token counting
- Depends on: `anthropic` SDK, `ANTHROPIC_API_KEY` env var
- Used by: `llm_reranker.py`, `page_verifier.py`, post-processing steps in `finals.py`

**Page Verifier (page_verifier.py):**
- Purpose: Verify cited pages support the answer; re-select pages if evidence not found
- Location: `page_verifier.py`
- Contains: Two-stage verification (deterministic keyword matching, then optional LLM fallback), PDF text extraction with caching
- Depends on: `pymupdf` (PDF reading), `llm_router.py` (optional LLM fallback)
- Used by: `finals.py` (Step 4)

**Format Guardian (format_guardian.py):**
- Purpose: Last-line format validation and correction before submission
- Location: `format_guardian.py`
- Contains: `FormatGuardian` class with type-specific fixers (boolean, number, date, name, names, free_text)
- Depends on: Nothing (pure logic)
- Used by: `finals.py` (Step 4 format check)

**LLM Reranker (llm_reranker.py):**
- Purpose: Haiku-based page reranking combining cross-encoder scores (30%) with LLM relevance scores (70%)
- Location: `llm_reranker.py`
- Contains: `rerank_with_llm()`, weighted score combination
- Depends on: `anthropic` SDK
- Used by: `retriever.py` (for free_text questions)

**Indexer (indexer.py):**
- Purpose: Build ChromaDB vector index from PDF documents
- Location: `indexer.py`
- Contains: `build_index()`, PDF extraction, page chunking, SAC (Summary-Augmented Context) generation, OCR fallback
- Depends on: `pymupdf`, `chromadb`, `anthropic` SDK, `sentence-transformers`
- Used by: `finals.py` (Step 0, if index missing)

## Data Flow

**Normal Question Flow (non-oracle, non-trick):**

1. `finals.py::run_pipeline()` loads questions JSON, sorts by target doc_id for prompt cache efficiency
2. `finals.py::_process_question()` wraps each question in async task with semaphore (max N concurrent)
3. `router.route(question, answer_type)` extracts case IDs, law names, articles via regex -> returns `RouteResult` with `target_doc_ids`, `metadata_answer`, `metadata_pages`
4. `finals.py::_process_question_inner()` checks three fast-paths:
   - **Fast Path A:** Router pre-computed answer (metadata_answer not None) -> return immediately with oracle pages
   - **Fast Path B:** `answerer_v3._lookup_oracle()` can answer from case metadata (judge/party booleans) -> return immediately
   - **Fast Path C:** `_is_trick_question()` detects criminal/non-DIFC concepts -> return empty pages + canned answer
5. `retriever.retrieve_pages(question, target_doc_ids, ...)` performs hybrid search:
   - Keyword matching narrows to candidate documents
   - ChromaDB vector search within candidate docs (BGE embeddings)
   - BM25 search across corpus, filtered to target docs
   - Cross-encoder reranking (BAAI/bge-reranker-v2-m3)
   - Optional LLM reranking for free_text (Haiku, 70% weight)
   - Returns top pages as `PageResult` objects
6. `answerer_v3.generate_answer(question, answer_type, source_pages)` makes single LLM call:
   - Sonnet 4.6 for deterministic types (boolean, number, date, name, names)
   - Opus 4.6 for free_text (higher quality needed for S_asst scoring)
   - Type-specific system prompts with structured reasoning (CoT in `<analysis>` tags for free_text)
7. Post-processing pipeline in `_process_question_inner()`:
   - **Step 4:** `page_verifier.verify_pages()` — deterministic page verification, replaces unsupported pages
   - **Step 3.5:** LLM page verification (for free_text/boolean with 2+ pages) — lightweight LLM call to confirm page relevance
   - **Step 4.5:** Grounding verification (free_text only) — checks claims are grounded in source pages
   - **Absence classifier:** Clears pages when both question pattern and answer text confirm absence
   - **Hallucination filter:** `_validate_chunk_pages()` removes page citations not in retrieved set
   - **Smart doc cap:** Limits citations to router's target doc count
   - **Hard cap:** `_enforce_page_limit()` — max 1 page per doc, max 3 pages total
8. `format_guardian.guard_result()` — programmatic format validation and correction
9. Results collected, sorted by original order, converted to submission format via `_to_submission_format()`

**Oracle Fast-Path Flow (~40% of questions):**

1. Router extracts case IDs and detects metadata question type (judge, parties, date_of_issue, claim_value)
2. Router returns `RouteResult.metadata_answer` pre-computed from `case_metadata_index.json`
3. OR `answerer_v3._lookup_oracle()` computes answer from cross-case metadata (judge overlap, party overlap, date comparison, claim value comparison)
4. Pages are constructed from case metadata (doc_id -> page where metadata was found)
5. Entire retrieval + LLM generation is skipped -> `total_time_ms` ~ 1ms

**State Management:**
- Module-level singletons for expensive resources: ChromaDB client, cross-encoder model, BGE embedding model, BM25 index, Anthropic client
- Thread-safe initialization via `threading.Lock` (critical for parallel workers)
- Pre-warming in `finals.py` Step 3b loads all singletons before parallel processing starts
- PDF text cached per-document in `page_verifier.py` (`_page_text_cache`)

## Key Abstractions

**RouteResult (router.py):**
- Purpose: Carries routing decisions from router to orchestrator
- Defined in: `router.py` line 222
- Pattern: Dataclass with `target_doc_ids`, `metadata_answer`, `metadata_pages`, `case_ids`, `law_names`, `article_numbers`, `metadata_type`

**PageResult (retriever.py):**
- Purpose: Represents a single retrieved page with score and text
- Defined in: `retriever.py` line 84
- Pattern: Dataclass with `doc_id`, `page_number`, `score`, `text`

**AnswerResult (answerer_v3.py):**
- Purpose: Carries generated answer with telemetry
- Defined in: `answerer_v3.py` line 73
- Pattern: Dataclass with `answer`, `chunk_pages`, timing fields, token counts, `model_name`

**chunk_pages format:**
- Purpose: Universal page citation format used throughout the pipeline
- Pattern: `[{"doc_id": str, "page_numbers": [int]}, ...]`
- Constraint: Max 1 page per doc, max 3 docs total

## Entry Points

**CLI (finals.py `__main__`):**
- Location: `finals.py` (bottom of file)
- Triggers: `uv run python finals.py --questions data/questions.json --workers 5 --output output/run1`
- Responsibilities: Parse args, call `asyncio.run(run_pipeline(...))`

**Corpus Preparation (prepare_corpus.py):**
- Location: `prepare_corpus.py`
- Triggers: `uv run python prepare_corpus.py`
- Responsibilities: Download docs, build ChromaDB index, extract metadata, build all data indexes, smoke test

**Index Building (Makefile `index` target):**
- Location: `Makefile`
- Triggers: `make index`
- Responsibilities: Run `build_case_metadata_auto.py`, `build_law_index_v2.py`, `build_article_index.py`, `indexer.py` in sequence

**Speed Agent (speed_agent/fast_pipeline.py):**
- Location: `speed_agent/fast_pipeline.py`
- Triggers: `pypy3 speed_agent/fast_pipeline.py --questions data/questions.json`
- Responsibilities: Optimized pipeline for speed competition (PyPy3, no C extensions, Gemini Flash Lite, pre-cached PDF text)

## Error Handling

**Strategy:** Multi-layer retry with graceful degradation

**Patterns:**
- **Question-level retry:** `_process_question()` retries up to 2 times on any exception, with 5s pause between retries
- **Timeout cascade:** 600s outer timeout -> 300s inner LLM timeout -> Sonnet fallback on timeout -> null answer as last resort
- **LLM retry with backoff:** `llm_router.py` retries rate-limited requests 3 times with 10s/30s/60s delays
- **Fallback modules:** If router/retriever/answerer modules fail to import, orchestrator uses fallback implementations
- **Fallback answers:** Boolean -> `False`, everything else -> `None`, with page-1 citations from routed docs
- **Thread-safe initialization:** All ML model loading uses `threading.Lock` to prevent races on cold start

## Cross-Cutting Concerns

**Logging:** Python `logging` module; info/warning/debug levels. Pipeline progress via `print()` to stdout, errors to stderr.

**Validation:** `validate_submission()` in `finals.py` performs comprehensive schema validation before any submission. `FormatGuardian` fixes type coercion issues (string "true" -> bool True).

**Authentication:** Single `ANTHROPIC_API_KEY` env var for all LLM calls. Pipeline exits immediately if not set.

**Unicode Normalization:** NFKC normalization + Cyrillic-to-Latin homoglyph replacement on all string answers (`_normalize_answer()` in `finals.py`, `check_homoglyphs()` in `answerer_v3.py`).

**Concurrency:** `asyncio.Semaphore(workers)` gates parallel question processing. `asyncio.to_thread()` wraps synchronous retriever/router calls. Thread locks protect model initialization.

---

*Architecture analysis: 2026-03-23*
