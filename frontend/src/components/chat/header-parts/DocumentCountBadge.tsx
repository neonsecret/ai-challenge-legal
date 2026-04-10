"use client"

import {FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"

interface DocumentCountBadgeProps {
    count: number
    max?: number
    isStrict: boolean
}

/**
 * Compact document count badge shown near the jurisdiction row.
 * Hidden when count === 0. Turns gold when count === max.
 */
export function DocumentCountBadge({count, max = 3, isStrict}: DocumentCountBadgeProps) {
    if (count === 0) return null

    const maxed = count >= max

    const bg = maxed
        ? "var(--doc-count-badge-maxed-bg)"
        : "var(--doc-count-badge-bg)"
    const border = maxed
        ? "var(--doc-count-badge-maxed-border)"
        : "var(--doc-count-badge-border)"
    const color = maxed
        ? "var(--doc-count-badge-maxed-color)"
        : "var(--doc-count-badge-color)"

    return (
        <span
            title={maxed ? `Maximum ${max} documents reached` : `${count} of ${max} documents`}
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 2,
                padding: `1px ${SPACE[2]}px`,
                borderRadius: RADIUS.full,
                background: bg,
                border,
                color,
                fontFamily: isStrict ? "Georgia, serif" : FONT.sans,
                fontSize: TYPE_SCALE.xs,
                fontWeight: isStrict ? 400 : 600,
                whiteSpace: "nowrap",
                flexShrink: 0,
                userSelect: "none",
            }}
        >
            {count}&thinsp;/&thinsp;{max}
        </span>
    )
}
