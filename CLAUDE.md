# Vitreon Legal — AI Legal Research Platform

## Rules

1. **NEVER commit .env, API keys, proxy URLs, company names, or sensitive data**
2. **NEVER push the `product` branch to GitHub**
3. Use `uv` for Python, `npm` for Node.js
4. Agent is the production path (`use_agent=True`); deterministic pipeline for benchmarks only
5. All status messages must be user-friendly — no internal details (model names, fallback info, algorithm names)
6. When working with llms, remember that we use the latest 2026 ones, e.g. sonnet/opus 4.6, haiku 4.5.
7. It is very imporant to remember that is is a production level application, which includes we don't apply any shortcuts or easy solutions/quick wins. each problem has to be thoroughly investigated for reasons why it appears, proper analytics conducted, and a production ready solution has to be implemeneted.
8. Use teammates and subagents to not clutter your own context. Ignore this if you're a subagent or a teammate yourself.
9. When writing code, modularize, don't write unreadable code, follow pep8, try writing tests that will actually test something reasonable with real data, not just test something that's obvious to work.
10. don't blindly discard ideas without properly analyzing them first, sometimes a system might work but needs minor fixes, but sometimes it's a non-fitting idea from the start.
11. a lot of past work has been done here so if you can't figure smth out, try researching the history (including prior claude code conversations)
12. Do not apply speculative patches, debug real errors. 
13. Do not remove existing UI content (source text, markdown formatting, etc.) unless explicitly asked. Do not over-dim, over-simplify, or strip styling during refactors. We need to follow the UI style. 
14. All risky changes have to be analyzed to not cause regressions.

## Infrastructure

| Service | Port | Plist |
|---------|------|-------|
| Backend (FastAPI) | 8000 | app.vitreon.backend |
| Frontend (Next.js) | 3000 | app.vitreon.frontend |
| Embedding (llama-server) | 8088 | app.vitreon.llama |
| Reranker (llama-server) | 8089 | app.vitreon.reranker |
| Cloudflare Tunnel | — | app.vitreon.tunnel |

- **RTX 3070**: 100.98.171.97 (optional, primary for embedding + reranking when online, it's my personal computer so it's sometimes disabled)
- **Domain**: vitreon.app (Cloudflare Tunnel → Mac:3000 frontend, Mac:8000 backend)
- **LLM**: Claude Sonnet 4.6 via Vertex AI (Haiku 4.5 for first-round query formulation). For now it's getting billed via a vertex project but it's temporary and it's a secret we can't disclose.

## Pricing

| Plan | Price | Daily Limit |
|------|-------|-------------|
| Free | $0 | 3/day |
| Starter | $29/mo | 30/day |
| Pro | $179/mo | 200/day |
| Enterprise | $499/mo | unlimited |

## Git Safety

- `.env`, `.planning/`, `paper/`, `.demo_key`, `models/*.gguf` are gitignored
