"use client"

import {useState, useCallback, useEffect, useRef, useMemo} from "react"
import {motion, AnimatePresence} from "motion/react"
import {Copy, Check, Globe} from "lucide-react"
import {cn, toSafeStringOrNull, toSafeNumber} from "@/lib/utils"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {
    SourceRef,
    isWebSource,
    isCourtDecision,
    isTxtSource,
    getDomain,
    formatCzechDate,
} from "./grounding-utils"
import {WebContentPreview} from "./web-content-preview"
import {TextSourceViewer} from "./source-viewers"

export type {SourceRef}

interface GroundingViewProps {
    answer: string
    sources: SourceRef[]
    isMobile?: boolean
    focusDocId?: string
    focusPage?: number
    /** Incremented on every citation click — forces the focus effect to fire even when focusDocId/focusPage are unchanged */
    focusSeq?: number
}

function resolveSource(
    sources: SourceRef[],
    focusDocId: string | undefined,
    focusPage: number | undefined
): SourceRef | null {
    if (!focusDocId) return sources[0] ?? null
    // 1. Exact match — when multiple sources share the same doc_id (different chunks),
    //    prefer the one whose page_numbers include focusPage so [DOC-N] citations navigate
    //    to the correct chunk rather than always landing on the first occurrence.
    const exactMatches = sources.filter(s => s.doc_id === focusDocId)
    if (exactMatches.length > 0) {
        if (focusPage) {
            const withPage = exactMatches.find(s => s.page_numbers.includes(focusPage))
            if (withPage) return withPage
        }
        return exactMatches[0]
    }
    // 2. Prefix — scored
    const candidates = sources.filter(s =>
        s.doc_id.startsWith(focusDocId) || focusDocId.startsWith(s.doc_id)
    )
    if (candidates.length > 0) {
        // prefer candidate where focusPage is in page_numbers
        const withPage = focusPage ? candidates.find(s => s.page_numbers.includes(focusPage)) : null
        if (withPage) return withPage
        // prefer closest length match
        candidates.sort((a, b) =>
            Math.abs(a.doc_id.length - focusDocId.length) -
            Math.abs(b.doc_id.length - focusDocId.length)
        )
        return candidates[0]
    }
    // 3. Page fallback
    if (focusPage) {
        return sources.find(s => s.page_numbers.includes(focusPage)) ?? null
    }
    return sources[0] ?? null
}

const crossfade = {duration: TIMING.fast.endsWith("ms") ? parseFloat(TIMING.fast) / 1000 : parseFloat(TIMING.fast)}

export function GroundingView({answer, sources: rawSources, isMobile = false, focusDocId, focusPage, focusSeq = 0}: GroundingViewProps) {
    // Normalize sources — filter out malformed entries and coerce fields to safe types
    const sources = useMemo(() => {
        const arr = Array.isArray(rawSources) ? rawSources : []
        return arr
            .filter((s): s is SourceRef => !!s && typeof s.doc_id === "string" && Array.isArray(s.page_numbers))
            .map(s => ({
                ...s,
                text: toSafeStringOrNull(s.text),
                title: toSafeStringOrNull(s.title),
                url: toSafeStringOrNull(s.url),
                chunk_id: toSafeStringOrNull(s.chunk_id),
                page_numbers: s.page_numbers.map(p => toSafeNumber(p)),
                source_type: s.source_type === "court_decision" ? "court_decision" as const : s.source_type === "statute" ? "statute" as const : null,
                case_number: toSafeStringOrNull(s.case_number),
                decision_date: toSafeStringOrNull(s.decision_date),
                court: toSafeStringOrNull(s.court),
                category: toSafeStringOrNull(s.category),
                ecli: toSafeStringOrNull(s.ecli),
                legal_thesis: toSafeStringOrNull(s.legal_thesis),
            }))
    }, [rawSources])
    const initialSource = resolveSource(sources, focusDocId, focusPage)
    const initialPage = focusPage ?? (initialSource?.page_numbers[0] ?? 1)

    const [activeSource, setActiveSource] = useState<SourceRef | null>(initialSource)
    const [activePage, setActivePage] = useState<number>(initialPage)

    // Keep a ref to always have the latest sources without adding them to the
    // focusDocId/focusPage effect's dependency array (which would cause
    // unwanted re-runs on every render).
    const sourcesRef = useRef(sources)
    useEffect(() => { sourcesRef.current = sources }, [sources])

    // Skip the first run — useState already initialised from the IIFE above.
    const isMounted = useRef(false)

    // When focusDocId/focusPage/focusSeq change (drawer already open, user clicks a citation).
    // focusSeq is incremented on every click so this fires even when the same citation is clicked twice.
    useEffect(() => {
        if (!isMounted.current) {
            isMounted.current = true
            return
        }
        if (!focusDocId && !focusPage) return
        const resolved = resolveSource(sourcesRef.current, focusDocId, focusPage)
        if (resolved) {
            setActiveSource(resolved)
            setActivePage(focusPage ?? resolved.page_numbers[0] ?? 1)
        } else if (focusPage) {
            const byPage = sourcesRef.current.find(s => s.page_numbers.includes(focusPage))
            if (byPage) { setActiveSource(byPage); setActivePage(focusPage) }
        }
    }, [focusDocId, focusPage, focusSeq])

    const handleSourceClick = (source: SourceRef, page: number) => {
        setActiveSource(source)
        setActivePage(page)
    }

    const handlePageFromText = useCallback((page: number) => {
        // Find the source that contains this page, or use the active source
        const matchingSource = sources.find((s) => s.page_numbers.includes(page))
        if (matchingSource) {
            setActiveSource(matchingSource)
            setActivePage(page)
        } else if (activeSource) {
            setActivePage(page)
        }
    }, [sources, activeSource])

    // Viewer panel — full-width PDF or text display
    const viewerPanel = (
        <div className={cn("overflow-hidden", isMobile ? "p-1 flex-1 min-h-0" : "flex-1 min-h-0 p-2")}>
            <AnimatePresence mode="wait">
                {activeSource ? (
                    <motion.div
                        key={`${activeSource.doc_id}-${activeSource.chunk_id ?? ""}-${activePage}`}
                        initial={{opacity: 0}}
                        animate={{opacity: 1}}
                        exit={{opacity: 0}}
                        transition={crossfade}
                        className="h-full"
                    >
                        {isWebSource(activeSource) ? (
                            <WebContentPreview
                                key={activeSource.url || activeSource.doc_id}
                                source={activeSource}
                                answer={answer}
                                isMobile={isMobile}
                            />
                        ) : (
                            <TextSourceViewer
                                source={activeSource}
                                page={activePage}
                                answer={answer}
                                isMobile={isMobile}
                                onPageClick={handlePageFromText}
                            />
                        )}
                    </motion.div>
                ) : (
                    <motion.div
                        key="no-source"
                        initial={{opacity: 0}}
                        animate={{opacity: 1}}
                        exit={{opacity: 0}}
                        transition={crossfade}
                        className="flex h-full items-center justify-center text-sm"
                        style={{color: "var(--dt-text-tertiary)"}}
                    >
                        No source selected
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )

    // Compact horizontal sources strip shown at the bottom of both layouts
    const sourcesStrip = sources.length > 0 ? (
        <div style={{
            flexShrink: 0,
            overflowX: "auto",
            overflowY: "hidden",
            WebkitOverflowScrolling: "touch",
            overscrollBehavior: "contain",
            display: "flex",
            gap: SPACE['2'],
            padding: SPACE['2'],
            paddingBottom: isMobile ? `max(${SPACE['2']}px, env(safe-area-inset-bottom))` : SPACE['2'],
            paddingLeft: `max(${SPACE['2']}px, env(safe-area-inset-left))`,
            paddingRight: `max(${SPACE['2']}px, env(safe-area-inset-right))`,
            minHeight: 0,
            maxHeight: 124,
            borderTop: `0.5px solid var(--gm-border-outer, var(--dt-glass-border-subtle))`,
            scrollbarWidth: "none",
        }}>
            {sources.map((source, i) => (
                <SourceCitationCard
                    key={`${source.doc_id}-${i}`}
                    source={source}
                    isActive={activeSource === source}
                    activePage={activeSource === source ? activePage : null}
                    onPageClick={(page) => handleSourceClick(source, page)}
                    compact
                />
            ))}
        </div>
    ) : null

    // Both mobile and desktop: viewer on top, sources strip at bottom
    return (
        <div className="flex flex-col h-full" style={{overflow: "hidden"}}>
            {viewerPanel}
            {sourcesStrip}
        </div>
    )
}

interface SourceCitationCardProps {
    source: SourceRef
    isActive: boolean
    activePage: number | null
    onPageClick: (page: number) => void
    /** Compact horizontal-strip mode — narrower card for the bottom sources bar */
    compact?: boolean
}

function SourceCitationCard({
    source,
    isActive,
    activePage,
    onPageClick,
    compact = false,
}: SourceCitationCardProps) {
    const [copied, setCopied] = useState(false)
    const isWeb = isWebSource(source)

    // In compact mode show last 16 chars; normal mode show last 28
    const maxChars = compact ? 16 : 28
    const displayId = isWeb
        ? (source.title || getDomain(source.url || source.doc_id.replace(/^web:/, "")))
        : source.doc_id.length > maxChars ? `\u2026${source.doc_id.slice(-maxChars)}` : source.doc_id

    const handleCopySource = (e: React.MouseEvent) => {
        e.stopPropagation()
        const text = isCourtDecision(source)
            ? `${source.case_number ?? source.doc_id}${source.ecli ? ` (${source.ecli})` : ""}`
            : isWeb
            ? (source.url || source.doc_id.replace(/^web:/, ""))
            : isTxtSource(source)
            ? `${source.doc_id} (L. ${source.page_numbers.join(", ")})`
            : `${source.doc_id} (p. ${source.page_numbers.join(", ")})`
        navigator.clipboard.writeText(text).then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        })
    }

    const firstPage = source.page_numbers[0] ?? 1

    if (compact) {
        const webDomain = isWeb ? getDomain(source.url || source.doc_id.replace(/^web:/, "")) : ""
        // Compact card for the horizontal strip — fixed width, no copy button in the label area
        return (
            <div
                className="group/card relative rounded-lg shrink-0"
                onClick={() => onPageClick(firstPage)}
                style={{
                    width: 140,
                    padding: `${SPACE['1']}px ${SPACE['2']}px`,
                    background: isActive
                        ? "var(--gm-surface-1, var(--dt-color-gold-tint))"
                        : "var(--gm-surface-3, var(--dt-glass-bg-subtle))",
                    border: `0.5px solid ${isActive
                        ? "var(--gm-accent-border, var(--dt-color-gold-border))"
                        : "var(--gm-border-inner-glow, var(--dt-glass-border-subtle))"}`,
                    backdropFilter: isActive ? "blur(15px)" : "blur(4px)",
                    WebkitBackdropFilter: isActive ? "blur(15px)" : "blur(4px)",
                    cursor: "pointer",
                    transition: `all ${TIMING.fast} ${EASE.out}`,
                }}
            >
                {isWeb ? (
                    <>
                        <div style={{display: "flex", alignItems: "center", gap: SPACE['1'], marginBottom: SPACE['1']}}>
                            <Globe size={10} style={{
                                color: "var(--dt-color-gold-base)",
                                flexShrink: 0,
                            }} />
                            <p className="truncate" title={source.title || ""} style={{
                                fontSize: TYPE_SCALE.xs,
                                fontWeight: 500,
                                fontFamily: FONT.sans,
                                color: "var(--dt-text-secondary)",
                                margin: 0,
                            }}>
                                {displayId.length > 18 ? displayId.slice(0, 18) + "\u2026" : displayId}
                            </p>
                        </div>
                        <p className="truncate" style={{
                            fontSize: TYPE_SCALE.xs,
                            fontFamily: FONT.sans,
                            color: "var(--dt-text-quaternary)",
                            margin: 0,
                        }}>{webDomain}</p>
                    </>
                ) : isCourtDecision(source) ? (
                    <>
                        <p className="truncate" title={source.case_number ?? source.doc_id} style={{
                            fontSize: TYPE_SCALE.xs,
                            fontWeight: 600,
                            fontFamily: FONT.sans,
                            color: "var(--dt-text-secondary)",
                            margin: `0 0 ${SPACE['1']}px`,
                        }}>
                            {(source.case_number ?? source.doc_id).length > 18
                                ? (source.case_number ?? source.doc_id).slice(0, 17) + "\u2026"
                                : (source.case_number ?? source.doc_id)}
                        </p>
                        <div style={{display: "flex", alignItems: "center", gap: SPACE['1']}}>
                            {source.decision_date && (
                                <span style={{
                                    fontSize: TYPE_SCALE.xs, fontFamily: FONT.sans,
                                    color: "var(--dt-text-quaternary)",
                                }}>{source.decision_date.slice(0, 4)}</span>
                            )}
                            {source.category && (
                                <span style={{
                                    fontSize: TYPE_SCALE.xs, fontWeight: 700, fontFamily: FONT.sans,
                                    padding: `0 ${SPACE['1']}px`, borderRadius: RADIUS.xs,
                                    background: source.category === "A" ? "var(--dt-color-gold-tint)" : "var(--dt-glass-bg-subtle)",
                                    border: `0.5px solid ${source.category === "A" ? "var(--dt-color-gold-border)" : "var(--dt-glass-border-subtle)"}`,
                                    color: source.category === "A" ? "var(--dt-color-gold-base)" : "var(--dt-text-tertiary)",
                                }}>{source.category}</span>
                            )}
                        </div>
                    </>
                ) : (
                    <>
                        <p className="truncate" title={source.doc_id} style={{
                            fontFamily: FONT.mono,
                            fontSize: TYPE_SCALE.xs,
                            color: "var(--dt-text-tertiary)",
                            marginBottom: SPACE['1'],
                        }}>
                            {displayId}
                        </p>
                        <div style={{display: "flex", flexWrap: "wrap", gap: SPACE['1']}}>
                            {source.page_numbers.map((page) => {
                                const isActivePage = isActive && activePage === page
                                return (
                                    <button
                                        key={page}
                                        onClick={(e) => { e.stopPropagation(); onPageClick(page) }}
                                        style={{
                                            display: "inline-flex", alignItems: "center",
                                            height: 18, padding: `0 ${SPACE['1']}px`,
                                            borderRadius: RADIUS.xs, fontSize: TYPE_SCALE.xs, fontWeight: 500,
                                            background: isActivePage
                                                ? "var(--gm-accent-glow, var(--dt-color-gold-glow))"
                                                : "var(--gm-surface-3, var(--dt-glass-bg-subtle))",
                                            border: `0.5px solid ${isActivePage
                                                ? "var(--gm-accent-border, var(--dt-color-gold-border))"
                                                : "var(--gm-border-inner-glow, var(--dt-glass-border))"}`,
                                            color: isActivePage
                                                ? "var(--gm-accent, var(--dt-color-gold-base))"
                                                : "var(--dt-text-tertiary)",
                                            cursor: "pointer",
                                            transition: `all ${TIMING.instant} ${EASE.out}`,
                                        }}
                                    >
                                        {isTxtSource(source) ? `L.${page}` : `p.${page}`}
                                    </button>
                                )
                            })}
                        </div>
                    </>
                )}
            </div>
        )
    }

    return (
        <div
            className="group/card relative rounded-lg p-3"
            onClick={() => onPageClick(firstPage)}
            style={{
                background: isActive
                    ? "var(--gm-surface-1, var(--dt-color-gold-tint))"
                    : "var(--gm-surface-3, var(--dt-glass-bg-subtle))",
                border: `0.5px solid ${isActive
                    ? "var(--gm-accent-border, var(--dt-color-gold-border))"
                    : "var(--gm-border-inner-glow, var(--dt-glass-border-subtle))"}`,
                backdropFilter: isActive ? "blur(15px)" : "blur(4px)",
                WebkitBackdropFilter: isActive ? "blur(15px)" : "blur(4px)",
                cursor: "pointer",
                transition: `all ${TIMING.fast} ${EASE.out}`,
            }}
        >
            <div className="flex items-center justify-between mb-2">
                {isCourtDecision(source) ? (
                    <div style={{display: "flex", alignItems: "center", justifyContent: "space-between", minWidth: 0, flex: 1, gap: SPACE['2']}}>
                        <p className="text-xs truncate" title={source.case_number ?? source.doc_id} style={{
                            color: "var(--dt-text-secondary)",
                            fontWeight: 700,
                            fontFamily: FONT.sans,
                        }}>
                            {source.case_number ?? displayId}
                        </p>
                        {source.category && (
                            <span style={{
                                fontSize: TYPE_SCALE.xs, fontWeight: 700, fontFamily: FONT.sans,
                                padding: `1px ${SPACE['2']}px`, borderRadius: RADIUS.xs, flexShrink: 0,
                                background: source.category === "A" ? "var(--dt-color-gold-tint)" : "var(--dt-glass-bg-subtle)",
                                border: `0.5px solid ${source.category === "A" ? "var(--dt-color-gold-border)" : "var(--dt-glass-border-subtle)"}`,
                                color: source.category === "A" ? "var(--dt-color-gold-base)" : "var(--dt-text-tertiary)",
                            }}>{source.category}</span>
                        )}
                    </div>
                ) : isWeb ? (
                    <div style={{display: "flex", alignItems: "center", gap: SPACE['2'], minWidth: 0, flex: 1}}>
                        <Globe size={TYPE_SCALE.sm} style={{
                            color: "var(--dt-color-gold-base)",
                            flexShrink: 0,
                        }} />
                        <p className="text-xs truncate" title={source.title || source.url || ""}
                           style={{
                               color: "var(--dt-text-secondary)",
                               fontWeight: 500,
                               fontFamily: FONT.sans,
                           }}
                        >
                            {displayId}
                        </p>
                    </div>
                ) : (
                    <p className="text-xs truncate" title={source.doc_id}
                       style={{
                           color: "var(--dt-text-tertiary)",
                           fontFamily: FONT.mono,
                       }}
                    >
                        {displayId}
                    </p>
                )}
                <button
                    onClick={handleCopySource}
                    className="rounded p-1 opacity-0 group-hover/card:opacity-100 focus-visible:opacity-100 shrink-0 ml-2"
                    style={{
                        background: "var(--gm-surface-3, var(--dt-glass-bg-subtle))",
                        border: `0.5px solid var(--gm-border-inner-glow, var(--dt-glass-border-subtle))`,
                        color: copied ? "var(--dt-color-blue-base)" : "var(--gm-accent, var(--dt-accent-color))",
                        transition: `all ${TIMING.instant} ${EASE.out}`,
                    }}
                    aria-label={isCourtDecision(source) ? "Copy case reference" : isWeb ? "Copy URL" : "Copy source reference"}
                >
                    {copied ? <Check className="size-2.5"/> : <Copy className="size-2.5"/>}
                </button>
            </div>
            {isCourtDecision(source) ? (
                <div>
                    {(source.court || source.decision_date) && (
                        <p style={{
                            fontSize: TYPE_SCALE.xs, fontFamily: FONT.sans,
                            color: "var(--dt-text-quaternary)",
                            margin: `0 0 ${SPACE['1']}px`,
                        }}>
                            {[source.court, formatCzechDate(source.decision_date)].filter(Boolean).join(" | ")}
                        </p>
                    )}
                    {source.legal_thesis && (
                        <p style={{
                            fontSize: TYPE_SCALE.xs, fontFamily: FONT.sans, fontStyle: "italic",
                            color: "var(--dt-text-tertiary)",
                            margin: 0,
                            overflow: "hidden",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                        }}>
                            {source.legal_thesis.length > 120
                                ? source.legal_thesis.slice(0, 120) + "\u2026"
                                : source.legal_thesis}
                        </p>
                    )}
                </div>
            ) : isWeb ? (
                <p className="truncate" style={{
                    fontSize: TYPE_SCALE.xs,
                    fontFamily: FONT.sans,
                    color: "var(--dt-text-quaternary)",
                    margin: 0,
                }}>{getDomain(source.url || source.doc_id.replace(/^web:/, ""))}</p>
            ) : (
                <div className="flex flex-wrap" style={{gap: SPACE['1']}}>
                    {source.page_numbers.map((page) => {
                        const isActivePage = isActive && activePage === page
                        return (
                            <button
                                key={page}
                                onClick={(e) => { e.stopPropagation(); onPageClick(page) }}
                                className="inline-flex items-center font-medium"
                                style={{
                                    height: SPACE['6'],
                                    padding: `0 ${SPACE['2']}px`,
                                    borderRadius: RADIUS.xs,
                                    fontSize: TYPE_SCALE.xs,
                                    background: isActivePage
                                        ? "var(--gm-accent-glow, var(--dt-color-gold-glow))"
                                        : "var(--gm-surface-3, var(--dt-glass-bg-subtle))",
                                    border: `0.5px solid ${isActivePage
                                        ? "var(--gm-accent-border, var(--dt-color-gold-border))"
                                        : "var(--gm-border-inner-glow, var(--dt-glass-border))"}`,
                                    color: isActivePage
                                        ? "var(--gm-accent, var(--dt-color-gold-base))"
                                        : "var(--dt-text-tertiary)",
                                    cursor: "pointer",
                                    transition: `all ${TIMING.instant} ${EASE.out}`,
                                }}
                            >
                                {isTxtSource(source) ? `L.${page}` : `p.${page}`}
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
