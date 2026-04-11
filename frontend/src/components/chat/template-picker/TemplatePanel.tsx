"use client"

import {useEffect, useState, useCallback, useRef, useId} from "react"
import {motion, AnimatePresence} from "motion/react"
import {X} from "lucide-react"
import {useIsMobile} from "@/hooks/use-mobile"
import {useTemplates} from "@/hooks/use-templates"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {TemplateCard} from "./TemplateCard"
import type {Template} from "@/types/documents"

const JURISDICTIONS = ["CZ", "DIFC", "UK", "General"] as const
type JurisdictionFilter = typeof JURISDICTIONS[number]

const CATEGORIES = ["Civil", "Labor", "Administrative", "Criminal", "General"] as const
type CategoryFilter = typeof CATEGORIES[number]

interface TemplatePanelProps {
    open: boolean
    onClose: () => void
    onSelect: (slug: string) => void
}

const CUSTOM_SLUG = "__custom__"

export function TemplatePanel({open, onClose, onSelect}: TemplatePanelProps) {
    const isMobile = useIsMobile()
    const {templates, isLoading, hasAttempted, error, load} = useTemplates()
    const panelRef = useRef<HTMLDivElement>(null)
    const titleId = useId()

    const [jurisdiction, setJurisdiction] = useState<JurisdictionFilter | null>(null)
    const [category, setCategory] = useState<CategoryFilter | null>(null)

    // Load all templates once when panel opens; client-side filter handles jurisdiction/category.
    // Passing jurisdiction to the server caused case-mismatch bugs (DB stores uppercase, "General"
    // has no jurisdiction value). Filtering is fast client-side given the small template count.
    useEffect(() => {
        if (!open) return
        load()
    }, [open, load])

    // Escape key + focus trap
    useEffect(() => {
        if (!open) return
        const el = panelRef.current
        if (!el) return

        const FOCUSABLE = "button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])"

        // Focus the first element on open (synchronous elements are present at this point)
        el.querySelectorAll<HTMLElement>(FOCUSABLE)[0]?.focus()

        const handleKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") { e.preventDefault(); onClose(); return }
            if (e.key !== "Tab") return
            // Re-query on every Tab press — template cards render asynchronously after
            // the panel opens, so a snapshot captured at open time would miss them.
            const live = el.querySelectorAll<HTMLElement>(FOCUSABLE)
            const first = live[0]
            const last = live[live.length - 1]
            if (e.shiftKey) {
                if (document.activeElement === first) { e.preventDefault(); last?.focus() }
            } else {
                if (document.activeElement === last) { e.preventDefault(); first?.focus() }
            }
        }
        document.addEventListener("keydown", handleKey)
        return () => document.removeEventListener("keydown", handleKey)
    }, [open, onClose])

    const handleSelect = useCallback((slug: string) => {
        onSelect(slug)
        onClose()
    }, [onSelect, onClose])

    const filtered = templates.filter((t: Template) => {
        const jMatch = !jurisdiction || t.jurisdiction.toUpperCase() === jurisdiction.toUpperCase() || (jurisdiction === "General" && !t.jurisdiction)
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
                        aria-hidden="true"
                        style={{
                            position: "fixed",
                            inset: 0,
                            zIndex: 60,
                            background: "var(--doc-overlay-bg)",
                            backdropFilter: "blur(4px)",
                            WebkitBackdropFilter: "blur(4px)",
                        }}
                    />

                    {/* Panel */}
                    <motion.div
                        ref={panelRef}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby={titleId}
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
                            background: "var(--doc-panel-bg)",
                            backdropFilter: "blur(32px) saturate(160%)",
                            WebkitBackdropFilter: "blur(32px) saturate(160%)",
                            border: "0.5px solid var(--doc-panel-border)",
                            boxShadow: "var(--doc-panel-shadow)",
                            willChange: "transform",
                        }}
                    >
                        {/* Header */}
                        <div style={{
                            padding: "14px 20px",
                            borderBottom: "0.5px solid var(--doc-panel-header-border)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            flexShrink: 0,
                            background: "var(--doc-panel-header-bg)",
                        }}>
                            <span id={titleId} style={{
                                fontSize: 11,
                                fontWeight: 700,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: "var(--doc-text-label)",
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
                                    background: "var(--doc-close-btn-bg)",
                                    border: "0.5px solid var(--doc-close-btn-border)",
                                    cursor: "pointer",
                                    color: "var(--doc-close-btn-color)",
                                    transition: `all ${TIMING.instant}`,
                                }}
                            >
                                <X size={14} strokeWidth={2} />
                            </button>
                        </div>

                        {/* Filters */}
                        <div style={{
                            padding: `${SPACE[3]}px ${SPACE[4]}px`,
                            borderBottom: "0.5px solid var(--doc-pill-inactive-border)",
                            flexShrink: 0,
                            display: "flex",
                            flexDirection: "column",
                            gap: SPACE[2],
                        }}>
                            <div style={{display: "flex", gap: SPACE[1], flexWrap: "wrap"}}>
                                {JURISDICTIONS.map((j) => (
                                    <PillButton
                                        key={j}
                                        label={j}
                                        active={jurisdiction === j}
                                        onClick={() => setJurisdiction(prev => prev === j ? null : j)}
                                    />
                                ))}
                            </div>
                            <div style={{display: "flex", gap: SPACE[1], flexWrap: "wrap"}}>
                                {CATEGORIES.map((c) => (
                                    <PillButton
                                        key={c}
                                        label={c}
                                        active={category === c}
                                        onClick={() => setCategory(prev => prev === c ? null : c)}
                                    />
                                ))}
                            </div>
                        </div>

                        {/* Template list */}
                        <div style={{flex: 1, overflowY: "auto", padding: SPACE[4], display: "flex", flexDirection: "column", gap: SPACE[2]}}>
                            {/* Custom document option */}
                            <button
                                onClick={() => handleSelect(CUSTOM_SLUG)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: SPACE[3],
                                    padding: `${SPACE[3]}px ${SPACE[4]}px`,
                                    borderRadius: RADIUS.lg,
                                    border: "1px solid var(--doc-custom-btn-border)",
                                    background: "var(--doc-custom-btn-bg)",
                                    cursor: "pointer",
                                    textAlign: "left",
                                    transition: `all ${TIMING.fast} ${EASE.out}`,
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = "var(--doc-custom-btn-hover-bg)"
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = "var(--doc-custom-btn-bg)"
                                }}
                            >
                                <span style={{
                                    width: 28,
                                    height: 28,
                                    borderRadius: RADIUS.md,
                                    background: "var(--doc-gold-card-bg-hover)",
                                    border: "1px solid var(--doc-gold-card-border)",
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
                                        color: "var(--doc-text-label)",
                                    }}>
                                        Custom document
                                    </span>
                                    <span style={{
                                        fontFamily: FONT.sans,
                                        fontSize: TYPE_SCALE.xs,
                                        color: "var(--doc-text-secondary)",
                                    }}>
                                        Start from scratch
                                    </span>
                                </div>
                            </button>

                            {/* Template cards */}
                            {isLoading || !hasAttempted ? (
                                <SkeletonList />
                            ) : error ? (
                                <p style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.sm, color: "var(--doc-text-secondary)", textAlign: "center", padding: SPACE[8]}}>
                                    Failed to load templates
                                </p>
                            ) : filtered.length === 0 ? (
                                <p style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.sm, color: "var(--doc-text-secondary)", textAlign: "center", padding: SPACE[8]}}>
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

function PillButton({label, active, onClick}: {label: string; active: boolean; onClick: () => void}) {
    return (
        <button
            onClick={onClick}
            aria-pressed={active}
            style={{
                fontFamily: FONT.sans,
                fontSize: TYPE_SCALE.xs,
                fontWeight: active ? 500 : 400,
                padding: `${SPACE[1]}px ${SPACE[2]}px`,
                borderRadius: RADIUS.sm,
                cursor: "pointer",
                background: active ? "var(--doc-pill-active-bg)" : "var(--doc-pill-inactive-bg)",
                border: active
                    ? "1px solid var(--doc-pill-active-border)"
                    : "1px solid var(--doc-pill-inactive-border)",
                color: active ? "var(--doc-pill-active-color)" : "var(--doc-pill-inactive-color)",
                transition: `all ${TIMING.fast} ${EASE.spring}`,
                whiteSpace: "nowrap" as const,
            }}
        >
            {label}
        </button>
    )
}

function SkeletonList() {
    return (
        <>
            {[1, 2, 3].map((i) => (
                <div key={i} style={{
                    height: 88,
                    borderRadius: RADIUS.lg,
                    background: "var(--doc-btn-glass-bg)",
                    border: "1px solid var(--doc-pill-inactive-border)",
                    animation: "gentle-pulse 1.5s ease-in-out infinite",
                    opacity: 1 - i * 0.15,
                }} />
            ))}
        </>
    )
}
