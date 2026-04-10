# Chat UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

> **CRITICAL:** Read the design spec at docs/superpowers/specs/2026-04-10-chat-redesign-spec.md FIRST. Every color value, animation timing, and layout decision was collaboratively brainstormed with the user. Do NOT deviate from the spec values.

---

## Scope

Merge the theme axes: **Neon = light mode**, **Strict = dark mode**. Redesign every chat UI element to match the Strict landing page aesthetic. Preserve all existing functionality. Components under 300 lines. Zero hardcoded colors — CSS variables only.

## What NOT to Change

- Light mode (Neon) design — stays as-is, only CSS selector migration (`.design-neon` -> `.light` / default)
- Backend API contracts
- localStorage session data structure (only add migration for theme key)
- Citation parsing logic (`remarkInlineCitations`, `rehypeInlineCitations`, `collectCitedSources`)
- Streaming/SSE infrastructure (`use-query-stream.ts`, `eventsource-parser`)
- Jurisdiction/law selection logic (only visual changes, behavior unchanged)
- `chat-state.ts` (session management, message state)
- `use-jurisdiction.ts` (jurisdiction hooks)
- `grounding-view.tsx` (source grounding internals)

---

## Preserved Functionality Checklist

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
- [ ] LocalStorage migration (old keys -> new)

---

## Batch 1: Theme System Overhaul

**Goal:** Replace the two-axis system (design version x color mode) with a single dark/light toggle. All downstream consumers switch from `useDesignVersion()` to `useColorMode()`.

### Task 1.1: Create `ColorModeContext` to replace `DesignVersionContext`

**File:** `frontend/src/lib/color-mode.tsx` (NEW)

- [ ] Create a new context provider: `ColorModeProvider`
- [ ] State: `mode: "light" | "dark" | "system"`, resolved to `resolvedMode: "light" | "dark"`
- [ ] localStorage key: `vitreon-color-mode`
- [ ] System detection: `window.matchMedia("(prefers-color-scheme: dark)")`
- [ ] Listen for `matchMedia` changes when mode is `"system"`
- [ ] Apply `.light` or `.dark` class on `<html>` (remove the other)
- [ ] Migration logic on first load:
  - If `vitreon-design-version === "strict"` -> set `vitreon-color-mode = "dark"`
  - If `vitreon-design-version === "neon"` -> set `vitreon-color-mode = "light"`
  - If `theme === "dark"` (from next-themes) -> set `vitreon-color-mode = "dark"`
  - Remove old key `vitreon-design-version`
- [ ] Export `useColorMode()` hook returning `{ mode, resolvedMode, setMode, isDark }`
- [ ] `useEffect` cleanup for `matchMedia` listener
- [ ] Keep component under 100 lines

### Task 1.2: Update FOUC prevention script in `layout.tsx`

**File:** `frontend/src/app/layout.tsx`

- [ ] Replace both inline `<script>` tags (theme + design-version) with a single unified script
- [ ] New script logic:
  ```
  1. Read `vitreon-color-mode` from localStorage
  2. If not found, check `vitreon-design-version` for migration
  3. If not found, check `theme` (next-themes key) for migration
  4. If still not found, use system `prefers-color-scheme`
  5. Apply `.dark` or `.light` class on <html>
  ```
- [ ] Remove `DesignVersionProvider` wrapper from the provider tree
- [ ] Replace `ThemeProvider` + `DesignVersionProvider` with `ColorModeProvider`
- [ ] Keep `I18nProvider`, `TooltipProvider`, `ToastProvider` unchanged

### Task 1.3: Migrate CSS selectors in `globals.css`

**File:** `frontend/src/app/globals.css`

- [ ] Replace `.design-neon` selectors with `.light` (or `:root` default where appropriate)
- [ ] Replace `.design-strict` selectors with `.dark`
- [ ] Replace `.design-neon.dark` selectors with `.dark` equivalents (merge into `.dark` block)
- [ ] Replace `.design-strict.dark` selectors with `.dark` equivalents
- [ ] Keep all CSS variable values EXACTLY as they are — only change selectors
- [ ] Verify no `.design-neon` or `.design-strict` references remain
- [ ] Add new animation keyframes needed by the redesign:
  - `@keyframes cursor-blink` (0.8s ease-in-out, opacity 0 <-> 1)
  - `@keyframes pipeline-dot-pulse` (1.5s ease-in-out, opacity 0.4 <-> 0.9)
- [ ] Add `.dark` scrollbar styles (spec section 11)

### Task 1.4: Update all consumers of `useDesignVersion`

**Files (15 files total):**
- `frontend/src/app/(app)/chat/page.tsx`
- `frontend/src/components/chat/chat-input.tsx`
- `frontend/src/components/chat/sources-panel.tsx`
- `frontend/src/components/landing/strict/strict-nav.tsx`
- `frontend/src/components/design-version-toggle.tsx`
- `frontend/src/components/app-sidebar.tsx`
- `frontend/src/app/(auth)/page.tsx`
- `frontend/src/app/(app)/settings/page.tsx`
- `frontend/src/app/(app)/documents/page.tsx`
- `frontend/src/app/(app)/billing/page.tsx`
- `frontend/src/app/(auth)/login/page.tsx`
- `frontend/src/components/app-background.tsx`
- `frontend/src/components/bottom-nav.tsx`
- `frontend/src/lib/design-version.tsx` (to be deprecated)

For each file:
- [ ] Replace `import { useDesignVersion } from "@/lib/design-version"` with `import { useColorMode } from "@/lib/color-mode"`
- [ ] Replace `const { version } = useDesignVersion()` with `const { isDark } = useColorMode()`
- [ ] Replace `version === "strict"` checks with `isDark`
- [ ] Replace `isGlassmorphic` / `isV3` patterns with `isDark`
- [ ] Remove combined `isStrict = mounted && designVersion === "strict"` patterns — now just `isDark`
- [ ] The existing `useTheme()` / `resolvedTheme` usage can be consolidated into `useColorMode()`
- [ ] Delete `frontend/src/components/design-version-toggle.tsx` (the Neon/Strict toggle component)
- [ ] Mark `frontend/src/lib/design-version.tsx` as deprecated (keep for one release cycle)

### Task 1.5: Simplify theme toggle to sun/moon icon

**File:** `frontend/src/components/theme-toggle.tsx` (NEW or modify existing)

- [ ] Simple button: sun icon (light mode) / moon icon (dark mode)
- [ ] Calls `useColorMode().setMode()` cycling: light -> dark -> system -> light
- [ ] Tooltip showing current mode
- [ ] Styled with CSS variables — no hardcoded colors
- [ ] Under 50 lines

---

## Batch 2: Parallel Component Work

All tasks in this batch are independent and can be worked on simultaneously. Each produces a self-contained component.

### Task 2.1: Pipeline Status Bar (replaces `AgentTrace`)

**File:** `frontend/src/components/chat/pipeline-status-bar.tsx` (NEW)

**Replaces:** `frontend/src/components/chat/agent-trace.tsx`

- [ ] Horizontal compact bar layout (not vertical timeline)
- [ ] Background: `var(--strict-pipeline-bg)` -> `rgba(201,168,76, 0.025)`
- [ ] Border: `1px solid var(--strict-pipeline-border)` -> `rgba(201,168,76, 0.05)`
- [ ] Border-radius: `6px`, padding: `7px 10px`
- [ ] Steps format: `Query formulated > 12 passages . reranked to 6 > Answer generated . 3 citations`
- [ ] Each step: 4px gold dot + `font: 8.5px/1 system-ui`, `color: var(--strict-text-dim)`
- [ ] Arrow separator: `>` character, `color: rgba(201,168,76, 0.15)`
- [ ] Parse trace strings into structured steps (reuse `getStepStyle` logic for icon selection)
- [ ] Active step during streaming: `color: var(--strict-gold-text)`, dot pulses with `pipeline-dot-pulse` animation
- [ ] Props: `trace: string[]`, `isStreaming: boolean`, `isDark: boolean`
- [ ] Light mode: existing Neon trace rendering (pass-through to old style or simplified inline)
- [ ] Under 120 lines
- [ ] No `useEffect` needed (pure render)

### Task 2.2: Collapsible Message Turns

**File:** `frontend/src/components/chat/collapsible-turn.tsx` (NEW)

- [ ] Component wraps a Q&A pair (user message + assistant message + footnotes)
- [ ] Props: `question: string`, `sourceCount: number`, `isLatest: boolean`, `children: ReactNode`
- [ ] When `isLatest === true`: always expanded, no collapse UI
- [ ] When `isLatest === false`: collapsed by default
- [ ] Collapsed row:
  - `padding: 6px 10px`, `border-radius: 6px`
  - `background: rgba(201,168,76, 0.02)`, `border: 1px solid rgba(201,168,76, 0.05)` (via CSS vars)
  - Chevron (right arrow) + italic question text + "N sources" count (right-aligned)
  - Hover: `background: rgba(201,168,76, 0.04)`, `border-color: rgba(201,168,76, 0.08)` (via CSS vars)
- [ ] Expand/collapse animation: CSS `grid-template-rows` transition (0.3s ease)
- [ ] Click on collapsed row toggles expanded state
- [ ] Light mode: pass children directly without collapse wrapper
- [ ] Under 100 lines

### Task 2.3: Footnotes Component (replaces source margin placement)

**File:** `frontend/src/components/chat/footnotes.tsx` (NEW)

- [ ] Renders below each assistant answer (inside the message, not in a margin)
- [ ] Props: `citedSources: CitedEntry[]`, `onSourceClick`, `isDark: boolean`
- [ ] Dark mode styling:
  - `border-top: 1px solid var(--strict-gold-border)`, `padding-top: 8px`, `margin-top: 12px`
  - Label: `font: 6px/1 system-ui`, uppercase, `letter-spacing: 1px`, `color: var(--strict-text-dim)`, text "SOURCES"
  - Each row: number (gold, Georgia 8px) + text (system-ui 8px, `color: var(--strict-text-secondary)`)
  - Clicking footnote number triggers `onSourceClick` for inline grounding + source panel
- [ ] Light mode: existing footnote rendering from `chat-message.tsx` (the `citedSources` block)
- [ ] Extract `collectCitedSources` and `CitedEntry` type from `chat-message.tsx` into a shared util
- [ ] Under 80 lines

### Task 2.4: Feedback Buttons (inside footnotes area)

**File:** `frontend/src/components/chat/feedback-buttons.tsx` (NEW)

- [ ] Extract feedback UI from `chat-message.tsx` (lines ~742-911)
- [ ] Props: `messageId`, `traceId`, `conversationId`, `feedback`, `onFeedback`, `isDark`, `content`
- [ ] Dark mode placement: below source list in footnotes, separated by `border-top: 1px solid rgba(201,168,76, 0.03)`
- [ ] Layout: Copy button + separator + thumbs up + thumbs down + "Helpful?" label (right-aligned)
- [ ] Button: 20x20px, `border-radius: 5px`, transparent, `color: var(--strict-text-dim)`
- [ ] Hover: `background: rgba(201,168,76, 0.05)`, `border: 1px solid var(--strict-gold-border)`
- [ ] Active (voted): `background: rgba(201,168,76, 0.08)`, `border-color: rgba(201,168,76, 0.15)`, `color: var(--strict-gold-text)`
- [ ] Negative feedback textarea: same gold glass styling, 2000 char max
- [ ] Copy button included (moved from the answer card hover overlay)
- [ ] Light mode: preserve existing pill-style feedback buttons
- [ ] Keep `postFeedback` API call logic exactly as-is
- [ ] Under 200 lines

### Task 2.5: Source Panel (tabbed, 42% width)

**File:** `frontend/src/components/chat/source-panel-v2.tsx` (NEW)

- [ ] Default state: **hidden** (answer takes full width with footnotes below)
- [ ] Active state: slides in from right when citation is clicked, takes **42% width**
- [ ] `border-left: 1px solid var(--strict-gold-border)`
- [ ] `background: rgba(0,0,0, 0.06)` (via CSS var)
- [ ] Source tabs at top:
  - Each tab: `padding: 9px 14px`, `font: 9px/1 system-ui`
  - Tab number badge: `font: 8px Georgia`, gold bg/border, `border-radius: 3px`, `padding: 1px 4px`
  - Active tab: `color: var(--strict-gold-text)`, `border-bottom: 2px solid rgba(201,168,76, 0.4)`
  - Close button (x) on far right
- [ ] Source meta section:
  - Document name: `font: 11px/1.3 Georgia`, `color: var(--strict-text-primary)`
  - Reference: `font: 9px/1.3 system-ui`, `color: var(--strict-text-dim)`
  - Page badge: `font: 8px system-ui`, gold glass styling
- [ ] Source document text:
  - `font: 12px/1.75 Georgia, serif`, `color: var(--strict-text-secondary)`
  - Matching passage: `background: rgba(201,168,76, 0.07)`, gold left border, `padding: 10px 14px`
- [ ] Slide-in animation: 0.25s ease-out (CSS transform or motion/react)
- [ ] Props: `sources: Source[]`, `activeSourceIndex: number | null`, `onTabChange`, `onClose`, `answer: string`
- [ ] Wraps existing `GroundingView` for the document content display
- [ ] Light mode: existing side panel behavior (pass through to current grounding panel)
- [ ] Under 250 lines

### Task 2.6: Sidebar Rail (functional buttons)

**File:** `frontend/src/components/chat/sidebar-rail.tsx` (NEW, replaces `strict-sidebar-rail.tsx`)

- [ ] Width: 44px, desktop only
- [ ] `background: var(--strict-glass-recessed)` -> `rgba(0,0,0, 0.1)`
- [ ] `border-right: 1px solid var(--strict-gold-border)`
- [ ] Functional buttons (top to bottom):
  1. **Logo**: Gold "V" in 24px circle, `border: 1px solid rgba(201,168,76, 0.2)`, 9px font
  2. **History**: Hamburger icon (Menu from lucide), toggles history pane
  3. **New chat**: SquarePen icon, creates new session
  4. **Divider**: 18px gold line, `background: var(--strict-gold-border)`
  5. **Doc index**: ListOrdered icon, toggles document index
  6. **Spacer**: `flex: 1`
  7. **Settings**: Settings icon, opens settings popover (theme toggle + language toggle)
- [ ] Button style: 28x28px, `border-radius: 6px`, transparent bg, `color: var(--strict-text-dim)`
- [ ] Hover: `background: rgba(201,168,76, 0.05)`, `border: 1px solid var(--strict-gold-border)`, `color: var(--strict-text-secondary)`
- [ ] Active: `background: rgba(201,168,76, 0.07)`, `border-color: rgba(201,168,76, 0.14)`, `color: var(--strict-gold-text)`
- [ ] Props: `onHistoryToggle`, `onNewChat`, `onDocIndexToggle`, `historyOpen`, `indexOpen`
- [ ] Settings popover: simple dropdown with ThemeToggle + LanguageSelector
- [ ] Under 200 lines

### Task 2.7: Empty State Redesign

**File:** `frontend/src/components/chat/empty-state.tsx` (MODIFY existing)

- [ ] Dark mode heading: `font: normal 16px/1.3 Georgia, serif`, `color: var(--strict-text-primary)`, "What would you like to research?"
- [ ] Dark mode subtitle: `font: 10px/1.4 system-ui`, `color: var(--strict-text-dim)`
- [ ] Dark mode question pills (3-4, stacked vertically):
  - `padding: 8px 12px`, `border-radius: 6px`
  - `background: rgba(201,168,76, 0.03)`, `border: 1px solid rgba(201,168,76, 0.07)` (via CSS vars)
  - `font: italic 10px/1.4 Georgia, serif`, `color: var(--strict-text-secondary)`
  - Law name: `color: var(--strict-gold-text)`, `font-style: normal`
  - Hover: `background: rgba(201,168,76, 0.07)`, `border-color: rgba(201,168,76, 0.15)`, `color: var(--strict-text-body)`
- [ ] Click sends the question (existing behavior preserved)
- [ ] Different questions per jurisdiction (existing `getPresetQuestions` preserved)
- [ ] Light mode: keep current Neon empty state exactly as-is
- [ ] Under 200 lines

### Task 2.8: Chat Input Redesign

**File:** `frontend/src/components/chat/chat-input.tsx` (MODIFY existing)

- [ ] Replace `useDesignVersion` with `useColorMode`
- [ ] Dark mode styling per spec section 9:
  - Input box height: 36px (auto-grows), `border-radius: 8px`
  - `background: rgba(19,19,19, 0.64)`, `border: 1px solid rgba(222,222,222, 0.1)` (via CSS vars)
  - `font: 11px/1 Georgia, serif`, `color: var(--strict-text-body)`
  - Focus: `border-color: rgba(201,168,76, 0.2)`, `box-shadow: 0 0 0 2px rgba(201,168,76, 0.08)`
  - Placeholder: "Continue your research..." / "Ask a legal question..." (empty state)
  - `caret-color: var(--strict-gold-base)`
- [ ] Send button: 32x32px, `border-radius: 7px`
  - `background: linear-gradient(135deg, rgba(201,168,76, 0.22), rgba(201,168,76, 0.12))`
  - `border: 1px solid rgba(201,168,76, 0.25)`
  - `color: var(--strict-gold-base)`
  - Hover: `transform: scale(1.06)`
  - Active (text entered): full gold gradient
  - Disabled (streaming): shows stop icon
- [ ] Disclaimer: `font: 8.5px/1.3 system-ui`, `color: var(--strict-text-ghost)`, centered
- [ ] Enter to send, Shift+Enter for newline — preserved
- [ ] Light mode: keep current Neon input exactly as-is
- [ ] Under 180 lines

### Task 2.9: Confidence Badge Update

**File:** `frontend/src/components/chat/confidence-badge.tsx` (MODIFY existing)

- [ ] Replace `isStrict` prop with `isDark` usage (from `useColorMode` or prop)
- [ ] Dark mode (per spec section 3.2):
  - `display: inline-flex`, `height: 18px`, `padding: 0 7px`, `border-radius: 4px`
  - `background: rgba(201,168,76, 0.06)`, `border: 1px solid rgba(201,168,76, 0.1)`
  - `font: 8px/1 system-ui`, uppercase, `letter-spacing: 0.5px`
  - `color: rgba(201,168,76, 0.55)`
  - 5px gold dot indicator
- [ ] Light mode: keep current colored confidence badges exactly as-is
- [ ] Under 100 lines

### Task 2.10: History Panel Styling Update

**File:** `frontend/src/components/chat/history-panel.tsx` (NEW — extract from `page.tsx`)

- [ ] Extract history panel from `page.tsx` (lines ~389-576) into standalone component
- [ ] Props: `sessions`, `currentSessionId`, `onLoadSession`, `onNewChat`, `onDeleteSession`, `onClose`, `isDark`, `isMobile`
- [ ] Dark mode: separate glass pane, width 220px, 8px gap from main pane
  - Glass styling: same as main pane (own border-radius, blur, shadow)
  - Header: `padding: 12px`, `border-bottom: 1px solid var(--strict-gold-border)`
  - "CHATS" label: 8px system-ui, uppercase, dim
  - New chat (+) button: 22x22px, gold glass
  - Session items: `padding: 7px 8px`, `border-radius: 6px`, `font: 10.5px/1.4 Georgia`
  - Active: `background: rgba(201,168,76, 0.04)`, gold border, `color: var(--strict-text-primary)`
  - Hover: `background: rgba(255,255,255, 0.02)`, `border: 1px solid var(--strict-gold-border)`
  - Date grouping: Today, Yesterday, Earlier (section labels: 8px uppercase, dim)
  - Delete button: appears on hover, trash icon, gold styling
- [ ] Light mode: keep current Neon history styling
- [ ] Mobile: full-screen glass overlay with close button
- [ ] Under 250 lines

---

## Batch 3: Chat Page Integration

**Depends on:** Batches 1 and 2 must be complete.

### Task 3.1: Rewrite `page.tsx` — Wire New Components

**File:** `frontend/src/app/(app)/chat/page.tsx` (MAJOR REWRITE)

**Goal:** Reduce from ~1850 lines to ~600 lines by extracting components and using the new ones.

- [ ] Replace `useDesignVersion` with `useColorMode`
- [ ] Replace `StrictLayout` + `StrictChatWrapper` with new layout using `SidebarRail` + `SourcePanelV2`
- [ ] Dark mode page structure:
  ```
  [12px padding]
  [HistoryPanel (220px)] [8px gap] [Main Glass Pane (flex:1)]
                                     [SidebarRail 44px] [Reading Area flex:1] [SourcePanelV2 42% (conditional)]
  ```
- [ ] Page background: `linear-gradient(170deg, #0E1118, #0B0E16, #0D0A12)` (via CSS var)
- [ ] Main glass pane:
  - `background: rgba(255,255,255, 0.02)`
  - `backdrop-filter: blur(24px)`
  - `border: 1px solid rgba(201,168,76, 0.06)`
  - `border-radius: 14px`
  - All via CSS variables
- [ ] Replace inline header with extracted `ChatHeader` component (see Task 3.2)
- [ ] Wire `SidebarRail` buttons to existing state handlers (`setHistoryOpen`, `newChat`, `setIndexOpen`)
- [ ] Wire `SourcePanelV2` to existing `handleSourceClick` / `setDrawerOpen` logic
- [ ] Use `CollapsibleTurn` for message rendering (previous turns collapsed, latest expanded)
- [ ] Use `PipelineStatusBar` instead of `AgentTrace`
- [ ] Use `Footnotes` + `FeedbackButtons` instead of inline footnotes/feedback in `ChatMessage`
- [ ] Keep all state management exactly as-is (sessions, jurisdiction, corpora, etc.)
- [ ] Keep `GroundingErrorBoundary` class component
- [ ] Keep all `useEffect` hooks with proper cleanups
- [ ] Keep `useCallback` wrappers for handlers
- [ ] Light mode: render without sidebar rail, without glass pane, with original layout structure

### Task 3.2: Extract Chat Header

**File:** `frontend/src/components/chat/chat-header.tsx` (NEW)

- [ ] Extract header section from `page.tsx` (lines ~608-936) into standalone component
- [ ] Props: `jurisdiction`, `onJurisdictionChange`, `selectedLaws`, `onSelectedLawsChange`, `availableLaws`, `lawPaneOpen`, `onLawPaneToggle`, `useInternet`, `onInternetToggle`, `currentCorpora`, `isDark`, `isMobile`, all corpus-related props
- [ ] Dark mode header (spec section 2.4):
  - Height: 44px, `border-bottom: 1px solid var(--strict-gold-border)`
  - `background: linear-gradient(180deg, rgba(255,255,255,0.015) 0%, transparent 100%)`
  - Logo: 26px circle, `border: 1px solid rgba(201,168,76, 0.2)`, gold "V" 9px
  - Brand: `font: 11px/1 Georgia, serif`, `color: var(--strict-text-secondary)`
  - Jurisdiction pills centered: `padding: 5px 8px`, `border-radius: 4px`, `font: 9px/9px system-ui`, dot separators
  - Internet toggle: same pill style
  - **No header action buttons** (history, new chat, doc index moved to sidebar rail)
- [ ] Jurisdiction pill long-press behavior preserved exactly
- [ ] Corpus warning/blocked banners preserved
- [ ] Law selector row (UK/AU) preserved
- [ ] Custom corpus row preserved
- [ ] Light mode: keep current Neon header with action buttons in header (since no sidebar rail in light mode)
- [ ] Under 300 lines

### Task 3.3: Update `ChatMessage` for new component composition

**File:** `frontend/src/components/chat/chat-message.tsx` (MODIFY)

- [ ] Remove inline footnotes rendering (now handled by `Footnotes` component)
- [ ] Remove inline feedback buttons (now handled by `FeedbackButtons` component)
- [ ] Remove inline `AgentTrace` usage (now handled by `PipelineStatusBar`)
- [ ] Remove copy button from answer card hover (moved to `FeedbackButtons`)
- [ ] Keep all markdown rendering, citation parsing, prose classes
- [ ] Replace `isStrict` prop with `isDark`
- [ ] Dark mode user question styling (spec section 3.3):
  - `font: italic 12.5px/1.6 Georgia, serif`
  - `color: var(--strict-text-question)` -> `rgba(255,255,255, 0.72)`
  - `padding-bottom: 14px`, `border-bottom: 1px solid var(--strict-gold-border)`
  - No bubble, no card
- [ ] Dark mode assistant answer (spec section 3.4):
  - `font: 12.5px/1.8 Georgia, serif`
  - `color: var(--strict-text-body)` -> `rgba(255,255,255, 0.56)`
  - h2: `font: normal 14px/1.4 Georgia, serif`, `color: var(--strict-text-primary)`
  - strong: `color: rgba(255,255,255, 0.68)`, `font-weight: 600`
  - sup citations: spec section 3.4 styling with hover/active states
- [ ] Export `collectCitedSources` and `CitedEntry` from a shared module (or keep in chat-message and re-export)
- [ ] Should now be under 300 lines (down from ~915)

---

## Batch 4: Mobile Adaptations

**Depends on:** Batch 3 complete.

### Task 4.1: Mobile Layout Adjustments

**File:** `frontend/src/app/(app)/chat/page.tsx` (MODIFY)

- [ ] No sidebar rail on mobile — logo moves to header
- [ ] No separate glass pane edges — full-screen glass or full-bleed
- [ ] Jurisdiction pills in scrollable row below header

### Task 4.2: Mobile Source Bottom Sheet

**File:** `frontend/src/components/chat/mobile-source-sheet.tsx` (NEW)

- [ ] Citation tap -> source document slides up as bottom sheet (50% screen)
- [ ] Drag handle: 24px centered bar, `border-radius: 1px`
- [ ] Drag up to expand to full screen, drag down to dismiss
- [ ] Same source meta + document text styling as desktop
- [ ] `background: rgba(13,10,18, 0.95)`, `backdrop-filter: blur(24px)` (via CSS vars)
- [ ] Uses touch events for drag gesture
- [ ] `useEffect` cleanup for touch event listeners
- [ ] Under 200 lines

### Task 4.3: Mobile History Overlay

**File:** `frontend/src/components/chat/history-panel.tsx` (MODIFY — add mobile overlay mode)

- [ ] Full-screen glass overlay on mobile
- [ ] `background: rgba(13,10,18, 0.95)`, `backdrop-filter: blur(20px)` (via CSS vars)
- [ ] Close button (x) in header
- [ ] Same session list styling as desktop
- [ ] Safe-area-inset padding for notch devices

### Task 4.4: Mobile Input Adjustments

**File:** `frontend/src/components/chat/chat-input.tsx` (MODIFY)

- [ ] Same styling as desktop
- [ ] `padding-bottom: env(safe-area-inset-bottom)` for home indicator
- [ ] Keyboard-aware positioning (existing behavior)

---

## Batch 5: Streaming State

**Depends on:** Batch 3 complete.

### Task 5.1: Typewriter Cursor

**File:** `frontend/src/components/chat/chat-message.tsx` (MODIFY)

- [ ] During streaming, append a blinking gold cursor element after the last rendered character
- [ ] Cursor: `width: 1.5px`, `height: matching line-height`, `background: var(--strict-gold-base)`
- [ ] Animation: `cursor-blink 0.8s ease-in-out infinite` (defined in globals.css, Task 1.3)
- [ ] Only visible during `isStreaming === true`
- [ ] Light mode: keep existing streaming indicator

### Task 5.2: Pipeline Status During Streaming

**File:** `frontend/src/components/chat/pipeline-status-bar.tsx` (MODIFY)

- [ ] Active step shows text with pulsing dot
- [ ] Other completed steps show static dots
- [ ] Dot pulse: 1.5s ease-in-out infinite, opacity 0.4 -> 0.9 (via CSS animation)

### Task 5.3: Stop Button

**File:** `frontend/src/components/chat/chat-message.tsx` or `page.tsx` (MODIFY)

- [ ] Below answer text during streaming
- [ ] `padding: 5px 10px`, `border-radius: 5px`
- [ ] Gold glass styling, gold square icon (6x6px) + "Stop generating" text
- [ ] Clicking triggers existing `abort` handler from `use-query-stream.ts`
- [ ] No footnotes shown during streaming (appear after completion)

### Task 5.4: Auto-scroll Behavior

**File:** `frontend/src/app/(app)/chat/page.tsx` (VERIFY)

- [ ] Scroll to top of answer on new message (existing behavior)
- [ ] No fighting during streaming (existing behavior — already implemented with `isNearBottomRef`)
- [ ] Verify existing auto-scroll logic works with new collapsible turns

---

## Batch 6: Cleanup and Verification

**Depends on:** All previous batches complete.

### Task 6.1: Remove Old Components

**Files to delete:**
- [ ] `frontend/src/components/chat/strict-layout.tsx` (replaced by inline layout in page.tsx)
- [ ] `frontend/src/components/chat/strict-source-margin.tsx` (replaced by footnotes + source-panel-v2)
- [ ] `frontend/src/components/chat/strict-sidebar-rail.tsx` (replaced by sidebar-rail.tsx)
- [ ] `frontend/src/components/design-version-toggle.tsx` (no longer needed)

**Files to deprecate (keep but mark):**
- [ ] `frontend/src/lib/design-version.tsx` (keep for any third-party consumers, add deprecation comment)

### Task 6.2: Remove Dead CSS

**File:** `frontend/src/app/globals.css`

- [ ] Remove any remaining `.design-neon` / `.design-strict` selectors that weren't migrated
- [ ] Remove unused CSS classes that were only used by deleted components
- [ ] Verify no CSS references to removed components

### Task 6.3: Import Cleanup

**All modified files:**

- [ ] Remove unused imports (old design-version, old components)
- [ ] Verify no circular dependencies introduced
- [ ] Run `npm run build` to catch any TypeScript errors

### Task 6.4: Full Functionality Verification

Run through the preserved functionality checklist:

- [ ] Jurisdiction switching: click DIFC/CZ/UK/AU/Custom, verify corpus changes
- [ ] Long-press on UK/AU pill: verify law isolate behavior
- [ ] Multi-corpus warning: switch jurisdiction mid-conversation, verify warning banner
- [ ] Corpus blocking: try 3rd jurisdiction, verify "max 2" error
- [ ] Law selector: click UK/AU, verify law pills appear, toggle individual laws
- [ ] Custom corpus: select Custom, verify collection pills, "Upload documents" link
- [ ] Internet toggle: click Internet pill, verify state persists
- [ ] Session CRUD: new chat, switch session, delete session, verify persistence
- [ ] Empty state: verify preset questions per jurisdiction, click to preview, click to send
- [ ] Source grounding: click citation in answer, verify source panel opens with correct document
- [ ] Document index: verify toggle, highlight focused doc, click entry to open grounding
- [ ] Copy answer: verify copy button in feedback area works
- [ ] Feedback: thumbs up, thumbs down, comment submission, verify API call
- [ ] Streaming: send query, verify typewriter + cursor + pipeline bar + auto-scroll
- [ ] Error: trigger error (e.g., network off), verify error banner + dismiss
- [ ] Cmd+K: verify focuses input
- [ ] Follow-ups: verify suggestions appear after answer, click sends as new message
- [ ] Status polling: refresh during streaming, verify recovery
- [ ] Theme toggle: switch light/dark, verify both render correctly
- [ ] Language toggle: switch languages, verify all translated strings
- [ ] Collapsible turns: send 2+ messages, verify previous turns collapse
- [ ] Mobile: verify responsive layout, bottom sheet, history overlay
- [ ] Citation formats: verify both `[DOC-N]` and `[[source:...]]` render correctly

### Task 6.5: Force Rebuild and Visual Inspection

- [ ] `cd frontend && rm -rf .next && npm run build`
- [ ] Verify no build errors
- [ ] Test in browser: dark mode chat page matches spec
- [ ] Test in browser: light mode chat page unchanged from current
- [ ] Test mobile viewport: verify responsive behavior
- [ ] Check for FOUC on page load (should see correct theme immediately)

---

## File Inventory

### New Files (8)
| File | Lines (est.) | Batch |
|------|-------------|-------|
| `frontend/src/lib/color-mode.tsx` | ~90 | 1 |
| `frontend/src/components/theme-toggle.tsx` | ~50 | 1 |
| `frontend/src/components/chat/pipeline-status-bar.tsx` | ~120 | 2 |
| `frontend/src/components/chat/collapsible-turn.tsx` | ~100 | 2 |
| `frontend/src/components/chat/footnotes.tsx` | ~80 | 2 |
| `frontend/src/components/chat/feedback-buttons.tsx` | ~200 | 2 |
| `frontend/src/components/chat/source-panel-v2.tsx` | ~250 | 2 |
| `frontend/src/components/chat/sidebar-rail.tsx` | ~200 | 2 |
| `frontend/src/components/chat/history-panel.tsx` | ~250 | 2 |
| `frontend/src/components/chat/chat-header.tsx` | ~300 | 3 |
| `frontend/src/components/chat/mobile-source-sheet.tsx` | ~200 | 4 |

### Modified Files (8)
| File | Change | Batch |
|------|--------|-------|
| `frontend/src/app/layout.tsx` | FOUC script, providers | 1 |
| `frontend/src/app/globals.css` | CSS selector migration | 1 |
| `frontend/src/app/(app)/chat/page.tsx` | Major rewrite ~1850 -> ~600 lines | 3 |
| `frontend/src/components/chat/chat-message.tsx` | Extract footnotes/feedback, update props | 3 |
| `frontend/src/components/chat/chat-input.tsx` | Theme system migration, styling update | 2 |
| `frontend/src/components/chat/empty-state.tsx` | Styling update per spec | 2 |
| `frontend/src/components/chat/confidence-badge.tsx` | Theme migration, spec styling | 2 |
| 12 other consumer files | `useDesignVersion` -> `useColorMode` | 1 |

### Deleted Files (4)
| File | Batch |
|------|-------|
| `frontend/src/components/chat/strict-layout.tsx` | 6 |
| `frontend/src/components/chat/strict-source-margin.tsx` | 6 |
| `frontend/src/components/chat/strict-sidebar-rail.tsx` | 6 |
| `frontend/src/components/design-version-toggle.tsx` | 6 |

---

## Dependency Graph

```
Batch 1 (sequential within, but tasks 1.1-1.5 can partially overlap)
  1.1 ColorModeContext
  1.2 FOUC script (depends on 1.1)
  1.3 CSS migration (independent of 1.1)
  1.4 Consumer migration (depends on 1.1)
  1.5 Theme toggle (depends on 1.1)

Batch 2 (all parallel, independent of each other, depends on Batch 1)
  2.1 PipelineStatusBar
  2.2 CollapsibleTurn
  2.3 Footnotes
  2.4 FeedbackButtons
  2.5 SourcePanelV2
  2.6 SidebarRail
  2.7 EmptyState
  2.8 ChatInput
  2.9 ConfidenceBadge
  2.10 HistoryPanel

Batch 3 (depends on Batch 1 + 2)
  3.1 page.tsx rewrite (depends on all Batch 2 components)
  3.2 ChatHeader extraction (can happen with 3.1)
  3.3 ChatMessage update (can happen with 3.1)

Batch 4 (depends on Batch 3)
  4.1 Mobile layout
  4.2 Mobile source sheet
  4.3 Mobile history
  4.4 Mobile input

Batch 5 (depends on Batch 3)
  5.1 Typewriter cursor
  5.2 Pipeline streaming
  5.3 Stop button
  5.4 Auto-scroll

Batch 6 (depends on ALL)
  6.1 Delete old files
  6.2 Dead CSS removal
  6.3 Import cleanup
  6.4 Functionality verification
  6.5 Build + visual inspection
```

---

## Risk Mitigation

1. **FOUC regression**: The FOUC prevention script is critical. Test by hard-refreshing with both dark and light modes saved. The inline script must run synchronously before first paint.

2. **Citation chain integrity**: Never re-order [DOC-N] labels. The `collectCitedSources` function and `remarkInlineCitations`/`rehypeInlineCitations` plugins must be preserved byte-for-byte.

3. **Streaming race conditions**: The `useStrictTypewriter` pattern and `activeAssistantId.current` ref tracking must be preserved. Do not introduce new state that could cause re-renders during streaming.

4. **CSS variable cascading**: All `.dark` variables must cascade correctly. Test that nested components (e.g., footnotes inside message inside glass pane) receive the correct variable values.

5. **Mobile safe areas**: The `env(safe-area-inset-*)` values must be preserved for iOS notch devices. Test on Safari iOS.

6. **Session data**: The `useChatState` hook and localStorage session format must not change. Only the theme key migration is allowed.

7. **Light mode regression**: Since light mode (Neon) is unchanged, verify that the CSS selector migration (`.design-neon` -> `.light`) doesn't break any Neon styling. Run a before/after visual comparison.
