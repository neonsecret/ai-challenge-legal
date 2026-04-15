"use client"

/**
 * SourcePanelV2 — right-side source panel for Strict dark mode.
 * Slides in at 42% width when a citation is clicked.
 * Shows source tabs, meta (doc name, reference, page badge), and the
 * matching passage highlighted within the full source text.
 *
 * Spec: section 5.2–5.5
 */

import { useState } from "react"
import { X } from "lucide-react"
import { motion, AnimatePresence } from "motion/react"
import type { Source } from "@/components/chat/use-query-stream"
import { isTxtSource } from "@/components/grounding/grounding-utils"

interface SourcePanelV2Props {
    sources: Source[]
    /** Index of the initially-active source (from citation click) */
    initialIndex?: number
    onClose: () => void
}

function formatDocId(doc_id: string): string {
    // Strip corpus prefix (e.g. "difc/", "uk/") for display
    const parts = doc_id.split("/")
    return parts.at(-1) ?? doc_id
}

function getDocName(source: Source): string {
    if (source.title) return source.title
    if (source.case_number) return source.case_number
    return formatDocId(source.doc_id)
}

function getReference(source: Source): string {
    const parts: string[] = []
    if (source.court) parts.push(source.court)
    if (source.case_number) parts.push(source.case_number)
    if (source.decision_date) parts.push(source.decision_date)
    if (source.ecli) parts.push(source.ecli)
    if (parts.length > 0) return parts.join(" · ")
    return formatDocId(source.doc_id)
}

function TabBadge({ num }: { num: number }) {
    return (
        <span
            style={{
                font: "8px/1 Georgia, serif",
                background: "rgba(201,168,76, 0.08)",
                border: "1px solid rgba(201,168,76, 0.15)",
                borderRadius: 3,
                padding: "1px 4px",
                color: "var(--strict-gold-text)",
                flexShrink: 0,
            }}
        >
            {num}
        </span>
    )
}

function PageBadge({ pages }: { pages: number[] }) {
    if (!pages.length) return null
    return (
        <span
            style={{
                font: "8px/1 system-ui, sans-serif",
                background: "rgba(201,168,76, 0.06)",
                border: "1px solid rgba(201,168,76, 0.12)",
                borderRadius: 4,
                padding: "2px 6px",
                color: "var(--strict-gold-text)",
                flexShrink: 0,
            }}
        >
            p.{pages.join(", ")}
        </span>
    )
}

export function SourcePanelV2({ sources, initialIndex = 0, onClose }: SourcePanelV2Props) {
    const [activeIndex, setActiveIndex] = useState(
        Math.min(initialIndex, Math.max(0, sources.length - 1))
    )

    if (!sources.length) return null

    // Clamp at render time — avoids calling setState inside an effect (react-hooks/set-state-in-effect).
    // When sources shrinks the displayed tab and content immediately snap to the last valid entry.
    const clampedIndex = Math.min(activeIndex, sources.length - 1)
    const active = sources[clampedIndex]

    return (
        <AnimatePresence>
            <motion.div
                key="source-panel-v2"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 24 }}
                transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
                style={{
                    width: "42%",
                    flexShrink: 0,
                    borderLeft: "1px solid var(--strict-gold-border)",
                    background: "rgba(0,0,0, 0.06)",
                    display: "flex",
                    flexDirection: "column",
                    minHeight: 0,
                    overflow: "hidden",
                }}
            >
                {/* Tab row */}
                <div
                    style={{
                        display: "flex",
                        alignItems: "stretch",
                        borderBottom: "1px solid var(--strict-gold-border)",
                        flexShrink: 0,
                        overflowX: "auto",
                        scrollbarWidth: "none",
                    }}
                >
                    {sources.map((src, i) => {
                        const isActive = i === clampedIndex
                        return (
                            <button
                                key={`${src.doc_id}-${i}`}
                                onClick={() => setActiveIndex(i)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 5,
                                    padding: "9px 14px",
                                    font: "9px/1 system-ui, sans-serif",
                                    color: isActive ? "var(--strict-gold-text)" : "var(--strict-text-dim)",
                                    borderBottom: isActive
                                        ? "2px solid rgba(201,168,76, 0.4)"
                                        : "2px solid transparent",
                                    background: "transparent",
                                    border: "none",
                                    borderBottomWidth: 2,
                                    borderBottomStyle: "solid",
                                    borderBottomColor: isActive ? "rgba(201,168,76, 0.4)" : "transparent",
                                    cursor: "pointer",
                                    flexShrink: 0,
                                    transition: "color 0.15s ease, border-color 0.15s ease",
                                    whiteSpace: "nowrap",
                                }}
                                onMouseEnter={(e) => {
                                    if (!isActive) e.currentTarget.style.color = "var(--strict-text-secondary)"
                                }}
                                onMouseLeave={(e) => {
                                    if (!isActive) e.currentTarget.style.color = "var(--strict-text-dim)"
                                }}
                            >
                                <TabBadge num={i + 1} />
                                <span style={{
                                    maxWidth: 120,
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                }}>
                                    {formatDocId(src.doc_id)}
                                </span>
                            </button>
                        )
                    })}

                    {/* Spacer + close button */}
                    <div style={{ flex: 1 }} />
                    <button
                        onClick={onClose}
                        title="Close sources"
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: 36,
                            flexShrink: 0,
                            background: "transparent",
                            border: "none",
                            color: "var(--strict-text-dim)",
                            cursor: "pointer",
                            transition: "color 0.15s ease",
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.color = "var(--strict-text-secondary)"
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.color = "var(--strict-text-dim)"
                        }}
                    >
                        <X size={12} strokeWidth={2} />
                    </button>
                </div>

                {/* Source meta */}
                <div
                    style={{
                        padding: "12px 18px",
                        borderBottom: "1px solid var(--strict-gold-border)",
                        flexShrink: 0,
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                    }}
                >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                        <p
                            style={{
                                font: "11px/1.3 Georgia, serif",
                                color: "var(--strict-text-primary)",
                                margin: 0,
                                flex: 1,
                                minWidth: 0,
                            }}
                        >
                            {getDocName(active)}
                        </p>
                        {!isTxtSource(active) && <PageBadge pages={active.page_numbers} />}
                    </div>

                    <p
                        style={{
                            font: "9px/1.3 system-ui, sans-serif",
                            color: "var(--strict-text-dim)",
                            margin: 0,
                        }}
                    >
                        {getReference(active)}
                    </p>
                </div>

                {/* Source text */}
                <div
                    style={{
                        flex: 1,
                        overflowY: "auto",
                        padding: "14px 18px",
                        scrollbarWidth: "thin",
                        scrollbarColor: "var(--strict-scrollbar) transparent",
                    }}
                >
                    {active.text ? (
                        /* Matching passage — highlighted block */
                        <div
                            style={{
                                background: "rgba(201,168,76, 0.07)",
                                borderLeft: "2px solid rgba(201,168,76, 0.35)",
                                padding: "10px 14px",
                                borderRadius: "0 6px 6px 0",
                                marginBottom: 12,
                            }}
                        >
                            <p
                                style={{
                                    font: "12px/1.75 Georgia, serif",
                                    color: "var(--strict-text-body)",
                                    margin: 0,
                                    whiteSpace: "pre-wrap",
                                }}
                            >
                                {active.text}
                            </p>
                        </div>
                    ) : (
                        <p
                            style={{
                                font: "12px/1.75 Georgia, serif",
                                color: "var(--strict-text-secondary)",
                                margin: 0,
                                fontStyle: "italic",
                                opacity: 0.6,
                            }}
                        >
                            Source text not available.
                        </p>
                    )}

                    {/* Legal thesis if present (Czech court decisions) */}
                    {active.legal_thesis && (
                        <div style={{ marginTop: 14 }}>
                            <p
                                style={{
                                    font: "8px/1 system-ui, sans-serif",
                                    textTransform: "uppercase",
                                    letterSpacing: "0.5px",
                                    color: "var(--strict-source-label)",
                                    marginBottom: 6,
                                }}
                            >
                                Legal Thesis
                            </p>
                            <p
                                style={{
                                    font: "11px/1.6 Georgia, serif",
                                    color: "var(--strict-text-secondary)",
                                    margin: 0,
                                    paddingLeft: 16,
                                    borderLeft: "1px solid var(--strict-gold-border)",
                                }}
                            >
                                {active.legal_thesis}
                            </p>
                        </div>
                    )}
                </div>
            </motion.div>
        </AnimatePresence>
    )
}
