# Vitreon "Strict" Design — V2 Design Spec

**Date:** 2026-04-09
**Status:** Approved
**Replaces:** V3 "Luminous" glassmorphism design
**Reference mockup:** `.superpowers/brainstorm/16696-1775754111/content/full-design-polished.html`

---

## 1. Overview

"Strict" is a new alternate design for Vitreon Legal, replacing the V3 "Luminous" (iris/aurora glassmorphism) design. The existing default design is renamed from "V2" to **"Neon"**. The toggle switches between **Neon** (default) and **Strict**.

**Design philosophy:** Dark glassmorphism with gold accents, inspired by [chatgpt-dark-glassmorphism](https://github.com/gastonmorixe/chatgpt-dark-glassmorphism). Readable, lawyer-friendly, minimal — the UI disappears and only the research remains.

**Core identity:** "Full Glass Scholar" — flowing serif prose with margin annotations, the entire reading surface lives inside one glass pane.

---

## 2. Toggle & Naming

| Internal ID | Display Name | Role |
|---|---|---|
| `neon` | Neon | Default design (current V2, unchanged) |
| `strict` | Strict | New glassmorphism design (replaces V3) |

- Toggle in `design-version.tsx` switches between `neon` and `strict`
- localStorage key stays `vitreon-design-version`
- CSS class on `<html>`: `.design-neon` or `.design-strict`
- All V3/luminous CSS, variables, and references are removed and replaced

---

## 3. Color System

### 3.1 Dark Mode (Primary Experience)

| Token | Value | Usage |
|---|---|---|
| `--strict-bg` | `linear-gradient(170deg, #0E1118, #0B0E16, #0D0A12)` | Page background |
| `--strict-bg-html` | `#0D0A12` | `<html>` bg (prevents white flash on overscroll) |
| `--strict-glass-bg` | `rgba(255,255,255, 0.02)` | Glass surface fill |
| `--strict-glass-border` | `rgba(201,168,76, 0.06)` | Glass panel border |
| `--strict-glass-blur` | `blur(24px)` | Primary backdrop-filter |
| `--strict-glass-shadow` | `0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025)` | Glass depth |
| `--strict-glass-recessed` | `rgba(0,0,0, 0.1)` | Recessed inner sections (sidebar, source margin) |
| `--strict-text-primary` | `rgba(230,235,245, 0.88)` | Headlines |
| `--strict-text-body` | `rgba(255,255,255, 0.56)` | Body/prose text |
| `--strict-text-question` | `rgba(255,255,255, 0.7)` | User questions (brighter than body) |
| `--strict-text-secondary` | `rgba(200,210,230, 0.42)` | Subtitles, descriptions |
| `--strict-text-dim` | `rgba(200,210,230, 0.22)` | Fine print, details |
| `--strict-text-ghost` | `rgba(255,255,255, 0.16)` | Placeholders |
| `--strict-gold-base` | `#C9A84C` | Brand gold |
| `--strict-gold-gradient` | `linear-gradient(135deg, #C9A84C, #E0C878)` | Gold gradient (hero accent, 100% stat) |
| `--strict-gold-text` | `rgba(201,168,76, 0.7)` | Gold text elements |
| `--strict-gold-border` | `rgba(201,168,76, 0.06)` | Subtle gold borders |
| `--strict-gold-border-active` | `rgba(201,168,76, 0.15)` | Active/featured borders |
| `--strict-gold-badge-bg` | `rgba(201,168,76, 0.06)` | Badge backgrounds |
| `--strict-gold-badge-border` | `rgba(201,168,76, 0.1)` | Badge borders |
| `--strict-gold-sep` | `linear-gradient(90deg, rgba(201,168,76,0.2), rgba(201,168,76,0.04))` | Gold gradient fade separator |
| `--strict-citation` | `rgba(201,168,76, 0.55)` | Citation superscript color |
| `--strict-nav-link` | `rgba(200,210,230, 0.38)` | Nav link text |
| `--strict-nav-link-hover` | `rgba(200,210,230, 0.6)` | Nav link hover |
| `--strict-source-text` | `rgba(255,255,255, 0.3)` | Source margin text |

### 3.2 Light Mode ("Ink on Fog")

| Token | Value | Usage |
|---|---|---|
| `--strict-light-bg` | `linear-gradient(160deg, #E2E4EA, #D8DAE2)` | Page background (cool gray gradient) |
| `--strict-light-glass-bg` | `rgba(20,22,30, 0.04)` | Glass surface (dark-tinted, inverted glassmorphism) |
| `--strict-light-glass-border` | `rgba(20,22,30, 0.08)` | Panel borders |
| `--strict-light-glass-highlight` | `inset 0 1px 0 rgba(255,255,255, 0.4)` | Specular highlight (top edge of glass) |
| `--strict-light-text-primary` | `rgba(20,22,30, 0.78)` | Body text |
| `--strict-light-text-secondary` | `rgba(20,22,30, 0.5)` | Subtitles |
| `--strict-light-gold-text` | `rgba(138,110,24, 0.7)` | Gold accent on light |
| `--strict-light-gold-border` | `rgba(180,150,60, 0.14)` | Gold borders on light |

---

## 4. Typography

| Element | Font | Size | Weight | Style |
|---|---|---|---|---|
| Hero title | Georgia, serif | 32px | normal | — |
| Hero accent word | Georgia, serif | 32px | normal | Gold gradient `-webkit-background-clip: text` |
| Section titles | Georgia, serif | 22px | normal | — |
| Body/prose | Georgia, serif | 12.5px | normal | `letter-spacing: 0.01em`, `line-height: 1.8` |
| Questions | Georgia, serif | 12px | normal | italic |
| Nav links | system-ui | 11px | normal | — |
| Labels/badges | system-ui | 8-10px | normal | `letter-spacing: 0.5-1.5px`, uppercase |
| Citations | system-ui | 9px | normal | superscript |
| Stat numbers | Georgia, serif | 24px (28px for 100%) | normal | — |

---

## 5. Component Specifications

### 5.1 Navigation Bar

- Horizontal bar: logo left, links right
- `VITREON` wordmark: gold (`0.7` opacity), 13px, `letter-spacing: 2px`
- Nav links: ghost text, no decoration
- Sign In: gold text with gold underline (`border-bottom: 1px solid`)
- Separator: thin line below nav (`1px solid rgba(201,168,76, 0.06)`)
- Hover: links brighten to `0.6`, Sign In brightens to `0.9` with stronger underline

### 5.2 Buttons

**Primary CTA (Gold Underbar):**
- Glass surface (`rgba(255,255,255, 0.025)`, `backdrop-filter: blur(12px)`)
- Border: `1px solid rgba(255,255,255, 0.04)`, bottom edge `1px solid rgba(201,168,76, 0.3)`
- Text: `rgba(230,235,245, 0.8)`, 12px
- Hover: `translateY(-1px)`, gold underbar brightens to `0.5`, subtle gold shadow
- Border radius: 8px

**Pricing CTA:** Same style as primary CTA. Featured plan: gold underbar at `0.5`, slightly brighter text.

### 5.3 Jurisdiction Pills

- **Default (unselected):** Dot-separated plain text — `DIFC · Czech · UK · Australia`
- Gold text at `0.5` opacity, dots at `0.15`
- **Hover:** Transition to bordered tag style — `background: rgba(201,168,76, 0.06)`, `border: 1px solid rgba(201,168,76, 0.14)`, `border-radius: 5px`
- **Selected/Active:** Bordered gold tag (same as hover but persistent)
- Transition: 0.2s ease on background, border, padding

### 5.4 Glass Panels

**Hero Slab (Living Glass Slab):**
- Full-width glass surface containing hero text + stats
- `border-radius: 18px`, `padding: 32px`
- Entrance: scale from `0.985` + `translateY(20px)`, 0.8s spring
- Contains gold divider line between text and stats sections

**Full Glass Scholar (Chat):**
- One glass pane containing sidebar rail + reading area + source margin
- `border-radius: 16px`
- Internal divisions via `1px solid` lines, NOT separate panels
- Sidebar rail: `44px` wide, recessed dark background
- Source margin: `160px` wide, recessed dark background
- Hover: deeper shadow

### 5.5 Source Margin

- Sources in right margin column within the glass pane
- Each source: gold number + text description
- Separator: gold gradient fade line (`linear-gradient(90deg, gold → transparent)`)
- **Animation:** Glass tile reveal — each source appears with `scale(0.95) → scale(1)` + `opacity: 0 → 1` + `translateX(12px) → 0`, staggered 250ms apart, spring easing

### 5.6 Stat Cards (Hero)

- Stat number: white, 24px Georgia serif
- Label: dim text, 10px, with optional gold badge (`+36% above SOTA`)
- Detail: ghost text, 9px
- Separator: gold gradient fade line
- **100% Citation accuracy (special):**
  - Number: 28px, gold gradient text (`-webkit-background-clip: text`)
  - Count-up animation from 0% to 100% over ~1s
  - Subtle gold radial glow behind (`radial-gradient ellipse, rgba(201,168,76, 0.12)`)
  - Gentle brightness pulse after landing (`filter: brightness` oscillation)
  - Badges pulse subtly (`opacity: 1 → 0.6 → 1`, 3s cycle)

---

## 6. Landing Page Sections

### Section order:
1. **Nav** (fixed top)
2. **Hero** (Living Glass Slab: title + stats)
3. **Preview** ("The research experience" — Full Glass Scholar chat demo)
4. **How It Works** (interactive 3-step with visual panel)
5. **Pricing** (4 glass cards)
6. **Footer**

### 6.1 Hero

- **Left side:** Serif headline "Legal Research, Reimagined" (accent word has gold gradient), subtitle, jurisdiction pills (dot-separated), CTA button
- **Right side:** Benchmark stats — 0.824 GaRAGe RAF (+36% SOTA), 0.860 Legal RAG Bench, 0.691 LEXam Open EN (+21% SOTA), 100% Citation accuracy (gold, animated)
- **Divider:** `1px` gold line between left and right
- **Background:** Slowly drifting mesh blobs (gold + cool blue, `filter: blur(80px)`, 8s animation cycle)

### 6.2 Preview — "The research experience"

- Full Glass Scholar component rendered as a demo
- **Animation when scrolled into view:**
  1. Glass pane fades up
  2. Question fades in + slides up (0.3s delay)
  3. Answer types out character by character (~8ms per char) with blinking gold cursor
  4. Citation superscripts appear inline with text (rendered via React, NOT innerHTML)
  5. Sources reveal as glass tiles — scale + opacity + slide from right, staggered 250ms
- Chat input at bottom with placeholder text

### 6.3 How It Works — "See it in action"

**Layout:** Left column (step list, 280px) + right panel (glass visual, flex)

**Steps (left column):**
- Vertical list of 3 clickable steps
- Active step: subtle glass background, gold progress bar (2px vertical, fills over 5s)
- Active step text brighter
- Clicking a step pauses auto-advance for 8s, then resumes

**Step content:**
1. **"Ask in plain language"** — Visual: typing animation with real question ("What are the indemnification obligations under Section 9?"), blinking cursor, ~35ms per char
2. **"AI searches statutes & case law"** — Visual: 3 scanning items appear sequentially with pulsing gold dots, animated progress lines, checkmarks. "Scanning 4,800+ documents", "Located Article 58 §2", "Ranked 5 passages"
3. **"Every answer cites sources"** — Visual: result card with header "Article 58 §2 · DIFC Law No. 4 of 2005 · Page 34", body text, and a highlighted legal quote that slides in with delay

**Czech locale variant:** When locale is `cs`, the demo question changes to a Czech-specific legal question (matching current `czech-caselaw-section.tsx` content).

### 6.4 Pricing

- 4 glass cards in a row: Free ($0, 3/day), Starter ($29/mo, 30/day), Pro ($179/mo, 200/day), Enterprise ($499/mo, unlimited)
- Featured card (Starter): gold border, subtle gold shadow
- All CTAs: "Get Started" (Free), "Subscribe" (paid plans)
- Staggered entrance animation (80ms between cards)
- Hover: cards lift 3px

### 6.5 Footer

- Minimal: `© 2026 Vitreon Legal · Privacy · Terms`
- Top border: thin gold line

---

## 7. Chat Page (Full Glass Scholar)

The actual chat page mirrors the "research experience" preview exactly.

### Layout:
```
┌──────────────────────────────────────────────────┐
│ ┌────┬───────────────────────────┬─────────────┐ │
│ │Rail│      Reading Area         │Source Margin │ │
│ │ V  │                           │  SOURCES    │ │
│ │ ◻  │  Question (italic, bright)│  1          │ │
│ │ ◻  │  ─────────────────────── │  Law ref    │ │
│ │ ◻  │  Answer prose (serif,     │  ──────     │ │
│ │    │  body opacity, footnotes) │  2          │ │
│ │    │                           │  Case ref   │ │
│ │    │                           │  ──────     │ │
│ │    │  Continue your research…↵│  3          │ │
│ └────┴───────────────────────────┴─────────────┘ │
└──────────────────────────────────────────────────┘
```

### Sidebar Rail (44px):
- Logo: gold-bordered circle with "V"
- Icon buttons: glass squares (chat, documents, settings)
- Vertical gold glow line hint

### Reading Area:
- Questions: `rgba(255,255,255, 0.7)`, italic, Georgia serif, gold bottom border separator
- Answers: `rgba(255,255,255, 0.56)`, Georgia serif, `line-height: 1.8`
- Citations: gold superscript numbers linking to source margin
- Input: thin underline style, placeholder "Continue your research...", ↵ hint

### Source Margin (160px):
- Recessed background (`rgba(0,0,0, 0.1)`)
- Gold "SOURCES" label
- Each source: gold number + text + gold gradient fade separator
- Click source → opens full document view (existing grounding drawer behavior)

---

## 8. Animation System

All animations use `motion/react` with existing spring presets from `v3-motion.ts`.

### Page-Level:
- **Mesh blobs:** 3 fixed blobs, `filter: blur(80px)`, 8s drift cycle, different delays
- **Scroll fade-up:** Elements start at `opacity: 0, translateY(24px)`, spring in when 15% visible
- **Stagger:** Children animate with 80ms delay between each

### Component-Level:
- **Hero slab:** Scale from `0.985` + `translateY(20px)`, children cascade with staggered delays
- **Hero stats:** Each stat row staggers in (150ms apart), 100% counter counts up
- **Chat typewriter:** ~8ms per character, React-rendered (not innerHTML), blinking cursor
- **Source tiles:** `scale(0.95) + translateX(12px) + opacity(0)` → identity, spring easing, 250ms stagger
- **HIW step progress:** 2px vertical gold bar fills over 5s (CSS `@keyframes`)
- **HIW visuals:** Typing at ~35ms/char, scanning items stagger 800ms with progress lines
- **Cards:** Hover lifts 3px with spring easing, border brightens
- **Buttons:** Hover lifts 1px, gold underbar brightens, subtle gold shadow
- **Badge pulse:** `opacity: 1 → 0.6 → 1`, 3s cycle
- **Gold glow pulse:** `filter: brightness(1 → 1.2 → 1)`, 2.5s cycle

### Reduced Motion:
- `<MotionConfig reducedMotion="user">` wraps everything (existing behavior)
- All animations respect `prefers-reduced-motion`

---

## 9. Scrollbar & Overscroll

- Custom webkit scrollbar: 6px wide, gold thumb (`rgba(201,168,76, 0.15)`), transparent track
- Hover: thumb brightens to `0.25`
- Firefox: `scrollbar-width: thin; scrollbar-color: rgba(201,168,76,0.15) transparent`
- `html { overscroll-behavior: none; background: #0D0A12 }` — no white flash on bounce

---

## 10. Implementation Notes

### What changes:
- Rename internal `v2` → `neon`, `v3` → `strict` in `design-version.tsx`
- Replace all `.design-v3` CSS with `.design-strict`
- Replace all `.design-v2` CSS with `.design-neon`
- New `strict` design tokens in `globals.css` (section 3 of this spec)
- New/modified landing components for Strict variant
- New chat layout variant for Strict (Full Glass Scholar)
- Update toggle labels in `design-version-toggle.tsx`

### What stays the same:
- All backend functionality, API contracts, streaming
- Citation system, grounding drawer, PDF viewer
- Auth flows, billing integration
- Neon design (current default, completely unchanged)
- Document management, jurisdiction selector
- Agent trace, confidence badge, streaming status

### Czech locale:
- Czech-specific landing section continues to render when locale is `cs`
- How It Works demo question changes to Czech-specific content
- Existing `czech-caselaw-section.tsx` adapted to Strict styling

### No hardcoding:
- All colors via CSS variables
- All animation timings via motion config / tokens
- All text via i18n-ready constants (no inline strings in components)
- Glass effects via Tailwind `@utility` directives (existing pattern)
