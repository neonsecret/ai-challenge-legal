# Mobile Audit — 2026-04-21

Playwright screenshot sweep across every public and authenticated route at three mobile viewports.
Screenshots: `docs/mobile-audit-screenshots/` · Raw findings JSON: `docs/mobile-audit-screenshots/findings.json`

## Viewports Covered

| Viewport | Width × Height |
|---|---|
| iPhone SE | 375 × 812 |
| iPhone 14 Pro | 390 × 844 |
| Android mid-range | 360 × 800 |

## Routes Audited

| Route | Auth required | Status |
|---|---|---|
| `/` | No | ✓ |
| `/blog` | No | ✓ |
| `/blog/czech-legal-ai-sota` | No | ✓ |
| `/login` | No | ✓ |
| `/forgot-password` | No | ✓ |
| `/pricing` | No | ✓ (404) |
| `/about` | No | ✓ |
| `/faq` | No | ✓ |
| `/privacy` | No | ✓ |
| `/terms` | No | ✓ |
| `/benchmarks` | No | ✓ |
| `/chat` | Yes | ✓ |
| `/settings` | Yes | ✓ |
| `/billing` | Yes | ✓ |
| `/documents` | Yes | ✓ |

---

## Summary

- Pages audited: 15 routes × 3 viewports = 45 screenshots
- **Critical (P0): 8 distinct findings**
- **High (P1): 23 distinct findings**
- **Medium (P2): 4 findings**

---

## Findings

### `/pricing` — all viewports

- **Severity**: P2
- **Issue**: Route returns HTTP 404. The public nav links to `#pricing` (anchor on the landing page), so the nav works correctly. However, direct navigation to `/pricing` (bookmarks, external links, SEO) returns a 404 with no redirect. This is a soft failure — not a broken nav, but a missing fallback route.
- **File**: No `frontend/src/app/pricing/` directory exists. Consider adding a redirect or stub page.
- **Screenshot**: `pricing--iphone-se.png`

---

### `/login` — all viewports

- **Severity**: P0
- **Issue**: Email input (`type="email"`) and password input are styled with `fontSize: "14px"`. iOS Safari auto-zooms the viewport when any input has font-size < 16px. Every mobile user who taps the login form gets an unwanted viewport zoom.
- **File**: `frontend/src/app/(auth)/login/page.tsx:112` — `fontSize: "14px"` in inline style object
- **Screenshot**: `login--iphone-se.png`

---

### `/forgot-password` — all viewports

- **Severity**: P0
- **Issue**: Email input styled at `fontSize: "15px"` — 1px below the iOS auto-zoom threshold.
- **File**: `frontend/src/app/forgot-password/page.tsx:51,66`
- **Screenshot**: `forgot-password--iphone-se.png`

---

### `/settings` — all viewports

- **Severity**: P0
- **Issue**: Language `<select>` element has `fontSize: "11px"` — far below the 16px iOS threshold. Any tap on the language selector zooms the viewport.
- **File**: `frontend/src/app/(app)/settings/page.tsx:253` — `darkSelect` style constant
- **Screenshot**: `settings--iphone-se--auth.png`

---

### `/chat` (authenticated) — all viewports

- **Severity**: P0
- **Issue**: Navigating to `/chat` while authenticated redirects to `/` (the marketing landing page). The chat interface is the core product feature — users who bookmark `/chat` or share a direct link land on the marketing site instead.
- **File**: Routing logic in `frontend/src/app/(app)/chat/page.tsx` or `(app)/layout.tsx`
- **Screenshot**: `chat-empty--iphone-se--auth.png` (shows landing page, not chat)

---

### `/billing` (authenticated) — all viewports

- **Severity**: P0
- **Issue**: Navigating to `/billing` while authenticated redirects to `/login`. The billing page is inaccessible to logged-in users. No explanation is shown — users just see the login form.
- **File**: `frontend/src/app/(app)/billing/page.tsx` — auth guard may be checking a plan/role that the test account lacks, but no graceful fallback is shown.
- **Screenshot**: `billing--iphone-se--auth.png` (shows login page)

---

### `/documents` — all viewports

- **Severity**: P0 (visible error)
- **Issue**: Page renders a red banner: `Failed to fetch: 401`. This raw error message is shown to users. On mobile it appears above all content.
- **File**: `frontend/src/app/(app)/documents/page.tsx` — error state rendering
- **Screenshot**: `documents--iphone-se--auth.png`

---

### Theme toggle button — all public pages

- **Severity**: P1
- **Issue**: `ThemeToggle` button is 28×28px — below the 44×44px minimum touch target size. Present on every page that uses the public nav header.
- **File**: `frontend/src/components/theme-toggle.tsx:35-36` — `width: 28, height: 28`
- **Fix**: Increase to `width: 44, height: 44` or add padding (the icon stays `size={14}`, the hit area grows).
- **Screenshot**: `landing--iphone-se.png` (top-right icon)

---

### Sign In / Sign Up tab buttons on login — all viewports

- **Severity**: P1
- **Issue**: The "Sign In" and "Sign Up" toggle tabs are `135×36px`. Height is 36px — 8px short of the 44px minimum. These are the first interactive elements every mobile user touches.
- **File**: `frontend/src/app/(auth)/login/page.tsx` — tab button styles
- **Screenshot**: `login--iphone-se.png`

---

### "Forgot password?" link — `/login`, `/billing` redirect

- **Severity**: P1
- **Issue**: Link is 103×15px. Text-only link with no padding — essentially untappable on mobile without precise targeting.
- **File**: `frontend/src/app/(auth)/login/page.tsx`
- **Screenshot**: `login--iphone-se.png`

---

### "Back to login" link — `/forgot-password`

- **Severity**: P1
- **Issue**: Link is 85×17px — only 17px tall. Bare text link below the submit button with no padding.
- **File**: `frontend/src/app/forgot-password/page.tsx`
- **Screenshot**: `forgot-password--iphone-se.png`

---

### VITREON logo link — all public pages

- **Severity**: P1
- **Issue**: Logo `<a>` element is 71×20px — only 20px tall. The touch area does not extend beyond the text. Tap is unreliable on most devices.
- **File**: `frontend/src/components/landing/strict/strict-nav.tsx`
- **Screenshot**: `landing--iphone-se.png` (top-left)

---

### Settings theme buttons (Light / Dark / System) — `/settings`

- **Severity**: P1
- **Issue**: Theme selection buttons are ~44×20px — 20px tall, less than half the minimum. These are key settings interactions.
- **File**: `frontend/src/app/(app)/settings/page.tsx` — theme button styles
- **Screenshot**: `settings--iphone-se--auth.png`

---

### Language button in app shell — `/documents`, `/settings`

- **Severity**: P1
- **Issue**: `<BUTTON>` language selector in the authenticated app shell is 39×25px — both dimensions below 44px minimum.
- **File**: `frontend/src/app/(app)/documents/page.tsx` and `(app)/settings/page.tsx`
- **Screenshot**: `documents--iphone-se--auth.png`

---

### Corpus selector rows — `/documents`

- **Severity**: P1
- **Issue**: Corpus library rows (e.g., "🇨🇿 Czech Legal Corpus") are interactive `<div>` elements at 247×34px — 10px short of the 44px height minimum.
- **File**: `frontend/src/app/(app)/documents/page.tsx`
- **Screenshot**: `documents--iphone-se--auth.png`

---

### "View Plans" link — `/documents`

- **Severity**: P1
- **Issue**: Upgrade CTA "View Plans" is 82×27px. Key conversion path for paid features is hard to tap on mobile.
- **File**: `frontend/src/app/(app)/documents/page.tsx`
- **Screenshot**: `documents--iphone-se--auth.png`

---

### CTA buttons (Get Started, Try Demo, Request Demo) — public pages

- **Severity**: P1
- **Issue**: Multiple primary CTA buttons across `/about`, `/faq`, `/benchmarks` measure at 40–43px tall — just 1–4px short of the minimum. The 43px "SOURCES ▾" button on the landing page demo preview is also affected.
- **File**: Various — `frontend/src/app/(auth)/landing-client.tsx`, `frontend/src/app/about/page.tsx`, `frontend/src/app/faq/page.tsx`
- **Screenshot**: `about--iphone-se.png`, `faq--iphone-se.png`

---

### Footer touch targets — all public pages

- **Severity**: P1
- **Issue**: All footer link items (About, Blog, FAQ, Benchmarks, Privacy, Terms) are 15–28px tall — far below 44px. The `StrictFooter` uses `text-[10px]` with no vertical padding on links. Affects every public page.
- **File**: `frontend/src/components/landing/strict/strict-footer.tsx` — link elements need `min-h-[44px] inline-flex items-center`
- **Screenshot**: `landing--iphone-se.png` (scroll to footer)

---

### Inline text links in legal pages — `/privacy`, `/terms`

- **Severity**: P1
- **Issue**: Inline links (email addresses, third-party links, "Back to home") are 15–20px tall with no padding. Examples: `privacy@vitreon.app` (137×17px), `← Back to home` (109×20px), `Stripe` (39×17px).
- **File**: `frontend/src/app/privacy/page.tsx`, `frontend/src/app/terms/page.tsx`
- **Screenshot**: `privacy--iphone-se.png`, `terms--iphone-se.png`

---

### Tiny nav link text in desktop dropdown — all public pages

- **Severity**: P1
- **Issue**: Navigation dropdown links (Benchmarks, Blog, Features, Pricing, EN locale label) render at 11px — at or below the legibility threshold. These appear in a hidden desktop dropdown that is collapsed behind the hamburger on mobile but the text nodes are still present in the DOM.
- **File**: `frontend/src/components/landing/strict/strict-nav.tsx`
- **Screenshot**: Detectable in DOM; links hidden behind hamburger menu.

---

### Scroll-triggered content appears blank before scroll — `/`, `/about`, `/faq`, `/benchmarks`

- **Severity**: P2
- **Issue**: Full-page screenshots show large blank dark areas below the hero section on multiple public pages. Content exists in the DOM but is hidden via Framer Motion enter animations that only trigger on scroll/intersection. On mobile where users may see a long dark empty stretch before scrolling, this looks like a broken or incomplete page. Users on slow connections who don't scroll may miss entire sections.
- **File**: `frontend/src/app/(auth)/landing-client.tsx` (52.9KB — scroll animations), `frontend/src/app/about/page.tsx`, `frontend/src/app/faq/page.tsx`
- **Screenshot**: `landing--iphone-se.png` (blank area below preview), `about--iphone-se.png`

---

### Forgot-password uses inconsistent light theme — `/forgot-password`

- **Severity**: P2
- **Issue**: The forgot-password page uses a warm amber/beige light theme, visually completely different from every other page (dark glassmorphism). Users navigating from `/login` experience a jarring visual context switch. The design language is inconsistent.
- **File**: `frontend/src/app/forgot-password/page.tsx`
- **Screenshot**: `forgot-password--iphone-se.png`

---

### Settings shows "Sign In" CTA for authenticated users — `/settings`

- **Severity**: P2
- **Issue**: The Account section of `/settings` shows a "Sign In" button even when the user is authenticated. This is confusing — users who are already logged in see a sign-in prompt where they expect to see their account info or a logout button.
- **File**: `frontend/src/app/(app)/settings/page.tsx` — `renderDarkAccount()` function
- **Screenshot**: `settings--iphone-se--auth.png`

---

## Horizontal Scroll Check

No horizontal overflow detected on any route at any viewport. All pages fit within 360–390px width without scrollbar.

## Keyboard Layout Check (Manual — not automated)

Not automated in this sweep. The `/login` page should be manually verified: with the virtual keyboard open on iOS, confirm the "Sign In" button remains visible without scrolling. Given the current login form height, this is likely fine, but input font-size fixes (P0 above) must be applied before testing.

## Reduced Motion Check

Framer Motion `useReducedMotion` is present in the codebase (referenced in landing-client.tsx). Audit of whether all animations actually respect `prefers-reduced-motion` is deferred to a dedicated accessibility review.

---

## Stream C Readiness

Stream C (rolling implementation) can begin. Priority order for fixes:

1. **P0-A**: Input font sizes — `login/page.tsx:112`, `forgot-password/page.tsx:51,66`, `settings/page.tsx:253` → set all to `"16px"`
2. **P0-B**: `/chat` routing (redirects to landing page) — investigate auth guard in `(app)/layout.tsx`
3. **P0-C**: `/billing` routing (redirects to login for authenticated users) — investigate plan-check guard
4. **P0-D**: `/documents` 401 error banner — hide raw HTTP errors from users, show friendly fallback
5. **P1-A**: ThemeToggle 28×28px → 44×44px — `theme-toggle.tsx:35-36` (one line)
6. **P1-B**: StrictFooter link heights — `strict-footer.tsx` — add `min-h-[44px] inline-flex items-center`
7. **P1-C**: VITREON logo link height — `strict-nav.tsx` — add `minHeight: "44px"` with flex centering
8. **P1-D**: Login form button heights (Sign In/Sign Up tabs 36px → 44px, Forgot password link)
9. **P1-E**: Settings theme buttons and language SELECT — `settings/page.tsx`
10. **P1-F**: Language toggle button — `frontend/src/components/language-toggle.tsx` — trigger button needs `minHeight: 44`
11. **P2**: `/pricing` missing route — add `next/navigation` redirect to `/#pricing` or create stub page
