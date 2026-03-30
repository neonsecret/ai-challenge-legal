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
        base: "#C9A84C",
        light: "#d4a843",
        /** Solid active background */
        solid: "rgba(201,168,76,0.75)",
        /** Subtle tinted background */
        tint: "rgba(201,168,76,0.14)",
        /** Border for active/highlighted elements */
        border: "rgba(201,168,76,0.40)",
        /** Faint glow */
        glow: "rgba(201,168,76,0.25)",
    },
    teal: {
        base: "#38B2AC",
        tint: "rgba(56,178,172,0.14)",
        border: "rgba(56,178,172,0.35)",
    },
    bronze: {
        base: "#d4956b",
        tint: "rgba(212,149,107,0.14)",
    },
    blue: {
        base: "#3576ae",
        tint: "rgba(53,118,174,0.18)",
        border: "rgba(53,118,174,0.38)",
    },
} as const

/** Dark theme text opacity levels */
export const TEXT_DARK = {
    primary: "rgba(255,255,255,0.92)",
    secondary: "rgba(255,255,255,0.72)",
    tertiary: "rgba(255,255,255,0.45)",
    quaternary: "rgba(255,255,255,0.25)",
} as const

/** Light theme text colors */
export const TEXT_LIGHT = {
    primary: "#1a0e04",
    secondary: "#2e1f08",
    tertiary: "rgba(46,31,8,0.55)",
    quaternary: "rgba(46,31,8,0.25)",
} as const

// ─── Glass ───────────────────────────────────────────────────────────────────

export const GLASS = {
    dark: {
        bg: "rgba(255,255,255,0.07)",
        bgSubtle: "rgba(255,255,255,0.04)",
        bgHover: "rgba(255,255,255,0.12)",
        border: "rgba(255,255,255,0.14)",
        borderSubtle: "rgba(255,255,255,0.08)",
        blur: "blur(40px) saturate(180%) brightness(108%)",
        blurLight: "blur(16px) saturate(160%)",
        innerGlow: "inset 0 1px 0 rgba(255,255,255,0.10)",
        shadow: "0 20px 60px rgba(0,0,0,0.40)",
    },
    light: {
        bg: "rgba(255,255,255,0.45)",
        bgSubtle: "rgba(255,255,255,0.22)",
        bgHover: "rgba(255,255,255,0.55)",
        border: "rgba(255,255,255,0.55)",
        borderSubtle: "rgba(255,255,255,0.35)",
        blur: "blur(40px) saturate(180%) brightness(108%)",
        blurLight: "blur(16px) saturate(160%)",
        innerGlow: "inset 0 1.5px 0 rgba(255,255,255,0.80)",
        shadow: "0 20px 60px rgba(100,50,0,0.08)",
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
        bg: "rgba(255,255,255,0.05)",
        border: "rgba(255,255,255,0.10)",
        footnoteBg: "rgba(255,255,255,0.03)",
    },
    light: {
        bg: "rgba(255,255,255,0.50)",
        border: "rgba(255,255,255,0.60)",
        footnoteBg: "rgba(245,240,230,0.40)",
    },
} as const
