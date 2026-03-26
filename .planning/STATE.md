# Project State

## Current Status
- Phase: 06-ui-polish-demo-readiness
- Progress: Phase 1 ✓, Phase 2 ✓, Phase 3 ✓, Phase 4 ✓, Phase 5 ✓, Phase 6 ✓
- Last session: 2026-03-26
- Stopped at: Completed 06-PLAN (UI polish + demo readiness)

## Completed Phases
- Phase 1: FastAPI Core + Pipeline Integration (30 tests)
- Phase 2: Auth + Audit Logging (45 unit + 8 CLI tests)
- Phase 3: Document Upload + Reindex (65 tests total)
- Phase 4: Next.js Frontend (chat UI + SSE streaming + document upload)
- Phase 5: Production Hardening (86 total tests, all passing)
- Phase 6: UI Polish + Demo Readiness (make demo, settings, landing, confidence badges, toasts)

## Phase 5 Summary
- 8 new files created, 3 modified
- 21 new tests (86 total, all passing)
- JSONErrorMiddleware — JSON 500s instead of HTML for unhandled exceptions
- RequestIDMiddleware — UUID per request, X-Request-ID header, request logging
- TimeoutMiddleware — 504 JSON on REQUEST_TIMEOUT_SECONDS (default 30s)
- logging_config.py — JSON (production) / human (dev) structured logging
- startup_validation.py — fail-fast check for data/ dir + required index files
- /health enhanced with uptime, request_count, avg_latency_ms, last_error_ts
- /health/live + /health/ready added (liveness + readiness probes)
- scripts/serve.sh — starts uvicorn + Next.js + Tailscale Funnel, graceful shutdown
- Commit: a20eec3

## Decisions Made
- JSONErrorMiddleware (BaseHTTPMiddleware) instead of @app.exception_handler(Exception)
  because Starlette routes unhandled exceptions to ServerErrorMiddleware (HTML), bypassing
  the app exception_handler registry
- stdlib logging only (no structlog) — keeps dependency surface minimal
- Timeout exempt for /health/* — liveness must always respond
- RequestIDMiddleware tracks metrics in neolex.main globals — correct for single-process uvicorn

## Decisions Made (all phases)
- Reindex worker stub-with-interface: tries arlc indexer, falls back to manifest-only stub
- Documents tracked in both SQLite (queries) and sidecar .meta files (filesystem discovery)
- asyncio.create_task for non-blocking reindex, to_thread for CPU/IO
- Per-client isolation enforced from API key client_slug, never from request body

## Key Files Added (Phase 5)
- neolex/middleware/error_handler.py — JSONErrorMiddleware
- neolex/middleware/request_id.py — RequestIDMiddleware
- neolex/middleware/timeout.py — TimeoutMiddleware
- neolex/logging_config.py — JSON/human structured logging
- neolex/startup_validation.py — fail-fast startup checks
- scripts/serve.sh — Tailscale Funnel launch script
- tests/neolex/test_production_hardening.py — 21 tests

## Known Stubs
- arlc indexer integration: writes manifest.json stub, deferred to future phase

## Phase 6 Summary
- 9 files created, 8 modified
- 86 tests still pass (added aiosqlite + python-multipart to pyproject.toml)
- make demo, make dev, make serve, make logs, make demo-stop targets
- DEMO_MODE=true: auto-seeds demo API key, frontend auto-fills it
- GET /api/v1/demo/config: serves demo mode flag, key, sample questions
- Route groups (app)/(auth): landing has no sidebar, app pages have sidebar
- Settings page: API key, backend URL, theme toggle, about section
- Landing/login page: auto-fills API key in demo mode, redirects if key exists
- Toast system: ToastProvider + useToast(), slide-in notifications
- chat-message.tsx: copy-to-clipboard, High/Medium/Low confidence badge
- chat/page.tsx: tab title updates while streaming, Cmd+K shortcut, sample Qs empty state
- app-sidebar.tsx: Demo Mode badge, Sign out button
- DEMO_QUESTIONS.md: 10 sales-ready DIFC questions with rationale
- Commits: 92a65fb, f628f21, 3a7c8fa, 15805a1, 20866ea

## Decisions Made (Phase 6)
- Route groups (app)/(auth) — landing page needs no sidebar; app pages share sidebar layout
- Lightweight custom toast vs shadcn Sonner — avoids extra npm dependency
- Demo key written to .demo_key file — SQLite doesn't store plaintext; file is gitignored
- Confidence thresholds: >=0.7 High, >=0.4 Medium, <0.4 Low — reasonable defaults, easily tuned

## Performance Metrics
| Phase | Duration | Tasks | Files | Tests |
|---|---|---|---|---|
| 05-01 | ~7.5 min | 6 | 11 | 21 new / 86 total |
| 06-01 | ~45 min | 7 | 17 | 86 pass (bug fix) |
