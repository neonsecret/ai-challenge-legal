---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: — Premium Frontend Overhaul
status: executing
last_updated: "2026-03-27T14:50:00Z"
last_activity: 2026-03-27 -- Phase 13 Plan 02 COMPLETE (warm chat shell + EmptyState component)
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 7
  completed_plans: 10
---

# Project State

## Current Position

Phase: 13 (Chat Page Total Rebuild) — In Progress
Plan: 2 of N — DONE (warm chat shell + EmptyState)
Status: Phase 13 executing. Plan 02 complete. Ready for Plan 03.
Last activity: 2026-03-27 -- Phase 13 Plan 02 complete (2 tasks, build passes, commit dddf6b3)

## Milestone v2.0 Progress

- Phase 12: COMPLETE (1/1 plans done) — Glass Design System Foundation (GLASS-01 to GLASS-05)
- Phase 13: In Progress (2/N plans done) — Chat Page Total Rebuild (CHAT-01 to CHAT-05, SRC-01 to SRC-04, CONF-01)
  - Plan 01: DONE — Merge Phase 12 + glass-warm @utility (commits: 85a46e6, 3ca9424, c9ccb55)
  - Plan 02: DONE — Warm amber chat shell + EmptyState standalone component (commit: dddf6b3)
- Phase 14: Not started — App Pages + Landing Polish (APP-01 to APP-03, LAND-01 to LAND-04)

**v2.0 requirements coverage:** 22/22 mapped, 0 unmapped

## Completed Phases (Previous Milestones)

- Phase 1-7: Core product (FastAPI + Auth + Upload + Frontend + Hardening + Demo + SOC2)
- Phase 8: Cancelled (using Qwen3-8B as-is, no fine-tuning)
- Phase 9: SOTA research complete (GaRAGe 0.826 beats SOTA 0.607)
- Phase 10: Premium UI redesign (light mode, Playfair serif, warm palette, marketing landing)
- Phase 11: Qwen3-4B integration + benchmark COMPLETE (2026-03-27) — 26947-vector FAISS index built, R@10 0.15→0.63 (+4.2x vs Snowflake Arctic)

## Tests: 129 passed, 0 failed (1 integration test pre-existing failure, unrelated to Phase 11)

## Accumulated Context

- Frontend: Next.js 16, Tailwind v4, shadcn/ui, motion/react (Framer Motion)
- Design palette: navy #0F1623 / #0A1120 / #060C16, gold #C9A84C, serif heading font
- Key issue: glassmorphism was surface-level (blur over near-black = invisible). Root cause: aurora orbs at rgba(..., 0.12) — too low to survive blur averaging. Fix: raise orb center stop to 0.40–0.45+.
- Chat reference: Perplexity layout + numbered source cards panel above answer text
- DESIGN SYSTEM LOCKED (2026-03-27) — pure CSS, no library:
  - Background: linear-gradient(145deg, #dfc090, #e8d4b8, #dbb870) + 3 warm amber radial blobs (0.35-0.45 opacity)
  - Glass panel: rgba(255,240,215,0.15), blur(36px) saturate(140%), border rgba(255,255,255,0.50), box-shadow 0 12px 40px rgba(100,50,0,0.28)
  - Palette "Arrakis/Dune": espresso CTA #5c2e08 · caramel badges #c47c00 · spice gold #c9a230 · camel #b29254 · Fremen blue #3576ae (success) · text #2e1f08 · muted #7a5a20
  - Showcase page: frontend/src/app/showcase/page.tsx — reference implementation
- Scope correction 2026-03-27: Landing page was solid, preserve its character. Dark sections get glass polish. Light trust section stays light.
- Chat page: complete rebuild. shadcn/ui AI components + @mawtech glass styling + Perplexity layout. Sources above answer. Wire existing useQueryStream + grounding-drawer.
- Remote GPU: ssh neon@100.98.171.97, RTX 3070, ~/.conda/envs/torch313/bin/python3
- Critical pitfall: shadcn --card is opaque (oklch 0.16) — GlassCard wraps it, never applies backdrop-filter to a raw shadcn Card without nulling its background
- Critical pitfall: never animate backdrop-filter blur values — animate opacity/transform only
- Critical pitfall: overflow:hidden parents destroy backdrop-filter — use overflow:clip on scroll parents
- Z-index contract: z-0 orbs / z-10 glass panels / z-20 content / z-30 input bar / z-40 sidebar / z-50 nav / z-60 modals / z-70 toasts (now formalized as --z-* tokens in @theme inline)
- Glass Design System: 19 CSS tokens + 25 @utility classes in globals.css (includes glass-warm warm Dune palette); AuroraBackground (3 presets), GlassCard (4 variants with overflow-clip), GlassPill (4 variants with CSS-only hover)
- Phase 13-01 key decision: stash unstaged before merge; glass-warm inserted after glass-pill-success, before @supports fallback
- Decision: @utility directive (not @layer utilities) for Tailwind v4 compatibility
- Decision: GlassCard outer div uses overflow-clip (not overflow-hidden) to prevent Chrome backdrop-filter stacking context bug
- Phase 13-02 key decisions: overflow-clip on chat root div; blobs placed WITHOUT blur() filter (vivid not diffuse); onSourceClick added to ChatMessage now (build requires it); GlassCard variant=subtle for EmptyState cards
- Phase 13-02 pattern: all hover states on glass elements use Tailwind hover: classes, never JS event handlers
- Phase 13-02 blob layout: top-right 580px + right 460px + bottom-center 380px at 0.35–0.45 opacity

## Phase 12 Entry Checklist

Before starting Phase 12 planning:

- [ ] Confirm Tailwind v4 @utility directive syntax from node_modules/next/dist/docs/ or official docs
- [ ] Visually audit current aurora orb opacity values in globals.css (expected: ~0.12, need: 0.40+)
- [ ] Identify all ~40 scattered inline glass styles to be replaced
- [ ] Confirm grounding-drawer.tsx and GroundingView component locations (Phase 13 will wire, not rewrite)
