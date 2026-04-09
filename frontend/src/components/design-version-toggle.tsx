"use client";

import { useRef } from "react";
import { motion, MotionConfig, AnimatePresence } from "motion/react";
import { useDesignVersion, type DesignVersion } from "@/lib/design-version";
import { V3_SPRING } from "@/lib/v3-motion";

// ─── Option definitions ────────────────────────────────────────────────────────

const OPTIONS: Array<{
    value: DesignVersion;
    label: string;
    /** CSS gradient representing this design's color signature */
    swatch: string;
}> = [
    {
        value: "neon",
        label: "Neon",
        swatch: "linear-gradient(135deg, #1E40AF 0%, #4F46E5 100%)",
    },
    {
        value: "strict",
        label: "Strict",
        swatch: "linear-gradient(135deg, rgba(201,168,76,0.3), rgba(201,168,76,0.1))",
    },
];

// ─── Style helpers ─────────────────────────────────────────────────────────────

type Variant = "dark" | "light" | "v2-light" | undefined;

/** Whether the placement surface is dark (needs light text). */
function isDarkSurface(variant: Variant): boolean {
    return variant === "dark" || variant === undefined;
}

/** Whether to use Neon-style accents (indigo/slate) instead of Strict gold. */
function isV2Accent(variant: Variant, version: DesignVersion): boolean {
    return variant === "light" || variant === "v2-light" || version === "neon";
}

function getTrackStyle(variant: Variant, version: DesignVersion): React.CSSProperties {
    const v2 = isV2Accent(variant, version);
    const dark = isDarkSurface(variant);

    if (v2 && !dark) {
        // V2 light: cool-slate background, indigo border
        return {
            background: "rgba(241,245,249,0.92)",
            border: "0.5px solid rgba(99,102,241,0.20)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
        };
    }

    if (version === "strict") {
        // Strict: glass surface, gold-tinted border
        return {
            background: "var(--strict-glass-bg)",
            border: "0.5px solid var(--strict-gold-border-active)",
            backdropFilter: "blur(16px) saturate(140%)",
            WebkitBackdropFilter: "blur(16px) saturate(140%)",
        };
    }

    // Default dark glass (V2 dark nav or no-variant default)
    return {
        background: "rgba(255,255,255,0.09)",
        border: "0.5px solid rgba(255,255,255,0.14)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
    };
}

function getActivePillStyle(
    optionValue: DesignVersion,
    variant: Variant,
    version: DesignVersion
): React.CSSProperties {
    // Neon option or Neon-style context: indigo accent
    if (optionValue === "neon" || isV2Accent(variant, version)) {
        return {
            background: "rgba(79,70,229,0.12)",
            border: "0.5px solid rgba(99,102,241,0.32)",
            boxShadow: "0 1px 4px rgba(79,70,229,0.10)",
        };
    }
    // Strict option in Strict context: gold accent
    return {
        background: "var(--strict-gold-badge-bg)",
        border: "0.5px solid var(--strict-gold-border-active)",
        boxShadow: "0 0 10px var(--strict-hiw-progress-track)",
    };
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function DesignVersionToggle(
    { variant }: { variant?: "dark" | "light" | "v2-light" } = {}
) {
    const { version, setVersion } = useDesignVersion();
    const buttonRefs = useRef<Map<DesignVersion, HTMLButtonElement | null>>(new Map());

    const dark = isDarkSurface(variant);

    const handleKeyDown = (
        e: React.KeyboardEvent<HTMLButtonElement>,
        current: DesignVersion
    ) => {
        let next: DesignVersion | null = null;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
            e.preventDefault();
            next = current === "neon" ? "strict" : "neon";
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
            e.preventDefault();
            next = current === "strict" ? "neon" : "strict";
        }
        if (next) {
            setVersion(next);
            buttonRefs.current.get(next)?.focus();
        }
    };

    return (
        <MotionConfig reducedMotion="user">
            <div
                role="tablist"
                aria-label="Design version"
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    borderRadius: 9999,
                    padding: "2px",
                    position: "relative",
                    ...getTrackStyle(variant, version),
                }}
            >
                {OPTIONS.map(({ value, label, swatch }) => {
                    const isActive = version === value;
                    // Strict gets a faint gold glow on its label when active
                    const isStrictActive = value === "strict" && isActive;

                    const textColor = dark
                        ? isActive ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.40)"
                        : isActive ? "#0D0F1A" : "rgba(13,15,26,0.42)";

                    return (
                        <button
                            key={value}
                            ref={(el) => { buttonRefs.current.set(value, el); }}
                            type="button"
                            role="tab"
                            aria-selected={isActive}
                            aria-label={`Switch to ${label} design`}
                            tabIndex={isActive ? 0 : -1}
                            onClick={() => setVersion(value)}
                            onKeyDown={(e) => handleKeyDown(e, value)}
                            style={{
                                position: "relative",
                                display: "flex",
                                alignItems: "center",
                                gap: 5,
                                padding: "3px 9px 3px 7px",
                                borderRadius: 9999,
                                border: "none",
                                cursor: "pointer",
                                background: "transparent",
                                fontSize: 11.5,
                                fontWeight: isActive ? 500 : 400,
                                color: textColor,
                                letterSpacing: "0.01em",
                                transition: "color 0.12s ease",
                                whiteSpace: "nowrap",
                                zIndex: 1,
                                minHeight: 24,
                                fontFamily:
                                    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                            }}
                        >
                            {/* Sliding active pill — spring-animated between options */}
                            <AnimatePresence initial={false}>
                                {isActive && (
                                    <motion.span
                                        key="design-toggle-pill"
                                        layoutId="design-toggle-pill"
                                        transition={V3_SPRING.micro}
                                        aria-hidden="true"
                                        style={{
                                            position: "absolute",
                                            inset: 0,
                                            borderRadius: 9999,
                                            ...getActivePillStyle(value, variant, version),
                                        }}
                                    />
                                )}
                            </AnimatePresence>

                            {/* Design signature swatch */}
                            <span
                                aria-hidden="true"
                                style={{
                                    display: "inline-block",
                                    width: 7,
                                    height: 7,
                                    borderRadius: 2,
                                    flexShrink: 0,
                                    background: swatch,
                                    opacity: isActive ? 1 : 0.45,
                                    transition: "opacity 0.12s ease",
                                    position: "relative",
                                    zIndex: 1,
                                }}
                            />

                            {/* Label — always visible; Strict label glows gold when active */}
                            <span
                                style={{
                                    position: "relative",
                                    zIndex: 1,
                                    transition: "text-shadow 0.3s ease",
                                    textShadow: isStrictActive
                                        ? "0 0 10px var(--strict-gold-underbar)"
                                        : "none",
                                }}
                            >
                                {label}
                            </span>
                        </button>
                    );
                })}
            </div>
        </MotionConfig>
    );
}
