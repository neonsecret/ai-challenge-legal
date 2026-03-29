---
phase: "06"
plan: "06"
subsystem: "frontend-polish-demo"
tags: ["frontend", "demo", "ux", "makefile", "settings"]
dependency_graph:
  requires: ["04-nextjs-frontend", "02-auth-audit-logging"]
  provides: ["make-demo", "settings-page", "landing-page", "demo-mode", "frontend-polish"]
  affects: ["neolex/main.py", "neolex/config.py", "frontend/src/app"]
tech_stack:
  added: ["aiosqlite>=0.21.0", "python-multipart>=0.0.12"]
  patterns: ["route-groups", "toast-system", "demo-mode-pattern"]
key_files:
  created:
    - Makefile (make demo, make dev, make serve, make logs, make demo-stop targets)
    - scripts/dev.sh
    - neolex/demo_setup.py
    - neolex/routers/demo.py
    - frontend/src/app/(app)/layout.tsx
    - frontend/src/app/(app)/settings/page.tsx
    - frontend/src/app/(auth)/page.tsx
    - frontend/src/components/ui/toast.tsx
    - DEMO_QUESTIONS.md
  modified:
    - neolex/config.py (DEMO_MODE flag)
    - neolex/main.py (demo key seeding in lifespan)
    - frontend/src/app/layout.tsx (route groups, ToastProvider)
    - frontend/src/app/(app)/chat/page.tsx (confidence, tab title, Cmd+K, empty state)
    - frontend/src/components/chat/chat-input.tsx (onFocusRef)
    - frontend/src/components/chat/chat-message.tsx (copy button, confidence badge)
    - frontend/src/components/app-sidebar.tsx (demo badge, sign-out button)
    - pyproject.toml (aiosqlite, python-multipart)
decisions:
  - "Route groups (app) / (auth) to give landing page no sidebar, app pages sidebar — clean separation"
  - "Lightweight custom toast system instead of shadcn Sonner to avoid extra dependency"
  - "Demo key written to .demo_key file so /api/v1/demo/config can serve it to frontend"
  - "Confidence badge uses High/Medium/Low thresholds: >=0.7 High, >=0.4 Medium, <0.4 Low"
metrics:
  duration: "~45 minutes"
  completed: "2026-03-26"
  tasks: 7
  files_created: 9
  files_modified: 8
---

# Phase 6: UI Polish + Demo Readiness Summary

**One-liner:** One-command demo setup (`make demo`), settings page, landing/login page, route groups, confidence badges,
copy-to-clipboard, tab title updates, demo mode badge, toast notifications.

## What Was Built

### Task 1: `make demo` One-Command Setup

- Added `make demo` target to Makefile: installs Python/npm deps, creates demo API key via `neolex/demo_setup.py`,
  starts backend on port 8000, waits for health check, starts frontend on port 3000, opens browser.
- Added `make dev` (hot-reload), `make serve` (production + Tailscale), `make logs`, `make demo-stop`.
- Added `scripts/dev.sh` for hot-reload development mode.
- Commit: `92a65fb`

### Task 2: Demo Mode Configuration

- `DEMO_MODE=true` env var added to `neolex/config.py`.
- On backend startup (lifespan), if `DEMO_MODE=true`, calls `ensure_demo_key()` to create a demo admin key in SQLite if
  absent.
- `GET /api/v1/demo/config` endpoint (unauthenticated) returns `{ demo_mode, api_key, sample_questions }` — lets
  frontend auto-fill key and show demo questions.
- Demo key written to `.demo_key` file for the endpoint to serve.
- Commit: `92a65fb`

### Task 3: Settings Page

- `frontend/src/app/(app)/settings/page.tsx`: API key input (show/hide toggle), backend URL configuration, theme
  toggle (Light/Dark/System), about section with version and API docs link.
- All values saved to localStorage.
- Commit: `f628f21`

### Task 4: Landing/Login Page

- `frontend/src/app/(auth)/page.tsx`: If localStorage has API key, redirects to `/chat`. If `DEMO_MODE=true`, fetches
  demo config and auto-fills key with a "Demo key pre-filled" notice. Otherwise, shows plain API key entry form.
- Clean landing with Scale icon logo mark.
- Sign-out button in sidebar footer clears localStorage and redirects to `/`.
- Commit: `f628f21`

### Route Group Restructuring

- Moved `chat/`, `documents/`, `settings/` into `(app)/` route group with its own `layout.tsx` (sidebar).
- Moved landing page into `(auth)/` route group (no sidebar).
- Root layout now only contains ThemeProvider, TooltipProvider, ToastProvider.
- Build passes cleanly — all 5 routes static.
- Commit: `f628f21`

### Task 5: Frontend Polish

**Toast system:** Lightweight `toast.tsx` with `ToastProvider` and `useToast()` hook. Slide-in toasts (
success/error/default), auto-dismiss in 4s, max 5 queued.

**Copy-to-clipboard:** Hover-visible copy button on assistant messages in `chat-message.tsx`. Shows checkmark for 1.5s
after copy.

**Confidence indicator:** Badge on assistant messages showing "High / Medium / Low" based on pipeline `confidence`
field (>=0.7 High, >=0.4 Medium, <0.4 Low). Color-coded (green/yellow/red).

**Tab title updates:** While streaming, browser tab title changes to the question text (truncated to 50 chars). Resets
to "NeoLex — Your AI Legal Counsel" when done.

**Keyboard shortcuts:** Cmd+K focuses chat input from anywhere in the app. Hint shown below input bar. `ChatInput`
exposes `onFocusRef` for wiring.

**Empty state:** Chat page shows Scale icon, heading, and 5 sample DIFC questions as clickable buttons.

**Demo Mode badge:** Sidebar header shows "Demo" badge when backend reports `demo_mode: true`.

**Sign-out button:** Sidebar footer has a Sign out button that clears `neolex_api_key` from localStorage.

- Commit: `3a7c8fa`

### Task 6: DEMO_QUESTIONS.md

- 10 demo-ready questions covering: limitation periods, employment, director duties, arbitration, contracts, winding up,
  remedies, jurisdiction, data protection, security enforcement.
- Each question has rationale for why it works in a sales demo.
- Demo script tips and expected performance section.
- Commit: `15805a1`

### Auto-Fix: Missing Dependencies (Rule 1 - Bug)

- `aiosqlite` and `python-multipart` were imported by `neolex/` but absent from `pyproject.toml`.
- This caused 100% of neolex test collection to fail (54 errors).
- Added both to `pyproject.toml` dependencies, ran `uv sync`.
- Result: 86 non-integration tests pass.
- Commit: `20866ea`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing aiosqlite and python-multipart in pyproject.toml**

- **Found during:** Task 7 (test verification)
- **Issue:** Both packages used by `neolex/db/audit.py` and `neolex/routers/documents.py` were not declared in
  `pyproject.toml`, causing `ModuleNotFoundError` during test collection.
- **Fix:** Added `aiosqlite>=0.21.0` and `python-multipart>=0.0.12` to `[project].dependencies`.
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** `20866ea`

**2. [Rule 2 - Missing critical functionality] Sign-out button**

- **Found during:** Task 4 (landing page)
- **Issue:** No way to sign out once logged in — users would be permanently stuck with a bad API key.
- **Fix:** Added Sign out button to sidebar footer that clears localStorage and redirects to `/`.
- **Files modified:** `frontend/src/components/app-sidebar.tsx`

### Plan Adjustments

- **Route groups added** (not in original plan spec): Needed to give landing page a bare layout vs app pages with
  sidebar. This is a required structural change, not an extra feature.
- **Demo key written to `.demo_key` file**: The plan assumed the backend would serve the key via the config endpoint.
  Since the key is only known at creation time and we can't store plaintext in SQLite, we write it to `.demo_key` on
  disk and serve from there. `.demo_key` is gitignored (not committed).

## Known Stubs

None. All implemented features are wired to real data sources.

- Chat confidence badge: reads from SSE `confidence` field — real pipeline value.
- Demo sample questions: served from `/api/v1/demo/config` — real backend endpoint.
- API key auto-fill: reads from `.demo_key` file — written by `demo_setup.py`.

## Self-Check: PASSED

Files verified:

- `Makefile` — exists, contains `demo`, `dev`, `serve`, `demo-stop` targets
- `neolex/demo_setup.py` — exists
- `neolex/routers/demo.py` — exists
- `neolex/config.py` — `demo_mode` field present
- `frontend/src/app/(app)/settings/page.tsx` — exists
- `frontend/src/app/(auth)/page.tsx` — exists
- `frontend/src/components/ui/toast.tsx` — exists
- `DEMO_QUESTIONS.md` — exists
- Frontend build: PASSES (Next.js 16.2.1 Turbopack, TypeScript clean)
- Backend tests: 86 passed (non-integration), 0 failures

Commits verified:

- `92a65fb` feat(06-01): make demo + demo mode setup
- `f628f21` feat(06-02): settings page + landing/login page + route groups
- `3a7c8fa` feat(06-03): frontend polish — toasts, copy, confidence, demo badge, shortcuts
- `15805a1` docs(06-04): add DEMO_QUESTIONS.md
- `20866ea` fix(06-05): add missing aiosqlite + python-multipart dependencies
