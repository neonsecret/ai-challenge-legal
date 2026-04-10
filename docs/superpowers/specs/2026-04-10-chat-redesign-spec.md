# Chat UI Redesign — Design Specification

## Overview

Overhaul the Vitreon Legal chat page to match the Strict landing page aesthetic. Merge the theme system: **Neon = light mode**, **Strict = dark mode** — a single dark/light toggle replaces the old Neon/Strict design picker. All existing functionality is preserved; this is a visual and layout redesign only.

**Guiding principle:** The chat IS the product. Every element — header, messages, sources, input, feedback — must feel like it belongs to the same design system as the landing page.

---

## 1. Theme System Overhaul

### Before
- Two independent axes: design version (Neon/Strict) × color mode (light/dark)
- `DesignVersionContext` with `"neon" | "strict"` toggle
- localStorage key: `vitreon-design-version`

### After
- Single axis: color mode (light/dark)
- Light mode = current Neon design (unchanged)
- Dark mode = Strict design (gold, glassmorphism, Georgia serif)
- Remove `DesignVersionContext`, `DesignVersionToggle` component
- Use system `prefers-color-scheme` with manual override
- localStorage key: `vitreon-color-mode` (`"light" | "dark" | "system"`)
- FOUC prevention: inline script applies `.light` or `.dark` class on `<html>` before paint
- CSS: `.dark` class replaces `.design-strict`, `.light` or default replaces `.design-neon`
- Language toggle and theme toggle remain in the header (simplified to sun/moon icon)

### Migration
- On first load, if `vitreon-design-version === "strict"` → set `vitreon-color-mode = "dark"`
- If `vitreon-design-version === "neon"` → set `vitreon-color-mode = "light"`
- Clean up old localStorage key

---

## 2. Dark Mode Layout (Strict — the focus of this redesign)

### 2.1 Page Structure

```
[12px padding around everything]
[History Pane (separate glass, 220px)] [8px gap] [Main Glass Pane (flex:1)]
                                                  [Rail 44px] [Reading Area flex:1] [Source Panel 42% (conditional)]
```

- **Page background**: `linear-gradient(170deg, #0E1118, #0B0E16, #0D0A12)`
- **Mesh blobs**: 3 fixed blobs, `blur(80px)`, 8s drift animation, `pointer-events: none`

### 2.2 Main Glass Pane
- `background: rgba(255,255,255, 0.02)`
- `backdrop-filter: blur(24px)`
- `border: 1px solid rgba(201,168,76, 0.06)`
- `box-shadow: 0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025)`
- `border-radius: 14px`
- Contains: sidebar rail + reading area + (conditional) source panel

### 2.3 Sidebar Rail (44px, desktop only)
- `background: var(--strict-glass-recessed)` — `rgba(0,0,0, 0.1)`
- `border-right: 1px solid var(--strict-gold-border)`
- Aligned center, vertical flex column

**Functional buttons (top to bottom):**
| Button | Icon | Action |
|--------|------|--------|
| Logo | Gold "V" in 24px circle | Home / brand |
| History | Hamburger (3 lines) | Toggle history pane |
| New chat | Square with + | Create new session |
| *divider* | 18px gold line | — |
| Doc index | List in rectangle | Toggle document index |
| *spacer* | flex: 1 | — |
| Settings | Gear | Theme toggle, language |

- Button style: 28×28px, `border-radius: 6px`, transparent bg, `color: var(--text-dim)`
- Hover: `background: rgba(201,168,76, 0.05)`, `border: 1px solid var(--gold-border)`, `color: var(--text-secondary)`
- Active: `background: rgba(201,168,76, 0.07)`, `border-color: rgba(201,168,76, 0.14)`, `color: var(--gold-text)`

### 2.4 Header (inside reading area, top)
- Height: 44px, `border-bottom: 1px solid var(--gold-border)`
- `background: linear-gradient(180deg, rgba(255,255,255,0.015) 0%, transparent 100%)`

**Layout:**
```
[Logo 26px circle] [Brand "Vitreon" 11px] | [Jurisdiction pills centered] [Internet toggle] |
```

- **Logo**: 26px circle, `border: 1px solid rgba(201,168,76, 0.2)`, gold "V" 9px
- **Brand**: `font: 11px/1 Georgia, serif`, `color: var(--text-secondary)`
- **Jurisdiction pills**: `padding: 5px 8px`, `border-radius: 4px`, `font: 9px/9px system-ui`, dot separators (3px circles)
  - Default: transparent bg, `color: var(--text-dim)`
  - Active: `background: rgba(201,168,76, 0.06)`, `border: 1px solid rgba(201,168,76, 0.15)`, `color: var(--gold-text)`
- **Internet toggle**: Same pill style, gold bg when active, dot indicator
- **No header action buttons** — those moved to sidebar rail

### 2.5 Law Selector Row (UK/AU only, conditional)
- Appears below header when law pane is open
- Scrollable horizontal row of law pills
- Same pill styling as jurisdiction pills
- "All" / "N/M" counter label
- Long-press (500ms) behavior preserved

### 2.6 Custom Corpus Row (conditional)
- Appears when Custom jurisdiction is selected
- Collection pills with doc counts
- "Upload documents" link if empty

---

## 3. Message Rendering

### 3.1 Pipeline Status Bar
- **Horizontal compact bar** (not vertical trace)
- `background: rgba(201,168,76, 0.025)`, `border: 1px solid rgba(201,168,76, 0.05)`, `border-radius: 6px`
- `padding: 7px 10px`
- Steps: `Query formulated › 12 passages · reranked to 6 › Answer generated · 3 citations`
- Each step: 4px gold dot + `font: 8.5px/1 system-ui`, `color: var(--text-dim)`
- Arrow separator: `›`, `color: rgba(201,168,76, 0.15)`
- Active step (during streaming): `color: var(--gold-text)`, dot pulses (1.5s ease-in-out infinite, opacity 0.4→0.9)

### 3.2 Confidence Badge
- `display: inline-flex`, `height: 18px`, `padding: 0 7px`, `border-radius: 4px`
- `background: rgba(201,168,76, 0.06)`, `border: 1px solid rgba(201,168,76, 0.1)`
- `font: 8px/1 system-ui`, uppercase, `letter-spacing: 0.5px`
- `color: rgba(201,168,76, 0.55)`
- 5px gold dot indicator

### 3.3 User Question
- `font: italic 12.5px/1.6 Georgia, serif`
- `color: var(--text-question)` — `rgba(255,255,255, 0.72)`
- `padding-bottom: 14px`, `border-bottom: 1px solid var(--gold-border)`
- `margin-bottom: 18px`, `letter-spacing: 0.01em`
- **No bubble, no card** — inline text with gold separator

### 3.4 Assistant Answer
- `font: 12.5px/1.8 Georgia, serif`
- `color: var(--text-body)` — `rgba(255,255,255, 0.56)`
- `letter-spacing: 0.01em`
- **h2**: `font: normal 14px/1.4 Georgia, serif`, `color: var(--text-primary)`, `margin: 18px 0 8px`
- **strong**: `color: rgba(255,255,255, 0.68)`, `font-weight: 600`
- **sup (citations)**: `font-size: 0.65em`, `color: var(--citation)`, `background: rgba(201,168,76, 0.07)`, `border: 1px solid rgba(201,168,76, 0.1)`, `border-radius: 3px`, `padding: 1px 3px`
  - Hover: `background: rgba(201,168,76, 0.14)`, `border-color: rgba(201,168,76, 0.22)`, `color: var(--gold-base)`
  - Active (clicked): `background: rgba(201,168,76, 0.2)`, `border-color: rgba(201,168,76, 0.4)`, `box-shadow: 0 0 8px rgba(201,168,76, 0.12)`
- **Inline grounding highlight** (on clicked citation): `background: rgba(201,168,76, 0.08)`, `border-bottom: 1px solid rgba(201,168,76, 0.25)`, `padding: 1px 0`, `border-radius: 2px`
- **Code blocks**: `background: var(--strict-code-bg)` — `rgba(201,168,76, 0.08)`
- **Tables**: `border-color: var(--strict-table-border)` — `rgba(20,22,30, 0.1)`
- **Blockquotes**: `background: var(--strict-blockquote-bg)` — `rgba(201,168,76, 0.04)`, gold left border

### 3.5 Footnotes (below each answer)
- `border-top: 1px solid var(--gold-border)`, `padding-top: 8px`, `margin-top: 12px`
- Label: `font: 6px/1 system-ui`, uppercase, `letter-spacing: 1px`, `color: var(--text-dim)`, text "SOURCES"
- Each row: number (gold, Georgia 8px) + text (system-ui 8px, `color: var(--text-secondary)`)
- Clicking a footnote number → inline grounding highlight on answer text + source panel opens (desktop) or bottom sheet (mobile)

### 3.6 Feedback Buttons (inside footnotes area)
- Below source list, separated by `border-top: 1px solid rgba(201,168,76, 0.03)`
- Copy button + separator + thumbs up + thumbs down + "Helpful?" label (right-aligned)
- Button: 20×20px, `border-radius: 5px`, transparent, `color: var(--text-dim)`
- Hover: `background: rgba(201,168,76, 0.05)`, `border: 1px solid var(--gold-border)`
- Active (voted): `background: rgba(201,168,76, 0.08)`, `border-color: rgba(201,168,76, 0.15)`, `color: var(--gold-text)`
- Negative feedback textarea: same gold glass styling, 2000 char max

### 3.7 Multi-Message Layout (Collapsible Turns)
- **Previous Q&A pairs collapse** to a single clickable row:
  - `padding: 6px 10px`, `border-radius: 6px`
  - `background: rgba(201,168,76, 0.02)`, `border: 1px solid rgba(201,168,76, 0.05)`
  - Chevron (right arrow) + italic question text + "N sources" count (right-aligned)
  - Click to expand (shows full answer + footnotes)
  - Hover: `background: rgba(201,168,76, 0.04)`, `border-color: rgba(201,168,76, 0.08)`
- **Latest Q&A pair** always fully expanded
- Expand/collapse animation: CSS grid `grid-template-rows` transition (0.3s ease)

---

## 4. Streaming State

- **Typewriter effect**: Character by character via rAF-based imperative DOM mutation (existing `useStrictTypewriter` pattern)
- **Blinking gold cursor**: `width: 1.5px`, `height: matching line-height`, `background: var(--gold-base)`, `animation: blink 0.8s ease-in-out infinite` (opacity 0↔1)
- **Pipeline bar**: Active step shows "Generating…" with pulsing dot
- **Stop button**: Below answer text, `padding: 5px 10px`, `border-radius: 5px`, gold glass styling, gold square icon (6×6px) + "Stop generating" text
- **No footnotes** shown during streaming (appear after completion)
- **Auto-scroll**: Scroll to top of answer on new message, no fighting during streaming

---

## 5. Source Panel (Desktop)

### 5.1 Default State
- **No source panel visible** — full-width answer with footnotes below (decision: C — footnotes)

### 5.2 Active State (citation clicked)
- Source panel slides in from right, takes **42% width**
- `border-left: 1px solid var(--gold-border)`
- `background: rgba(0,0,0, 0.06)`
- Answer column shrinks to remaining space

### 5.3 Source Tabs
- Top of source panel, horizontal row
- Each tab: `padding: 9px 14px`, `font: 9px/1 system-ui`
- Tab number badge: `font: 8px Georgia`, gold bg/border, `border-radius: 3px`, `padding: 1px 4px`
- Active tab: `color: var(--gold-text)`, `border-bottom: 2px solid rgba(201,168,76, 0.4)`
- Close button (×) on far right

### 5.4 Source Meta
- `padding: 12px 18px`
- Document name: `font: 11px/1.3 Georgia`, `color: var(--text-primary)`
- Reference: `font: 9px/1.3 system-ui`, `color: var(--text-dim)`
- Page badge: `font: 8px system-ui`, gold glass styling

### 5.5 Source Document Text
- `font: 12px/1.75 Georgia, serif`, `color: var(--text-secondary)`
- Article headings: `color: var(--text-body)`, `margin-top: 14px`
- **Matching passage**: `background: rgba(201,168,76, 0.07)`, `border-left: 2px solid rgba(201,168,76, 0.35)`, `padding: 10px 14px`, `border-radius: 0 6px 6px 0`, `color: var(--text-body)`
- Sub-articles: `padding-left: 16px`, `color: var(--text-dim)`

---

## 6. History Panel (Desktop)

- **Separate glass pane** to the left of main pane
- Width: 220px
- Same glass styling as main pane (own border-radius, blur, shadow)
- Gap: 8px between history pane and main pane

### 6.1 Header
- `padding: 12px`, `border-bottom: 1px solid var(--gold-border)`
- "CHATS" label (8px system-ui, uppercase, dim)
- New chat (+) button: 22×22px, gold glass

### 6.2 Session List
- Scrollable, grouped by date (Today, Yesterday, Earlier)
- Section labels: 8px uppercase, dim
- Session items: `padding: 7px 8px`, `border-radius: 6px`, `font: 10.5px/1.4 Georgia`
  - Default: `color: var(--text-secondary)`, transparent border
  - Hover: `background: rgba(255,255,255, 0.02)`, `border: 1px solid var(--gold-border)`
  - Active: `background: rgba(201,168,76, 0.04)`, `border-color: rgba(201,168,76, 0.1)`, `color: var(--text-primary)`
- Date: `font: 8px system-ui`, `color: var(--text-dim)`
- Delete button: appears on hover, trash icon, gold styling

---

## 7. Empty State (Suggested Questions)

- Centered in reading area
- Heading: `font: normal 16px/1.3 Georgia, serif`, `color: var(--text-primary)`, "What would you like to research?"
- Subtitle: `font: 10px/1.4 system-ui`, `color: var(--text-dim)`
- **Question pills** (3-4, stacked vertically):
  - `padding: 8px 12px`, `border-radius: 6px`
  - `background: rgba(201,168,76, 0.03)`, `border: 1px solid rgba(201,168,76, 0.07)`
  - `font: italic 10px/1.4 Georgia, serif`, `color: var(--text-secondary)`
  - Law name highlighted: `color: var(--gold-text)`, `font-style: normal`
  - Hover: `background: rgba(201,168,76, 0.07)`, `border-color: rgba(201,168,76, 0.15)`, `color: var(--text-body)`
- Click sends the question
- Different questions per jurisdiction (existing `scenarios.ts`)

---

## 8. Follow-up Suggestions

- `padding: 12px 24px`, `border-top: 1px solid var(--gold-border)`
- Horizontal flex wrap, `gap: 6px`
- Pill: `height: 28px`, `padding: 0 12px`, `border-radius: 5px`
- `background: rgba(201,168,76, 0.04)`, `border: 1px solid rgba(201,168,76, 0.08)`
- `font: 10.5px/1 Georgia, serif`, `color: var(--text-secondary)`
- Hover: `background: rgba(201,168,76, 0.08)`, `border-color: rgba(201,168,76, 0.18)`, `color: var(--text-body)`
- Click sends as new message

---

## 9. Input Footer

- `padding: 10px 16px 14px`, `border-top: 1px solid rgba(201,168,76, 0.06)`
- **Input box**: `height: 36px` (auto-grows), `border-radius: 8px`
  - `background: rgba(19,19,19, 0.64)`, `border: 1px solid rgba(222,222,222, 0.1)`
  - `font: 11px/1 Georgia, serif`, `color: var(--text-body)`
  - Focus: `border-color: rgba(201,168,76, 0.2)`, `box-shadow: 0 0 0 2px rgba(201,168,76, 0.08)`
  - Placeholder: "Continue your research…" / "Ask a legal question…" (empty state)
  - `caret-color: var(--gold-base)`
- **Send button**: 32×32px, `border-radius: 7px`
  - `background: linear-gradient(135deg, rgba(201,168,76, 0.22), rgba(201,168,76, 0.12))`
  - `border: 1px solid rgba(201,168,76, 0.25)`
  - `color: var(--gold-base)`
  - Hover: `transform: scale(1.06)`
  - Active (text entered): full gold gradient
  - Disabled (streaming): shows stop icon
- **Disclaimer**: `font: 8.5px/1.3 system-ui`, `color: var(--text-ghost)`, centered
- Enter to send, Shift+Enter for newline (preserved)
- Cmd+K focus shortcut (preserved)

---

## 10. Mobile Layout

### 10.1 Base Layout
- No sidebar rail — logo moves to header
- No separate glass pane edges — full-screen glass or full-bleed
- Jurisdiction pills in scrollable row below header

### 10.2 Mobile Header
- `height: 44px`, same gold glass styling
- Logo (16px) + Brand + flex spacer + History button + New chat button
- Jurisdiction row: separate row below, scrollable, same pill styling

### 10.3 Mobile Sources (Bottom Sheet)
- Citation tap → source document slides up as bottom sheet (50% screen)
- Drag handle: 24px centered bar, `border-radius: 1px`
- Drag up to expand to full screen, drag down to dismiss
- Same source meta + document text styling as desktop
- `background: rgba(13,10,18, 0.95)`, `backdrop-filter: blur(24px)`

### 10.4 Mobile History
- Full-screen glass overlay
- `background: rgba(13,10,18, 0.95)`, `backdrop-filter: blur(20px)`
- Close button (×) in header
- Same session list styling

### 10.5 Mobile Input
- Same styling, safe-area-inset-bottom padding
- Keyboard-aware positioning

---

## 11. Scrollbar

- `width: 6px`, `height: 6px`
- Track: `background: rgba(0,0,0, 0.15)`, `border-radius: 3px`
- Thumb: `background: rgba(201,168,76, 0.12)`, `border-radius: 3px`, `border: 1px solid rgba(0,0,0, 0.2)`
- Thumb hover: `background: rgba(201,168,76, 0.22)`
- Firefox: `scrollbar-width: thin`, `scrollbar-color: rgba(201,168,76, 0.12) transparent`

---

## 12. Localization

- Language toggle: accessible from settings (gear icon in sidebar rail)
- All 5 languages preserved: en, cs, de, ru, ar
- RTL support for Arabic preserved
- Geo-detection preserved
- All translated strings must work with new layout
- Theme toggle (sun/moon) co-located with language toggle in settings area

---

## 13. Preserved Functionality Checklist

All of the following must work identically after redesign:

- [ ] Jurisdiction switching (click + long-press)
- [ ] Multi-corpus warning + blocking (max 2)
- [ ] Law selector (UK/AU) with long-press isolate
- [ ] Custom corpus selection + collections
- [ ] Document upload navigation
- [ ] Internet/web search toggle
- [ ] Session CRUD (create, switch, delete, persist)
- [ ] Preview/demo scenarios in empty state
- [ ] Source grounding (inline highlight + panel)
- [ ] Document index toggle + highlight
- [ ] Copy answer to clipboard
- [ ] Feedback voting (thumbs + comment)
- [ ] Streaming (typewriter, abort, auto-scroll)
- [ ] Error display + dismiss
- [ ] Cmd+K focus shortcut
- [ ] Follow-up suggestions
- [ ] Status polling for interrupted messages
- [ ] Cross-tab sync (jurisdiction, theme)
- [ ] Confidence badge display
- [ ] Agent trace (now horizontal pipeline bar)
- [ ] Citation parsing (both `[DOC-N]` and `[[source:...]]` formats)
- [ ] Markdown rendering (GFM, tables, code blocks)
- [ ] LocalStorage migration (old keys → new)

---

## 14. Light Mode (Neon — unchanged)

The current Neon design is preserved as-is for light mode. No changes to Neon styling, components, or behavior. The only change is how it's activated:
- Old: `DesignVersionToggle` component selecting "Neon"
- New: Color mode toggle selecting "Light" (or system preference)

CSS selectors change from `.design-neon` → `.light` (or default/no class).

---

## 15. CSS Token Architecture

All dark mode values use `--strict-*` CSS custom properties (already defined in globals.css). No hardcoded values anywhere. The token system is already comprehensive — see globals.css lines 641-831 for the full inventory.

Key token groups:
- `--strict-glass-*` (surfaces)
- `--strict-text-*` (text hierarchy)
- `--strict-gold-*` (accent colors)
- `--strict-input-*` (form fields)
- `--strict-nav-*` (navigation)
- `--strict-source-*` (source panel)
- `--strict-hiw-*` (how it works — landing only)

---

## 16. Animation Tokens

All timings from `strict-tokens.ts`:
- Spring presets: `V3_SPRING.micro/standard/gentle/snappy/bouncy`
- Typewriter: 8ms/char (landing preview), actual chat uses streaming speed
- Source stagger: 250ms
- Mesh drift: 8s cycle
- Badge pulse: 3s cycle
- Counter: 20ms interval, +2 step

New additions:
- Cursor blink: 0.8s ease-in-out
- Pipeline dot pulse: 1.5s ease-in-out
- Collapse/expand: 0.3s ease (CSS grid-template-rows)
- Source panel slide: 0.25s ease-out
- Bottom sheet: 0.3s ease (transform translateY)
