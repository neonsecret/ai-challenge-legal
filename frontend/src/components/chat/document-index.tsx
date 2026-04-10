"use client"

import {useState, useRef, useEffect, useCallback} from "react"
import {motion, AnimatePresence} from "motion/react"
import {ChevronDown, FileText} from "lucide-react"
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

    const gold = isDark ? "#C9A84C" : "#c47c00"
    const mutedText = isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.50)"
    const bodyText = isDark ? "rgba(255,255,255,0.75)" : "rgba(46,31,8,0.75)"
    const font = "-apple-system, BlinkMacSystemFont, system-ui, sans-serif"

    if (entries.length === 0) {
        return (
            <div style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                height: "100%", padding: "24px 12px",
            }}>
                <p style={{
                    fontSize: 12, color: isDark ? "var(--strict-text-dim)" : mutedText,
                    textAlign: "center",
                    fontFamily: isDark ? "Georgia, serif" : font,
                    fontStyle: isDark ? "italic" : undefined,
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
                flex: 1, overflowY: "auto", padding: "8px",
                scrollbarWidth: "thin",
                scrollbarColor: isDark ? "rgba(255,255,255,0.12) transparent" : "rgba(46,31,8,0.12) transparent",
            }}
        >
            {entries.map((entry) => {
                const isExpanded = expandedId === entry.docId
                const isHighlighted = highlightedId === entry.docId

                return (
                    <div
                        key={entry.docId}
                        ref={setRef(entry.docId)}
                        style={{marginBottom: 6}}
                    >
                        <motion.div
                            animate={isHighlighted ? {
                                boxShadow: [
                                    `0 0 0 0px ${gold}00`,
                                    `0 0 0 3px ${gold}55`,
                                    `0 0 0 0px ${gold}00`,
                                ],
                            } : {}}
                            transition={isHighlighted ? {duration: 1, repeat: 1} : {}}
                            style={{
                                borderRadius: 14,
                                background: isHighlighted
                                    ? isDark ? "rgba(201,168,76,0.12)" : "rgba(233,196,106,0.18)"
                                    : isDark ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.18)",
                                border: isHighlighted
                                    ? isDark ? "0.5px solid rgba(201,168,76,0.35)" : "0.5px solid rgba(196,124,0,0.30)"
                                    : isDark ? "1px solid rgba(201,168,76,0.06)" : "0.5px solid rgba(255,255,255,0.45)",
                                backdropFilter: "blur(8px)",
                                WebkitBackdropFilter: "blur(8px)",
                                overflow: "hidden",
                                transition: "background 0.2s, border-color 0.2s",
                            }}
                        >
                            {/* Card header — always visible */}
                            <button
                                onClick={() => {
                                    setExpandedId(isExpanded ? null : entry.docId)
                                    onEntryClick?.(entry)
                                }}
                                style={{
                                    display: "flex", alignItems: "flex-start", gap: 10,
                                    width: "100%", textAlign: "left",
                                    padding: "10px 12px",
                                    background: "none", border: "none",
                                    cursor: "pointer",
                                    fontFamily: font,
                                }}
                            >
                                {/* Number badge */}
                                <div style={{
                                    width: 26, height: 26, borderRadius: 8, flexShrink: 0,
                                    background: isDark ? "rgba(201,168,76,0.14)" : "rgba(196,124,0,0.12)",
                                    border: isDark ? "0.5px solid rgba(201,168,76,0.28)" : "0.5px solid rgba(196,124,0,0.24)",
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    marginTop: 1,
                                }}>
                                    <FileText size={13} strokeWidth={1.8} style={{color: gold}} />
                                </div>

                                {/* Text content */}
                                <div style={{flex: 1, minWidth: 0}}>
                                    {/* Law name */}
                                    <p style={{
                                        fontSize: 9, fontWeight: 700,
                                        textTransform: "uppercase",
                                        letterSpacing: "0.10em",
                                        color: gold,
                                        margin: "0 0 3px",
                                        fontFamily: font,
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                    }}>
                                        {entry.lawName}
                                    </p>

                                    {/* Section number */}
                                    {entry.sectionNumber && (
                                        <p style={{
                                            fontSize: isDark ? 12 : 14, fontWeight: isDark ? 500 : 600,
                                            color: isDark ? "rgba(255,255,255,0.88)" : "#1a0e04",
                                            fontFamily: isDark ? "system-ui" : "Georgia, 'Times New Roman', serif",
                                            margin: "0 0 4px",
                                        }}>
                                            {entry.sectionNumber}
                                        </p>
                                    )}

                                    {/* Meta row: pages + citation count */}
                                    <div style={{display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap"}}>
                                        {/* Page badges */}
                                        {entry.pages.slice(0, 5).map((page) => (
                                            <span
                                                key={page}
                                                style={{
                                                    display: "inline-flex", alignItems: "center",
                                                    height: 18, padding: "0 6px",
                                                    borderRadius: 4, fontSize: 10, fontWeight: 500,
                                                    background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.30)",
                                                    border: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.50)",
                                                    color: isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.60)",
                                                    fontFamily: font,
                                                }}
                                            >
                                                p.{page}
                                            </span>
                                        ))}
                                        {entry.pages.length > 5 && (
                                            <span style={{fontSize: 10, color: mutedText, fontFamily: font}}>
                                                +{entry.pages.length - 5}
                                            </span>
                                        )}

                                        {/* Citation count */}
                                        {entry.citationCount > 1 && (
                                            <span style={{
                                                fontSize: 10, fontWeight: 500,
                                                color: gold, opacity: 0.75,
                                                fontFamily: font,
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
                                            color: mutedText,
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
                                            padding: "0 12px 10px 48px",
                                            borderTop: isDark ? "0.5px solid rgba(255,255,255,0.06)" : "0.5px solid rgba(255,255,255,0.30)",
                                            margin: "0 8px",
                                            paddingTop: 8,
                                        }}>
                                            <p style={{
                                                fontSize: 12, lineHeight: 1.65,
                                                color: bodyText,
                                                fontFamily: "Georgia, 'Times New Roman', serif",
                                                margin: 0,
                                                whiteSpace: "pre-wrap",
                                                maxHeight: 200,
                                                overflowY: "auto",
                                                scrollbarWidth: "thin",
                                                scrollbarColor: isDark
                                                    ? "rgba(255,255,255,0.10) transparent"
                                                    : "rgba(46,31,8,0.10) transparent",
                                            }}>
                                                {entry.text.length > 800
                                                    ? entry.text.slice(0, 800) + "..."
                                                    : entry.text}
                                            </p>

                                            {/* Turn indices */}
                                            {entry.turnIndices.length > 0 && (
                                                <p style={{
                                                    fontSize: 10, color: mutedText,
                                                    fontFamily: font, marginTop: 8,
                                                    margin: "8px 0 0",
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
