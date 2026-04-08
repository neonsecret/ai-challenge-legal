"use client";

import { motion, MotionConfig } from "motion/react";
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
        value: "v2",
        label: "Modern",
        swatch: "linear-gradient(135deg, #1E40AF 0%, #4F46E5 100%)",
    },
    {
        value: "v3",
        label: "Luminous",
        swatch: "linear-gradient(135deg, #7B5EA7 0%, #4F8FD4 55%, #2DD4BF 100%)",
    },
];

// ─── Style helpers ─────────────────────────────────────────────────────────────

type Variant = "dark" | "light" | "v2-light" | undefined;

/** Whether the placement surface is dark (needs light text). */
function isDarkSurface(variant: Variant): boolean {
    return variant === "dark" || variant === undefined;
}

/** Whether to use V2-style accents (indigo/slate) instead of V3 iris. */
function useV2Accent(variant: Variant, version: DesignVersion): boolean {
    return variant === "light" || variant === "v2-light" || version === "v2";
}

function getTrackStyle(variant: Variant, version: DesignVersion): React.CSSProperties {
    const v2 = useV2Accent(variant, version);
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

    if (version === "v3") {
        // V3: glass surface, iris-tinted border
        return {
            background: "rgba(255,255,255,0.10)",
            border: "0.5px solid rgba(123,94,167,0.24)",
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
    // V2 option or V2-style context: indigo accent
    if (optionValue === "v2" || useV2Accent(variant, version)) {
        return {
            background: "rgba(79,70,229,0.12)",
            border: "0.5px solid rgba(99,102,241,0.32)",
            boxShadow: "0 1px 4px rgba(79,70,229,0.10)",
        };
    }
    // V3 option in V3 context: iris accent
    return {
        background: "rgba(123,94,167,0.18)",
        border: "0.5px solid rgba(123,94,167,0.38)",
        boxShadow: "0 0 10px rgba(123,94,167,0.16)",
    };
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function DesignVersionToggle(
    { variant }: { variant?: "dark" | "light" | "v2-light" } = {}
) {
    const { version, setVersion } = useDesignVersion();

    const dark = isDarkSurface(variant);

    const handleKeyDown = (
        e: React.KeyboardEvent<HTMLButtonElement>,
        current: DesignVersion
    ) => {
        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
            e.preventDefault();
            setVersion(current === "v2" ? "v3" : "v2");
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
            e.preventDefault();
            setVersion(current === "v3" ? "v2" : "v3");
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
                    // Luminous gets a faint aurora glow on its label when active
                    const isLuminousActive = value === "v3" && isActive;

                    const textColor = dark
                        ? isActive ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.40)"
                        : isActive ? "#0D0F1A" : "rgba(13,15,26,0.42)";

                    return (
                        <button
                            key={value}
                            role="tab"
                            aria-selected={isActive}
                            aria-label={`Switch to ${label} design`}
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
                            {isActive && (
                                <motion.span
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

                            {/* Label — always visible; Luminous label glows when active */}
                            <span
                                style={{
                                    position: "relative",
                                    zIndex: 1,
                                    transition: "text-shadow 0.3s ease",
                                    textShadow: isLuminousActive
                                        ? "0 0 12px var(--v3-aurora-glow, #60A5FA)"
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
