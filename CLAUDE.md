# Vitreon Legal — AI Legal Research Platform

## Rules

1. **NEVER commit .env, API keys, proxy URLs, company names, or sensitive data**
2. **NEVER push sensitive data (.env, API keys, company names) to any GitHub repo (public or private). The private repo is neonsecret/vitreon-legal.**
3. Use `uv` for Python (always `uv run`, `uv add`, `uv pip` — NEVER use system pip, system python, or modify system packages), `npm` for Node.js
4. Agent is the production path (`use_agent=True`); deterministic pipeline for benchmarks only
5. All status messages must be user-friendly — no internal details (model names, fallback info, algorithm names)
6. It's 2026 — latest LLMs are Claude Sonnet/Opus 4.6, Haiku 4.5, GPT-5.4, Gemini 3.1 Pro. We use Claude Sonnet 4.6 (via Vertex AI) for answers, Haiku 4.5 for fast tasks (query formulation, follow-ups).
7. It is very imporant to remember that is is a production level application, which includes we don't apply any shortcuts or easy solutions/quick wins. each problem has to be thoroughly investigated for reasons why it appears, proper analytics conducted, and a production ready solution has to be implemeneted.
8. Use teammates and subagents to not clutter your own context. Ignore this if you're a subagent or a teammate yourself.
9. When writing code, modularize, don't write unreadable code, follow pep8, try writing tests that will actually test something reasonable with real data, not just test something that's obvious to work.
10. don't blindly discard ideas without properly analyzing them first, sometimes a system might work but needs minor fixes, but sometimes it's a non-fitting idea from the start.
11. a lot of past work has been done here so if you can't figure smth out, try researching the history (including prior claude code conversations)
12. Do not apply speculative patches, debug real errors. 
13. Do not remove existing UI content (source text, markdown formatting, etc.) unless explicitly asked. Do not over-dim, over-simplify, or strip styling during refactors. We need to follow the UI style. 
14. All risky changes have to be analyzed to not cause regressions.
15. Never roll your own SSE parser or protocol handler — use battle-tested libraries (e.g. `eventsource-parser`); never trust per-file code reviews to catch integration bugs — always include an API contract reviewer that checks backend schemas against frontend interfaces, and an E2E tester that actually calls endpoints.
16. Never re-order, re-sort, or relabel accumulated documents — the LLM sees [DOC-N] labels during tool calls and the same labels must stay consistent in the system prompt and final source mapping. Sorting by score, deduplication, or any reindexing breaks the citation chain. Speed optimizations must never change what the LLM sees or how its output maps to sources — always run a benchmark before and after.
17. Don't procrastinate — when optimizations or fixes are identified, implement them immediately in the same session. Don't defer to "later" or "future session" unless blocked by external dependencies (e.g. hardware unavailable).
18. Always test your own changes end-to-end before deploying — run actual queries via the API, verify the frontend renders correctly, check that sub-components (PDF viewer, streaming, citations) work with real data, not just compile checks. Force-rebuild the frontend (`rm -rf .next && npm run build`) when UI changes aren't taking effect.
20. When writing implementation plans, give agents clear direction but don't micromanage — let them write clean modularized code with freedom on exact structure.
19. Pre-commit hooks (ruff + bandit) are configured — all code must pass linting and security scanning before commit. Always run security reviews (bandit/semgrep) after significant changes. Every feature must be PEP 8 compliant, production-hardened, and grounded end-to-end (citations must trace back to real source chunks, not regex-matched text).

## Infrastructure

| Service | Port | Plist |
|---------|------|-------|
| Backend (FastAPI) | 8000 | app.vitreon.backend |
| Frontend (Next.js) | 3000 | app.vitreon.frontend |
| Embedding (llama-server) | 8088 | app.vitreon.llama |
| Reranker (llama-server) | 8089 | app.vitreon.reranker |
| Cloudflare Tunnel | — | app.vitreon.tunnel |
| Langfuse (observability) | 3040 | app.vitreon.langfuse |

> **Langfuse secret rotation (mandatory before first start):** All `LANGFUSE_*` vars must be set in `.env` before running Langfuse. Generate crypto-safe values: `openssl rand -hex 32` for `LANGFUSE_ENCRYPTION_KEY`, `LANGFUSE_SALT`, and `LANGFUSE_NEXTAUTH_SECRET`. Never use all-zeros or placeholder values — Langfuse will start but data at rest will be unencrypted.

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
