"use client"

import {useState, useRef, useEffect, useCallback} from "react"
import {motion, AnimatePresence} from "motion/react"
import {ChevronDown, FileText} from "lucide-react"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING} from "@/lib/tokens"
import type {IndexEntry} from "./use-document-index"

interface DocumentIndexProps {
    entries: IndexEntry[]
    isDark: boolean
    focusDocId?: string | null
    onEntryClick?: (entry: IndexEntry) => void
}

export function DocumentIndex({entries, isDark, focusDocId, onEntryClick}: DocumentIndexProps) {
    const [expandedId, setExpandedId] = useState<string | null>(null)
    const [highlightedId, setHighlightedId] = useState<string | null>(null)
    const entryRefs = useRef<Map<string, HTMLDivElement>>(new Map())
    const scrollContainerRef = useRef<HTMLDivElement>(null)

    // Scroll to focused doc and highlight it
    useEffect(() => {
        if (!focusDocId) return
        const el = entryRefs.current.get(focusDocId)
        if (el) {
            el.scrollIntoView({behavior: "smooth", block: "center"})
            setHighlightedId(focusDocId)
            const timer = setTimeout(() => setHighlightedId(null), 1500)
            return () => clearTimeout(timer)
        }
    }, [focusDocId])

    const setRef = useCallback((docId: string) => (el: HTMLDivElement | null) => {
        if (el) entryRefs.current.set(docId, el)
        else entryRefs.current.delete(docId)
    }, [])

    if (entries.length === 0) {
        return (
            <div style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                height: "100%", padding: `${SPACE["6"]}px ${SPACE["3"]}px`,
            }}>
                <p style={{
                    fontSize: TYPE_SCALE.sm,
                    color: isDark ? "var(--strict-text-dim)" : "var(--dt-text-tertiary)",
                    textAlign: "center",
                    fontFamily: isDark ? "var(--strict-prose-font)" : FONT.sans,
                    fontStyle: "italic",
                    lineHeight: 1.5, margin: 0,
                }}>
                    No sources yet
                </p>
            </div>
        )
    }

    return (
        <div
            ref={scrollContainerRef}
            style={{
                flex: 1, overflowY: "auto",
                padding: `${SPACE["2"]}px`,
                scrollbarWidth: "thin",
                scrollbarColor: isDark
                    ? "var(--strict-scrollbar) transparent"
                    : "var(--dt-text-quaternary) transparent",
            }}
        >
            {entries.map((entry) => {
                const isExpanded = expandedId === entry.docId
                const isHighlighted = highlightedId === entry.docId

                return (
                    <div
                        key={entry.docId}
                        ref={setRef(entry.docId)}
                        style={{marginBottom: SPACE["1"] + 2}}
                    >
                        <motion.div
                            animate={isHighlighted ? {
                                boxShadow: [
                                    "0 0 0 0px var(--dt-accent-color)00",
                                    "0 0 0 3px var(--dt-accent-border-color)",
                                    "0 0 0 0px var(--dt-accent-color)00",
                                ],
                            } : {}}
                            transition={isHighlighted ? {duration: 1, repeat: 1} : {}}
                            style={{
                                borderRadius: isDark ? 10 : RADIUS.lg,
                                background: isHighlighted
                                    ? "var(--dt-accent-tint)"
                                    : isDark ? "var(--strict-glass-bg)" : "var(--dt-glass-bg)",
                                border: isHighlighted
                                    ? `1px solid var(--dt-accent-border-color)`
                                    : isDark
                                        ? "1px solid var(--strict-gold-border)"
                                        : "0.5px solid var(--dt-glass-border)",
                                backdropFilter: isDark ? "var(--strict-glass-blur)" : "none",
                                WebkitBackdropFilter: isDark ? "var(--strict-glass-blur)" : "none",
                                overflow: "hidden",
                                transition: `background ${TIMING.fast}, border-color ${TIMING.fast}`,
                            }}
                        >
                            {/* Card header — always visible */}
                            <button
                                onClick={() => {
                                    setExpandedId(isExpanded ? null : entry.docId)
                                    onEntryClick?.(entry)
                                }}
                                style={{
                                    display: "flex", alignItems: "flex-start", gap: SPACE["2"] + 2,
                                    width: "100%", textAlign: "left",
                                    padding: `${SPACE["2"] + 2}px ${SPACE["3"]}px`,
                                    background: "none", border: "none",
                                    cursor: "pointer",
                                    fontFamily: FONT.sans,
                                }}
                            >
                                {/* Document icon badge */}
                                <div style={{
                                    width: 26, height: 26,
                                    borderRadius: isDark ? RADIUS.sm : RADIUS.md,
                                    flexShrink: 0,
                                    background: isDark
                                        ? "var(--strict-gold-badge-bg)"
                                        : "var(--dt-accent-tint)",
                                    border: isDark
                                        ? "1px solid var(--strict-gold-badge-border)"
                                        : "0.5px solid var(--dt-accent-border-subtle)",
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    marginTop: 1,
                                }}>
                                    <FileText
                                        size={13}
                                        strokeWidth={1.8}
                                        style={{color: "var(--dt-accent-color)"}}
                                    />
                                </div>

                                {/* Text content */}
                                <div style={{flex: 1, minWidth: 0}}>
                                    {/* Law name — label style */}
                                    <p style={{
                                        fontSize: isDark ? 9 : TYPE_SCALE.xs - 1,
                                        fontWeight: isDark ? 500 : 700,
                                        textTransform: "uppercase",
                                        letterSpacing: isDark ? "1.2px" : "0.10em",
                                        color: "var(--dt-accent-color)",
                                        margin: `0 0 ${SPACE["1"]}px`,
                                        fontFamily: isDark ? "system-ui, sans-serif" : FONT.sans,
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                    }}>
                                        {entry.lawName}
                                    </p>

                                    {/* Section number — body text */}
                                    {entry.sectionNumber && (
                                        <p style={{
                                            fontSize: TYPE_SCALE.sm,
                                            fontWeight: 500,
                                            color: isDark
                                                ? "var(--strict-text-primary)"
                                                : "var(--dt-text-primary)",
                                            fontFamily: isDark
                                                ? "var(--strict-prose-font)"
                                                : FONT.sans,
                                            margin: `0 0 ${SPACE["1"]}px`,
                                            lineHeight: 1.4,
                                        }}>
                                            {entry.sectionNumber}
                                        </p>
                                    )}

                                    {/* Meta row: pages + citation count */}
                                    <div style={{display: "flex", alignItems: "center", gap: SPACE["1"] + 2, flexWrap: "wrap"}}>
                                        {/* Page badges */}
                                        {entry.pages.slice(0, 5).map((page) => (
                                            <span
                                                key={page}
                                                style={{
                                                    display: "inline-flex", alignItems: "center",
                                                    height: 18, padding: `0 ${SPACE["1"] + 2}px`,
                                                    borderRadius: RADIUS.xs,
                                                    fontSize: TYPE_SCALE.xs - 1,
                                                    fontWeight: 500,
                                                    background: isDark
                                                        ? "var(--strict-glass-bg)"
                                                        : "var(--dt-glass-bg)",
                                                    border: isDark
                                                        ? "1px solid var(--strict-glass-border)"
                                                        : "0.5px solid var(--dt-glass-border)",
                                                    color: isDark
                                                        ? "var(--strict-text-secondary)"
                                                        : "var(--dt-text-tertiary)",
                                                    fontFamily: FONT.sans,
                                                }}
                                            >
                                                p.{page}
                                            </span>
                                        ))}
                                        {entry.pages.length > 5 && (
                                            <span style={{
                                                fontSize: TYPE_SCALE.xs - 1,
                                                color: isDark ? "var(--strict-text-dim)" : "var(--dt-text-tertiary)",
                                                fontFamily: FONT.sans,
                                            }}>
                                                +{entry.pages.length - 5}
                                            </span>
                                        )}

                                        {/* Citation count */}
                                        {entry.citationCount > 1 && (
                                            <span style={{
                                                fontSize: TYPE_SCALE.xs - 1,
                                                fontWeight: 500,
                                                color: "var(--dt-accent-color)",
                                                opacity: 0.75,
                                                fontFamily: FONT.sans,
                                                marginLeft: 2,
                                            }}>
                                                {entry.citationCount}x cited
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Expand chevron */}
                                {entry.text && (
                                    <motion.div
                                        animate={{rotate: isExpanded ? 180 : 0}}
                                        transition={{duration: 0.2}}
                                        style={{
                                            flexShrink: 0, marginTop: 4,
                                            color: isDark ? "var(--strict-text-dim)" : "var(--dt-text-tertiary)",
                                        }}
                                    >
                                        <ChevronDown size={14} strokeWidth={2} />
                                    </motion.div>
                                )}
                            </button>

                            {/* Expandable text */}
                            <AnimatePresence initial={false}>
                                {isExpanded && entry.text && (
                                    <motion.div
                                        initial={{height: 0, opacity: 0}}
                                        animate={{height: "auto", opacity: 1}}
                                        exit={{height: 0, opacity: 0}}
                                        transition={{duration: 0.25, ease: [0.32, 0.72, 0, 1]}}
                                        style={{overflow: "hidden"}}
                                    >
                                        <div style={{
                                            padding: `0 ${SPACE["3"]}px ${SPACE["2"] + 2}px 48px`,
                                            borderTop: isDark
                                                ? "1px solid var(--strict-gold-border)"
                                                : "0.5px solid var(--dt-glass-border-subtle)",
                                            margin: `0 ${SPACE["2"]}px`,
                                            paddingTop: SPACE["2"],
                                        }}>
                                            <p style={{
                                                fontSize: TYPE_SCALE.sm,
                                                lineHeight: 1.65,
                                                color: isDark
                                                    ? "var(--strict-text-body)"
                                                    : "var(--dt-text-secondary)",
                                                fontFamily: isDark
                                                    ? "var(--strict-prose-font)"
                                                    : FONT.sans,
                                                margin: 0,
                                                whiteSpace: "pre-wrap",
                                                maxHeight: 200,
                                                overflowY: "auto",
                                                scrollbarWidth: "thin",
                                                scrollbarColor: isDark
                                                    ? "var(--strict-scrollbar) transparent"
                                                    : "var(--dt-text-quaternary) transparent",
                                            }}>
                                                {entry.text.length > 800
                                                    ? entry.text.slice(0, 800) + "..."
                                                    : entry.text}
                                            </p>

                                            {/* Turn indices */}
                                            {entry.turnIndices.length > 0 && (
                                                <p style={{
                                                    fontSize: TYPE_SCALE.xs - 1,
                                                    color: isDark ? "var(--strict-text-dim)" : "var(--dt-text-tertiary)",
                                                    fontFamily: FONT.sans,
                                                    margin: `${SPACE["2"]}px 0 0`,
                                                }}>
                                                    Cited in turn{entry.turnIndices.length > 1 ? "s" : ""}{" "}
                                                    {entry.turnIndices.map((ti, i) => (
                                                        <span key={ti}>
                                                            {i > 0 && ", "}
                                                            #{Math.floor(ti / 2) + 1}
                                                        </span>
                                                    ))}
                                                </p>
                                            )}
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </motion.div>
                    </div>
                )
            })}
        </div>
    )
}
