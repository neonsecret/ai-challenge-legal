# Mobile Audit — Vitreon Legal
**Date:** 2026-04-21  
**Tool:** Playwright screenshot sweep (`frontend/mobile-audit.mjs`)  
**Viewports:** iPhone SE 375×812, iPhone 14 Pro 390×844, Android Mid 360×800  
**Pages audited:** 15 routes (11 public + 4 authenticated)  
**Total findings:** 507 (21 P0, 486 P1)

---

## Summary

| Severity | Count | Root Causes |
|----------|-------|-------------|
| P0 | 21 | iOS auto-zoom on form inputs (5 unique issues × 3 viewports) + false-positive 404 |
| P1 | 486 | Touch targets < 44×44px (333), text < 12px (153) |

---

## P0 Findings — Must Fix

### P0-1: iOS Auto-Zoom — Login form inputs (14px < 16px)
- **Routes affected:** `/login`, and `/billing` (login redirect when unauthenticated)
- **Elements:** `<INPUT type="email">`, `<INPUT type="password">`
- **Current size:** 14px — iOS Safari auto-zooms the page on focus when `font-size < 16px`
- **Fix:** `inputStyle.fontSize` in `frontend/src/app/(auth)/login/page.tsx` line ~112 → `"16px"`

### P0-2: iOS Auto-Zoom — Forgot-password email input (15px < 16px)
- **Route affected:** `/forgot-password`
- **Element:** `<INPUT type="email">`
- **Current size:** 15px
- **Fix:** locate inputStyle in `frontend/src/app/(auth)/forgot-password/page.tsx` → `"16px"`

### P0-3: iOS Auto-Zoom — Settings language select (11px < 16px)
- **Route affected:** `/settings`
- **Element:** `<SELECT type="select-one">`
- **Current size:** 11px (`darkSelect.fontSize` in `frontend/src/app/(app)/settings/page.tsx` line ~253)
- **Fix:** `darkSelect.fontSize` → `"16px"` (native selects must be ≥ 16px; visual appearance can be adjusted via `transform: scale()` if needed, but 16px is readable)

### P0-4 (False Positive): /pricing — HTTP 404
- **Status:** NOT a real bug. The nav uses `href="#pricing"` (anchor on landing page). There is no standalone `/pricing` route. The audit script included `/pricing` as a separate route which does not exist.
- **Action:** None required. The audit script should be updated to remove `/pricing` from `PUBLIC_ROUTES`.

---

## P1 Findings — High Priority

### Root Cause Analysis

All 486 P1 issues reduce to **7 root causes**. Fixing each root cause resolves all instances on all pages.

---

### P1-A: StrictFooter — all links too small (affects ALL pages)

**Component:** `frontend/src/components/landing/strict/strict-footer.tsx`

Footer uses `text-[10px]` with `gap-y-1` — links render at ≤15px height, far below 44px touch target.

Affected elements and sizes:
| Element | Size | Routes |
|---------|------|--------|
| "About" | 28×15px | all public pages |
| "Blog" | 21×15px | all public pages |
| "FAQ" | 19×15px | all public pages |
| "Benchmarks" | 59×15px | all public pages |
| "Privacy" / "Terms" | 35×29px | all public pages |

**Fix:** Add `min-h-[44px] inline-flex items-center` to each `<Link>` in the footer. The text size can remain 10px (design choice) as long as the tap area is 44px.

---

### P1-B: StrictNav — VITREON logo link too small

**Component:** `frontend/src/components/landing/strict/strict-nav.tsx`

`<Link href="/">` "VITREON" renders at 71×20px — no min-height.

**Fix:** Add `min-h-[44px]` (via `style={{ minHeight: "44px", display: "inline-flex", alignItems: "center" }}`) to the VITREON logo link. The desktop nav links (`hidden sm:block`) are already hidden at mobile viewports — no fix needed there. The hamburger button already has 44×44px.

---

### P1-C: ThemeToggle button too small (28×28px)

**Component:** `frontend/src/components/theme-toggle.tsx`

The theme toggle button has `width: 28, height: 28` — 28px is below 44px.

**Fix:** Change to `width: 44, height: 44` (or wrap in a 44px container). The icon can remain 28px visually inside the larger hit area.

---

### P1-D: CTA buttons insufficient height on marketing pages

Affected CTAs:
| Element | Size | Pages |
|---------|------|-------|
| "Get Started Free" | 172×40px | /about, /faq, /terms (5 routes) |
| "Get Started" | 194×43px | /blog, /blog/slug |
| "Sign In" button | 135×36px | /login, /billing (2 routes) |
| "Sign Up" button | 135×36px | /login, /billing (2 routes) |
| "Try the Demo" | 293×42px | /about, /faq |
| "Try Vitreon Free" | 171×40px | / |
| "Subscribe" | 194×43px | /pricing section |

All fail the 44px height requirement by 1–8px.

**Fix:** Ensure all CTA buttons have `min-h-[44px]` or equivalent `minHeight: "44px"` in their style definitions.

---

### P1-E: Settings theme buttons too short (Light / Dark / System)

**Component:** `frontend/src/app/(app)/settings/page.tsx`

Theme toggle buttons (`themeButtonLight` / `themeButtonDark` styles) use `padding: "8px 16px"` which results in ~20px height.

**Fix:** Add `minHeight: "44px"` to `themeButtonLight` and `themeButtonDark` style objects (line ~134 and dark equivalent).

---

### P1-F: Language toggle button too small (EN, 39×25px)

**Component:** `frontend/src/components/language-toggle.tsx`

The trigger button is 39×25px.

**Fix:** Add `minHeight: "44px"` to the trigger button style and ensure `width` ≥ 44px or the button is wrapped in a 44px touch target.

---

### P1-G: Misc small touch targets (various components)

| Element | Size | Location |
|---------|------|----------|
| `<A> "Forgot password?"` | 103×15px | `/login`, `/billing` |
| `<A> "Back to login"` | 85×17px | `/forgot-password` |
| `<A> "Sign in"` nav link | 35×44px (too narrow) | `/login` |
| `<A> "Go home"` (404 page) | 66×24px | `/` redirect |
| `<BUTTON> "Sign up"` (small) | 48×20px | multiple |
| `<A> "← Back to home"` | 109×20px | multiple |

**Fix:** Add `min-h-[44px]` and sufficient inline-padding (`px-3` minimum) to these links/buttons.

---

## P1 Text Size Issues

All text-size P1s are 11px or below. Root causes:

| Element | Size | Location |
|---------|------|----------|
| Nav links (Features, Pricing, Benchmarks, Blog) | 11px | `StrictNav` desktop links (hidden on mobile — visible on ≥640px only) |
| Footer span "Legal" | 11px | `StrictFooter` `text-[10px]` |
| Login "Legal research, reimagined" tagline | 11px | Login page |
| Login "or" divider | 11px | Login page |
| EN language indicator | 11px | `LanguageToggle` |

Most text-size P1s on mobile are from the footer (`text-[10px]`). The nav desktop links are `hidden sm:block` so they're not actionable on mobile — acceptable.

**Fix:** Footer text can remain 10px for design, but the surrounding tap areas still need 44px height (P1-A covers this). For login page text ("or", tagline), consider bumping to `12px` minimum.

---

## Scope of Implementation

### Subtask 1 — P0: iOS auto-zoom fix
Files to touch:
- `frontend/src/app/(auth)/login/page.tsx` — `inputStyle.fontSize` line ~112
- `frontend/src/app/(auth)/forgot-password/page.tsx` — email input fontSize
- `frontend/src/app/(app)/settings/page.tsx` — `darkSelect.fontSize` line ~253

### Subtask 2 — P1: Footer and nav touch targets (highest impact — fixes 300+ findings)
Files to touch:
- `frontend/src/components/landing/strict/strict-footer.tsx` — footer links
- `frontend/src/components/landing/strict/strict-nav.tsx` — VITREON logo
- `frontend/src/components/theme-toggle.tsx` — button size
- `frontend/src/components/language-toggle.tsx` — trigger button size

### Subtask 3 — P1: CTA buttons and settings buttons
Files to touch:
- Landing page CTA button components (Get Started Free, Try Vitreon Free, Try the Demo)
- `frontend/src/app/(auth)/login/page.tsx` — Sign In / Sign Up button heights
- `frontend/src/app/(app)/settings/page.tsx` — `themeButtonLight` / `themeButtonDark` padding

---

## Screenshots

All per-page screenshots saved to `docs/mobile-audit-screenshots/`:
- `{page}--iphone-se.png`
- `{page}--iphone-14-pro.png`
- `{page}--android-mid.png`

Raw findings: `docs/mobile-audit-screenshots/findings.json` (507 entries)
