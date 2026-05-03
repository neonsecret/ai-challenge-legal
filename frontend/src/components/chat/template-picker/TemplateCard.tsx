"use client"

import {useState} from "react"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import type {Template} from "@/types/documents"

interface TemplateCardProps {
    template: Template
    onSelect: (template: {slug: string; name: string; jurisdiction?: string}) => void
}

export function TemplateCard({template, onSelect}: TemplateCardProps) {
    const [active, setActive] = useState(false)

    return (
        <button
            onClick={() => onSelect({slug: template.slug, name: template.name, jurisdiction: template.jurisdiction || undefined})}
            onMouseEnter={() => setActive(true)}
            onMouseLeave={() => setActive(false)}
            onTouchStart={() => setActive(true)}
            onTouchEnd={() => setActive(false)}
            onTouchCancel={() => setActive(false)}
            style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                gap: SPACE[2],
                padding: SPACE[4],
                borderRadius: RADIUS.lg,
                width: "100%",
                minHeight: 144,
                textAlign: "left",
                cursor: "pointer",
                overflow: "visible",
                background: active ? "var(--doc-card-hover-bg)" : "var(--doc-card-bg)",
                border: `1px solid ${active ? "var(--doc-card-hover-border)" : "var(--doc-card-border)"}`,
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                transition: `all ${TIMING.fast} ${EASE.out}`,
            }}
        >
            <span style={{
                fontFamily: "Georgia, serif",
                fontSize: TYPE_SCALE.sm,
                fontWeight: "normal",
                color: "var(--doc-text-primary)",
                lineHeight: 1.5,
                textTransform: "uppercase" as const,
                letterSpacing: "0.06em",
                width: "100%",
                wordBreak: "break-word",
                overflowWrap: "break-word",
                hyphens: "auto",
            }}>
                {template.name}
            </span>

            {template.description && (
                <span style={{
                    fontFamily: FONT.sans,
                    fontSize: TYPE_SCALE.xs,
                    color: "var(--doc-text-secondary)",
                    lineHeight: 1.5,
                    wordBreak: "break-word",
                    overflowWrap: "break-word",
                    width: "100%",
                }}>
                    {template.description}
                </span>
            )}

            <div style={{display: "flex", gap: SPACE[1], flexWrap: "wrap", marginTop: "auto"}}>
                <Badge label={template.jurisdiction} variant="jurisdiction" />
                <Badge label={template.category} variant="category" />
            </div>
        </button>
    )
}

function Badge({label, variant}: {label: string; variant: "jurisdiction" | "category"}) {
    const isJurisdiction = variant === "jurisdiction"
    return (
        <span style={{
            fontFamily: FONT.sans,
            fontSize: TYPE_SCALE.xs - 1,
            fontWeight: 500,
            padding: `1px ${SPACE[2]}px`,
            borderRadius: RADIUS.full,
            background: isJurisdiction ? "var(--doc-gold-card-bg)" : "var(--doc-pill-inactive-bg)",
            border: isJurisdiction
                ? "1px solid var(--doc-gold-card-border)"
                : "1px solid var(--doc-pill-inactive-border)",
            color: isJurisdiction ? "var(--doc-text-label)" : "var(--doc-text-secondary)",
            textTransform: "uppercase" as const,
            letterSpacing: "0.06em",
            flexShrink: 0,
        }}>
            {label}
        </span>
    )
}
