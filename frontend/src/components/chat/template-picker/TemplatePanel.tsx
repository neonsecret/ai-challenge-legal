"use client"

import {useEffect, useState, useCallback} from "react"
import {motion, AnimatePresence} from "motion/react"
import {X} from "lucide-react"
import {useColorMode} from "@/lib/color-mode"
import {useIsMobile} from "@/hooks/use-mobile"
import {useTemplates} from "@/hooks/use-templates"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {TemplateCard} from "./TemplateCard"
import type {Template} from "@/types/documents"

const JURISDICTIONS = ["CZ", "DIFC", "UK", "General"] as const
type JurisdictionFilter = typeof JURISDICTIONS[number]

const CATEGORIES = ["Civil", "Labour", "Administrative", "Criminal", "General"] as const
type CategoryFilter = typeof CATEGORIES[number]

interface TemplatePanelProps {
    open: boolean
    onClose: () => void
    onSelect: (slug: string) => void
}

const CUSTOM_SLUG = "__custom__"

export function TemplatePanel({open, onClose, onSelect}: TemplatePanelProps) {
    const {isDark} = useColorMode()
    const isMobile = useIsMobile()
    const {templates, isLoading, error, load} = useTemplates()

    const [jurisdiction, setJurisdiction] = useState<JurisdictionFilter | null>(null)
    const [category, setCategory] = useState<CategoryFilter | null>(null)

    // Fetch on first open
    useEffect(() => {
        if (open) load()
    }, [open, load])

    // Refresh when filters change
    useEffect(() => {
        if (!open) return
        load(
            jurisdiction ? jurisdiction.toLowerCase() : undefined,
            category ? category.toLowerCase() : undefined,
        )
    }, [open, jurisdiction, category, load])

    const handleSelect = useCallback((slug: string) => {
        onSelect(slug)
        onClose()
    }, [onSelect, onClose])

    const filtered = templates.filter((t: Template) => {
        const jMatch = !jurisdiction || t.jurisdiction.toUpperCase() === jurisdiction || (jurisdiction === "General" && !t.jurisdiction)
        const cMatch = !category || t.category.toLowerCase() === category.toLowerCase()
        return jMatch && cMatch
    })

    return (
        <AnimatePresence>
            {open && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{opacity: 0}}
                        animate={{opacity: 1}}
                        exit={{opacity: 0}}
                        transition={{duration: 0.2}}
                        onClick={onClose}
                        style={{
                            position: "fixed",
                            inset: 0,
                            zIndex: 60,
                            background: isDark ? "rgba(0,0,0,0.50)" : "rgba(60,30,0,0.18)",
                            backdropFilter: "blur(4px)",
                            WebkitBackdropFilter: "blur(4px)",
                        }}
                    />

                    {/* Panel */}
                    <motion.div
                        initial={isMobile ? {y: "100%", opacity: 0.5} : {x: "100%", opacity: 0.5}}
                        animate={isMobile ? {y: 0, opacity: 1} : {x: 0, opacity: 1}}
                        exit={isMobile ? {y: "100%", opacity: 0} : {x: "100%", opacity: 0}}
                        transition={{type: "spring", damping: 30, stiffness: 300, mass: 0.8}}
                        style={{
                            position: "fixed",
                            ...(isMobile
                                ? {left: 0, right: 0, bottom: 0, top: "5dvh", borderRadius: "20px 20px 0 0"}
                                : {top: 8, right: 8, bottom: 8, width: "min(90vw, 480px)", borderRadius: 20}),
                            zIndex: 61,
                            display: "flex",
                            flexDirection: "column",
                            overflow: "clip",
                            background: isDark
                                ? "rgba(15,21,32,0.92)"
                                : "rgba(255,250,235,0.94)",
                            backdropFilter: "blur(32px) saturate(160%)",
                            WebkitBackdropFilter: "blur(32px) saturate(160%)",
                            border: isDark
                                ? "0.5px solid rgba(255,255,255,0.10)"
                                : "0.5px solid rgba(255,255,255,0.55)",
                            boxShadow: isDark
                                ? "0 20px 80px rgba(0,0,0,0.65), inset 0 1px 0 rgba(255,255,255,0.06)"
                                : "0 16px 64px rgba(80,40,0,0.22), inset 0 1.5px 0 rgba(255,255,255,0.85)",
                            willChange: "transform",
                        }}
                    >
                        {/* Header */}
                        <div style={{
                            padding: "14px 20px",
                            borderBottom: isDark
                                ? "0.5px solid rgba(201,168,76,0.08)"
                                : "0.5px solid rgba(255,255,255,0.45)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            flexShrink: 0,
                            background: isDark
                                ? "rgba(255,255,255,0.02)"
                                : "rgba(255,255,255,0.12)",
                        }}>
                            <span style={{
                                fontSize: 11,
                                fontWeight: 700,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: isDark ? "rgba(201,168,76,0.70)" : "#7a4a00",
                                fontFamily: FONT.sans,
                            }}>
                                Document Templates
                            </span>
                            <button
                                onClick={onClose}
                                aria-label="Close template panel"
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: 28,
                                    height: 28,
                                    borderRadius: 8,
                                    background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.35)",
                                    border: isDark
                                        ? "0.5px solid rgba(255,255,255,0.10)"
                                        : "0.5px solid rgba(255,255,255,0.55)",
                                    cursor: "pointer",
                                    color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.45)",
                                    transition: `all ${TIMING.instant}`,
                                }}
                            >
                                <X size={14} strokeWidth={2} />
                            </button>
                        </div>

                        {/* Filters */}
                        <div style={{
                            padding: `${SPACE[3]}px ${SPACE[4]}px`,
                            borderBottom: isDark
                                ? "0.5px solid rgba(255,255,255,0.05)"
                                : "0.5px solid rgba(255,255,255,0.35)",
                            flexShrink: 0,
                            display: "flex",
                            flexDirection: "column",
                            gap: SPACE[2],
                        }}>
                            {/* Jurisdiction pills */}
                            <div style={{display: "flex", gap: SPACE[1], flexWrap: "wrap"}}>
                                {JURISDICTIONS.map((j) => (
                                    <PillButton
                                        key={j}
                                        label={j}
                                        active={jurisdiction === j}
                                        isDark={isDark}
                                        onClick={() => setJurisdiction(prev => prev === j ? null : j)}
                                    />
                                ))}
                            </div>
                            {/* Category pills */}
                            <div style={{display: "flex", gap: SPACE[1], flexWrap: "wrap"}}>
                                {CATEGORIES.map((c) => (
                                    <PillButton
                                        key={c}
                                        label={c}
                                        active={category === c}
                                        isDark={isDark}
                                        onClick={() => setCategory(prev => prev === c ? null : c)}
                                    />
                                ))}
                            </div>
                        </div>

                        {/* Template list */}
                        <div style={{flex: 1, overflowY: "auto", padding: SPACE[4], display: "flex", flexDirection: "column", gap: SPACE[2]}}>
                            {/* Custom document option — always pinned at top */}
                            <button
                                onClick={() => handleSelect(CUSTOM_SLUG)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: SPACE[3],
                                    padding: `${SPACE[3]}px ${SPACE[4]}px`,
                                    borderRadius: RADIUS.lg,
                                    border: isDark
                                        ? "1px solid rgba(201,168,76,0.15)"
                                        : "0.5px solid rgba(196,124,0,0.22)",
                                    background: isDark ? "rgba(201,168,76,0.05)" : "rgba(196,124,0,0.04)",
                                    cursor: "pointer",
                                    textAlign: "left",
                                    transition: `all ${TIMING.fast} ${EASE.out}`,
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = isDark
                                        ? "rgba(201,168,76,0.10)"
                                        : "rgba(196,124,0,0.08)"
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = isDark
                                        ? "rgba(201,168,76,0.05)"
                                        : "rgba(196,124,0,0.04)"
                                }}
                            >
                                <span style={{
                                    width: 28,
                                    height: 28,
                                    borderRadius: RADIUS.md,
                                    background: isDark ? "rgba(201,168,76,0.12)" : "rgba(196,124,0,0.10)",
                                    border: isDark
                                        ? "1px solid rgba(201,168,76,0.20)"
                                        : "0.5px solid rgba(196,124,0,0.25)",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: TYPE_SCALE.md,
                                    flexShrink: 0,
                                }}>
                                    ✦
                                </span>
                                <div style={{display: "flex", flexDirection: "column", gap: 2}}>
                                    <span style={{
                                        fontFamily: "Georgia, serif",
                                        fontSize: TYPE_SCALE.sm,
                                        color: isDark ? "var(--strict-gold-text)" : "#7a4a00",
                                    }}>
                                        Custom document
                                    </span>
                                    <span style={{
                                        fontFamily: FONT.sans,
                                        fontSize: TYPE_SCALE.xs,
                                        color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a",
                                    }}>
                                        Start from scratch
                                    </span>
                                </div>
                            </button>

                            {/* Template cards */}
                            {isLoading ? (
                                <SkeletonList isDark={isDark} />
                            ) : error ? (
                                <p style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.sm, color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a", textAlign: "center", padding: SPACE[8]}}>
                                    Failed to load templates
                                </p>
                            ) : filtered.length === 0 ? (
                                <p style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.sm, color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a", textAlign: "center", padding: SPACE[8]}}>
                                    No templates match these filters
                                </p>
                            ) : (
                                filtered.map((t: Template) => (
                                    <TemplateCard key={t.slug} template={t} onSelect={handleSelect} />
                                ))
                            )}
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    )
}

function PillButton({label, active, isDark, onClick}: {label: string; active: boolean; isDark: boolean; onClick: () => void}) {
    return (
        <button
            onClick={onClick}
            style={{
                fontFamily: FONT.sans,
                fontSize: TYPE_SCALE.xs,
                fontWeight: active ? 500 : 400,
                padding: `${SPACE[1]}px ${SPACE[2]}px`,
                borderRadius: RADIUS.sm,
                cursor: "pointer",
                background: active
                    ? (isDark ? "var(--strict-pill-active-bg)" : "rgba(196,124,0,0.10)")
                    : (isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.45)"),
                border: active
                    ? (isDark ? "1px solid var(--strict-pill-active-border)" : "0.5px solid rgba(196,124,0,0.28)")
                    : (isDark ? "1px solid rgba(255,255,255,0.06)" : "0.5px solid rgba(255,255,255,0.55)"),
                color: active
                    ? (isDark ? "var(--strict-text-primary)" : "#7a4a00")
                    : (isDark ? "var(--strict-text-secondary)" : "#5c3d1a"),
                transition: `all ${TIMING.fast} ${EASE.spring}`,
                whiteSpace: "nowrap" as const,
            }}
        >
            {label}
        </button>
    )
}

function SkeletonList({isDark}: {isDark: boolean}) {
    return (
        <>
            {[1, 2, 3].map((i) => (
                <div key={i} style={{
                    height: 88,
                    borderRadius: RADIUS.lg,
                    background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.45)",
                    border: isDark ? "1px solid rgba(255,255,255,0.05)" : "0.5px solid rgba(255,255,255,0.50)",
                    animation: "pulse 1.5s ease-in-out infinite",
                    opacity: 1 - i * 0.15,
                }} />
            ))}
        </>
    )
}
