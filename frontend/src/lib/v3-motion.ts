/**
 * V3 motion tokens (used by both Neon and Strict designs).
 *
 * Spring physics presets and animation variants for Framer Motion.
 * Import these instead of inline configs to ensure consistency across
 * all V3 components.
 */

import type { Variants, Transition } from "motion/react";

// ─── Spring presets ───────────────────────────────────────────────────────────

export const V3_SPRING = {
    /** Micro-interactions: hover states, button press, icon nudge */
    micro: { type: "spring", stiffness: 500, damping: 30, mass: 0.8 } satisfies Transition,

    /** Standard: panel open/close, card lift, dropdown */
    standard: { type: "spring", stiffness: 300, damping: 25, mass: 1.0 } satisfies Transition,

    /** Gentle: page transitions, list stagger entrance */
    gentle: { type: "spring", stiffness: 180, damping: 20, mass: 1.2 } satisfies Transition,

    /** Snappy: command palette, context menu, tooltip */
    snappy: { type: "spring", stiffness: 400, damping: 28, mass: 0.9 } satisfies Transition,

    /** Bouncy: success states, notification pop, badge */
    bouncy: { type: "spring", stiffness: 350, damping: 18, mass: 0.8 } satisfies Transition,
} as const;

// ─── Stagger configs ─────────────────────────────────────────────────────────

export const V3_STAGGER = {
    /** Card grid, feature list */
    fast: { staggerChildren: 0.04 } satisfies Transition,
    /** Section content */
    standard: { staggerChildren: 0.06 } satisfies Transition,
    /** Hero headline words */
    slow: { staggerChildren: 0.10 } satisfies Transition,
} as const;

// ─── Variants ────────────────────────────────────────────────────────────────

/** Standard fade-up entrance for panels, cards, sections */
export const V3_FADE_UP: Variants = {
    hidden: { opacity: 0, y: 12, scale: 0.98 },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: V3_SPRING.gentle,
    },
    exit: {
        opacity: 0,
        y: -8,
        scale: 0.98,
        transition: { duration: 0.15, ease: "easeIn" },
    },
};

/** Staggered list container — use with V3_ITEM_VARIANT on children */
export const V3_LIST_VARIANT: Variants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { ...V3_STAGGER.standard, delayChildren: 0.05 },
    },
};

/** Individual list/grid item */
export const V3_ITEM_VARIANT: Variants = {
    hidden: { opacity: 0, y: 8 },
    visible: { opacity: 1, y: 0, transition: V3_SPRING.gentle },
};

/** Glass panel — used for modals, drawers, sheets */
export const V3_GLASS_PANEL: Variants = {
    hidden: { opacity: 0, scale: 0.97, y: 6 },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: V3_SPRING.snappy,
    },
    exit: {
        opacity: 0,
        scale: 0.97,
        y: 4,
        transition: { duration: 0.18, ease: "easeIn" },
    },
};

/** Command palette / floating panel — drops in from above */
export const V3_COMMAND_PALETTE: Variants = {
    hidden: { opacity: 0, scale: 0.95, y: -8 },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: V3_SPRING.snappy,
    },
    exit: {
        opacity: 0,
        scale: 0.95,
        y: -6,
        transition: { duration: 0.14, ease: "easeIn" },
    },
};

// ─── Interactive props ────────────────────────────────────────────────────────

/** 3D lift on hover — for cards, source panels */
export const V3_CARD_HOVER = {
    whileHover: {
        y: -4,
        scale: 1.005,
        transition: V3_SPRING.micro,
    },
    whileTap: {
        y: 0,
        scale: 0.99,
        transition: V3_SPRING.micro,
    },
} as const;

/** Button press feedback */
export const V3_BUTTON_PRESS = {
    whileHover: { scale: 1.02, transition: V3_SPRING.micro },
    whileTap: { scale: 0.97, transition: V3_SPRING.micro },
} as const;

/** Icon nudge — for interactive icons */
export const V3_ICON_NUDGE = {
    whileHover: { rotate: 8, scale: 1.1, transition: V3_SPRING.bouncy },
} as const;

// ─── Global motion config ─────────────────────────────────────────────────────

/**
 * Place at the root of the V3 layout tree:
 *
 *   import { MotionConfig } from "motion/react";
 *   import { V3_MOTION_CONFIG } from "@/lib/v3-motion";
 *   ...
 *   <MotionConfig {...V3_MOTION_CONFIG}>{children}</MotionConfig>
 *
 * `reducedMotion: "user"` makes Framer Motion respect the OS
 * prefers-reduced-motion setting for ALL JS-driven spring animations,
 * closing the gap that CSS @media (prefers-reduced-motion) cannot cover.
 */
export const V3_MOTION_CONFIG = {
    reducedMotion: "user" as const,
};
