# Requirements: NeoLex

**Defined:** 2026-03-26
**Core Value:** A law firm partner can ask a legal question, get a grounded, cited answer in under 15 seconds, and trust
it enough to bill on.

## v1 Requirements

Requirements for initial release. Each maps to a roadmap phase.

### API Core

- [ ] **API-01**: Client can submit a legal question via POST `/api/v1/query` and receive a JSON answer with source
  citations
- [ ] **API-02**: Client can request streaming responses via GET `/api/v1/query/stream` using SSE (Server-Sent Events)
- [ ] **API-03**: API returns structured response:
  `{answer, sources: [{doc_id, page, excerpt}], confidence, latency_ms}`
- [ ] **API-04**: API returns meaningful error responses (4xx for bad input, 5xx for pipeline failure) with error codes
- [x] **API-05**: Health check endpoint `GET /health` returns pipeline status, index freshness, and model availability
- [ ] **API-06**: API enforces per-key rate limiting (configurable requests/minute per API key)

### Authentication

- [ ] **AUTH-01**: API key middleware validates `Authorization: Bearer <key>` on all protected endpoints
- [ ] **AUTH-02**: API keys are stored hashed (SHA-256) in SQLite — plaintext never persisted
- [ ] **AUTH-03**: Invalid or missing API key returns 401 with clear error message
- [ ] **AUTH-04**: Admin can create, revoke, and list API keys via management CLI (`python -m neolex.admin`)
- [ ] **AUTH-05**: Each API key is scoped to a client/corpus — cross-client access is impossible by design

### Document Management

- [x] **DOC-01**: Authenticated client can upload PDF documents via `POST /api/v1/documents` (multipart/form-data)
- [x] **DOC-02**: Upload endpoint accepts PDFs up to 50MB, rejects other file types with 415 error
- [x] **DOC-03**: Uploaded documents are stored in a per-client directory isolated from other clients
- [x] **DOC-04**: Background reindex job triggers automatically after upload (non-blocking, returns job ID)
- [x] **DOC-05**: Client can poll reindex status via `GET /api/v1/documents/reindex/{job_id}`
- [x] **DOC-06**: Client can list all uploaded documents via `GET /api/v1/documents`
- [x] **DOC-07**: Client can delete a document and trigger reindex via `DELETE /api/v1/documents/{doc_id}`

### Audit Logging

- [ ] **AUDIT-01**: Every query is logged to SQLite: timestamp, api_key_hash, question, answer, sources, latency_ms,
  model_name
- [ ] **AUDIT-02**: Every document upload/delete is logged: timestamp, api_key_hash, filename, action, status
- [ ] **AUDIT-03**: Authentication failures are logged: timestamp, ip_address, key_prefix (first 8 chars),
  failure_reason
- [ ] **AUDIT-04**: Admin can query audit log via `GET /api/v1/admin/audit?from=&to=&key=` (requires admin key)
- [ ] **AUDIT-05**: Audit log is append-only — no UPDATE or DELETE operations on log rows
- [ ] **AUDIT-06**: Log entries include request IP address and User-Agent header

### Pipeline Integration

- [x] **PIPE-01**: FastAPI backend wraps `arlc/pipeline.py` without modifying core pipeline code
- [x] **PIPE-02**: Per-client FAISS + BM25 indexes are loaded on startup and cached in memory
- [x] **PIPE-03**: Pipeline runs with `--workers 5` equivalent (async worker pool, prevents cross-encoder lock
  contention)
- [ ] **PIPE-04**: End-to-end query latency is under 15 seconds for 95th percentile (p95)
- [ ] **PIPE-05**: Pipeline gracefully degrades — if reranker fails, returns BM25-only results with degraded flag
- [x] **PIPE-06**: Index hot-reload supported — new index replaces old without server restart

### Web UI

- [ ] **UI-01**: Next.js 14 frontend served at root URL (`/`) with TypeScript throughout
- [ ] **UI-02**: Login screen accepts API key, stores in `localStorage`, includes in all subsequent requests
- [ ] **UI-03**: QA chat interface: question input, submit button, streamed answer display with source citations
- [ ] **UI-04**: Sources panel shows doc name, page number, and excerpt for each citation alongside the answer
- [ ] **UI-05**: Document upload panel: drag-and-drop PDF upload with progress indicator and reindex status polling
- [ ] **UI-06**: Query history panel: last 50 queries with question, answer summary, and timestamp (client-side storage)
- [ ] **UI-07**: Streaming answer renders token-by-token as SSE events arrive (no full-page reload)
- [ ] **UI-08**: UI works on desktop Chrome, Firefox, and Safari — no mobile requirement for v1
- [ ] **UI-09**: Loading states for all async operations (query in flight, upload in progress, reindex running)
- [ ] **UI-10**: Error states displayed inline (API error, network failure, rate limit hit)

### Non-Functional Requirements

- [ ] **NFR-01**: All API endpoints served over HTTPS via Tailscale Funnel — no plaintext HTTP in production
- [x] **NFR-02**: Data isolation — each client's documents and indexes stored in separate namespaced directories
- [x] **NFR-03**: Secrets (API keys, LLM keys) loaded from `.env` only — never hardcoded or logged
- [ ] **NFR-04**: SQLite audit database uses WAL mode for concurrent read access
- [x] **NFR-05**: Server startup completes in under 30 seconds (index load from disk)
- [ ] **NFR-06**: Working demo deployable on any Apple Silicon Mac in under 5 minutes via `make demo`
- [ ] **NFR-07**: CORS configured to allow Next.js dev server origin in development, locked to Tailscale domain in
  production
- [x] **NFR-08**: All request/response bodies validated with Pydantic v2 models — no raw dict passing

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Multi-Tenancy

- **MULTI-01**: Multiple clients can be provisioned on the same server with isolated corpora
- **MULTI-02**: Per-client usage quotas (queries/month, storage GB) configurable per key
- **MULTI-03**: Admin dashboard shows per-client usage metrics and billing data
- **MULTI-04**: Client self-service: upload documents, manage API keys, view usage without admin involvement

### SSO and Enterprise Auth

- **SSOAUTH-01**: SAML 2.0 SSO integration for enterprise law firm identity providers
- **SSOAUTH-02**: OAuth 2.0 / OIDC support (Microsoft Entra ID, Google Workspace)
- **SSOAUTH-03**: Role-based access control: Partner, Associate, Compliance Officer, Admin roles
- **SSOAUTH-04**: Session tokens with configurable TTL, refresh token rotation

### Billing

- **BILL-01**: Stripe integration for usage-based billing (per query or per seat)
- **BILL-02**: Monthly invoice generation with query breakdown
- **BILL-03**: Usage alerts when client approaches quota limits

### Notifications

- **NOTF-01**: Email notification when reindex job completes
- **NOTF-02**: Alert to admin when pipeline error rate exceeds threshold
- **NOTF-03**: Weekly usage digest email to client

### Mobile

- **MOB-01**: Responsive UI works on iPad (landscape)
- **MOB-02**: Progressive Web App (PWA) manifest for iOS home screen installation

### PostgreSQL Migration

- **PG-01**: Migrate SQLite audit log to PostgreSQL for production scale
- **PG-02**: Connection pooling via PgBouncer
- **PG-03**: Read replica for audit log queries

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature                          | Reason                                                                                                                                                  |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| SOC 2 certification              | Architecture must be SOC 2 ready, but audit and certification is a 6-12 month process requiring company formation — deferred until revenue justifies it |
| SSO / SAML / OIDC                | API key auth sufficient for pilot contracts; SSO adds significant complexity with no v1 deal requirement                                                |
| Multi-tenant provisioning UI     | Single active client in v1; multi-tenant managed via CLI is sufficient                                                                                  |
| Mobile app (iOS/Android)         | Law firm partners use desktops; mobile is a v3+ consideration                                                                                           |
| Billing system / Stripe          | Revenue collection handled via invoice/bank transfer for pilot contracts; Stripe adds compliance surface area                                           |
| Real-time collaboration          | No identified use case for v1; law firms research individually                                                                                          |
| Answer feedback / thumbs up-down | Valuable for model improvement but no training loop in v1                                                                                               |
| Answer caching / deduplication   | Latency is acceptable; caching introduces staleness risk for legal queries                                                                              |
| Fine-tuned models                | Pipeline already outperforms SOTA zero-shot; fine-tuning requires labeled data collection first                                                         |
| Cloud deployment (AWS/GCP/Azure) | Mac + Tailscale Funnel is zero-cost and sufficient for pilot demos; migrate when revenue justifies infra spend                                          |
| Webhook notifications            | No integration partners in v1; REST polling is sufficient                                                                                               |
| PDF annotation / highlighting    | High UI complexity; citation excerpts in text are sufficient for v1                                                                                     |

## Traceability

Which phases cover which requirements.

| Requirement | Phase   | Status   |
|-------------|---------|----------|
| API-01      | Phase 1 | Pending  |
| API-02      | Phase 1 | Pending  |
| API-03      | Phase 1 | Pending  |
| API-04      | Phase 1 | Pending  |
| API-05      | Phase 1 | Complete |
| API-06      | Phase 2 | Pending  |
| AUTH-01     | Phase 2 | Pending  |
| AUTH-02     | Phase 2 | Pending  |
| AUTH-03     | Phase 2 | Pending  |
| AUTH-04     | Phase 2 | Pending  |
| AUTH-05     | Phase 2 | Pending  |
| AUDIT-01    | Phase 2 | Pending  |
| AUDIT-02    | Phase 2 | Pending  |
| AUDIT-03    | Phase 2 | Pending  |
| AUDIT-04    | Phase 2 | Pending  |
| AUDIT-05    | Phase 2 | Pending  |
| AUDIT-06    | Phase 2 | Pending  |
| DOC-01      | Phase 3 | Complete |
| DOC-02      | Phase 3 | Complete |
| DOC-03      | Phase 3 | Complete |
| DOC-04      | Phase 3 | Complete |
| DOC-05      | Phase 3 | Complete |
| DOC-06      | Phase 3 | Complete |
| DOC-07      | Phase 3 | Complete |
| PIPE-01     | Phase 1 | Complete |
| PIPE-02     | Phase 1 | Complete |
| PIPE-03     | Phase 1 | Complete |
| PIPE-04     | Phase 1 | Pending  |
| PIPE-05     | Phase 5 | Pending  |
| PIPE-06     | Phase 3 | Complete |
| UI-01       | Phase 4 | Pending  |
| UI-02       | Phase 4 | Pending  |
| UI-03       | Phase 4 | Pending  |
| UI-04       | Phase 4 | Pending  |
| UI-05       | Phase 4 | Pending  |
| UI-06       | Phase 4 | Pending  |
| UI-07       | Phase 4 | Pending  |
| UI-08       | Phase 6 | Pending  |
| UI-09       | Phase 4 | Pending  |
| UI-10       | Phase 4 | Pending  |
| NFR-01      | Phase 5 | Pending  |
| NFR-02      | Phase 3 | Complete |
| NFR-03      | Phase 1 | Complete |
| NFR-04      | Phase 2 | Pending  |
| NFR-05      | Phase 1 | Complete |
| NFR-06      | Phase 6 | Pending  |
| NFR-07      | Phase 4 | Pending  |
| NFR-08      | Phase 1 | Complete |

**Coverage:**

- v1 requirements: 48 total
- Mapped to phases: 48
- Unmapped: 0

---

## v2.0 Requirements — Premium Frontend Overhaul

**Milestone goal:** Redesign every frontend screen into a cohesive, Perplexity-quality glassmorphism UI that closes law
firm demos and looks portfolio-worthy.

### GLASS — Glass Design System Foundation

- [x] **GLASS-01**: User sees glass panels with visible frosted blur — CSS `@utility` classes (`glass-sm`, `glass-md`,
  `glass-lg`, `glass-gold`) in `globals.css` using Tailwind v4 `@utility` directive, replacing ~40 scattered inline
  glass styles
- [x] **GLASS-02**: Glass tokens exist as CSS variables — `--glass-bg`, `--glass-border-color`, `--glass-shadow`,
  `--orb-gold-color`, `--orb-blue-color`, `--orb-teal-color` added to `.dark` in `globals.css`
- [x] **GLASS-03**: Aurora orbs produce visible color behind glass — `AuroraBackground` reusable component with orbs at
  `0.40–0.55` opacity, `filter: blur(80–140px)`, configurable preset (`chat` / `landing` / `app-subtle`)
- [x] **GLASS-04**: Glass cards work without fighting shadcn — `GlassCard` component with
  `backdrop-filter: blur(32px) saturate(150%)`, correct background opacity (`0.08–0.12`), leaves shadcn `--card` token
  untouched
- [x] **GLASS-05**: Glass pills work for badges, chips, nav items — `GlassPill` component with
  `backdrop-filter: blur(16px)`, gold accent variant, hover state via CSS `@utility` not JS event handlers

### CHAT-LAYOUT — Chat Page Total Rebuild

- [x] **CHAT-01**: Chat page has dramatic aurora background — `AuroraBackground preset="chat"` with three vivid orbs (
  gold `0.45`, deep violet `0.40`, teal `0.35`)
- [x] **CHAT-02**: Chat input is a large prominent glass bar — full-width glass input container (
  `backdrop-filter: blur(32px)`), gold glow on send button when text present, sticky at bottom with frosted glass
  overlay
- [x] **CHAT-03**: User questions display as section headings — user message rendered as bold `font-heading` heading
  above the assistant response block, replacing right-aligned chat bubble
- [x] **CHAT-04**: Assistant responses sit in a glass content panel — response rendered in `GlassCard`, prose
  typography, clean Perplexity-style answer flow
- [ ] **CHAT-05**: Empty state uses glassmorphism suggestion cards — large centered layout with shield logo glow,
  numbered `GlassCard` suggestion buttons with gold hover

### CHAT-SOURCES — Source Document Visualization

- [x] **SRC-01**: Sources panel appears before the answer — labeled "Sources" section with numbered `GlassPill` source
  cards displayed ABOVE the prose answer (Perplexity pattern)
- [x] **SRC-02**: Each source card shows document name and page — chip displays `doc_id` (truncated), page number in
  gold, numbered badge
- [x] **SRC-03**: Clicking a source card opens the grounding drawer — wires existing `grounding-drawer.tsx` +
  `GroundingView` split pane to the selected source
- [x] **SRC-04**: Streaming shows descriptive RAG status labels — `streamingStatus` prop drives: "Searching
  documents…", "Analyzing sources…", "Synthesizing answer…" in a glass status pill

### CONF — Confidence Display

- [x] **CONF-01**: Confidence displays as icon badge — high/medium/low shown as pill with
  ShieldCheck/AlertTriangle/AlertCircle icon, appears after answer prose

### APP-PAGES — App Pages Glass Treatment

- [ ] **APP-01**: Documents page has aurora background and glass cards — `AuroraBackground preset="app-subtle"`, upload
  zone and document list use `GlassCard`
- [ ] **APP-02**: Settings page has aurora background and glass cards — `AuroraBackground preset="app-subtle"`, settings
  section cards use `GlassCard`
- [ ] **APP-03**: App layout mobile header is frosted glass — `backdrop-filter: blur(20px)`, `rgba(6,12,22,0.80)`
  background

### LANDING — Landing Page Polish (preserve original character)

**Scope correction 2026-03-27:** Original landing page design was solid. Phase 14 polishes it, does NOT overhaul it.
Light trust section stays light. Overall aesthetic preserved.

- [ ] **LAND-01**: Trust/access form card upgraded — current plain white card gets subtle glass treatment (
  `backdrop-filter: blur(20px)`, `rgba(255,255,255,0.88)` bg, amber border `rgba(220,150,20,0.4)`) while section
  background stays `#FAFAF9` (light stays light)
- [ ] **LAND-02**: Value pillar cards get frosty glass upgrade — `GlassCard` replaces inline glass styles, gold
  top-accent line on each card (already dark section, glass looks right here)
- [ ] **LAND-03**: How-it-works step panel gets `GlassCard` — replaces inline glass styles
- [ ] **LAND-04**: Demo panel outer container shadow upgraded — richer depth (
  `0 40px 80px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.08)`)

---

## Traceability (v2.0)

| Requirement | Phase    | Status   |
|-------------|----------|----------|
| GLASS-01    | Phase 12 | Complete |
| GLASS-02    | Phase 12 | Complete |
| GLASS-03    | Phase 12 | Complete |
| GLASS-04    | Phase 12 | Complete |
| GLASS-05    | Phase 12 | Complete |
| CHAT-01     | Phase 13 | Complete |
| CHAT-02     | Phase 13 | Complete |
| CHAT-03     | Phase 13 | Complete |
| CHAT-04     | Phase 13 | Complete |
| CHAT-05     | Phase 13 | Pending  |
| SRC-01      | Phase 13 | Complete |
| SRC-02      | Phase 13 | Complete |
| SRC-03      | Phase 13 | Complete |
| SRC-04      | Phase 13 | Complete |
| CONF-01     | Phase 13 | Complete |
| APP-01      | Phase 14 | Pending  |
| APP-02      | Phase 14 | Pending  |
| APP-03      | Phase 14 | Pending  |
| LAND-01     | Phase 14 | Pending  |
| LAND-02     | Phase 14 | Pending  |
| LAND-03     | Phase 14 | Pending  |
| LAND-04     | Phase 14 | Pending  |

**v2.0 Coverage:**

- v2.0 requirements: 22 total (LAND-05 dropped — low priority)
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-03-26*
*v2.0 requirements added: 2026-03-27*
*v2.0 traceability expanded with status column: 2026-03-27*
