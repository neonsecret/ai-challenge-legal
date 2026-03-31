"use client"

import {useState, useCallback, useEffect, useRef, useMemo} from "react"
import {motion, AnimatePresence} from "motion/react"
import {PdfViewer} from "./pdf-viewer"
import {cn} from "@/lib/utils"
import {Copy, Check, Globe, ExternalLink, ChevronDown, ChevronUp} from "lucide-react"
import {
    FONT, TYPE_SCALE, SPACE, COLOR, GLASS, RADIUS, TIMING, EASE,
    TEXT_DARK, TEXT_LIGHT,
} from "@/lib/design-tokens"

interface SourceRef {
    doc_id: string
    page_numbers: number[]
    text?: string | null
    url?: string | null
    title?: string | null
}

/** Check if a URL has a safe protocol (http/https only — blocks javascript: etc). */
function isSafeUrl(raw: string): boolean {
    try { return ["https:", "http:"].includes(new URL(raw).protocol) }
    catch { return false }
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

/** Navigation/boilerplate lines to strip from raw judgment text.
 *  Matches lines that consist entirely of common nav items. */
const NAV_BOILERPLATE_RE = /^\s*(DIFC Courts?|Home|About|FAQs?|Careers?|Contact|Login|Sign [Ii]n|Newsroom|News|Media|Press|Subscribe|Newsletter|Search|Menu|Skip to (?:content|main)|Cookie|Privacy|Terms|Accessibility|Sitemap|Follow us|Share|Print|Back to top|Copyright|All [Rr]ights [Rr]eserved|\u00a9.*$|Toggle navigation|Close)\s*$/i

/** Maximum character count before truncation in the source panel */
const TEXT_TRUNCATE_LIMIT = 2000

/** Strip navigation boilerplate, insert paragraph breaks, and clean up raw judgment text.
 *  DIFC judgment TXT files are scraped webpage text — one continuous blob
 *  with navigation menus, breadcrumbs, and no paragraph breaks. */
function cleanJudgmentText(raw: string): string {
    let text = raw
    // Strip everything before the first case-like heading (e.g. "Claim No:", "IN THE COURT", party names)
    const caseStart = text.search(/(?:Claim No|IN THE\s*COURT|BETWEEN|BEFORE|Hearing:|Judgment:)/i)
    if (caseStart > 100) text = text.slice(caseStart)

    // Insert paragraph breaks before numbered paragraphs (1. 2. 3. etc.)
    text = text.replace(/(?<=[.!?"'])\s*(\d{1,3}\.\s+[A-Z])/g, "\n\n$1")
    // Insert breaks before common legal section headers
    text = text.replace(/((?:IT IS HEREBY ORDERED|JUDGMENT OF|Background|Parties|The Claimant|The Defendant|Conclusion|Analysis|Discussion|Issues?|Decision|Orders?)\s*(?:that)?:?)/gi, "\n\n$1")
    // Insert breaks before ALLCAPS headings (3+ consecutive caps words)
    text = text.replace(/([.!?])\s*([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})*)/g, "$1\n\n$2")

    // Now filter lines
    return text
        .split("\n")
        .filter((line) => !NAV_BOILERPLATE_RE.test(line))
        .join("\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim()
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
            .catch(() => {
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

        return (
            <>
                <span>{before}</span>
                <mark style={{
                    background: COLOR.gold.tint,
                    borderBottom: `2px solid ${COLOR.gold.border}`,
                    borderRadius: RADIUS.xs,
                    padding: `1px ${SPACE['1']}px`,
                    color: "inherit",
                }}>{highlighted}</mark>
                <span>{after}</span>
            </>
        )
    }, [])

    const accentColor = isDark ? COLOR.gold.base : COLOR.gold.base
    const mutedColor = isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary
    const textColor = isDark ? TEXT_DARK.secondary : TEXT_LIGHT.secondary

    return (
        <div className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
            background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
            border: `0.5px solid ${isDark ? GLASS.dark.border : GLASS.light.borderSubtle}`,
            backdropFilter: isDark ? GLASS.dark.blurLight : GLASS.light.blurLight,
            WebkitBackdropFilter: isDark ? GLASS.dark.blurLight : GLASS.light.blurLight,
            boxShadow: isDark
                ? `${GLASS.dark.innerGlow}, 0 ${SPACE['1']}px ${SPACE['6']}px rgba(0,0,0,0.20)`
                : `${GLASS.light.innerGlow}, 0 ${SPACE['1']}px ${SPACE['6']}px rgba(100,50,0,0.08)`,
        }}>
            {/* Header: favicon + title + domain */}
            <div style={{display: "flex", alignItems: "center", gap: SPACE['3'], marginBottom: SPACE['3']}}>
                <img
                    src={`https://icons.duckduckgo.com/ip3/${domain}.ico`}
                    alt=""
                    width={SPACE['5']}
                    height={SPACE['5']}
                    style={{borderRadius: RADIUS.xs, flexShrink: 0}}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                />
                <div style={{minWidth: 0, flex: 1}}>
                    <p style={{
                        fontSize: TYPE_SCALE.sm,
                        fontWeight: 600,
                        fontFamily: FONT.sans,
                        color: textColor,
                        margin: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>{displayTitle}</p>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        fontFamily: FONT.sans,
                        color: mutedColor,
                        margin: `${SPACE['1']}px 0 0`,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>{domain}</p>
                </div>
            </div>

            {/* Open original link */}
            <a
                href={isSafeUrl(url) ? url : "#"}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: SPACE['1'],
                    fontSize: TYPE_SCALE.xs,
                    fontWeight: 500,
                    fontFamily: FONT.sans,
                    color: accentColor,
                    textDecoration: "none",
                    marginBottom: SPACE['4'],
                    padding: `${SPACE['1']}px ${SPACE['3']}px`,
                    borderRadius: RADIUS.sm,
                    background: COLOR.gold.tint,
                    border: `0.5px solid ${COLOR.gold.border}`,
                    transition: `all ${TIMING.instant} ${EASE.out}`,
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = COLOR.gold.glow
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = COLOR.gold.tint
                }}
            >
                <ExternalLink size={SPACE['3']} />
                Open original page
            </a>

            {/* Snippet preview (always shown) */}
            {snippet && (
                <div style={{
                    marginBottom: SPACE['4'],
                    padding: SPACE['3'],
                    borderRadius: RADIUS.md,
                    background: COLOR.gold.tint,
                    borderLeft: `3px solid ${accentColor}`,
                }}>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        fontWeight: 700,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.10em",
                        fontFamily: FONT.sans,
                        color: accentColor,
                        margin: `0 0 ${SPACE['2']}px`,
                    }}>Search snippet</p>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        lineHeight: 1.65,
                        color: textColor,
                        fontFamily: FONT.brand,
                        margin: 0,
                    }}>{snippet}</p>
                </div>
            )}

            {/* Full page content */}
            {loading ? (
                <div style={{display: "flex", flexDirection: "column", gap: SPACE['2']}}>
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} style={{
                            height: SPACE['4'],
                            borderRadius: RADIUS.xs,
                            width: `${60 + Math.random() * 35}%`,
                            background: isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                            animation: "pulse 1.5s ease-in-out infinite",
                        }} />
                    ))}
                    <style>{`@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }`}</style>
                </div>
            ) : error ? (
                <p style={{fontSize: TYPE_SCALE.xs, color: mutedColor, fontStyle: "italic"}}>{error}</p>
            ) : content ? (
                <div>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        fontWeight: 700,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.10em",
                        fontFamily: FONT.sans,
                        color: mutedColor,
                        margin: `0 0 ${SPACE['2']}px`,
                    }}>Page content</p>
                    <div style={{
                        fontSize: TYPE_SCALE.sm,
                        lineHeight: 1.7,
                        color: textColor,
                        fontFamily: FONT.sans,
                    }}>
                        {content.split(/\n{2,}/).filter(Boolean).map((para, pi) => (
                            <p key={pi} style={{margin: `0 0 ${SPACE['3']}px`}}>
                                {renderContentWithHighlight(para.replace(/\n/g, " ").trim(), snippet)}
                            </p>
                        ))}
                    </div>
                </div>
            ) : (
                <p style={{fontSize: TYPE_SCALE.xs, color: mutedColor, fontStyle: "italic"}}>No content could be extracted from this page.</p>
            )}
        </div>
    )
}

/** Text-only source viewer — cleans, truncates, and formats raw judgment text. */
function TextSourceViewer({source, answer, isDark, isMobile, onPageClick}: {
    source: SourceRef
    answer: string
    isDark: boolean
    isMobile: boolean
    onPageClick: (page: number) => void
}) {
    const [expanded, setExpanded] = useState(false)

    const raw = source.text ?? answer
    const headerMatch = raw.match(/^\[([^\]]+)\]\s*([^\n]*)\n?([\s\S]*)$/)
    const lawName = headerMatch?.[1] ?? ""
    const breadcrumb = headerMatch?.[2]?.trim() ?? ""
    const body = headerMatch?.[3] ?? raw

    const cleanedBody = useMemo(() => cleanJudgmentText(body), [body])
    const needsTruncation = cleanedBody.length > TEXT_TRUNCATE_LIMIT
    const displayBody = expanded || !needsTruncation
        ? cleanedBody
        : cleanedBody.slice(0, TEXT_TRUNCATE_LIMIT)

    // Split into paragraphs for better readability
    const paragraphs = useMemo(() => {
        return displayBody
            .split(/\n{2,}/)
            .map((p) => p.trim())
            .filter(Boolean)
    }, [displayBody])

    const textColor = isDark ? TEXT_DARK.secondary : TEXT_LIGHT.secondary
    const mutedColor = isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary

    return (
        <div className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
            background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
            border: `0.5px solid ${isDark ? GLASS.dark.border : GLASS.light.borderSubtle}`,
            backdropFilter: isDark ? GLASS.dark.blurLight : GLASS.light.blurLight,
            WebkitBackdropFilter: isDark ? GLASS.dark.blurLight : GLASS.light.blurLight,
            boxShadow: isDark
                ? `${GLASS.dark.innerGlow}, 0 ${SPACE['1']}px ${SPACE['6']}px rgba(0,0,0,0.20)`
                : `${GLASS.light.innerGlow}, 0 ${SPACE['1']}px ${SPACE['6']}px rgba(100,50,0,0.08)`,
        }}>
            {/* Header: law name + breadcrumb */}
            {(lawName || breadcrumb) && (
                <div style={{marginBottom: SPACE['3']}}>
                    {lawName && (
                        <p style={{
                            fontSize: TYPE_SCALE.xs,
                            fontWeight: 700,
                            textTransform: "uppercase" as const,
                            letterSpacing: "0.10em",
                            color: isDark ? COLOR.gold.solid : COLOR.gold.base,
                            margin: `0 0 ${SPACE['1']}px`,
                            fontFamily: FONT.sans,
                        }}>{lawName.replace(/_/g, " ")}</p>
                    )}
                    {breadcrumb && (
                        <p style={{
                            fontSize: TYPE_SCALE.xs,
                            color: mutedColor,
                            margin: 0,
                            fontFamily: FONT.sans,
                        }}>{breadcrumb}</p>
                    )}
                </div>
            )}

            {/* Body text — paragraph-split with legal highlighting */}
            <div style={{
                display: "flex",
                flexDirection: "column",
                gap: SPACE['3'],
            }}>
                {paragraphs.map((para, pi) => (
                    <p key={pi} style={{
                        fontSize: TYPE_SCALE.sm,
                        lineHeight: 1.7,
                        color: textColor,
                        fontFamily: FONT.sans,
                        margin: 0,
                        wordBreak: "break-word",
                    }}>
                        <HighlightedLegalText text={para} isDark={isDark} onPageClick={onPageClick}/>
                    </p>
                ))}
            </div>

            {/* Truncation: "Show more" / "Show less" toggle */}
            {needsTruncation && (
                <button
                    onClick={() => setExpanded((v) => !v)}
                    style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: SPACE['1'],
                        marginTop: SPACE['3'],
                        padding: `${SPACE['1']}px ${SPACE['3']}px`,
                        fontSize: TYPE_SCALE.xs,
                        fontWeight: 500,
                        fontFamily: FONT.sans,
                        color: COLOR.gold.base,
                        background: COLOR.gold.tint,
                        border: `0.5px solid ${COLOR.gold.border}`,
                        borderRadius: RADIUS.sm,
                        cursor: "pointer",
                        transition: `all ${TIMING.instant} ${EASE.out}`,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = COLOR.gold.glow }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = COLOR.gold.tint }}
                >
                    {expanded ? (
                        <>
                            <ChevronUp size={SPACE['3']} />
                            Show less
                        </>
                    ) : (
                        <>
                            <ChevronDown size={SPACE['3']} />
                            Show more ({Math.round(cleanedBody.length / 1000)}k chars)
                        </>
                    )}
                </button>
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

                if (seg.kind === "page" && onPageClick) {
                    const pageNum = parseInt(seg.text.replace(/\D+/g, ""), 10)
                    return (
                        <span
                            key={i}
                            onClick={() => !isNaN(pageNum) && onPageClick(pageNum)}
                            style={{
                                color: COLOR.gold.base,
                                fontWeight: 600,
                                cursor: "pointer",
                                textDecoration: "underline",
                                textDecorationStyle: "dotted",
                                textUnderlineOffset: "2px",
                                textDecorationColor: COLOR.gold.border,
                            }}
                        >
              {seg.text}
            </span>
                    )
                }

                return (
                    <span key={i} style={{color: COLOR.gold.base, fontWeight: 600}}>
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

const crossfade = {duration: parseFloat(TIMING.fast)}

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
            <AnimatePresence mode="wait">
                {activeSource ? (
                    <motion.div
                        key={activeSource.doc_id}
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
                            <TextSourceViewer
                                source={activeSource}
                                answer={answer}
                                isDark={isDark}
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
                        style={{color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary}}
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
            display: "flex",
            gap: SPACE['2'],
            padding: SPACE['2'],
            minHeight: 0,
            maxHeight: 124,
            borderTop: `0.5px solid ${isDark ? GLASS.dark.borderSubtle : GLASS.light.borderSubtle}`,
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
                className="group/card relative rounded-lg shrink-0"
                onClick={() => onPageClick(firstPage)}
                style={{
                    width: 140,
                    padding: `${SPACE['1']}px ${SPACE['2']}px`,
                    background: isActive
                        ? COLOR.gold.tint
                        : isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                    border: `0.5px solid ${isActive
                        ? COLOR.gold.border
                        : isDark ? GLASS.dark.borderSubtle : GLASS.light.border}`,
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    cursor: "pointer",
                    transition: `all ${TIMING.fast} ${EASE.out}`,
                }}
            >
                {isWeb ? (
                    <>
                        <div style={{display: "flex", alignItems: "center", gap: SPACE['1'], marginBottom: SPACE['1']}}>
                            <Globe size={10} style={{
                                color: COLOR.gold.base,
                                flexShrink: 0,
                            }} />
                            <p className="truncate" title={source.title || ""} style={{
                                fontSize: TYPE_SCALE.xs,
                                fontWeight: 500,
                                fontFamily: FONT.sans,
                                color: isDark ? TEXT_DARK.secondary : TEXT_LIGHT.secondary,
                                margin: 0,
                            }}>
                                {displayId.length > 18 ? displayId.slice(0, 18) + "\u2026" : displayId}
                            </p>
                        </div>
                        <p className="truncate" style={{
                            fontSize: TYPE_SCALE.xs,
                            fontFamily: FONT.sans,
                            color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                            margin: 0,
                        }}>{webDomain}</p>
                    </>
                ) : (
                    <>
                        <p className="truncate" title={source.doc_id} style={{
                            fontFamily: FONT.mono,
                            fontSize: TYPE_SCALE.xs,
                            color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                                                ? COLOR.gold.glow
                                                : isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                            border: `0.5px solid ${isActivePage
                                                ? COLOR.gold.border
                                                : isDark ? GLASS.dark.border : GLASS.light.border}`,
                                            color: isActivePage
                                                ? COLOR.gold.base
                                                : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                            cursor: "pointer",
                                            transition: `all ${TIMING.instant} ${EASE.out}`,
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
            className="group/card relative rounded-lg p-3"
            onClick={() => onPageClick(firstPage)}
            style={{
                background: isActive
                    ? COLOR.gold.tint
                    : isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                border: `0.5px solid ${isActive
                    ? COLOR.gold.border
                    : isDark ? GLASS.dark.borderSubtle : GLASS.light.border}`,
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                cursor: "pointer",
                transition: `all ${TIMING.fast} ${EASE.out}`,
            }}
        >
            <div className="flex items-center justify-between mb-2">
                {isWeb ? (
                    <div style={{display: "flex", alignItems: "center", gap: SPACE['2'], minWidth: 0, flex: 1}}>
                        <Globe size={TYPE_SCALE.sm} style={{
                            color: COLOR.gold.base,
                            flexShrink: 0,
                        }} />
                        <p className="text-xs truncate" title={source.title || source.url || ""}
                           style={{
                               color: isDark ? TEXT_DARK.secondary : TEXT_LIGHT.secondary,
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
                           color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                        background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                        border: `0.5px solid ${isDark ? GLASS.dark.border : GLASS.light.borderSubtle}`,
                        color: copied ? COLOR.blue.base : isDark ? TEXT_DARK.tertiary : COLOR.gold.base,
                        transition: `all ${TIMING.instant} ${EASE.out}`,
                    }}
                    aria-label={isWeb ? "Copy URL" : "Copy source reference"}
                >
                    {copied ? <Check className="size-2.5"/> : <Copy className="size-2.5"/>}
                </button>
            </div>
            {isWeb ? (
                <p className="truncate" style={{
                    fontSize: TYPE_SCALE.xs,
                    fontFamily: FONT.sans,
                    color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
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
                                        ? COLOR.gold.glow
                                        : isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                    border: `0.5px solid ${isActivePage
                                        ? COLOR.gold.border
                                        : isDark ? GLASS.dark.border : GLASS.light.border}`,
                                    color: isActivePage
                                        ? COLOR.gold.base
                                        : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                    cursor: "pointer",
                                    transition: `all ${TIMING.instant} ${EASE.out}`,
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
