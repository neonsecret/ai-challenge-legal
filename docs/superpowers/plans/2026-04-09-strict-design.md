# Strict Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **CRITICAL:** Read `docs/superpowers/specs/2026-04-09-strict-design-spec.md` FIRST. Every color value, animation timing, and layout decision was collaboratively brainstormed with the user through interactive visual mockups. Do NOT deviate from the spec values. Do NOT substitute your own color choices, animation timings, or layout ideas. The spec IS the source of truth.
>
> **Reference mockup:** `.superpowers/brainstorm/16696-1775754111/content/full-design-polished.html` — open this in a browser to see what you're building.

**Goal:** Replace the V3 "Luminous" design with a new "Strict" dark glassmorphism theme, rename V2 to "Neon", and build a Full Glass Scholar chat layout with animated landing page.

**Architecture:** The existing design toggle system (`design-version.tsx` + CSS class on `<html>`) stays. Internal IDs change from `v2/v3` to `neon/strict`. All Strict styling lives in CSS custom properties scoped to `.design-strict` and `.design-strict.dark`. New landing components are created per-section to keep files focused. The chat page gets a new layout variant (Full Glass Scholar) rendered when `designVersion === "strict"`.

**Tech Stack:** Next.js 16, Tailwind CSS v4, motion/react, CSS custom properties, TypeScript

---

## File Map

### New Files
| File | Responsibility |
|---|---|
| `src/components/landing/strict/strict-hero.tsx` | Hero glass slab: title + benchmark stats + 100% counter |
| `src/components/landing/strict/strict-preview.tsx` | "The research experience" animated chat demo |
| `src/components/landing/strict/strict-how-it-works.tsx` | Interactive 3-step with visual panel |
| `src/components/landing/strict/strict-pricing.tsx` | 4-plan pricing cards |
| `src/components/landing/strict/strict-nav.tsx` | Strict navigation bar |
| `src/components/landing/strict/strict-footer.tsx` | Minimal footer |
| `src/components/landing/strict/strict-mesh-blobs.tsx` | Animated background blobs |
| `src/components/landing/strict/strict-landing.tsx` | Landing page orchestrator (imports all sections) |
| `src/components/chat/strict-layout.tsx` | Full Glass Scholar: glass pane + rail + reading area + source margin |
| `src/components/chat/strict-source-margin.tsx` | Source margin with glass tile animations |
| `src/lib/strict-tokens.ts` | Strict-specific animation timings, typewriter speeds, step durations |

### Modified Files
| File | Changes |
|---|---|
| `src/lib/design-version.tsx` | Type: `"v2"\|"v3"` → `"neon"\|"strict"`, default `"neon"`, class names |
| `src/components/design-version-toggle.tsx` | Labels: "Modern"→"Neon", "Luminous"→"Strict", swatch colors |
| `src/app/layout.tsx` | FOUC script: `design-v2/v3` → `design-neon/strict` |
| `src/app/globals.css` | Rename `.design-v2`→`.design-neon`, replace `.design-v3` block with `.design-strict` tokens |
| `src/app/(auth)/page.tsx` | Landing: `v3` branch → `strict` branch, render `<StrictLanding>` |
| `src/app/(app)/chat/page.tsx` | Chat: `isV3` → `isStrict`, render `<StrictLayout>` wrapper |
| `src/components/chat/chat-input.tsx` | `version === "v3"` → `version === "strict"`, gold accent colors |
| `src/components/app-sidebar.tsx` | Add `useDesignVersion()`, Strict glass styles |
| `src/lib/v3-motion.ts` | Rename file references (keep springs, they're good) |

---

### Task 1: Rename Design Version System (v2→neon, v3→strict)

**Files:**
- Modify: `src/lib/design-version.tsx`
- Modify: `src/app/layout.tsx` (lines 43–45, FOUC script)

- [ ] **Step 1: Update design-version.tsx types and constants**

In `src/lib/design-version.tsx`:
- Line 24: Change `export type DesignVersion = "v2" | "v3"` → `export type DesignVersion = "neon" | "strict"`
- Line 36: Change `const DEFAULT_VERSION: DesignVersion = "v2"` → `const DEFAULT_VERSION: DesignVersion = "neon"`
- Lines 50–53: Update `applyVersion()` — replace `design-v2`/`design-v3` class names with `design-neon`/`design-strict`

```typescript
function applyVersion(version: DesignVersion) {
  document.documentElement.classList.toggle("design-neon", version === "neon");
  document.documentElement.classList.toggle("design-strict", version === "strict");
}
```

- [ ] **Step 2: Update FOUC prevention script in layout.tsx**

In `src/app/layout.tsx`, lines 43–45, update the inline script:
```typescript
<script dangerouslySetInnerHTML={{__html: `try{var dv=localStorage.getItem('vitreon-design-version');if(dv==='neon'){document.documentElement.classList.add('design-neon')}else if(dv==='strict'){document.documentElement.classList.add('design-strict')}else{document.documentElement.classList.add('design-neon')}}catch(e){document.documentElement.classList.add('design-neon')}`}} />
```

Note: Old localStorage values (`v2`, `v3`) will fall through to the else-branch and get `design-neon` as default. This is intentional — existing users seamlessly migrate.

- [ ] **Step 3: Update toggle component labels and styles**

In `src/components/design-version-toggle.tsx`:
- Line 11–18: Change first option from `{ id: "v2", label: "Modern", ...}` to `{ id: "neon", label: "Neon", ...}`
- Line 19–25: Change second option from `{ id: "v3", label: "Luminous", ...}` to `{ id: "strict", label: "Strict", ...}`
- Update swatch gradient for Strict: use `linear-gradient(135deg, rgba(201,168,76,0.3), rgba(201,168,76,0.1))` (gold glass)
- In `getActivePillStyle()` (lines 75–94): Replace V3 iris accent with gold: `rgba(201,168,76, 0.15)` bg, `rgba(201,168,76, 0.25)` border

- [ ] **Step 4: Commit**

```bash
git add src/lib/design-version.tsx src/app/layout.tsx src/components/design-version-toggle.tsx
git commit -m "refactor: rename design versions v2→neon, v3→strict"
```

---

### Task 2: Rename CSS Classes in globals.css

**Files:**
- Modify: `src/app/globals.css`

This task ONLY renames classes. No new tokens yet.

- [ ] **Step 1: Rename all `.design-v2` selectors to `.design-neon`**

Find and replace across `globals.css`:
- `.design-v2` → `.design-neon` (all occurrences, lines 464–622 and anywhere else)
- `.design-v2.dark` → `.design-neon.dark`

- [ ] **Step 2: Rename all `.design-v3` selectors to `.design-strict`**

Find and replace:
- `.design-v3` → `.design-strict` (all occurrences, lines 637–2336)
- `.design-v3.dark` → `.design-strict.dark`

- [ ] **Step 3: Update any JS/TSX files that reference design-v2/v3 class names**

Search the codebase for any hardcoded `design-v2` or `design-v3` strings in TypeScript/TSX files. These should now be `design-neon` and `design-strict`. Common locations:
- `src/app/(app)/chat/page.tsx` — search for `"design-v3"` or `v3-glass`
- `src/components/app-sidebar.tsx`
- `src/components/chat/chat-input.tsx`
- Any component that checks `designVersion === "v3"` — change to `=== "strict"`

Run: `grep -r "design-v[23]\|=== ['\"]v[23]['\"]" src/ --include="*.tsx" --include="*.ts"`

Update ALL matches.

- [ ] **Step 4: Verify the app builds and both designs still work**

```bash
cd frontend && rm -rf .next && npm run build
```

Expected: Build succeeds with no errors. Neon design renders as before, Strict renders with the old V3 luminous look (will be replaced in next tasks).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: rename CSS classes design-v2→neon, design-v3→strict"
```

---

### Task 3: Add Strict Design Tokens (Dark Mode)

**Files:**
- Modify: `src/app/globals.css`

Replace the existing `.design-strict` dark-mode token block (previously V3 luminous) with the new Strict palette. Reference: spec section 3.1.

- [ ] **Step 1: Replace `.design-strict.dark` token block**

Find the existing `.design-strict.dark` block (was `.design-v3.dark`, around lines 908–1259) and replace its custom property declarations with the Strict dark palette. Keep the selector, replace the contents:

```css
.design-strict.dark {
  /* Page */
  --strict-bg-html: #0D0A12;
  --background: #0B0E16;

  /* Glass surfaces */
  --strict-glass-bg: rgba(255,255,255, 0.02);
  --strict-glass-border: rgba(201,168,76, 0.06);
  --strict-glass-blur: blur(24px);
  --strict-glass-shadow: 0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025);
  --strict-glass-recessed: rgba(0,0,0, 0.1);
  --strict-glass-hover-shadow: 0 12px 40px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.03);

  /* Text hierarchy */
  --strict-text-primary: rgba(230,235,245, 0.88);
  --strict-text-body: rgba(255,255,255, 0.56);
  --strict-text-question: rgba(255,255,255, 0.7);
  --strict-text-secondary: rgba(200,210,230, 0.42);
  --strict-text-dim: rgba(200,210,230, 0.22);
  --strict-text-ghost: rgba(255,255,255, 0.16);

  /* Gold system */
  --strict-gold-base: #C9A84C;
  --strict-gold-text: rgba(201,168,76, 0.7);
  --strict-gold-border: rgba(201,168,76, 0.06);
  --strict-gold-border-active: rgba(201,168,76, 0.15);
  --strict-gold-badge-bg: rgba(201,168,76, 0.06);
  --strict-gold-badge-border: rgba(201,168,76, 0.1);
  --strict-gold-badge-text: rgba(201,168,76, 0.45);
  --strict-citation: rgba(201,168,76, 0.55);
  --strict-gold-sep: linear-gradient(90deg, rgba(201,168,76,0.2), rgba(201,168,76,0.04));
  --strict-gold-underbar: rgba(201,168,76, 0.3);
  --strict-gold-underbar-hover: rgba(201,168,76, 0.5);

  /* Nav */
  --strict-nav-link: rgba(200,210,230, 0.38);
  --strict-nav-link-hover: rgba(200,210,230, 0.6);
  --strict-nav-signin: rgba(201,168,76, 0.7);
  --strict-nav-signin-hover: rgba(201,168,76, 0.9);
  --strict-nav-sep: rgba(201,168,76, 0.06);

  /* Source margin */
  --strict-source-text: rgba(255,255,255, 0.3);
  --strict-source-num: rgba(201,168,76, 0.4);
  --strict-source-label: rgba(201,168,76, 0.3);

  /* Scrollbar */
  --strict-scrollbar: rgba(201,168,76, 0.15);
  --strict-scrollbar-hover: rgba(201,168,76, 0.25);

  /* Map to existing dt-* tokens for components that use them */
  --dt-glass-bg: var(--strict-glass-bg);
  --dt-glass-border: var(--strict-glass-border);
  --dt-glass-blur: var(--strict-glass-blur);
  --dt-text-primary: var(--strict-text-primary);
  --dt-text-secondary: var(--strict-text-secondary);
  --dt-accent-color: var(--strict-gold-base);
  --dt-color-gold-base: var(--strict-gold-base);
}
```

- [ ] **Step 2: Add Strict light mode tokens**

Replace the `.design-strict` (no `.dark`) block with Ink on Fog palette. Reference: spec section 3.2.

```css
.design-strict {
  --strict-bg-html: #D8DAE2;
  --background: #E0E2E8;

  --strict-glass-bg: rgba(20,22,30, 0.04);
  --strict-glass-border: rgba(20,22,30, 0.08);
  --strict-glass-blur: blur(14px);
  --strict-glass-shadow: 0 2px 6px rgba(80,60,20,0.04), inset 0 1px 0 rgba(255,255,255,0.4);
  --strict-glass-recessed: rgba(20,22,30, 0.03);

  --strict-text-primary: rgba(20,22,30, 0.78);
  --strict-text-body: rgba(20,22,30, 0.65);
  --strict-text-question: rgba(20,22,30, 0.82);
  --strict-text-secondary: rgba(20,22,30, 0.5);
  --strict-text-dim: rgba(20,22,30, 0.3);
  --strict-text-ghost: rgba(20,22,30, 0.2);

  --strict-gold-base: #8B6914;
  --strict-gold-text: rgba(138,110,24, 0.7);
  --strict-gold-border: rgba(180,150,60, 0.14);
  --strict-gold-border-active: rgba(180,150,60, 0.25);
  --strict-gold-badge-bg: rgba(180,150,60, 0.07);
  --strict-gold-badge-border: rgba(180,150,60, 0.14);
  --strict-gold-badge-text: rgba(138,110,24, 0.6);
  --strict-citation: rgba(138,110,24, 0.65);
  --strict-gold-sep: linear-gradient(90deg, rgba(180,150,60,0.15), rgba(180,150,60,0.03));
  --strict-gold-underbar: rgba(180,150,60, 0.25);
  --strict-gold-underbar-hover: rgba(180,150,60, 0.4);

  --strict-nav-link: rgba(20,22,30, 0.38);
  --strict-nav-link-hover: rgba(20,22,30, 0.6);
  --strict-nav-signin: rgba(138,110,24, 0.7);
  --strict-nav-signin-hover: rgba(138,110,24, 0.9);
  --strict-nav-sep: rgba(180,150,60, 0.08);

  --strict-source-text: rgba(20,22,30, 0.35);
  --strict-source-num: rgba(138,110,24, 0.5);
  --strict-source-label: rgba(138,110,24, 0.4);

  --strict-scrollbar: rgba(180,150,60, 0.12);
  --strict-scrollbar-hover: rgba(180,150,60, 0.2);

  --dt-glass-bg: var(--strict-glass-bg);
  --dt-glass-border: var(--strict-glass-border);
  --dt-glass-blur: var(--strict-glass-blur);
  --dt-text-primary: var(--strict-text-primary);
  --dt-text-secondary: var(--strict-text-secondary);
  --dt-accent-color: var(--strict-gold-base);
}
```

- [ ] **Step 3: Add Strict scrollbar and overscroll CSS**

Add after the Strict token blocks:

```css
.design-strict {
  scrollbar-width: thin;
  scrollbar-color: var(--strict-scrollbar) transparent;
}
.design-strict::-webkit-scrollbar { width: 6px; }
.design-strict::-webkit-scrollbar-track { background: transparent; }
.design-strict::-webkit-scrollbar-thumb { background: var(--strict-scrollbar); border-radius: 3px; }
.design-strict::-webkit-scrollbar-thumb:hover { background: var(--strict-scrollbar-hover); }

html.design-strict { background: var(--strict-bg-html); overscroll-behavior: none; }
```

- [ ] **Step 4: Remove old V3 luminous-specific utilities that don't apply**

Remove or replace these V3-specific sections that used iris/aurora colors:
- Aurora background keyframes and classes (lines ~1340–1421) — replace with mesh blob animation
- V3 text gradient classes (lines ~1424–1441) — replace with strict gold gradient
- V3 glass panel classes (lines ~1442–1487) — simplify to strict glass

Add strict mesh blob animation:
```css
@keyframes strict-drift {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(15px, -10px); }
  66% { transform: translate(-10px, 15px); }
}
```

- [ ] **Step 5: Commit**

```bash
git add src/app/globals.css && git commit -m "feat: add Strict design tokens (dark + light mode)"
```

---

### Task 4: Create Strict Animation Tokens

**Files:**
- Create: `src/lib/strict-tokens.ts`

- [ ] **Step 1: Create strict-tokens.ts**

```typescript
/** Strict design animation and timing constants */

/** Typewriter speeds (ms per character) */
export const STRICT_TYPEWRITER = {
  /** Chat preview on landing page */
  preview: 8,
  /** How It Works typing demo */
  hiw: 35,
} as const;

/** How It Works auto-advance */
export const STRICT_HIW = {
  /** Duration each step is active (ms) */
  stepDuration: 5000,
  /** Pause after user clicks a step before resuming auto (ms) */
  userPause: 8000,
  /** Delay between scanning items appearing (ms) */
  scanStagger: 800,
  /** Delay before result highlight slides in (ms) */
  resultHighlightDelay: 400,
} as const;

/** Source margin reveal */
export const STRICT_SOURCES = {
  /** Stagger between each source tile appearing (ms) */
  stagger: 250,
} as const;

/** Mesh blob animation */
export const STRICT_MESH = {
  /** Full drift cycle duration (s) */
  driftDuration: 8,
} as const;

/** 100% citation accuracy counter */
export const STRICT_COUNTER = {
  /** Increment per tick */
  step: 2,
  /** Ms between ticks */
  interval: 20,
  /** Delay before counter starts (ms) */
  delay: 1200,
} as const;

/** Hero stat stagger delay (ms between each stat row) */
export const STRICT_HERO_STAGGER = 150;

/** Badge pulse cycle (seconds) */
export const STRICT_BADGE_PULSE = 3;

/** Gold glow brightness pulse cycle (seconds) */
export const STRICT_GLOW_PULSE = 2.5;
```

- [ ] **Step 2: Commit**

```bash
git add src/lib/strict-tokens.ts && git commit -m "feat: add Strict animation timing tokens"
```

---

### Task 5: Build Strict Mesh Blobs Background

**Files:**
- Create: `src/components/landing/strict/strict-mesh-blobs.tsx`

- [ ] **Step 1: Create the mesh blobs component**

Three fixed-position blobs with blur and drift animation. Reference: spec section 6.1.

```typescript
"use client";

import { STRICT_MESH } from "@/lib/strict-tokens";

const BLOBS = [
  { top: "-5%", left: "-5%", width: 400, height: 400, bg: "rgba(201,168,76,0.04)", delay: 0 },
  { bottom: "-10%", right: "-5%", width: 350, height: 350, bg: "rgba(100,130,200,0.03)", delay: -3 },
  { top: "40%", left: "55%", width: 300, height: 300, bg: "rgba(201,168,76,0.025)", delay: -6 },
] as const;

export function StrictMeshBlobs() {
  return (
    <>
      {BLOBS.map((blob, i) => (
        <div
          key={i}
          className="fixed rounded-full pointer-events-none"
          style={{
            top: "top" in blob ? blob.top : undefined,
            bottom: "bottom" in blob ? blob.bottom : undefined,
            left: "left" in blob ? blob.left : undefined,
            right: "right" in blob ? blob.right : undefined,
            width: blob.width,
            height: blob.height,
            background: blob.bg,
            filter: "blur(80px)",
            animation: `strict-drift ${STRICT_MESH.driftDuration}s ease-in-out infinite`,
            animationDelay: `${blob.delay}s`,
          }}
        />
      ))}
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/components/landing/strict/strict-mesh-blobs.tsx
git commit -m "feat: add Strict mesh blob background component"
```

---

### Task 6: Build Strict Navigation Bar

**Files:**
- Create: `src/components/landing/strict/strict-nav.tsx`

- [ ] **Step 1: Create nav component**

Reference: spec section 5.1. Gold underline Sign In, thin separator below.

```typescript
"use client";

import Link from "next/link";

const NAV_LINKS = [
  { href: "#features", label: "Features" },
  { href: "#pricing", label: "Pricing" },
] as const;

export function StrictNav() {
  return (
    <nav
      className="flex items-center mx-auto max-w-[880px] px-8 py-5"
      style={{ borderBottom: "1px solid var(--strict-nav-sep)" }}
    >
      <Link href="/" className="text-[13px] tracking-[2px] font-normal" style={{ color: "var(--strict-nav-signin)" }}>
        VITREON
      </Link>
      <div className="ml-auto flex items-center gap-5">
        {NAV_LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="text-[11px] no-underline transition-colors duration-150"
            style={{ color: "var(--strict-nav-link)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--strict-nav-link-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--strict-nav-link)")}
          >
            {link.label}
          </a>
        ))}
        <Link
          href="/login"
          className="text-[11px] no-underline pb-px transition-all duration-150"
          style={{
            color: "var(--strict-nav-signin)",
            borderBottom: "1px solid var(--strict-gold-underbar)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "var(--strict-nav-signin-hover)";
            e.currentTarget.style.borderBottomColor = "var(--strict-gold-underbar-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--strict-nav-signin)";
            e.currentTarget.style.borderBottomColor = "var(--strict-gold-underbar)";
          }}
        >
          Sign In
        </Link>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/components/landing/strict/strict-nav.tsx
git commit -m "feat: add Strict navigation bar component"
```

---

### Task 7: Build Strict Hero Slab with Benchmark Stats

**Files:**
- Create: `src/components/landing/strict/strict-hero.tsx`

This is the most complex landing component. Reference: spec sections 5.3, 5.4, 5.6, 6.1.

- [ ] **Step 1: Create hero component**

Key requirements:
- Living Glass Slab with hero text (left) + benchmark stats (right)
- Gold gradient on "Reimagined"
- Jurisdiction pills: dot-separated, hoverable (transition to bordered tag)
- Gold Underbar CTA button
- 100% Citation accuracy: count-up animation, gold gradient text, glow, brightness pulse
- All stat rows stagger in
- Czech locale: demo question changes (read `useParams` or i18n context)

The hero component needs the `motion/react` library for entrance animations. Use `V3_SPRING` presets (they apply to Strict too — same physics, different visuals). The 100% counter uses a `useEffect` with `setInterval`. Jurisdiction pills manage their own hover state.

Write the full component. It should be ~200-250 lines. Use CSS variables from `--strict-*` for all colors. No hardcoded color values in the component.

The stats data should come from a constant array:
```typescript
const STATS = [
  { value: "0.824", label: "GaRAGe RAF", badge: "+36% above SOTA", detail: "Retrieval-augmented factuality · ACL 2025" },
  { value: "0.860", label: "Legal RAG Bench retrieval", detail: "Full 100-question evaluation" },
  { value: "0.691", label: "LEXam Open EN", badge: "+21% above SOTA", detail: "Published SOTA: 0.572 (Claude 3.7-S)" },
] as const;
```

The 100% stat is rendered separately with special treatment (gold gradient, counter, glow).

- [ ] **Step 2: Commit**

```bash
git add src/components/landing/strict/strict-hero.tsx
git commit -m "feat: add Strict hero slab with benchmark stats and 100% counter"
```

---

### Task 8: Build Strict Chat Preview ("The research experience")

**Files:**
- Create: `src/components/landing/strict/strict-preview.tsx`

- [ ] **Step 1: Create preview component**

Reference: spec section 6.2. This renders a static Full Glass Scholar pane with scroll-triggered animations:

1. Glass pane fades up (IntersectionObserver)
2. Question fades in + slides up
3. Answer types out via React state (NOT innerHTML) — accumulate a string in state, render via `dangerouslySetInnerHTML` on a single element so `<sup>` tags work correctly. Speed: `STRICT_TYPEWRITER.preview` (8ms).
4. Sources reveal as glass tiles: `scale(0.95) + translateX(12px) + opacity(0)` → identity, staggered `STRICT_SOURCES.stagger` (250ms)

**Critical implementation detail for typewriter:** The answer text contains `<sup>1</sup>` tags. You MUST accumulate the full string in a ref/state variable and set `dangerouslySetInnerHTML={{ __html: buffer }}` on each tick. Do NOT use `element.innerHTML +=` — it re-parses and breaks tags. Use a ref for the buffer and setState to trigger re-render.

The answer text and source data should be defined as constants at module level.

- [ ] **Step 2: Commit**

```bash
git add src/components/landing/strict/strict-preview.tsx
git commit -m "feat: add Strict chat preview with typewriter animation"
```

---

### Task 9: Build Strict How It Works

**Files:**
- Create: `src/components/landing/strict/strict-how-it-works.tsx`

- [ ] **Step 1: Create component**

Reference: spec section 6.3. This is the most animation-heavy landing component.

**Layout:** Left column (step list, 280px) + right panel (glass visual, flex-1).

**Left column:** 3 clickable steps with:
- Vertical gold progress bar (2px, fills over `STRICT_HIW.stepDuration`)
- Active step has brighter text, subtle glass bg
- Auto-advances through steps; clicking pauses for `STRICT_HIW.userPause` then resumes

**Right panel:** Three visual states (only active one visible):

1. **Typing visual:** Input box with blinking cursor, types out "What are the indemnification obligations under Section 9?" at `STRICT_TYPEWRITER.hiw` speed. Czech locale variant: "Jaké jsou povinnosti odškodnění podle §9?"

2. **Scanning visual:** Three items appear sequentially (`STRICT_HIW.scanStagger` apart):
   - "Scanning 4,800+ documents" with pulsing gold dot + progress line + checkmark
   - "Located Article 58 §2"
   - "Ranked 5 passages"

3. **Result visual:** Glass card showing "Article 58 §2 · DIFC Law No. 4 of 2005 · Page 34" with highlighted legal quote that slides in after `STRICT_HIW.resultHighlightDelay`.

Use `useEffect` for auto-advance timer. Use `useCallback` for step transitions. Each visual resets its animation state when activated.

- [ ] **Step 2: Commit**

```bash
git add src/components/landing/strict/strict-how-it-works.tsx
git commit -m "feat: add Strict How It Works with interactive visual panel"
```

---

### Task 10: Build Strict Pricing Section

**Files:**
- Create: `src/components/landing/strict/strict-pricing.tsx`

- [ ] **Step 1: Create pricing component**

Reference: spec section 6.4. Four glass cards, staggered entrance, Gold Underbar CTAs.

```typescript
const PLANS = [
  { name: "FREE", price: "$0", sub: "3 queries / day", features: ["All jurisdictions", "Source citations", "Basic export"], cta: "Get Started", featured: false },
  { name: "STARTER", price: "$29", priceSuffix: "/mo", sub: "30 queries / day", features: ["Everything in Free", "Document upload", "Priority support"], cta: "Subscribe", featured: true },
  { name: "PRO", price: "$179", priceSuffix: "/mo", sub: "200 queries / day", features: ["Everything in Starter", "API access", "Team workspace"], cta: "Subscribe", featured: false },
  { name: "ENTERPRISE", price: "$499", priceSuffix: "/mo", sub: "Unlimited queries", features: ["Everything in Pro", "Dedicated support", "Custom integrations"], cta: "Subscribe", featured: false },
] as const;
```

Each card: glass background, hover lift 3px, featured has gold border + subtle shadow. CTAs use Gold Underbar style. Scroll-triggered fade-up with 80ms stagger.

- [ ] **Step 2: Commit**

```bash
git add src/components/landing/strict/strict-pricing.tsx
git commit -m "feat: add Strict pricing section"
```

---

### Task 11: Build Strict Footer

**Files:**
- Create: `src/components/landing/strict/strict-footer.tsx`

- [ ] **Step 1: Create footer**

Minimal — thin gold top border, copyright text. Reference: spec section 6.5.

- [ ] **Step 2: Commit**

```bash
git add src/components/landing/strict/strict-footer.tsx
git commit -m "feat: add Strict footer component"
```

---

### Task 12: Build Strict Landing Orchestrator

**Files:**
- Create: `src/components/landing/strict/strict-landing.tsx`
- Modify: `src/app/(auth)/page.tsx`

- [ ] **Step 1: Create landing orchestrator**

Imports all Strict landing sections and renders them in order. Wraps in `<MotionConfig reducedMotion="user">`.

```typescript
"use client";

import { MotionConfig } from "motion/react";
import { StrictMeshBlobs } from "./strict-mesh-blobs";
import { StrictNav } from "./strict-nav";
import { StrictHero } from "./strict-hero";
import { StrictPreview } from "./strict-preview";
import { StrictHowItWorks } from "./strict-how-it-works";
import { StrictPricing } from "./strict-pricing";
import { StrictFooter } from "./strict-footer";

export function StrictLanding() {
  return (
    <MotionConfig reducedMotion="user">
      <div
        className="min-h-screen overflow-x-hidden"
        style={{ background: "var(--strict-bg-html)" }}
      >
        <StrictMeshBlobs />
        <StrictNav />
        <StrictHero />
        <StrictPreview />
        <StrictHowItWorks />
        <StrictPricing />
        <StrictFooter />
      </div>
    </MotionConfig>
  );
}
```

- [ ] **Step 2: Update landing page to render StrictLanding**

In `src/app/(auth)/page.tsx`, find the conditional at line 126:
```typescript
if (designVersion === "v3") {
```
Change to:
```typescript
if (designVersion === "strict") {
```
And replace the entire V3/luminous branch with:
```typescript
return <StrictLanding />;
```

Keep the Neon branch untouched.

- [ ] **Step 3: Verify landing page renders**

```bash
cd frontend && npm run dev
```
Open browser, toggle to Strict design. Verify all sections render.

- [ ] **Step 4: Commit**

```bash
git add src/components/landing/strict/strict-landing.tsx src/app/\(auth\)/page.tsx
git commit -m "feat: wire up Strict landing page orchestrator"
```

---

### Task 13: Build Full Glass Scholar Chat Layout

**Files:**
- Create: `src/components/chat/strict-layout.tsx`
- Create: `src/components/chat/strict-source-margin.tsx`

This is the core chat experience. Reference: spec section 7.

- [ ] **Step 1: Create source margin component**

The source margin renders inside the glass pane. Each source has glass tile animation on entrance.

Props: `sources: Array<{ id: string; label: string; detail: string }>`, `onSourceClick: (id: string) => void`

Each source tile animates with motion/react: `initial={{ opacity: 0, scale: 0.95, x: 12 }}`, `animate={{ opacity: 1, scale: 1, x: 0 }}`, staggered by index × `STRICT_SOURCES.stagger`. Use `V3_SPRING.standard` for the transition.

Gold gradient fade separator between sources. Gold "SOURCES" label at top.

- [ ] **Step 2: Create Full Glass Scholar layout wrapper**

This wraps the existing chat content in the glass scholar structure:
- One glass pane (`border-radius: 16px`, Strict glass tokens)
- Sidebar rail (44px): logo circle + icon buttons, recessed bg
- Reading area (flex-1): receives children (existing chat messages)
- Source margin (160px): `<StrictSourceMargin>` component

The layout receives children for the reading area content and source data as props. It does NOT reimplement chat logic — it wraps the existing `ChatMessage`, streaming, input components.

Questions should render in `var(--strict-text-question)` italic Georgia. Answers in `var(--strict-text-body)` Georgia. Citations in `var(--strict-citation)`.

- [ ] **Step 3: Commit**

```bash
git add src/components/chat/strict-layout.tsx src/components/chat/strict-source-margin.tsx
git commit -m "feat: add Full Glass Scholar chat layout and source margin"
```

---

### Task 14: Wire Strict Layout into Chat Page

**Files:**
- Modify: `src/app/(app)/chat/page.tsx`
- Modify: `src/components/chat/chat-input.tsx`
- Modify: `src/components/app-sidebar.tsx`

- [ ] **Step 1: Update chat page to use StrictLayout**

In `src/app/(app)/chat/page.tsx`:
- Line 132: Change `const isV3 = mounted && designVersion === "v3"` → `const isStrict = mounted && designVersion === "strict"`
- When `isStrict` is true, wrap the chat content in `<StrictLayout>` instead of the default panel layout
- Pass source data to `StrictLayout` for the margin
- All `isV3` conditionals throughout the file → `isStrict`
- The `makeGlassPanel()` function: update V3 branch to use `--strict-*` tokens

- [ ] **Step 2: Update chat input for Strict**

In `src/components/chat/chat-input.tsx`:
- Line 24: Change `version === "v3"` → `version === "strict"`
- Replace iris colors with gold:
  - Send button active: `"linear-gradient(135deg, rgba(201,168,76,0.25), rgba(201,168,76,0.15))"` (gold glass)
  - Send button text active: `"var(--strict-gold-base)"`
  - Send button disabled: `"rgba(50,50,50,0.40)"`
  - Border focused: `"var(--strict-gold-underbar)"`
  - Container bg: `"rgba(19,19,19,0.64)"` (keep, it's the same dark glass)
  - Caret color: `"var(--strict-gold-text)"`

- [ ] **Step 3: Update sidebar for Strict**

In `src/components/app-sidebar.tsx`:
- Import `useDesignVersion`
- Add Strict glass styles to `makeLiquidGlass()`:
  - When strict + dark: bg `var(--strict-glass-recessed)`, border `var(--strict-glass-border)`, gold accents
  - When strict + light: use light Strict tokens
- Update `makeActiveItemStyle()` for Strict: gold pill instead of indigo

- [ ] **Step 4: Test chat page end-to-end**

```bash
cd frontend && npm run dev
```
- Toggle to Strict design
- Open a chat, ask a question
- Verify: glass scholar layout renders, sources appear in margin, typewriter works, citations are superscript, sidebar has correct styling

- [ ] **Step 5: Commit**

```bash
git add src/app/\(app\)/chat/page.tsx src/components/chat/chat-input.tsx src/components/app-sidebar.tsx
git commit -m "feat: wire Strict layout into chat page, input, and sidebar"
```

---

### Task 15: Polish Animations and 60fps Verification

**Files:**
- Modify: Various Strict components as needed

- [ ] **Step 1: Verify all scroll-triggered animations**

Open the Strict landing page in Chrome DevTools Performance tab. Scroll through the entire page and record a performance trace.

Check:
- No layout thrashing (forced reflows during animation)
- All animations use `transform` and `opacity` only (GPU-composited)
- No `backdrop-filter` animation (it's static per element, not transitioning)
- Mesh blobs stay at 60fps (they use CSS animation, not JS)
- IntersectionObserver fires correctly for all `.fade-up` elements

- [ ] **Step 2: Verify chat typewriter performance**

Open the chat preview section. The typewriter should:
- Type smoothly at 8ms/char without jank
- `<sup>` citation numbers render correctly as superscripts
- Blinking cursor stays smooth
- Source tiles animate in with spring physics after text completes

If any animation janks, check for:
- Re-renders from state updates during animation (use refs where possible)
- Layout shifts from changing `innerHTML`

- [ ] **Step 3: Verify How It Works auto-advance**

- Steps cycle automatically (5s per step)
- Clicking a step pauses, resumes after 8s
- Typing animation resets cleanly on each cycle
- Scanning items reset and re-animate
- No memory leaks from setInterval/setTimeout (check with DevTools Memory tab)

- [ ] **Step 4: Verify reduced motion**

Turn on "Reduce motion" in system settings. All animations should:
- Not play (or play instantly)
- Content still visible and functional
- No broken layouts from missing animation keyframes

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: polish Strict animations for 60fps and reduced motion"
```

---

### Task 16: Force Rebuild and Full E2E Verification

**Files:** None (verification only)

- [ ] **Step 1: Force rebuild frontend**

```bash
cd frontend && rm -rf .next && npm run build
```

Expected: Build succeeds with zero errors and zero warnings related to Strict components.

- [ ] **Step 2: Verify Neon design unchanged**

Start dev server, toggle to Neon. Check:
- Landing page renders identically to before
- Chat page renders identically
- No style leakage from Strict tokens
- Toggle works in both directions

- [ ] **Step 3: Verify Strict dark mode**

Toggle to Strict, enable dark mode:
- Landing: all 6 sections render (nav, hero, preview, how-it-works, pricing, footer)
- Chat: Full Glass Scholar layout, source margin, gold citations
- Scrollbar is thin gold
- No white flash on overscroll
- Mesh blobs animate
- All hover states work (nav, buttons, cards, jurisdiction pills)

- [ ] **Step 4: Verify Strict light mode (Ink on Fog)**

Toggle to Strict, switch to light mode:
- Background is cool gray gradient (not white, not warm)
- Glass panels use dark-tinted glass (inverted glassmorphism)
- Specular highlight on top edge of glass panels
- Gold accents are darker/muted (adapted for light bg)
- Text is readable

- [ ] **Step 5: Verify Czech locale**

Switch to Czech locale (`cs`):
- How It Works demo question is in Czech
- Czech caselaw section renders with Strict styling
- All other sections work normally

---

## Execution Notes

- **Total tasks:** 16
- **Estimated complexity:** Tasks 7, 8, 9, 13, 14 are the heaviest (hero, preview, HIW, chat layout, wiring)
- **Dependencies:** Tasks 1-4 must come first (foundation). Tasks 5-11 can be parallelized. Task 12 needs 5-11. Tasks 13-14 can start after 1-4. Task 15-16 are final.
- **Reference constantly:** `docs/superpowers/specs/2026-04-09-strict-design-spec.md` and the mockup HTML file
- **No creative license:** Every color, timing, and layout decision was made in collaboration with the user. Implement exactly as specified.
