"use client";

import { useDesignVersion } from "@/lib/design-version";

interface DesignVersionToggleProps {
    /**
     * "dark" — gold accent (used on dark/navy nav backgrounds).
     * "light" — slate/sepia accent (used on light/warm nav backgrounds).
     */
    variant?: "dark" | "light";
}

const VARIANTS = {
    dark: {
        border: "1px solid rgba(201,168,76,0.22)",
        activeBackground: "rgba(201,168,76,0.14)",
        activeColor: "#C9A84C",
        inactiveColor: "rgba(255,255,255,0.35)",
    },
    light: {
        border: "1px solid rgba(92,46,8,0.18)",
        activeBackground: "rgba(92,46,8,0.10)",
        activeColor: "#5c2e08",
        inactiveColor: "rgba(92,46,8,0.35)",
    },
} as const;

export function DesignVersionToggle({ variant = "dark" }: DesignVersionToggleProps) {
    const { version, setVersion } = useDesignVersion();
    const isV2 = version === "v2";
    const styles = VARIANTS[variant];

    return (
        <button
            onClick={() => setVersion(isV2 ? "v1" : "v2")}
            style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: 28,
                padding: "0 10px",
                borderRadius: 8,
                border: styles.border,
                background: isV2 ? styles.activeBackground : "transparent",
                cursor: "pointer",
                color: isV2 ? styles.activeColor : styles.inactiveColor,
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.04em",
                transition: "all 0.15s ease",
            }}
            aria-label={`Switch to ${isV2 ? "Classic" : "Modern"} design`}
        >
            {isV2 ? "Classic" : "Modern"}
        </button>
    );
}
