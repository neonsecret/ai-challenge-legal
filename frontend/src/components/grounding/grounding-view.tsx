"use client"

import {useState, useCallback, useEffect, useRef} from "react"
import {PdfViewer} from "./pdf-viewer"
import {cn} from "@/lib/utils"
import {Copy, Check} from "lucide-react"

interface SourceRef {
    doc_id: string
    page_numbers: number[]
    text?: string | null
}

interface GroundingViewProps {
    answer: string
    sources: SourceRef[]
    isDark?: boolean
    isMobile?: boolean
    focusDocId?: string
    focusPage?: number
    /** Incremented on every citation click — forces the focus effect to fire even when focusDocId/focusPage are unchanged */
    focusSeq?: number
}

// ── Legal term highlighting in grounding text ──
const LEGAL_HIGHLIGHT_RE =
    /\b((?:Article|Section|Art\.|Sec\.)\s+\d+(?:\(\d+\))?(?:\([a-z]\))?)\b|\b((?:Page|p\.)\s*\d+(?:\s*[-–]\s*\d+)?)\b|\b(pp\.\s*\d+\s*[-–]\s*\d+)\b|\b([A-Z][A-Z\s]{2,}(?:Law|Act|Code|Decree|Regulation|Directive|Statute))\b|§\s*\d+[a-z]?(?:\s+odst\.\s*\d+)?(?:\s+písm\.\s*[a-z]\))?/g

type SegmentKind = "text" | "article" | "page" | "law"

interface Segment {
    kind: SegmentKind
    text: string
}

function tokenizeLegalText(text: string): Segment[] {
    const segments: Segment[] = []
    let lastIndex = 0
    LEGAL_HIGHLIGHT_RE.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = LEGAL_HIGHLIGHT_RE.exec(text)) !== null) {
        if (match.index > lastIndex) {
            segments.push({kind: "text", text: text.slice(lastIndex, match.index)})
        }
        const kind: SegmentKind = match[1] ? "article" : match[2] || match[3] ? "page" : "law"
        segments.push({kind, text: match[0]})
        lastIndex = match.index + match[0].length
    }
    if (lastIndex < text.length) {
        segments.push({kind: "text", text: text.slice(lastIndex)})
    }
    return segments
}

function HighlightedLegalText({text, isDark, onPageClick}: {
    text: string
    isDark: boolean
    onPageClick?: (page: number) => void
}) {
    const segments = tokenizeLegalText(text)
    if (segments.length <= 1 && segments[0]?.kind === "text") return <>{text}</>

    return (
        <>
            {segments.map((seg, i) => {
                if (seg.kind === "text") return <span key={i}>{seg.text}</span>

                const accentColor = isDark ? "#C9A84C" : "#c47c00"

                if (seg.kind === "page" && onPageClick) {
                    const pageNum = parseInt(seg.text.replace(/\D+/g, ""), 10)
                    return (
                        <span
                            key={i}
                            onClick={() => !isNaN(pageNum) && onPageClick(pageNum)}
                            style={{
                                color: accentColor,
                                fontWeight: 600,
                                cursor: "pointer",
                                textDecoration: "underline",
                                textDecorationStyle: "dotted",
                                textUnderlineOffset: "2px",
                                textDecorationColor: isDark ? "rgba(201,168,76,0.40)" : "rgba(196,124,0,0.30)",
                            }}
                        >
              {seg.text}
            </span>
                    )
                }

                return (
                    <span key={i} style={{color: accentColor, fontWeight: 600}}>
            {seg.text}
          </span>
                )
            })}
        </>
    )
}

function resolveSource(
    sources: SourceRef[],
    focusDocId: string | undefined,
    focusPage: number | undefined
): SourceRef | null {
    if (!focusDocId) return sources[0] ?? null
    // 1. Exact
    const exact = sources.find(s => s.doc_id === focusDocId)
    if (exact) return exact
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

export function GroundingView({answer, sources, isDark = false, isMobile = false, focusDocId, focusPage, focusSeq = 0}: GroundingViewProps) {
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
            {activeSource ? (
                /^[0-9a-f]{20,}$/i.test(activeSource.doc_id) ? (
                    <PdfViewer
                        key={activeSource.doc_id}
                        docId={activeSource.doc_id}
                        page={activePage}
                        className="h-full"
                        highlightText={answer.slice(0, 200)}
                    />
                ) : (
                    <div className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
                        background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.22)",
                        border: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.45)",
                        backdropFilter: "blur(16px) saturate(160%)",
                        WebkitBackdropFilter: "blur(16px) saturate(160%)",
                        boxShadow: isDark
                            ? "inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 24px rgba(0,0,0,0.20)"
                            : "inset 0 1.5px 0 rgba(255,255,255,0.80), 0 4px 24px rgba(100,50,0,0.08)",
                    }}>
                        {(() => {
                            const raw = activeSource.text ?? answer
                            const headerMatch = raw.match(/^\[([^\]]+)\]\s*([^\n]*)\n?([\s\S]*)$/)
                            const lawName = headerMatch?.[1] ?? ""
                            const breadcrumb = headerMatch?.[2]?.trim() ?? ""
                            const body = headerMatch?.[3] ?? raw
                            return (
                                <>
                                    {(lawName || breadcrumb) && (
                                        <div style={{marginBottom: 12}}>
                                            {lawName && (
                                                <p style={{
                                                    fontSize: 10,
                                                    fontWeight: 700,
                                                    textTransform: "uppercase" as const,
                                                    letterSpacing: "0.10em",
                                                    color: isDark ? "rgba(201,168,76,0.75)" : "#7a4a00",
                                                    margin: "0 0 2px",
                                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                                }}>{lawName.replace(/_/g, " ")}</p>
                                            )}
                                            {breadcrumb && (
                                                <p style={{
                                                    fontSize: 11,
                                                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
                                                    margin: 0,
                                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                                }}>{breadcrumb}</p>
                                            )}
                                        </div>
                                    )}
                                    <p style={{
                                        fontSize: 13,
                                        lineHeight: 1.75,
                                        color: isDark ? "rgba(255,255,255,0.82)" : "#2e1f08",
                                        fontFamily: "Georgia, 'Times New Roman', serif",
                                        margin: 0,
                                        whiteSpace: "pre-wrap",
                                    }}>
                                        <HighlightedLegalText text={body} isDark={isDark} onPageClick={handlePageFromText}/>
                                    </p>
                                </>
                            )
                        })()}
                    </div>
                )
            ) : (
                <div className="flex h-full items-center justify-center text-sm"
                     style={{color: isDark ? "rgba(255,255,255,0.35)" : "rgba(46,31,8,0.40)"}}
                >
                    No source selected
                </div>
            )}
        </div>
    )

    // Compact horizontal sources strip shown at the bottom of both layouts
    const sourcesStrip = sources.length > 0 ? (
        <div style={{
            flexShrink: 0,
            overflowX: "auto",
            overflowY: "hidden",
            display: "flex",
            gap: 6,
            padding: "6px 8px",
            minHeight: 0,
            maxHeight: 124,
            borderTop: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.30)",
            scrollbarWidth: "none",
            WebkitOverflowScrolling: "touch",
        }}>
            {sources.map((source, i) => (
                <SourceCitationCard
                    key={`${source.doc_id}-${i}`}
                    source={source}
                    isActive={activeSource?.doc_id === source.doc_id}
                    activePage={activeSource?.doc_id === source.doc_id ? activePage : null}
                    onPageClick={(page) => handleSourceClick(source, page)}
                    isDark={isDark}
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
    isDark?: boolean
    /** Compact horizontal-strip mode — narrower card for the bottom sources bar */
    compact?: boolean
}

function SourceCitationCard({
                                source,
                                isActive,
                                activePage,
                                onPageClick,
                                isDark = false,
                                compact = false,
                            }: SourceCitationCardProps) {
    const [copied, setCopied] = useState(false)
    // In compact mode show last 16 chars; normal mode show last 28
    const maxChars = compact ? 16 : 28
    const displayId =
        source.doc_id.length > maxChars ? `\u2026${source.doc_id.slice(-maxChars)}` : source.doc_id

    const handleCopySource = (e: React.MouseEvent) => {
        e.stopPropagation()
        const text = `${source.doc_id} (p. ${source.page_numbers.join(", ")})`
        navigator.clipboard.writeText(text).then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        })
    }

    const firstPage = source.page_numbers[0] ?? 1

    if (compact) {
        // Compact card for the horizontal strip — fixed width, no copy button in the label area
        return (
            <div
                className="group/card relative rounded-lg transition-all shrink-0"
                onClick={() => onPageClick(firstPage)}
                style={{
                    width: 140,
                    padding: "5px 8px",
                    background: isActive
                        ? isDark ? "rgba(201,168,76,0.12)" : "rgba(233,196,106,0.18)"
                        : isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.22)",
                    border: isActive
                        ? isDark ? "0.5px solid rgba(201,168,76,0.32)" : "0.5px solid rgba(196,124,0,0.30)"
                        : isDark ? "0.5px solid rgba(255,255,255,0.08)" : "0.5px solid rgba(255,255,255,0.50)",
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    cursor: "pointer",
                }}
            >
                <p className="font-mono truncate" title={source.doc_id} style={{
                    fontSize: 10,
                    color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.50)",
                    marginBottom: 4,
                }}>
                    {displayId}
                </p>
                <div style={{display: "flex", flexWrap: "wrap", gap: 3}}>
                    {source.page_numbers.map((page) => {
                        const isActivePage = isActive && activePage === page
                        return (
                            <button
                                key={page}
                                onClick={(e) => { e.stopPropagation(); onPageClick(page) }}
                                style={{
                                    display: "inline-flex", alignItems: "center",
                                    height: 18, padding: "0 5px",
                                    borderRadius: 4, fontSize: 10, fontWeight: 500,
                                    background: isActivePage
                                        ? isDark ? "rgba(201,168,76,0.22)" : "rgba(196,124,0,0.16)"
                                        : isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.30)",
                                    border: isActivePage
                                        ? isDark ? "0.5px solid rgba(201,168,76,0.45)" : "0.5px solid rgba(196,124,0,0.35)"
                                        : isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.55)",
                                    color: isActivePage
                                        ? isDark ? "#C9A84C" : "#7a4a00"
                                        : isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.60)",
                                    cursor: "pointer",
                                }}
                            >
                                p.{page}
                            </button>
                        )
                    })}
                </div>
            </div>
        )
    }

    return (
        <div
            className="group/card relative rounded-lg p-3 transition-all"
            onClick={() => onPageClick(firstPage)}
            style={{
                background: isActive
                    ? isDark ? "rgba(201,168,76,0.12)" : "rgba(233,196,106,0.18)"
                    : isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.22)",
                border: isActive
                    ? isDark ? "0.5px solid rgba(201,168,76,0.32)" : "0.5px solid rgba(196,124,0,0.30)"
                    : isDark ? "0.5px solid rgba(255,255,255,0.08)" : "0.5px solid rgba(255,255,255,0.50)",
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                cursor: "pointer",
            }}
        >
            <div className="flex items-center justify-between mb-2">
                <p className="font-mono text-xs truncate" title={source.doc_id}
                   style={{color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.50)"}}
                >
                    {displayId}
                </p>
                <button
                    onClick={handleCopySource}
                    className="rounded p-1 transition-all opacity-0 group-hover/card:opacity-100 focus-visible:opacity-100 shrink-0 ml-2"
                    style={{
                        background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,240,215,0.30)",
                        border: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.40)",
                        color: copied ? "#3576ae" : isDark ? "rgba(255,255,255,0.40)" : "#7a5a20",
                    }}
                    aria-label="Copy source reference"
                >
                    {copied ? <Check className="size-2.5"/> : <Copy className="size-2.5"/>}
                </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
                {source.page_numbers.map((page) => {
                    const isActivePage = isActive && activePage === page
                    return (
                        <button
                            key={page}
                            onClick={(e) => { e.stopPropagation(); onPageClick(page) }}
                            className="inline-flex h-6 items-center rounded px-2 text-[11px] font-medium transition-all"
                            style={{
                                background: isActivePage
                                    ? isDark ? "rgba(201,168,76,0.22)" : "rgba(196,124,0,0.16)"
                                    : isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.30)",
                                border: isActivePage
                                    ? isDark ? "0.5px solid rgba(201,168,76,0.45)" : "0.5px solid rgba(196,124,0,0.35)"
                                    : isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.55)",
                                color: isActivePage
                                    ? isDark ? "#C9A84C" : "#7a4a00"
                                    : isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.60)",
                                cursor: "pointer",
                            }}
                        >
                            p.{page}
                        </button>
                    )
                })}
            </div>
        </div>
    )
}
