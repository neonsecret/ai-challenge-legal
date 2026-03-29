# Vitreon Legal — AI Legal Research Platform

## Architecture

Two layers: `arlc/` (core RAG pipeline, competition-proven) wrapped by `neolex/` (FastAPI web layer + frontend).

### Core Pipeline (arlc/)

- `arlc/pipeline.py` — Orchestrator: route → retrieve → answer (+ on_status/on_token callbacks)
- `arlc/router.py` — Deterministic document routing (regex, no LLM)
- `arlc/retriever.py` — Hybrid BM25 + FAISS (Qwen3-8B via llama-server) + Qwen3-Reranker-0.6B
- `arlc/answerer.py` — Single LLM call per question (Claude via Vertex AI)
- `arlc/llm/router.py` — LLM backend selector (litellm/vertex/anthropic/auto)

### Web Layer (neolex/)

- `neolex/main.py` — FastAPI app with lifespan pre-warming
- `neolex/auth/` — HttpOnly cookie sessions, API key auth, Google OAuth, email/password
- `neolex/routers/` — query (POST + SSE streaming), documents, admin, demo, stripe, auth
- `neolex/db/` — SQLite audit log (WAL), PostgreSQL for users/billing
- `neolex/embeddings/` — Qwen3-8B adapter (llama-server backend)

### Frontend (frontend/)

- Next.js 16 + TypeScript + Tailwind v4
- Glassmorphism design system, dark/light themes
- SSE token streaming via @microsoft/fetch-event-source
- HttpOnly cookie auth (no API keys in localStorage or URLs)

## Key Rules

1. **NEVER commit .env, API keys, proxy URLs, company names, or sensitive data**
2. **NEVER push the `product` branch to GitHub**
3. Do NOT modify `arlc/` without good reason — it's the competition-proven core
4. Pipeline improvements help, manual patches hurt
5. Bug fixes win. "Improvements" lose.

## Package Management

- **Python**: use `uv` for dependency management (`uv pip install`, `uv add`)
- **Node.js**: use `npm` for frontend

## Infrastructure

- **Embedding server**: llama-server (Qwen3-8B-Q4_K_M.gguf) — runs on RTX 3070 remote (100.98.171.97:8088) or locally
- **FAISS index**: `data/faiss_llama-server.bin` (26,947 vectors, dim=4096)
- **Metadata**: `data/faiss_llama-server.json` (doc_id, pdf_id, page, text)
- **Czech index**: `data/faiss_czech.bin` (1,216 vectors, dim=4096)
- **Domain**: vitreon.app (Cloudflare Tunnel → Mac:3000 frontend, Mac:8000 backend)
- **Database**: SQLite for audit (local), PostgreSQL on local Mac for auth/billing

## Benchmarks

| Benchmark                    | Score | SOTA          | Notes                      |
|------------------------------|-------|---------------|----------------------------|
| GaRAGe RAF                   | 0.826 | 0.607         | +36% above SOTA            |
| Legal RAG Bench              | 88%   | 94% (Kanon 2) | Qwen3-8B via llama-server  |
| ContractNLI Contradiction F1 | 0.611 | 0.357         | +71% above fine-tuned BERT |

## Git Safety

- `.env`, `.planning/`, `paper/`, `.demo_key` are gitignored
- `scripts/scan-secrets.sh` — run before any commit
- Git author email is `@rohlik.cz` — rewrite history before any public push

## Data Files

- `data/documents/` — 303 DIFC PDFs (competition corpus)
- `data/corpus/czech/` — 5 Czech codes (Civil, Criminal, Labour, Business, Admin)
- `data/case_metadata_index.json` — case metadata
- `data/article_page_index.json` — article-to-page mappings
- `data/law_name_index.json` — law name variants to doc IDs
