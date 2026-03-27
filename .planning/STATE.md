---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: — Premium Frontend Overhaul
status: executing
last_updated: "2026-03-27T11:12:00Z"
last_activity: 2026-03-27 -- Phase 12 Plan 01 Tasks 1-5 complete, awaiting visual checkpoint
progress:
  total_phases: 10
  completed_phases: 1
  total_plans: 8
  completed_plans: 10
---

# Project State

## Current Position

Phase: 12 (Glass Design System Foundation) — EXECUTING
Plan: 1 of 1 (Tasks 1-5 complete, Task 6 visual checkpoint pending)
Status: Awaiting visual checkpoint verification
Last activity: 2026-03-27 -- Phase 12 Plan 01 Tasks 1-5 complete

## Milestone v2.0 Progress

- Phase 12: In progress (1/1 plans, Tasks 1-5 done, visual checkpoint pending) — Glass Design System Foundation (GLASS-01 to GLASS-05)
- Phase 13: Not started — Chat Page Total Rebuild (CHAT-01 to CHAT-05, SRC-01 to SRC-04, CONF-01)
- Phase 14: Not started — App Pages + Landing Unification (APP-01 to APP-03, LAND-01 to LAND-05)

**v2.0 requirements coverage:** 23/23 mapped, 0 unmapped

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
- Glassmorphism reference: semi-transparent bg + blur + rounded corners + soft shadow + vivid color behind
- Remote GPU: ssh neon@100.98.171.97, RTX 3070, ~/.conda/envs/torch313/bin/python3
- Critical pitfall: shadcn --card is opaque (oklch 0.16) — GlassCard wraps it, never applies backdrop-filter to a raw shadcn Card without nulling its background
- Critical pitfall: never animate backdrop-filter blur values — animate opacity/transform only
- Critical pitfall: overflow:hidden parents destroy backdrop-filter — use overflow:clip on scroll parents
- Z-index contract: z-0 orbs / z-10 glass panels / z-20 content / z-30 input bar / z-40 sidebar / z-50 nav / z-60 modals / z-70 toasts (now formalized as --z-* tokens in @theme inline)
- Glass Design System: 19 CSS tokens + 17 @utility classes in globals.css; AuroraBackground (3 presets), GlassCard (4 variants with overflow-clip), GlassPill (4 variants with CSS-only hover)
- Decision: @utility directive (not @layer utilities) for Tailwind v4 compatibility
- Decision: GlassCard outer div uses overflow-clip (not overflow-hidden) to prevent Chrome backdrop-filter stacking context bug

## Phase 12 Entry Checklist

Before starting Phase 12 planning:

- [ ] Confirm Tailwind v4 @utility directive syntax from node_modules/next/dist/docs/ or official docs
- [ ] Visually audit current aurora orb opacity values in globals.css (expected: ~0.12, need: 0.40+)
- [ ] Identify all ~40 scattered inline glass styles to be replaced
- [ ] Confirm grounding-drawer.tsx and GroundingView component locations (Phase 13 will wire, not rewrite)
