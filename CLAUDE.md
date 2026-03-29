# Vitreon Legal — AI Legal Research Platform

## Architecture

Three layers: `arlc/` (core RAG + agent), `neolex/` (FastAPI web layer), `frontend/` (Next.js UI).

### Core Pipeline (arlc/)

- `arlc/pipeline.py` — Deterministic pipeline: route → retrieve → answer (competition-proven)
- `arlc/agent/` — LangGraph ReAct agent (production path, `use_agent=True`)
  - `graph.py` — StateGraph: reason → search → reason → answer
  - `tools.py` — Search tool wrapping `retrieve_pages()` with deduplication
  - `prompts.py` — System prompt with grounding rules + prompt caching zones
  - `config.py` — All constants and tunable parameters
  - `verification.py` — Page verification adapter
- `arlc/router.py` — Deterministic document routing (regex, no LLM)
- `arlc/retriever.py` — Hybrid BM25 + FAISS + HyDE + RRF fusion + cross-encoder reranking
- `arlc/answerer.py` — LLM answer generation (Claude via Vertex AI)
- `arlc/page_verifier.py` — Post-retrieval page verification
- `arlc/qwen3_reranker.py` — Qwen3-Reranker + LlamaServerReranker client

### Web Layer (neolex/)

- `neolex/main.py` — FastAPI app with CSRF middleware, session cleanup, lifespan pre-warming
- `neolex/auth/` — HttpOnly cookie sessions, Google OAuth, email/password, rate limiting
- `neolex/routers/` — query (SSE streaming + agent), documents, admin, stripe, auth
- `neolex/db/` — PostgreSQL (auth/billing/conversations/audit)
- `neolex/services/` — agent_pipeline.py (agent adapter), conversation.py (multi-turn persistence)
- `neolex/middleware/` — CSRF, timeout (SSE-exempt), request ID, error handler

### Frontend (frontend/)

- Next.js 16 + TypeScript + Tailwind v4
- Glassmorphism design system, dark/light themes
- SSE token streaming via @microsoft/fetch-event-source
- HttpOnly cookie auth, CSRF headers on all POST requests
- Document index UI, law selector, session persistence
- i18n: EN, CS, DE, RU, AR

## Key Rules

1. **NEVER commit .env, API keys, proxy URLs, company names, or sensitive data**
2. **NEVER push the `product` branch to GitHub**
3. Use `uv` for Python, `npm` for Node.js
4. Agent is the production path (`use_agent=True`); deterministic pipeline for benchmarks
5. All status messages must be user-friendly — no internal details (model names, fallback info)

## Infrastructure

- **Embedding**: llama-server (Qwen3-8B-Q4_K_M.gguf) — failover: RTX 3070 → local Mac Metal
- **Reranking**: llama-server (Qwen3-Reranker-0.6B-Q8_0.gguf) — failover: RTX 3070 → local Mac Metal
- **FAISS indexes**: DIFC (26,947 chunks), Czech (6,826 chunks from 11 laws) — both dim=4096
- **Domain**: vitreon.app (Cloudflare Tunnel → Mac:3000 frontend, Mac:8000 backend)
- **Database**: PostgreSQL on local Mac (auth/billing/conversations/audit)
- **LLM**: Claude Sonnet 4.6 via Vertex AI (Haiku 4.5 for first-round query formulation)

### launchd Services

| Service | Port | Plist |
|---------|------|-------|
| Backend (FastAPI) | 8000 | app.vitreon.backend |
| Frontend (Next.js) | 3000 | app.vitreon.frontend |
| Embedding (llama-server) | 8088 | app.vitreon.llama |
| Reranker (llama-server) | 8089 | app.vitreon.reranker |
| Cloudflare Tunnel | — | app.vitreon.tunnel |

### RTX 3070 (100.98.171.97, optional)

When online, serves as primary for embedding (:8088) and reranking (:8089).
Backend auto-detects via health checks every 30s. Mid-query failover to local.

## Czech Corpus (11 laws)

obcansky_zakonik, trestni_zakonik, zakonik_prace, zakon_obch_korporace,
spravni_rad, zivnostensky_zakon, zakon_duchodove_pojisteni, zakon_dph,
zakon_dane_prijmu, zakon_nemocenske_pojisteni, danovy_rad

## Pricing (Sonnet 4.6 via Vertex AI)

| Plan | Price | Daily Limit | Avg Cost/Query |
|------|-------|-------------|----------------|
| Free | $0 | 3/day | $0.044 |
| Starter | $29/mo | 30/day | $0.044 |
| Pro | $179/mo | 200/day | $0.044 |
| Enterprise | $499/mo | unlimited | $0.044-0.165 |

## Security

- CSRF: X-Requested-With header required on all POST/PUT/DELETE
- Auth: HttpOnly SameSite=Lax cookies, bcrypt password hashing
- Sessions: SHA-256 hashed tokens, hourly cleanup of expired
- Rate limiting: per-user daily query limits, brute-force protection on login
- Admin: restricted to ADMIN_EMAILS env var
- Stripe: webhook signature verification + idempotency (LRU dedup)
- CSP, X-Frame-Options DENY, nosniff, strict Referrer-Policy
- Prompt injection defense in agent system prompt
- Input validation: law IDs, corpus names, conversation IDs all regex-validated
- Model name masked as "vitreon-legal" in API responses

## Benchmarks

| Benchmark | Score | SOTA | Notes |
|-----------|-------|------|-------|
| GaRAGe RAF | 0.826 | 0.607 | +36% above SOTA |
| Legal RAG Bench | 88% | 94% (Kanon 2) | Qwen3-8B via llama-server |
| ContractNLI F1 | 0.611 | 0.357 | +71% above fine-tuned BERT |

## Git Safety

- `.env`, `.planning/`, `paper/`, `.demo_key`, `models/*.gguf` are gitignored
- Git author email is `@rohlik.cz` — rewrite history before any public push
