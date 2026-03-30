# Vitreon Legal — AI Legal Research Platform

## Rules

1. **NEVER commit .env, API keys, proxy URLs, company names, or sensitive data**
2. **NEVER push the `product` branch to GitHub**
3. Use `uv` for Python, `npm` for Node.js
4. Agent is the production path (`use_agent=True`); deterministic pipeline for benchmarks only
5. All status messages must be user-friendly — no internal details (model names, fallback info, algorithm names)
6. When working with llms, remember that we use the latest 2026 ones, e.g. sonnet/opus 4.6, haiku 4.5.

## Infrastructure

| Service | Port | Plist |
|---------|------|-------|
| Backend (FastAPI) | 8000 | app.vitreon.backend |
| Frontend (Next.js) | 3000 | app.vitreon.frontend |
| Embedding (llama-server) | 8088 | app.vitreon.llama |
| Reranker (llama-server) | 8089 | app.vitreon.reranker |
| Cloudflare Tunnel | — | app.vitreon.tunnel |

- **RTX 3070**: 100.98.171.97 (optional, primary for embedding + reranking when online)
- **Domain**: vitreon.app (Cloudflare Tunnel → Mac:3000 frontend, Mac:8000 backend)
- **LLM**: Claude Sonnet 4.6 via Vertex AI (Haiku 4.5 for first-round query formulation)

## Pricing

| Plan | Price | Daily Limit |
|------|-------|-------------|
| Free | $0 | 3/day |
| Starter | $29/mo | 30/day |
| Pro | $179/mo | 200/day |
| Enterprise | $499/mo | unlimited |

## Git Safety

- `.env`, `.planning/`, `paper/`, `.demo_key`, `models/*.gguf` are gitignored
