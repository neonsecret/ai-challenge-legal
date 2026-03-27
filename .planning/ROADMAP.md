# Roadmap: NeoLex

**Defined:** 2026-03-26
**Goal:** Law firm partner can open a URL, upload documents, ask a legal question, and get a streamed, cited answer — demo-ready for a $5–10K pilot conversation.

## Phase Overview

| Phase | Name | Goal | Status |
|-------|------|------|--------|
| 1 | FastAPI Core + Pipeline Integration | Working query endpoint backed by `arlc/` | Complete |
| 2 | Auth + Audit Logging | API key middleware + append-only query log | Complete |
| 3 | Document Upload + Reindex | PDF upload + per-client index management | Complete |
| 4 | Next.js Frontend | Chat UI + streaming + upload UI | Complete |
| 5 | Production Hardening | Error handling, rate limiting, Tailscale Funnel | Complete |
| 6 | UI Polish + Demo Readiness | shadcn/ui, responsive design, one-command demo | Complete |
| 7 | SOC 2 Foundations | Audit completeness, access controls, data retention | Complete |
| 8 | Fine-tune Legal Embedder | Cancelled — using Qwen3-8B as-is | Complete |
| 9 | Benchmark + SOTA Update | SOTA research done, benchmarks pending final model | Complete |
| 10 | Premium UI Redesign | Light mode, Playfair serif, warm palette, marketing landing | Complete |
| 11 | Qwen3-8B Integration + Full Benchmark | Build FAISS index with Qwen3-8B on RTX 3070, integrate into hybrid pipeline, re-benchmark GaRAGe + ContractNLI + Legal RAG Bench, update README | Pending |
| 12 | Glass Design System Foundation | CSS infrastructure (tokens, aurora, glass components) that all pages depend on | Complete |
| 13 | 4/5 | In Progress|  |
| 14 | App Pages + Landing Unification | Every authenticated page and the landing page share the same aurora + glass visual language | Not started |

---

## Phase 1: FastAPI Core + Pipeline Integration

**Goal:** A working `POST /api/v1/query` endpoint that routes through the existing `arlc/` pipeline and returns a grounded JSON answer with source citations. This is the core value loop — everything else wraps it.

**Key Deliverables:**

- `neolex/` package directory with `main.py` (FastAPI app factory)
- `neolex/api/query.py` — query endpoint (sync and SSE streaming variants)
- `neolex/core/pipeline_adapter.py` — thin adapter wrapping `arlc/pipeline.py` without modifying it
- `neolex/schemas.py` — Pydantic v2 request/response models (`QueryRequest`, `QueryResponse`, `SourceCitation`)
- `GET /health` — returns pipeline status, index load time, model name
- `pyproject.toml` with `neolex` package declared alongside existing `arlc` package
- Index loading on startup: FAISS + BM25 indexes cached in memory from `data/`
- Async worker pool equivalent to `--workers 5` (prevents cross-encoder lock contention)
- `.env` respected for all LLM credentials — no hardcoded keys anywhere

**Success Criteria:**

- `curl -X POST localhost:8000/api/v1/query -d '{"question": "What is the limitation period under DIFC Law No. 5 of 2005?"}'` returns a valid JSON response with answer and sources
- `GET /health` returns 200 with index status
- p95 query latency under 15 seconds on local corpus
- `arlc/` code is not modified — adapter pattern only

**Dependencies:** None (first phase)

---

## Phase 2: Auth + Audit Logging

**Goal:** Every endpoint is protected by API key auth. Every query, upload, and auth failure is recorded in an append-only SQLite audit log. This is the minimum viable security posture for a law firm pilot.

**Key Deliverables:**

- `neolex/auth/middleware.py` — FastAPI middleware extracting and validating `Authorization: Bearer <key>`
- `neolex/auth/keys.py` — API key hashing (SHA-256), storage, and validation against SQLite
- `neolex/db/audit.py` — SQLite audit log with WAL mode, append-only schema
- Audit schema: `queries` table (id, ts, key_hash, question, answer_text, sources_json, latency_ms, model_name, ip, user_agent)
- Audit schema: `events` table (id, ts, key_hash, event_type, detail_json, ip)
- `python -m neolex.admin keys create --name "Al Tamimi POC"` — prints plaintext key once, stores hash
- `python -m neolex.admin keys list` — lists active keys with name, created_at, last_used
- `python -m neolex.admin keys revoke <key_prefix>` — marks key inactive
- `GET /api/v1/admin/audit` — paginated audit log query (requires admin-scoped key)
- Rate limiting: configurable requests/minute per key via `RATE_LIMIT_RPM` env var
- Per-client corpus namespace: each API key maps to a client slug, documents stored in `data/clients/<slug>/`

**Success Criteria:**

- Request without valid API key returns 401
- Every successful query appears in `audit.db` within 100ms of response
- Auth failures logged with IP and key prefix
- `admin keys create` round-trip works end-to-end
- NFR-02: Two different API keys cannot access each other's documents

**Dependencies:** Phase 1

---

## Phase 3: Document Upload + Reindex

**Goal:** Authenticated clients can upload PDFs that get indexed into their private corpus, and query against those documents. This is the core product differentiator — grounding answers in the firm's own documents.

**Key Deliverables:**

- `POST /api/v1/documents` — multipart upload, validates PDF MIME type, stores to `data/clients/<slug>/docs/`
- `GET /api/v1/documents` — lists client's uploaded documents with metadata (filename, size, upload_ts, indexed)
- `DELETE /api/v1/documents/{doc_id}` — removes document and triggers reindex
- `neolex/indexing/reindex_worker.py` — background asyncio task running `arlc/indexing/indexer.py` on client corpus
- `GET /api/v1/documents/reindex/{job_id}` — polls job status (pending / running / complete / failed)
- Audit log entries for all document operations
- Index hot-reload: after reindex completes, pipeline adapter swaps in new index without server restart
- File size guard: reject uploads over 50MB with 413 error
- File type guard: reject non-PDF uploads with 415 error

**Success Criteria:**

- Upload a PDF, poll until reindex complete, ask a question about that document, get a cited answer
- Deleting a document and reindexing removes it from future query results
- Reindex runs in background — upload returns immediately with job ID
- Two clients uploading different PDFs cannot retrieve each other's documents in query results
- Audit log captures all upload/delete/reindex events

**Dependencies:** Phase 2

---

## Phase 4: Next.js Frontend

**Goal:** A polished web UI that a law firm partner can use without explanation — chat interface with streaming answers, source citations, document upload, and query history.

**Key Deliverables:**

- `frontend/` Next.js 14 app with TypeScript, Tailwind CSS, shadcn/ui component library
- `frontend/app/page.tsx` — login screen: API key entry form, stores in `localStorage`
- `frontend/app/query/page.tsx` — main QA chat interface
- `frontend/components/ChatInput.tsx` — question input with keyboard shortcut (Cmd+Enter)
- `frontend/components/AnswerStream.tsx` — SSE consumer rendering tokens as they arrive
- `frontend/components/SourcesPanel.tsx` — expandable citations panel (doc name, page, excerpt)
- `frontend/components/DocumentUpload.tsx` — drag-and-drop upload zone with progress bar and reindex polling
- `frontend/components/QueryHistory.tsx` — last 50 queries from `localStorage`, clickable to re-run
- CORS: FastAPI configured to accept requests from `http://localhost:3000` in dev
- `frontend/.env.local.example` with `NEXT_PUBLIC_API_URL`
- Loading spinners and skeleton states for all async operations
- Inline error display for API errors, rate limit hits, network failures

**Success Criteria:**

- Open browser, enter API key, ask a question, see answer streaming token by token
- Sources panel expands to show citations for each answer
- Drag a PDF onto upload zone, see progress, see "Reindexing..." → "Ready", ask question about it
- Query history shows previous questions; clicking one pre-fills the input
- No full-page reload at any point in the workflow

**Dependencies:** Phase 2 (auth), Phase 3 (document API)

---

## Phase 5: Production Hardening

**Goal:** The server is stable under real usage, fails gracefully, is observable, and is accessible from any browser worldwide via Tailscale Funnel. This phase converts a working demo into a system safe to hand to a client.

**Key Deliverables:**

- Tailscale Funnel configuration: `tailscale funnel 8000` with HTTPS termination, documented in `DEPLOY.md`
- Pipeline graceful degradation: if cross-encoder fails, fall back to BM25-only results with `degraded: true` flag in response
- Global exception handler: unhandled exceptions return 500 with request ID, log full traceback to file
- Request ID middleware: every request gets `X-Request-ID` header, logged in audit trail
- Structured logging: `structlog` JSON output to `logs/neolex.log` with rotation (10MB, 5 backups)
- `/metrics` endpoint: request count, error rate, p50/p95/p99 latency (Prometheus text format)
- Startup checks: verify FAISS index exists, LLM backend reachable, SQLite writable — fail fast with clear message
- Timeout enforcement: 30-second hard timeout on pipeline execution, returns 504 with message
- CORS locked to Tailscale domain in production via `ALLOWED_ORIGINS` env var
- `Makefile` targets: `make serve` (production), `make dev` (hot-reload), `make logs`

**Success Criteria:**

- Tailscale Funnel URL loads the frontend from a phone browser on a different network
- Killing the cross-encoder process does not crash the server — query returns with `degraded: true`
- Querying a down LLM backend returns 503 within 30 seconds (not hang indefinitely)
- Logs contain request ID traceable from frontend error to server log entry
- `GET /metrics` returns Prometheus-formatted counters after 10 queries

**Dependencies:** Phase 1, Phase 2

---

## Phase 6: UI Polish + Demo Readiness

**Goal:** The product looks professional enough that a law firm partner trusts it. One-command demo setup with the DIFC corpus included. The demo can be run on any Apple Silicon Mac in under 5 minutes.

**Key Deliverables:**

- NeoLex branding: logo (SVG), color palette (navy + gold legal aesthetic), typography (Inter + Playfair Display)
- shadcn/ui component audit: replace all raw HTML elements with shadcn Card, Button, Input, Badge, Skeleton
- Responsive layout: works correctly at 1280px, 1440px, 1920px widths (no mobile breakpoints required)
- Demo mode flag: `DEMO_MODE=true` uses pre-loaded DIFC corpus, shows sample queries in UI sidebar
- `make demo` target: installs deps, loads DIFC index, starts backend + frontend, opens browser
- `DEMO_QUESTIONS.md` — 10 demo-ready questions with expected answer quality for sales calls
- Empty state design: first-time user sees "Upload your first document or try our DIFC sample corpus"
- Answer confidence indicator: badge showing "High / Medium / Low" based on pipeline confidence field
- Copy-to-clipboard button on answers
- Keyboard shortcut help tooltip (Cmd+Enter to submit, Cmd+K to focus search)
- Browser tab title updates to question text while streaming

**Success Criteria:**

- `make demo` runs end-to-end without manual steps on a fresh Mac with uv installed
- Demo runs for 30 minutes without error or memory leak
- Non-technical observer watches demo and understands the product within 60 seconds
- UI passes basic accessibility check (sufficient color contrast, focusable elements)
- All 10 demo questions return answers with citations in under 15 seconds

**Dependencies:** Phase 4, Phase 5

---

## Phase 7: SOC 2 Foundations

**Goal:** The architecture, logging, and access controls satisfy the structural requirements of a SOC 2 Type I audit. This is not certification — it is building the foundation so that certification is achievable when the business requires it.

**Key Deliverables:**

- `SECURITY.md` — threat model, data flows, trust boundaries, encryption in transit/at rest
- `DATA_RETENTION.md` — documented policy: audit logs retained 90 days, documents deleted on client request within 30 days
- Encryption at rest: uploaded PDFs and SQLite audit DB stored in an encrypted directory (macOS FileVault documented as sufficient for v1)
- Access control audit: verify no endpoint accessible without valid API key (automated test suite)
- Admin key separation: admin-scoped keys cannot be used for query endpoints; query keys cannot access admin endpoints
- Log completeness test: script that runs 20 known queries and verifies all 20 appear in audit log
- Secrets scan CI check: `make secrets-check` runs `gitleaks` on staged files, blocks commit if hits found
- Dependency vulnerability scan: `make vuln-check` runs `pip-audit` and `npm audit`, reports CVEs
- `INCIDENT_RESPONSE.md` — documented procedure for data breach: who to notify, steps to contain, 72-hour timeline
- Key rotation procedure: documented steps to rotate API keys with zero downtime
- Architecture diagram: data flow from browser → Tailscale → FastAPI → pipeline → Claude API → audit log

**Success Criteria:**

- Running `make security-check` (audit test suite) passes 100% — no unprotected endpoints
- `make secrets-check` catches a planted fake API key in a test file
- Log completeness test passes: 20/20 queries appear in audit log
- `SECURITY.md` reviewed and accurate (walkthrough with someone unfamiliar with the codebase)
- No hardcoded credentials found in any committed file

**Dependencies:** Phase 2 (audit log), Phase 5 (production config)

---

## Milestone: Demo-Ready (End of Phase 6)

The product is considered demo-ready when:

- [ ] Tailscale Funnel URL loads the full UI in any browser
- [ ] Law firm partner can complete the full workflow (login → upload → query → see cited answer) without explanation
- [ ] `make demo` runs end-to-end on a fresh Mac in under 5 minutes
- [ ] p95 query latency under 15 seconds
- [ ] Audit log captures all interactions
- [ ] No hardcoded credentials in any committed file

---

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Wrap `arlc/` via adapter, not rewrite | Pipeline has 150+ experiments validating it; rewriting resets all that learning | — Pending |
| SQLite for audit log (v1) | Zero ops overhead, sufficient for single-tenant; PostgreSQL when multi-tenant | — Pending |
| API key auth before SSO | No DIFC law firm has required SSO for a pilot; ship faster | — Pending |
| Tailscale Funnel over cloud hosting | Zero infrastructure cost, HTTPS included, accessible globally, instant setup | — Pending |
| Next.js 14 + shadcn/ui | Fastest path to professional UI; shadcn components look credible in demos | — Pending |
| Single-tenant v1 | Multi-tenancy adds auth complexity; prove value with one client first | — Pending |
| FastAPI over Django/Flask | Native async, Pydantic v2, OpenAPI docs auto-generated, familiar to Python ML teams | — Pending |

---

---

## Milestone: v2.0 — Premium Frontend Overhaul

**Goal:** Every frontend screen is a cohesive, Perplexity-quality glassmorphism UI that closes law firm demos and looks portfolio-worthy.

**Phases:** 12–14

---

## Phases (v2.0)

- [x] **Phase 12: Glass Design System Foundation** - CSS infrastructure (design tokens, `@utility` glass classes, `AuroraBackground`, `GlassCard`, `GlassPill`) that all subsequent phases depend on
- [ ] **Phase 13: Chat Page Total Rebuild** - Chat page rebuilt to Perplexity-quality standard: sources above answer, user question as heading, vivid aurora, glass panels
- [ ] **Phase 14: App Pages + Landing Unification** - Every authenticated app page and the landing page unified with aurora depth and glass panels — no flat dark surfaces remain

## Phase Details (v2.0)

### Phase 12: Glass Design System Foundation

**Goal:** Establish the CSS infrastructure — design tokens, `@utility` glass classes, `AuroraBackground` component, `GlassCard`, and `GlassPill` — that all subsequent phases depend on. Nothing visual is complete after this phase; it is infrastructure only.

**Depends on:** Phase 11 (existing frontend codebase)

**Requirements:** GLASS-01, GLASS-02, GLASS-03, GLASS-04, GLASS-05

**Key Deliverables:**

- `src/app/globals.css` — add `--glass-bg`, `--glass-border-color`, `--glass-shadow`, `--orb-gold-color`, `--orb-blue-color`, `--orb-teal-color` CSS custom properties to `.dark`; define `glass-sm`, `glass-md`, `glass-lg`, `glass-gold` as Tailwind v4 `@utility` classes; replace ~40 scattered inline glass styles
- `src/components/ui/aurora-background.tsx` — new reusable component with orbs at `0.40–0.55` opacity, `filter: blur(80–140px)`, and named presets (`chat` / `landing` / `app-subtle`); `position: absolute`, `pointer-events-none`, `aria-hidden`
- `src/components/ui/glass-card.tsx` — wraps shadcn `<Card>` without forking it; sets `background: rgba(255,255,255,0.08)`, `backdrop-filter: blur(32px) saturate(150%)`, bypasses opaque `--card` variable; variant props: `panel / subtle / heavy / gold`; optional gold top-accent pseudo-element
- `src/components/ui/glass-pill.tsx` — pill/badge component with `backdrop-filter: blur(16px)`, gold accent variant, hover state via CSS `&:hover` not JS event handlers

**Critical constraint:** `AuroraBackground` orbs MUST render at `0.40+` opacity. The aurora background in isolation (no glass panels) must look like "a dark sky with visible glowing areas." Declare this phase done only after a visual screenshot confirms this.

**Success Criteria:**

1. Developer opens a bare test page with `<AuroraBackground preset="chat" />` on `#060C16` and sees three distinct colored glow zones (gold, violet, teal) without any glass panels present — the orbs are unmistakably visible
2. A `<GlassCard>` placed over the aurora shows a clearly frosted surface — the color bleed from behind is perceptible through the blur, not a flat dark card
3. A `<GlassPill>` with gold variant shows gold-tinted frosted glass on hover without triggering a React re-render (verified by React DevTools profiler showing no component highlight on hover)
4. Running a full-text search for `rgba(` in `globals.css` returns zero inline glass background values — all glass alpha values live in CSS custom properties
5. The existing UI has no visual regressions — pages that used inline glass styles continue to render identically (or better) after the migration to `@utility` classes

**Plans:** 1 plan

Plans:
- [x] 12-01-PLAN.md — Glass tokens, @utility classes, AuroraBackground, GlassCard, GlassPill
**UI hint**: yes

---

### Phase 13: Chat Page Total Rebuild

**Goal:** The chat page looks like a Perplexity-quality premium AI research tool. A law firm partner opens it and immediately trusts the product.

**Depends on:** Phase 12 (glass design system)

**Requirements:** CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, SRC-01, SRC-02, SRC-03, SRC-04, CONF-01

**Key Deliverables:**

- `src/app/(app)/chat/page.tsx` — add `<AuroraBackground preset="chat" />` at z-0; restructure layout for Perplexity-style Q+A flow
- `src/components/chat/chat-message.tsx` — user message rendered as bold `font-heading` `<h2>` section heading above the assistant response block (not a right-aligned bubble); assistant response wrapped in `<GlassCard variant="panel">`
- `src/components/chat/sources-panel.tsx` — new component: numbered `<GlassPill>` source cards in a horizontal row with explicit "Sources" label, displayed ABOVE the prose answer; each card shows truncated `doc_id` and page number in gold; clicking a card opens grounding drawer
- `src/components/chat/chat-input.tsx` — full-width glass input container (`backdrop-filter: blur(32px)`), gold glow on send button when text is present, sticky at bottom (`z-30`), frosted glass overlay
- `src/components/chat/streaming-status.tsx` — glass status pill driven by `streamingStatus` prop: "Searching documents...", "Analyzing sources...", "Synthesizing answer..."
- `src/components/chat/empty-state.tsx` — large centered layout, shield logo glow, numbered `<GlassCard>` suggestion buttons with gold hover
- `src/components/chat/confidence-badge.tsx` — pill with ShieldCheck / AlertTriangle / AlertCircle icon for high / medium / low confidence; appears after answer prose
- Wire existing `grounding-drawer.tsx` and `GroundingView` to source card click — do not rebuild them

**Critical constraints:**
- Sources panel MUST appear above the answer prose (Perplexity pattern) — never below
- User question MUST render as a bold heading, not a right-aligned chat bubble
- `grounding-drawer.tsx` and `GroundingView` must be wired, not rewritten

**Success Criteria:**

1. A law firm partner looking at the chat page for the first time sees a numbered "Sources" row (e.g., "1. DIFC-EMP-2019 · p.4", "2. DIFC-COA-2021 · p.12") before they read the answer — sources are visually above the response text
2. The user's question appears as a large bold heading (like a document section title) rather than a chat bubble — the page reads like a legal research document, not a messaging app
3. Clicking any source card opens the grounding drawer showing the referenced document page — the existing `grounding-drawer.tsx` + `GroundingView` components activate with the correct source selected
4. During streaming, a glass status pill cycles through descriptive labels ("Searching documents...", "Analyzing sources...", "Synthesizing answer...") — the RAG pipeline stages are visible to the user
5. The chat page aurora is obviously vivid — opening the page on a 15-inch laptop in a conference room, the colored orb glow is perceptible from 2 meters away; the glass input bar shows visible frosted blur over the background

**Plans:** 4/5 plans executed

Plans:
- [x] 13-01-PLAN.md — Phase 12 merge + glass-warm utility
- [x] 13-02-PLAN.md — Chat page shell + EmptyState rebuild
- [x] 13-03-PLAN.md — ChatMessage + SourcesPanel + StreamingStatus + ConfidenceBadge
- [x] 13-04-PLAN.md — ChatInput re-skin + grounding drawer wire
- [ ] 13-05-PLAN.md — Visual verification checkpoint
**UI hint**: yes

---

### Phase 14: App Pages + Landing Unification

**Goal:** Every authenticated app page (Documents, Settings) and the landing page are visually cohesive with the chat page — aurora depth and glass panels everywhere, no flat dark surfaces remaining.

**Depends on:** Phase 12 (glass design system), Phase 13 (chat page as visual reference)

**Requirements:** APP-01, APP-02, APP-03, LAND-01, LAND-02, LAND-03, LAND-04, LAND-05

**Key Deliverables:**

- `src/app/(app)/documents/page.tsx` — add `<AuroraBackground preset="app-subtle" />`; upload zone and document list wrapped in `<GlassCard>`; remove flat card backgrounds
- `src/app/(app)/settings/page.tsx` — add `<AuroraBackground preset="app-subtle" />`; settings section panels wrapped in `<GlassCard>`; remove flat card backgrounds
- `src/components/layout/app-layout.tsx` (or equivalent mobile header file) — mobile top bar gets `backdrop-filter: blur(20px)`, `rgba(6,12,22,0.80)` background
- `src/components/landing/` — trust/access section: background changed from `#FAFAF9` (light) to `#080E1A` (dark); `<AuroraBackground preset="landing" />` added behind glass API key form card
- Landing hero — orb opacity raised from `0.06–0.12` to `0.35–0.45` across all hero orb definitions
- Value pillars section — inline styles replaced with `<GlassCard>` components
- How-it-works section — step content panels replaced with `<GlassCard>` components
- Mobile source strip on demo panel — existing mobile source badge migrated to `<GlassPill>`

**Critical constraint:** The landing trust section background MUST change from light (`#FAFAF9`) to dark (`#080E1A`) with aurora — a light island in a dark page breaks the visual unity the milestone requires.

**Success Criteria:**

1. Navigating from the chat page to the Documents page, a user sees the same aurora glow and glass card aesthetic — the transition feels like one product, not two different design systems
2. The landing page trust section is dark with visible aurora orbs behind the glass API key form — there is no light-colored block interrupting the dark, immersive hero experience
3. The Settings page has no flat dark card surfaces — all content panels show frosted glass treatment with perceptible aurora color bleed
4. The mobile app header is frosted glass — when scrolling any app page on a phone-width viewport, the header shows a blurred representation of the content scrolling beneath it
5. The landing page hero section orbs are vivid — a first-time visitor to the landing page (no prior context) notices the colored glow behind the headline within the first 3 seconds of loading

**Plans:** TBD
**UI hint**: yes

---

## Progress Table (v2.0)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 12. Glass Design System Foundation | 1/1 | Complete | 2026-03-27 |
| 13. Chat Page Total Rebuild | 0/5 | Planned | - |
| 14. App Pages + Landing Unification | 0/? | Not started | - |

---
*Roadmap defined: 2026-03-26*
*Last updated: 2026-03-27 — Phase 13 PLANNED (5 plans created)*
