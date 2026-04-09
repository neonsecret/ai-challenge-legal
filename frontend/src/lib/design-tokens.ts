/**
 * Design tokens for Vitreon Legal UI.
 *
 * ALL visual constants live here. Components import from this file
 * instead of using magic numbers. To change the look, edit this file.
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

// ─── Spacing (4px grid) ─────────────────────────────────────────────────────

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

// ─── Colors ──────────────────────────────────────────────────────────────────

export const COLOR = {
    gold: {
        base: "var(--dt-color-gold-base)",
        light: "var(--dt-color-gold-light)",
        /** Solid active background */
        solid: "var(--dt-color-gold-solid)",
        /** Subtle tinted background */
        tint: "var(--dt-color-gold-tint)",
        /** Border for active/highlighted elements */
        border: "var(--dt-color-gold-border)",
        /** Faint glow */
        glow: "var(--dt-color-gold-glow)",
    },
    teal: {
        base: "var(--dt-color-teal-base)",
        tint: "var(--dt-color-teal-tint)",
        border: "var(--dt-color-teal-border)",
    },
    bronze: {
        base: "var(--dt-color-bronze-base)",
        tint: "var(--dt-color-bronze-tint)",
    },
    blue: {
        base: "var(--dt-color-blue-base)",
        tint: "var(--dt-color-blue-tint)",
        border: "var(--dt-color-blue-border)",
    },
} as const

/** Dark theme text opacity levels */
export const TEXT_DARK = {
    primary: "var(--dt-text-dark-primary)",
    secondary: "var(--dt-text-dark-secondary)",
    tertiary: "var(--dt-text-dark-tertiary)",
    quaternary: "var(--dt-text-dark-quaternary)",
} as const

/** Light theme text colors */
export const TEXT_LIGHT = {
    primary: "var(--dt-text-light-primary)",
    secondary: "var(--dt-text-light-secondary)",
    tertiary: "var(--dt-text-light-tertiary)",
    quaternary: "var(--dt-text-light-quaternary)",
} as const

// ─── Glass ───────────────────────────────────────────────────────────────────

export const GLASS = {
    dark: {
        bg: "var(--dt-glass-dark-bg)",
        bgSubtle: "var(--dt-glass-dark-bg-subtle)",
        bgHover: "var(--dt-glass-dark-bg-hover)",
        border: "var(--dt-glass-dark-border)",
        borderSubtle: "var(--dt-glass-dark-border-subtle)",
        blur: "var(--dt-glass-dark-blur)",
        blurLight: "var(--dt-glass-dark-blur-light)",
        innerGlow: "var(--dt-glass-dark-inner-glow)",
        shadow: "var(--dt-glass-dark-shadow)",
    },
    light: {
        bg: "var(--dt-glass-light-bg)",
        bgSubtle: "var(--dt-glass-light-bg-subtle)",
        bgHover: "var(--dt-glass-light-bg-hover)",
        border: "var(--dt-glass-light-border)",
        borderSubtle: "var(--dt-glass-light-border-subtle)",
        blur: "var(--dt-glass-light-blur)",
        blurLight: "var(--dt-glass-light-blur-light)",
        innerGlow: "var(--dt-glass-light-inner-glow)",
        shadow: "var(--dt-glass-light-shadow)",
    },
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

export const STEP_COLOR = {
    thinking: COLOR.bronze.base,
    search: COLOR.blue.base,
    web: COLOR.teal.base,
    found: COLOR.gold.base,
    answer: COLOR.gold.base,
    connecting: COLOR.bronze.base,
    default: COLOR.bronze.base,
} as const

// ─── Answer card ─────────────────────────────────────────────────────────────

export const ANSWER_CARD = {
    dark: {
        bg: "var(--dt-answer-dark-bg)",
        border: "var(--dt-answer-dark-border)",
        footnoteBg: "var(--dt-answer-dark-footnote-bg)",
    },
    light: {
        bg: "var(--dt-answer-light-bg)",
        border: "var(--dt-answer-light-border)",
        footnoteBg: "var(--dt-answer-light-footnote-bg)",
    },
} as const
