/**
 * Non-theme design tokens — layout, typography, animation.
 * These are stable values that don't vary by theme/mode.
 *
 * Theme-dependent tokens (color, glass, text) are CSS custom properties
 * (--dt-*) defined in globals.css. Use them directly as "var(--dt-...)".
 */

// ─── Typography ──────────────────────────────────────────────────────────────

export const FONT = {
    /** Body text, UI elements, headings */
    sans: "var(--font-sans), -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
    /** Brand mark only ("Vitreon Legal" wordmark) */
    brand: "Georgia, 'Times New Roman', serif",
    /** Source document IDs in grounding panel */
    mono: "'SF Mono', 'Fira Code', 'Cascadia Code', monospace",
} as const

export const TYPE_SCALE = {
    /** Meta labels, source chip text, footnotes */
    xs: 11,
    /** Body text, answers, list items */
    sm: 13,
    /** Subheadings, status labels */
    md: 15,
    /** Section headings in answers */
    lg: 18,
    /** Page titles (rarely used) */
    xl: 28,
} as const

// ─── Spacing (4px grid) ──────────────────────────────────────────────────────

export const SPACE = {
    '1': 4,
    '2': 8,
    '3': 12,
    '4': 16,
    '5': 20,
    '6': 24,
    '8': 32,
    '10': 40,
    '12': 48,
} as const

// ─── Radii ───────────────────────────────────────────────────────────────────

export const RADIUS = {
    xs: 4,
    sm: 6,
    md: 8,
    lg: 12,
    xl: 16,
    '2xl': 24,
    full: 9999,
} as const

// ─── Animation ───────────────────────────────────────────────────────────────

export const TIMING = {
    /** Micro-feedback: hovers, clicks */
    instant: "0.1s",
    /** Small transitions: toggles, pills */
    fast: "0.15s",
    /** Medium: modals, panels */
    medium: "0.25s",
    /** Large: page transitions, drawers */
    slow: "0.35s",
} as const

export const EASE = {
    out: "cubic-bezier(0.16, 1, 0.3, 1)",
    in: "cubic-bezier(0.55, 0, 1, 0.45)",
    inOut: "cubic-bezier(0.65, 0, 0.35, 1)",
    spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
} as const

// ─── Step colors (agent trace / streaming status) ────────────────────────────
// Kept as hardcoded hex because streaming status appends hex opacity suffixes.

export const STEP_COLOR = {
    thinking: "#d4956b",
    search: "#3576ae",
    web: "#38B2AC",
    found: "#C9A84C",
    answer: "#C9A84C",
    connecting: "#d4956b",
    default: "#d4956b",
} as const
