# ARLC 2026 Legal QA Pipeline

## Pipeline Architecture

The **core** scoring path per question is: `route -> retrieve -> answer` (one LLM generation call in `arlc/answerer.py` for non-oracle questions).

- `arlc/pipeline.py` — Orchestrator: routing, retrieval, answering, then **post-processing** (article page fixes, absence detection, telemetry/doc_id guards).
- `arlc/router.py` — Deterministic document routing (regex, no LLM)
- `arlc/retriever.py` — Hybrid BM25 + FAISS vector + cross-encoder reranking
- `arlc/answerer.py` — Single LLM call per question (`claude-sonnet-4-6`)
- `arlc/llm/router.py` — LLM backend selector (`LLM_BACKEND`: litellm/vertex/anthropic/auto)
- `arlc/llm/litellm_backend.py` — Multi-endpoint round-robin with failover (default backend)

## Key Rules

1. Max 1 page per document, max 3 pages total per question
2. **Answer generation:** one main LLM call per question in `arlc/answerer.py`
3. TARGETED fixes only — NEVER make blanket changes to all answers
4. Confidence calibration MUST be included when info is absent ("document does not specify...")
5. Always run with `--workers 5` (prevents cross-encoder lock contention timeout)

## Answer Quality

- Free-text answers: **400-650 chars optimal**
- Confidence calibration: ALWAYS acknowledge when information is absent
- Targeted fixes to specific failing questions work best

## Telemetry

- Oracle entries: `total_time_ms` MUST be > 0
- Trick questions: MUST return EMPTY pages `[]` + answer starting "There is no information..."

## Git Safety

- **NEVER commit .env, API keys, proxy URLs, company names, or any sensitive data**
- Always scan staged files for secrets before committing (grep for sk-, rohlik, rhl, api_key, password, token patterns)
- `.env`, `.planning/`, `paper/` are gitignored — keep it that way
- The litellm proxy URLs and keys live ONLY in .env, never in committed code

## Data Files

- `data/case_metadata_index.json` — case metadata (judges, dates, parties, claims)
- `data/article_page_index.json` — article-to-page mappings for law docs
- `data/law_name_index.json` — law name variants to doc IDs
- `data/latest_edition_index.json` — latest edition of each law
