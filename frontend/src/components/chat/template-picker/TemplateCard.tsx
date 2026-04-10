"use client"

import {useColorMode} from "@/lib/color-mode"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import type {Template} from "@/types/documents"

interface TemplateCardProps {
    template: Template
    onSelect: (slug: string) => void
}

export function TemplateCard({template, onSelect}: TemplateCardProps) {
    const {isDark} = useColorMode()

    return (
        <button
            onClick={() => onSelect(template.slug)}
            style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                gap: SPACE[2],
                padding: SPACE[4],
                borderRadius: RADIUS.lg,
                width: "100%",
                textAlign: "left",
                cursor: "pointer",
                background: isDark
                    ? "rgba(255,255,255,0.03)"
                    : "rgba(255,255,255,0.55)",
                border: isDark
                    ? "1px solid rgba(201,168,76,0.06)"
                    : "0.5px solid rgba(255,255,255,0.60)",
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                transition: `all ${TIMING.fast} ${EASE.out}`,
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.background = isDark
                    ? "rgba(201,168,76,0.07)"
                    : "rgba(201,168,76,0.06)"
                e.currentTarget.style.borderColor = isDark
                    ? "rgba(201,168,76,0.18)"
                    : "rgba(196,124,0,0.25)"
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.background = isDark
                    ? "rgba(255,255,255,0.03)"
                    : "rgba(255,255,255,0.55)"
                e.currentTarget.style.borderColor = isDark
                    ? "rgba(201,168,76,0.06)"
                    : "rgba(255,255,255,0.60)"
            }}
        >
            {/* Name */}
            <span style={{
                fontFamily: "Georgia, serif",
                fontSize: TYPE_SCALE.sm,
                fontWeight: "normal",
                color: isDark ? "var(--strict-text-primary)" : "#1a1006",
                lineHeight: 1.4,
            }}>
                {template.name}
            </span>

            {/* Description */}
            {template.description && (
                <span style={{
                    fontFamily: FONT.sans,
                    fontSize: TYPE_SCALE.xs,
                    color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a",
                    lineHeight: 1.5,
                }}>
                    {template.description}
                </span>
            )}

            {/* Badges */}
            <div style={{display: "flex", gap: SPACE[1], flexWrap: "wrap", marginTop: SPACE[1]}}>
                <Badge label={template.jurisdiction} isDark={isDark} variant="jurisdiction" />
                <Badge label={template.category} isDark={isDark} variant="category" />
            </div>
        </button>
    )
}

function Badge({label, isDark, variant}: {label: string; isDark: boolean; variant: "jurisdiction" | "category"}) {
    const isJurisdiction = variant === "jurisdiction"
    return (
        <span style={{
            fontFamily: FONT.sans,
            fontSize: TYPE_SCALE.xs - 1,
            fontWeight: 500,
            padding: `1px ${SPACE[2]}px`,
            borderRadius: RADIUS.full,
            background: isJurisdiction
                ? (isDark ? "rgba(201,168,76,0.08)" : "rgba(196,124,0,0.08)")
                : (isDark ? "rgba(255,255,255,0.05)" : "rgba(92,46,8,0.06)"),
            border: isJurisdiction
                ? (isDark ? "1px solid rgba(201,168,76,0.15)" : "0.5px solid rgba(196,124,0,0.20)")
                : (isDark ? "1px solid rgba(255,255,255,0.08)" : "0.5px solid rgba(92,46,8,0.12)"),
            color: isJurisdiction
                ? (isDark ? "var(--strict-gold-text)" : "#7a4a00")
                : (isDark ? "var(--strict-text-secondary)" : "#5c3d1a"),
            textTransform: "uppercase" as const,
            letterSpacing: "0.06em",
        }}>
            {label}
        </span>
    )
}
