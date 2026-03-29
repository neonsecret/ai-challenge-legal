# NeoLex Security Architecture

**Version:** 1.0
**Date:** 2026-03-26
**Owner:** Engineering

---

## System Overview

NeoLex is a legal QA API that retrieves context from law firm documents and generates
grounded answers using the Claude API. It is designed for single-tenant or multi-tenant
law firm deployment behind Tailscale Funnel (zero-trust network access).

---

## Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                           INTERNET (untrusted)                               ║
╚════════════════════════════════╦═════════════════════════════════════════════╝
                                 │ HTTPS (TLS 1.3)
                                 │ via Tailscale Funnel
                                 ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  TRUST BOUNDARY: FRONTEND (Next.js)                                          ║
║                                                                              ║
║  Next.js Dev Server (port 3000)                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │  pages/api/*      — server-side API proxy (never exposes API keys)  │     ║
║  │  app/chat/*       — streaming chat UI (SSE EventSource)             │     ║
║  │  app/documents/*  — document upload UI                              │     ║
║  └─────────────────────────────────────────────────────────────────────┘     ║
║                                                                              ║
╚════════════════════════════════╦═════════════════════════════════════════════╝
                                 │ HTTP (localhost only, internal)
                                 │ Authorization: Bearer <api_key>
                                 ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  TRUST BOUNDARY: BACKEND (FastAPI)                                           ║
║                                                                              ║
║  FastAPI (port 8000, single uvicorn process)                                 ║
║                                                                              ║
║  ┌─ Middleware Stack (applied in order) ──────────────────────────────────┐  ║
║  │  1. RequestIDMiddleware   — assigns UUID per request, logs to stdout   │  ║
║  │  2. TimeoutMiddleware     — enforces REQUEST_TIMEOUT_SECONDS limit      │  ║
║  │  3. JSONErrorMiddleware   — converts exceptions to RFC 7807 responses   │  ║
║  │  4. CORSMiddleware        — restricts origins via ALLOWED_ORIGINS env   │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌─ Auth Layer ───────────────────────────────────────────────────────────┐  ║
║  │  get_api_key()     — validates SHA-256(key) against SQLite api_keys    │  ║
║  │  get_admin_key()   — additionally requires scope == 'admin'            │  ║
║  │  All failures → 401/403 + audit log event (IP + user-agent captured)   │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌─ Routers ──────────────────────────────────────────────────────────────┐  ║
║  │  POST  /api/v1/query          → query.py → arlc/ pipeline             │  ║
║  │  GET   /api/v1/query/stream   → query.py → arlc/ pipeline (SSE)       │  ║
║  │  POST  /api/v1/documents      → documents.py → save + reindex         │  ║
║  │  GET   /api/v1/documents      → documents.py → list client docs       │  ║
║  │  DELETE /api/v1/documents/{id}→ documents.py → delete + reindex       │  ║
║  │  POST  /api/v1/documents/reindex → documents.py → trigger reindex     │  ║
║  │  GET   /api/v1/documents/reindex/{job_id} → poll job status           │  ║
║  │  GET   /api/v1/admin/audit    → admin.py → read audit log (admin)     │  ║
║  │  GET   /health*               → health.py → no auth required          │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌─ Data Stores ──────────────────────────────────────────────────────────┐  ║
║  │  neolex.db (SQLite, WAL mode)                                          │  ║
║  │    ├── api_keys        — key hashes, scopes, client slugs             │  ║
║  │    ├── queries         — APPEND ONLY — question, answer, latency, IP  │  ║
║  │    ├── events          — APPEND ONLY — auth failures, uploads, deletes │  ║
║  │    ├── documents       — document registry                             │  ║
║  │    └── reindex_jobs    — async job status                              │  ║
║  │                                                                        │  ║
║  │  data/                (filesystem)                                     │  ║
║  │    ├── *.faiss / *.pkl        — shared corpus FAISS + BM25 indexes    │  ║
║  │    └── clients/<slug>/        — per-client namespace                   │  ║
║  │           ├── docs/<doc_id>.pdf  — uploaded PDFs                      │  ║
║  │           └── (indexes)          — per-client FAISS/BM25 (future)     │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
╚════════════════════════════════╦═════════════════════════════════════════════╝
                                 │ Python function call (in-process)
                                 │ asyncio.Semaphore(5) — max concurrency
                                 ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  TRUST BOUNDARY: ML PIPELINE (arlc/)                                         ║
║                                                                              ║
║  arlc/pipeline.py  — Orchestrator (route → retrieve → answer)               ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │  arlc/router.py     — deterministic doc routing (regex, no LLM)    │     ║
║  │  arlc/retriever.py  — BM25 + FAISS vector + cross-encoder rerank   │     ║
║  │  arlc/answerer.py   — single LLM call per question                 │     ║
║  │  arlc/llm/          — LLM backend (litellm, vertex, anthropic)     │     ║
║  └─────────────────────────────────────────────────────────────────────┘     ║
║                                                                              ║
║  Singletons (warmed at startup, held in memory):                             ║
║    FAISS index — vector embeddings (~1-5GB)                                  ║
║    BM25 index  — sparse retrieval (~200MB)                                   ║
║    Cross-encoder — sentence-transformers model (~500MB)                      ║
║    Embedding model — for query encoding                                      ║
║                                                                              ║
╚════════════════════════════════╦═════════════════════════════════════════════╝
                                 │ HTTPS (TLS 1.3)
                                 │ Anthropic API or LiteLLM proxy
                                 ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  TRUST BOUNDARY: EXTERNAL LLM PROVIDER                                       ║
║                                                                              ║
║  Anthropic API (claude-sonnet-4-6)                                           ║
║    - Receives: retrieved document chunks + client question                   ║
║    - Does NOT receive: API keys, client identity, prior query history        ║
║    - Returns: generated answer text                                          ║
║                                                                              ║
║  OR: LiteLLM Proxy (internal, Tailscale network)                             ║
║    - Round-robin across multiple endpoint configurations                     ║
║    - Failover on provider errors                                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Trust Boundaries

| Boundary          | Description                                   | Controls                                 |
|-------------------|-----------------------------------------------|------------------------------------------|
| Internet / Funnel | Public internet to Tailscale Funnel endpoint  | TLS 1.3, Tailscale ACL                   |
| Frontend          | Next.js client — serves UI, proxies API calls | CORS, no API key exposure to browser     |
| Backend           | FastAPI server — all business logic           | API key auth, rate limiting, audit log   |
| ML Pipeline       | arlc/ — retrieval and generation              | Semaphore (max 5 concurrent), in-process |
| LLM Provider      | Anthropic / LiteLLM — external AI inference   | HTTPS, API key in .env only              |

---

## Network Topology

```
[Client Browser] ──HTTPS──► [Tailscale Funnel] ──HTTPS──► [Host Machine]
                                                                 │
                                                    ┌────────────┴───────────┐
                                                    │  localhost:3000        │
                                                    │  Next.js frontend      │
                                                    └───────────┬────────────┘
                                                                │ localhost:8000
                                                    ┌───────────┴────────────┐
                                                    │  localhost:8000        │
                                                    │  FastAPI backend       │
                                                    └───────────┬────────────┘
                                                                │ HTTPS
                                                    ┌───────────┴────────────┐
                                                    │  api.anthropic.com     │
                                                    │  Claude API            │
                                                    └────────────────────────┘
```

---

## Secrets and Credentials

| Secret                | Where Stored          | Access Pattern                                        |
|-----------------------|-----------------------|-------------------------------------------------------|
| Anthropic API key     | `.env` only           | Read by arlc/ at startup via python-dotenv            |
| LiteLLM proxy URL/key | `.env` only           | Read by arlc/llm/litellm_backend.py at startup        |
| NeoLex API keys       | `neolex.db`           | SHA-256 hash only; plaintext shown once, never stored |
| Tailscale auth key    | OS keychain or `.env` | Not committed to source control                       |

`.env` is gitignored. `.planning/` is gitignored. `paper/` is gitignored.
Run `bash scripts/scan-secrets.sh` before every commit.

---

## Data at Rest (Storage Inventory)

| Location                    | Contents                                   | Encryption             | Backup            |
|-----------------------------|--------------------------------------------|------------------------|-------------------|
| `neolex.db`                 | Audit log, API keys (hashes), doc metadata | Filesystem permissions | None configured   |
| `data/*.faiss`              | FAISS vector index (embeddings)            | Filesystem             | Rebuild from PDFs |
| `data/*.pkl`                | BM25 sparse index                          | Filesystem             | Rebuild from PDFs |
| `data/clients/<slug>/docs/` | Uploaded client PDFs                       | Filesystem             | None configured   |
| Application logs            | Request IDs, IPs, paths, status codes      | None (plaintext)       | Log rotation      |

---

## Request Lifecycle (Query)

```
1. Client sends: POST /api/v1/query
   {"question": "...", "answer_type": "free_text"}
   Authorization: Bearer nxk_<key>

2. RequestIDMiddleware assigns UUID, logs request start

3. TimeoutMiddleware starts countdown (REQUEST_TIMEOUT_SECONDS)

4. get_api_key() dependency:
   a. Extracts key from Authorization header
   b. Computes SHA-256 hash
   c. Looks up hash in api_keys table (SQLite)
   d. On failure: logs auth_failure event, raises 401
   e. On success: updates last_used timestamp
   f. Checks rate limit (per-key sliding window counter)

5. query() handler calls arlc/ pipeline:
   a. route_fn(question) → doc_ids (regex routing)
   b. retrieve_fn(question, doc_ids) → ranked pages
   c. answer_fn(question, pages) → Claude API call → answer text

6. Audit log: queries table INSERT (question, answer, sources, latency, IP)

7. Response returned to client

8. RequestIDMiddleware logs request completion (status code, duration_ms)
   X-Request-ID header added to response
```

---

## Component Versions (2026-03-26)

| Component             | Version           | Role                     |
|-----------------------|-------------------|--------------------------|
| FastAPI               | 0.115.x           | ASGI web framework       |
| Uvicorn               | latest            | ASGI server              |
| aiosqlite             | 0.21.x            | Async SQLite driver      |
| httpx                 | 0.28.x            | Async HTTP client        |
| sse-starlette         | 2.x               | Server-Sent Events       |
| Claude API            | claude-sonnet-4-6 | LLM inference            |
| sentence-transformers | latest            | Cross-encoder reranking  |
| FAISS                 | 1.x               | Vector similarity search |
| Next.js               | 15.x              | Frontend framework       |
