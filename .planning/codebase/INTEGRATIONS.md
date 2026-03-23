# External Integrations

**Analysis Date:** 2026-03-23

## APIs & External Services

**Anthropic Claude API:**
- Primary integration for the entire pipeline
- SDK: `anthropic` >= 0.84.0
- Auth: `ANTHROPIC_API_KEY` env var
- Client initialization: `llm_anthropic.py` (singleton pattern with 120s timeout)
- Streaming: Uses `client.messages.stream()` for all LLM calls
- Cache control: Ephemeral cache on system prompts (`cache_control: {"type": "ephemeral"}`)
- Tool use: `answerer_v3.py` uses tool-based structured output (`submit_answer` tool)

**Models used:**

| Model | Purpose | Location |
|-------|---------|----------|
| `claude-sonnet-4-6` | Main answer generation (boolean, number, name types) | `answerer_v3.py` (MODEL constant) |
| `claude-opus-4-6` | Free-text answer generation (higher quality) | `answerer_v3.py` (MODEL_FREE_TEXT, env override) |
| `claude-haiku-4-5-20251001` | LLM reranking, query expansion, metadata extraction | `retriever.py`, `llm_reranker.py`, `answerer_v3.py` (MODEL_DECOMPOSE) |

**Call patterns:**
- `llm_anthropic.py`: Low-level streaming call, returns `(text, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens)`
- `llm_router.py`: Retry wrapper with exponential backoff (3 retries, 10/30/60s delays for rate limits)
- `answerer_v3.py`: Direct `anthropic.Anthropic` client (separate singleton, 120s timeout), uses both streaming and tool-use APIs
- `retriever.py`: Direct `anthropic.Anthropic` client (separate singleton, 30s timeout) for HyDE/query variants
- `llm_reranker.py`: Uses `llm_router.call_llm()` for reranking calls

**ARLC Platform API:**
- Competition platform for corpus download and submission
- SDK: Custom client in `starter_kit/arlc/` (imported as `EvaluationClient`)
- Auth: `EVAL_API_KEY` env var
- Used in: `prepare_corpus.py` (step_download function)
- Operations: `client.download_questions()`, `client.download_documents()`
- Submission: JSON file output (not direct API submission from code)

**Google AI API (optional, speed agent only):**
- SDK: Not directly used in main pipeline
- Auth: `GOOGLE_AI_API_KEY` env var (optional)
- Purpose: Gemini Flash Lite for the speed-optimized agent at `speed_agent/fast_pipeline.py`

## Data Storage

**Vector Database:**
- ChromaDB (persistent client)
  - Connection: Local filesystem at `data/chroma_db/`
  - Client: `chromadb.PersistentClient(path=CHROMA_DIR)`
  - Collection: `legal_docs` with cosine similarity HNSW index
  - Embedding: `SentenceTransformerEmbeddingFunction` with `BAAI/bge-large-en-v1.5` at index time
  - Query: Explicit embeddings via `SentenceTransformer.encode()` at query time (avoids loading model twice)
  - Built by: `indexer.py` (`build_index()`)

**BM25 Sparse Index:**
- `bm25s` library with disk cache
  - Location: `data/bm25_cache/`
  - Corpus IDs: `data/bm25_cache/corpus_ids.json`
  - Built from ChromaDB collection content at first query
  - Thread-safe lazy initialization with locks in `retriever.py`

**File Storage:**
- Local filesystem only
  - PDF documents: `data/documents/*.pdf`
  - JSON indices: `data/*.json` (article_page_index, case_metadata_index, law_name_index, latest_edition_index, appeal_index)
  - Pipeline output: `submission.json` (or custom path via `--output`)

**Caching:**
- In-memory caches (module-level dicts/singletons):
  - `retriever.py`: `_doc_index`, `_chunks_by_doc`, `_bm25_index`, `_collection`, `_reranker`, `_embedding_model`
  - `answerer_v3.py`: `_client` (Anthropic singleton)
  - `indexer.py`: `_doc_summary_cache` (SAC summaries)
  - `page_verifier.py`: `_page_text_cache` (PDF page text)
- All caches use double-checked locking pattern with `threading.Lock()` for thread safety

## ML Models (Local)

**Embedding Model:**
- `BAAI/bge-large-en-v1.5` (default, overridable via `EMBEDDING_MODEL` env var)
  - Used for: Document chunk embeddings (indexing) and query embeddings (retrieval)
  - Query prefix: `"Represent this sentence for searching relevant passages: "` (asymmetric retrieval)
  - Device: MPS (Apple Silicon) when available, else CPU
  - Loaded in: `retriever.py` (`get_embedding_model()`), `indexer.py` (via ChromaDB embedding function)

**Cross-Encoder Reranker:**
- `BAAI/bge-reranker-v2-m3`
  - Used for: Reranking retrieved chunks by relevance (max_length=1024 tokens)
  - Device: MPS (Apple Silicon) when available
  - Loaded in: `retriever.py` (`get_reranker()`)
  - Thread-safe: tokenizer requires lock (`_reranker_lock`)

**LLM Reranker (hybrid):**
- Combines cross-encoder scores (30% weight) with Haiku LLM relevance scores (70% weight)
  - Cross-encoder logits normalized via sigmoid to [0,1]
  - LLM scores parsed from JSON output, clamped to [0,1]
  - Implementation: `llm_reranker.py` (`llm_rerank_pages()`)

## Authentication & Identity

**Auth Provider:**
- API key-based (no user auth - CLI tool)
  - `ANTHROPIC_API_KEY`: Anthropic Claude API access
  - `EVAL_API_KEY`: ARLC competition platform access

## Monitoring & Observability

**Error Tracking:**
- None (logging to stderr/stdout)

**Logs:**
- Python `logging` module throughout all modules
- `print()` statements for progress reporting in pipeline steps
- Telemetry captured per question: `ttft_ms`, `tpot_ms`, `total_time_ms`, `input_tokens`, `output_tokens`

## CI/CD & Deployment

**Hosting:**
- Local execution only (competition pipeline)

**CI Pipeline:**
- None detected (no `.github/workflows/`, no CI config files)

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Claude API access for answer generation, reranking, metadata extraction
- `EVAL_API_KEY` - ARLC platform access for corpus download (only needed for `prepare_corpus.py`)

**Optional env vars:**
- `EMBEDDING_MODEL` - Override embedding model (default: `BAAI/bge-large-en-v1.5`)
- `MODEL_FREE_TEXT` - Override free-text model (default: `claude-opus-4-6`)
- `MODEL_NAME` - OCR model for scanned PDFs (disabled if empty)
- `LLM_RERANK_MODEL` - Override LLM reranker model (default: `claude-haiku-4-5-20251001`)
- `LLM_RERANK_WEIGHT` - LLM weight in hybrid reranking (default: 0.70)
- `LLM_RERANK_MAX_CHARS` - Max chars per page for LLM reranker (default: 1500)
- `GOOGLE_AI_API_KEY` - Gemini Flash Lite for speed agent

**Secrets location:**
- `.env` file in project root (gitignored)
- `.env.example` provides template

## Webhooks & Callbacks

**Incoming:**
- None (CLI pipeline, no server)

**Outgoing:**
- None (submission is JSON file output, not webhook)

---

*Integration audit: 2026-03-23*
