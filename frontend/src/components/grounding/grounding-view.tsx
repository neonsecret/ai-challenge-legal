"use client"

import {useState, useCallback, useEffect, useRef} from "react"
import {PdfViewer} from "./pdf-viewer"
import {cn} from "@/lib/utils"
import {Copy, Check, Globe, ExternalLink} from "lucide-react"

interface SourceRef {
    doc_id: string
    page_numbers: number[]
    text?: string | null
    url?: string | null
    title?: string | null
}

/** Check if a source is a web source (doc_id starts with "web:" or has a url field). */
function isWebSource(source: SourceRef): boolean {
    return source.doc_id.startsWith("web:") || !!source.url
}

/** Extract the domain from a URL string. */
function getDomain(url: string): string {
    try {
        return new URL(url).hostname
    } catch {
        return url.slice(0, 40)
    }
}

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

/** Web content preview component — fetches and displays extracted text from a URL. */
function WebContentPreview({source, answer, isDark, isMobile}: {
    source: SourceRef
    answer: string
    isDark: boolean
    isMobile: boolean
}) {
    const [content, setContent] = useState<string | null>(null)
    const [fetchedTitle, setFetchedTitle] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const url = source.url || source.doc_id.replace(/^web:/, "")
    const displayTitle = source.title || fetchedTitle || getDomain(url)
    const domain = getDomain(url)
    const snippet = source.text || ""

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        setContent(null)

        fetch(`${API_BASE}/api/v1/proxy/web-content?url=${encodeURIComponent(url)}`, {
            credentials: "include",
        })
            .then(async (res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                return res.json()
            })
            .then((data) => {
                if (cancelled) return
                setContent(data.content || "")
                if (data.title) setFetchedTitle(data.title)
                setLoading(false)
            })
            .catch((err) => {
                if (cancelled) return
                setError("Could not load page content")
                setLoading(false)
            })

        return () => { cancelled = true }
    }, [url])

    // Highlight the snippet within the full content
    const renderContentWithHighlight = useCallback((fullText: string, snippetText: string) => {
        if (!snippetText || snippetText.length < 10) {
            return <span>{fullText}</span>
        }
        // Normalize whitespace for matching
        const normalizedSnippet = snippetText.replace(/\s+/g, " ").trim()
        const normalizedFull = fullText.replace(/\s+/g, " ")
        const idx = normalizedFull.toLowerCase().indexOf(normalizedSnippet.toLowerCase().slice(0, 60))
        if (idx === -1) {
            return <span>{fullText}</span>
        }

        // Map back to original text approximately
        const before = fullText.slice(0, idx)
        const highlighted = fullText.slice(idx, idx + normalizedSnippet.length)
        const after = fullText.slice(idx + normalizedSnippet.length)
        const highlightBg = isDark ? "rgba(201,168,76,0.18)" : "rgba(233,196,106,0.30)"
        const highlightBorder = isDark ? "rgba(201,168,76,0.35)" : "rgba(196,124,0,0.25)"

        return (
            <>
                <span>{before}</span>
                <mark style={{
                    background: highlightBg,
                    borderBottom: `2px solid ${highlightBorder}`,
                    borderRadius: 2,
                    padding: "1px 2px",
                    color: "inherit",
                }}>{highlighted}</mark>
                <span>{after}</span>
            </>
        )
    }, [isDark])

    const accentColor = isDark ? "#C9A84C" : "#7a4a00"
    const mutedColor = isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)"
    const textColor = isDark ? "rgba(255,255,255,0.82)" : "#2e1f08"

    return (
        <div className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
            background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.22)",
            border: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.45)",
            backdropFilter: "blur(16px) saturate(160%)",
            WebkitBackdropFilter: "blur(16px) saturate(160%)",
            boxShadow: isDark
                ? "inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 24px rgba(0,0,0,0.20)"
                : "inset 0 1.5px 0 rgba(255,255,255,0.80), 0 4px 24px rgba(100,50,0,0.08)",
        }}>
            {/* Header: favicon + title + domain */}
            <div style={{display: "flex", alignItems: "center", gap: 10, marginBottom: 12}}>
                <img
                    src={`https://icons.duckduckgo.com/ip3/${domain}.ico`}
                    alt=""
                    width={20}
                    height={20}
                    style={{borderRadius: 4, flexShrink: 0}}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                />
                <div style={{minWidth: 0, flex: 1}}>
                    <p style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: textColor,
                        margin: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>{displayTitle}</p>
                    <p style={{
                        fontSize: 10,
                        color: mutedColor,
                        margin: "2px 0 0",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>{domain}</p>
                </div>
            </div>

            {/* Open original link */}
            <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    fontSize: 11,
                    fontWeight: 500,
                    color: accentColor,
                    textDecoration: "none",
                    marginBottom: 16,
                    padding: "4px 10px",
                    borderRadius: 6,
                    background: isDark ? "rgba(201,168,76,0.08)" : "rgba(233,196,106,0.15)",
                    border: isDark ? "0.5px solid rgba(201,168,76,0.20)" : "0.5px solid rgba(196,124,0,0.18)",
                    transition: "all 0.12s ease",
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = isDark ? "rgba(201,168,76,0.15)" : "rgba(233,196,106,0.25)"
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = isDark ? "rgba(201,168,76,0.08)" : "rgba(233,196,106,0.15)"
                }}
            >
                <ExternalLink size={12} />
                Open original page
            </a>

            {/* Snippet preview (always shown) */}
            {snippet && (
                <div style={{
                    marginBottom: 16,
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: isDark ? "rgba(201,168,76,0.06)" : "rgba(233,196,106,0.10)",
                    borderLeft: `3px solid ${accentColor}`,
                }}>
                    <p style={{
                        fontSize: 10,
                        fontWeight: 700,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.10em",
                        color: accentColor,
                        margin: "0 0 6px",
                    }}>Search snippet</p>
                    <p style={{
                        fontSize: 12.5,
                        lineHeight: 1.65,
                        color: textColor,
                        fontFamily: "Georgia, 'Times New Roman', serif",
                        margin: 0,
                    }}>{snippet}</p>
                </div>
            )}

            {/* Full page content */}
            {loading ? (
                <div style={{display: "flex", flexDirection: "column", gap: 8}}>
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} style={{
                            height: 14,
                            borderRadius: 4,
                            width: `${60 + Math.random() * 35}%`,
                            background: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)",
                            animation: "pulse 1.5s ease-in-out infinite",
                        }} />
                    ))}
                    <style>{`@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }`}</style>
                </div>
            ) : error ? (
                <p style={{fontSize: 12, color: mutedColor, fontStyle: "italic"}}>{error}</p>
            ) : content ? (
                <div>
                    <p style={{
                        fontSize: 10,
                        fontWeight: 700,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.10em",
                        color: mutedColor,
                        margin: "0 0 8px",
                    }}>Page content</p>
                    <div style={{
                        fontSize: 13,
                        lineHeight: 1.7,
                        color: textColor,
                        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
                    }}>
                        {content.split(/\n{2,}/).filter(Boolean).map((para, pi) => (
                            <p key={pi} style={{margin: "0 0 12px"}}>
                                {renderContentWithHighlight(para.replace(/\n/g, " ").trim(), snippet)}
                            </p>
                        ))}
                    </div>
                </div>
            ) : (
                <p style={{fontSize: 12, color: mutedColor, fontStyle: "italic"}}>No content could be extracted from this page.</p>
            )}
        </div>
    )
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
    /\b((?:Article|Section|Art\.|Sec\.)\s+\d+(?:\(\d+\))?(?:\([a-z]\))?)\b|\b((?:Page|p\.)\s*\d+(?:\s*[-–]\s*\d+)?)\b|\b(pp\.\s*\d+\s*[-–]\s*\d+)\b|\b((?:DIFC|UAE|UK|EU)\s+(?:Law|Act|Code)\s+No\.\s*\d+(?:\s+of\s+\d{4})?)\b|\b((?:[A-Z][a-z]+\s+){1,4}(?:Law|Act|Code|Decree|Regulation|Directive|Statute)(?:\s+No\.\s*\d+)?)\b|§\s*\d+[a-z]?(?:\s+odst\.\s*\d+)?(?:\s+písm\.\s*[a-z]\))?/g

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
        const kind: SegmentKind = match[1] ? "article" : match[2] || match[3] ? "page" : (match[4] || match[5]) ? "law" : "article"
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
                isWebSource(activeSource) ? (
                    <WebContentPreview
                        key={activeSource.url || activeSource.doc_id}
                        source={activeSource}
                        answer={answer}
                        isDark={isDark}
                        isMobile={isMobile}
                    />
                ) : /^[0-9a-f]{20,}$/i.test(activeSource.doc_id) ? (
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
    const isWeb = isWebSource(source)

    // In compact mode show last 16 chars; normal mode show last 28
    const maxChars = compact ? 16 : 28
    const displayId = isWeb
        ? (source.title || getDomain(source.url || source.doc_id.replace(/^web:/, "")))
        : source.doc_id.length > maxChars ? `\u2026${source.doc_id.slice(-maxChars)}` : source.doc_id

    const handleCopySource = (e: React.MouseEvent) => {
        e.stopPropagation()
        const text = isWeb
            ? (source.url || source.doc_id.replace(/^web:/, ""))
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
                {isWeb ? (
                    <>
                        <div style={{display: "flex", alignItems: "center", gap: 4, marginBottom: 3}}>
                            <Globe size={10} style={{
                                color: isDark ? "#C9A84C" : "#7a4a00",
                                flexShrink: 0,
                            }} />
                            <p className="truncate" title={source.title || ""} style={{
                                fontSize: 10,
                                fontWeight: 500,
                                color: isDark ? "rgba(255,255,255,0.65)" : "rgba(46,31,8,0.70)",
                                margin: 0,
                            }}>
                                {displayId.length > 18 ? displayId.slice(0, 18) + "\u2026" : displayId}
                            </p>
                        </div>
                        <p className="truncate" style={{
                            fontSize: 9,
                            color: isDark ? "rgba(255,255,255,0.30)" : "rgba(46,31,8,0.35)",
                            margin: 0,
                        }}>{webDomain}</p>
                    </>
                ) : (
                    <>
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
                    </>
                )}
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
                {isWeb ? (
                    <div style={{display: "flex", alignItems: "center", gap: 6, minWidth: 0, flex: 1}}>
                        <Globe size={13} style={{
                            color: isDark ? "#C9A84C" : "#7a4a00",
                            flexShrink: 0,
                        }} />
                        <p className="text-xs truncate" title={source.title || source.url || ""}
                           style={{color: isDark ? "rgba(255,255,255,0.65)" : "rgba(46,31,8,0.70)", fontWeight: 500}}
                        >
                            {displayId}
                        </p>
                    </div>
                ) : (
                    <p className="font-mono text-xs truncate" title={source.doc_id}
                       style={{color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.50)"}}
                    >
                        {displayId}
                    </p>
                )}
                <button
                    onClick={handleCopySource}
                    className="rounded p-1 transition-all opacity-0 group-hover/card:opacity-100 focus-visible:opacity-100 shrink-0 ml-2"
                    style={{
                        background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,240,215,0.30)",
                        border: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.40)",
                        color: copied ? "#3576ae" : isDark ? "rgba(255,255,255,0.40)" : "#7a5a20",
                    }}
                    aria-label={isWeb ? "Copy URL" : "Copy source reference"}
                >
                    {copied ? <Check className="size-2.5"/> : <Copy className="size-2.5"/>}
                </button>
            </div>
            {isWeb ? (
                <p className="text-[10px] truncate" style={{
                    color: isDark ? "rgba(255,255,255,0.30)" : "rgba(46,31,8,0.35)",
                    margin: 0,
                }}>{getDomain(source.url || source.doc_id.replace(/^web:/, ""))}</p>
            ) : (
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
            )}
        </div>
    )
}
