"use client"

import {useState, useEffect, useRef, useMemo} from "react"
import {ChevronDown, ChevronUp} from "lucide-react"
import {cn} from "@/lib/utils"
import {toSafeString, toSafeStringOrNull, toSafeNumber} from "@/lib/utils"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {PdfViewer} from "./pdf-viewer"
import {
    SourceRef,
    stripChunkPrefix,
    cleanJudgmentText,
    TEXT_TRUNCATE_LIMIT,
    isCourtDecision,
    isTxtSource,
    formatCzechDate,
    API_BASE,
} from "./grounding-utils"
import {
    HighlightedLegalText,
    ContextChunkView,
    ChunkContextItem,
    ChunkContextResult,
} from "./legal-text"

// ── Citation scoring ──────────────────────────────────────────────────────────

const CITATION_SCORE_THRESHOLD = 0.12

/** Score how relevant a source paragraph is to the answer using 3-gram overlap.
 *  Returns [0, 1]; higher means more trigrams from the paragraph appear verbatim
 *  in the answer text. Used to highlight paragraphs the AI drew from. */
function paragraphCitationScore(para: string, answer: string): number {
    const normalize = (s: string) =>
        s.replace(/[^a-z0-9\s]/gi, " ").replace(/\s+/g, " ").toLowerCase().trim()
    const normPara = normalize(para)
    const normAnswer = normalize(answer)
    const words = normPara.split(" ").filter(w => w.length > 3)
    if (words.length < 4) return 0
    let matches = 0
    for (let i = 0; i <= words.length - 3; i++) {
        if (normAnswer.includes(words.slice(i, i + 3).join(" "))) matches++
    }
    return matches / Math.max(1, words.length - 2)
}

/** PDF viewer with automatic fallback to text viewer when PDF is not found (404). */
export function PdfViewerWithFallback({source, page, answer, isMobile, onPageClick}: {
    source: SourceRef
    page: number
    answer: string
    isMobile: boolean
    onPageClick: (page: number) => void
}) {
    const [pdfFailed, setPdfFailed] = useState(false)

    if (pdfFailed) {
        return <TextSourceViewer source={source} page={page} answer={answer} isMobile={isMobile} onPageClick={onPageClick} pdfFailed />
    }

    return (
        <PdfViewer
            key={source.doc_id}
            docId={source.doc_id}
            page={page}
            className="h-full"
            highlightText={stripChunkPrefix(source.text) ?? undefined}
            onError={() => setPdfFailed(true)}
        />
    )
}

/** Text viewer for Czech Supreme Court decisions.
 *  Shows case metadata header (case number, court, date, category badge) followed
 *  by the decision text with interactive highlights, same as statute sources. */
export function CourtDecisionTextViewer({source, isMobile, onPageClick}: {
    source: SourceRef
    isMobile: boolean
    onPageClick: (page: number) => void
}) {
    const [expanded, setExpanded] = useState(false)

    const isLandmark = source.category === "A"
    const caseLabel = toSafeStringOrNull(source.case_number) ?? source.doc_id
    const formattedDate = formatCzechDate(source.decision_date)
    const subtitle = [toSafeStringOrNull(source.court), formattedDate].filter(Boolean).join(" | ")

    const raw = source.text ?? ""
    const body = raw.trim()
    const needsTruncation = body.length > TEXT_TRUNCATE_LIMIT
    const displayBody = expanded || !needsTruncation ? body : body.slice(0, TEXT_TRUNCATE_LIMIT)
    const paragraphs = useMemo(
        () => displayBody.split(/\n{2,}/).map(p => p.trim()).filter(Boolean),
        [displayBody],
    )

    return (
        <div className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
            background: "var(--gm-surface-0, var(--dt-content-card-bg))",
            border: `1px solid var(--gm-border-outer, var(--dt-content-card-border))`,
            backdropFilter: "blur(10px)",
            WebkitBackdropFilter: "blur(10px)",
            boxShadow: `inset 0 0 2px 1px var(--gm-border-inner-glow, rgba(222,222,222,0.14)), 0 ${SPACE['1']}px ${SPACE['6']}px rgba(0,0,0,0.30)`,
        }}>
            {/* Case metadata header */}
            <div style={{marginBottom: SPACE['4']}}>
                <div style={{display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: SPACE['2'], marginBottom: SPACE['1']}}>
                    <p style={{
                        fontSize: TYPE_SCALE.sm,
                        fontWeight: 700,
                        fontFamily: FONT.sans,
                        color: "var(--dt-text-strong)",
                        margin: 0,
                        wordBreak: "break-word",
                    }}>{caseLabel}</p>
                    {source.category && (
                        <span style={{
                            fontSize: TYPE_SCALE.xs,
                            fontWeight: 700,
                            fontFamily: FONT.sans,
                            padding: `1px ${SPACE['2']}px`,
                            borderRadius: RADIUS.xs,
                            background: isLandmark ? "var(--dt-color-gold-tint)" : "var(--dt-glass-bg-subtle)",
                            border: `0.5px solid ${isLandmark ? "var(--dt-color-gold-border)" : "var(--dt-glass-border-subtle)"}`,
                            color: isLandmark ? "var(--dt-color-gold-base)" : "var(--dt-text-tertiary)",
                            flexShrink: 0,
                        }}>{source.category}</span>
                    )}
                </div>
                {subtitle && (
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        fontFamily: FONT.sans,
                        color: "var(--dt-text-tertiary)",
                        margin: 0,
                    }}>{subtitle}</p>
                )}
            </div>

            <div style={{
                height: "0.5px",
                background: "var(--dt-glass-border-subtle)",
                marginBottom: SPACE['4'],
            }} />

            {/* Decision text — all paragraphs highlighted (entire text is the cited source) */}
            <div style={{display: "flex", flexDirection: "column", gap: SPACE['3']}}>
                {paragraphs.map((para, pi) => (
                    <p key={pi} style={{
                        fontSize: TYPE_SCALE.sm,
                        lineHeight: 1.7,
                        color: "var(--dt-text-strong)",
                        fontFamily: FONT.sans,
                        margin: 0,
                        wordBreak: "break-word",
                        background: "var(--dt-accent-tint-faint)",
                        borderLeft: `3px solid var(--dt-accent-highlight-strong)`,
                        paddingLeft: SPACE['2'],
                        paddingTop: 6,
                        paddingBottom: 6,
                        borderRadius: `0 ${RADIUS.xs}px ${RADIUS.xs}px 0`,
                    }}>
                        <HighlightedLegalText text={para} onPageClick={onPageClick} />
                    </p>
                ))}
            </div>

            {needsTruncation && (
                <button
                    onClick={() => setExpanded(v => !v)}
                    style={{
                        display: "inline-flex", alignItems: "center", gap: SPACE['1'],
                        marginTop: SPACE['3'], padding: `${SPACE['1']}px ${SPACE['3']}px`,
                        fontSize: TYPE_SCALE.xs, fontWeight: 500, fontFamily: FONT.sans,
                        color: "var(--dt-color-gold-base)", background: "var(--dt-color-gold-tint)",
                        border: `0.5px solid var(--dt-color-gold-border)`, borderRadius: RADIUS.sm,
                        cursor: "pointer", transition: `all ${TIMING.instant} ${EASE.out}`,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--dt-color-gold-glow)" }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "var(--dt-color-gold-tint)" }}
                >
                    {expanded ? (
                        <><ChevronUp size={SPACE['3']} />Show less</>
                    ) : (
                        <><ChevronDown size={SPACE['3']} />Show more ({Math.round(body.length / 1000)}k chars)</>
                    )}
                </button>
            )}
        </div>
    )
}

/** Single-chunk fallback view — used while context is loading or when chunk_id is absent.
 *  Extracted as a separate component so its hooks are isolated from TextSourceViewer's
 *  conditional returns (which would otherwise violate the Rules of Hooks). */
export function SingleChunkView({source, raw, answer, isMobile, onPageClick}: {
    source: SourceRef
    raw: string
    answer: string
    isMobile: boolean
    onPageClick: (page: number) => void
}) {
    const [expanded, setExpanded] = useState(false)

    // When `source.text` is present it IS the retrieved chunk — the entire chunk
    // is relevant. Skip trigram scoring against the AI answer in that case and
    // treat all paragraphs as cited so the user sees the full cited passage highlighted.
    const isChunkMode = source.text != null

    const headerMatch = raw.match(/^\[([^\]]+)\]\s*([^\n]*)\n?([\s\S]*)$/)
    const lawName = headerMatch?.[1] ?? ""
    const breadcrumb = headerMatch?.[2]?.trim() ?? ""
    const body = headerMatch?.[3] ?? raw

    const cleanedBody = useMemo(() => cleanJudgmentText(body), [body])
    const needsTruncation = cleanedBody.length > TEXT_TRUNCATE_LIMIT
    const displayBody = expanded || !needsTruncation
        ? cleanedBody
        : cleanedBody.slice(0, TEXT_TRUNCATE_LIMIT)

    const paragraphs = useMemo(() => {
        return displayBody
            .split(/\n{2,}/)
            .map((p) => p.trim())
            .filter(Boolean)
    }, [displayBody])

    const fullParagraphs = useMemo(() => {
        return cleanedBody
            .split(/\n{2,}/)
            .map((p) => p.trim())
            .filter(Boolean)
    }, [cleanedBody])

    const scrollContainerRef = useRef<HTMLDivElement>(null)
    const firstCitedRef = useRef<HTMLParagraphElement>(null)

    const fullCitationScores = useMemo(
        () => fullParagraphs.map(p => paragraphCitationScore(p, answer)),
        [fullParagraphs, answer]
    )
    const firstCitedIdxFull = fullCitationScores.findIndex(s => s >= CITATION_SCORE_THRESHOLD)

    useEffect(() => {
        if (!expanded && needsTruncation && firstCitedIdxFull >= paragraphs.length) {
            setExpanded(true)
        }
    }, [firstCitedIdxFull, paragraphs.length, needsTruncation, expanded])

    const firstCitedIdx = firstCitedIdxFull !== -1 && firstCitedIdxFull < paragraphs.length
        ? firstCitedIdxFull
        : -1

    useEffect(() => {
        const t = setTimeout(() => {
            const container = scrollContainerRef.current
            const el = firstCitedRef.current
            if (!container || !el) return
            const relTop = el.getBoundingClientRect().top
                - container.getBoundingClientRect().top
                + container.scrollTop
            container.scrollTo({top: Math.max(0, relTop - SPACE["5"]), behavior: "smooth"})
        }, 200)
        return () => clearTimeout(t)
    }, [source.doc_id, firstCitedIdx])

    return (
        <div ref={scrollContainerRef} className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
            background: "var(--gm-surface-0, var(--dt-content-card-bg))",
            border: `1px solid var(--gm-border-outer, var(--dt-content-card-border))`,
            backdropFilter: "blur(10px)",
            WebkitBackdropFilter: "blur(10px)",
            boxShadow: `inset 0 0 2px 1px var(--gm-border-inner-glow, rgba(222,222,222,0.14)), 0 ${SPACE['1']}px ${SPACE['6']}px rgba(0,0,0,0.30)`,
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
                            color: "var(--dt-color-gold-base)",
                            margin: `0 0 ${SPACE['1']}px`,
                            fontFamily: FONT.sans,
                        }}>{lawName.replace(/_/g, " ")}</p>
                    )}
                    {breadcrumb && (
                        <p style={{
                            fontSize: TYPE_SCALE.xs,
                            color: "var(--dt-text-tertiary)",
                            margin: 0,
                            fontFamily: FONT.sans,
                        }}>{breadcrumb}</p>
                    )}
                </div>
            )}

            {/* Jump to cited passage — shown when citation scoring found a match */}
            {firstCitedIdx >= 0 && (
                <div style={{marginBottom: SPACE["3"]}}>
                    <button
                        onClick={() => {
                            const container = scrollContainerRef.current
                            const el = firstCitedRef.current
                            if (!container || !el) return
                            const relTop = el.getBoundingClientRect().top
                                - container.getBoundingClientRect().top
                                + container.scrollTop
                            container.scrollTo({top: Math.max(0, relTop - SPACE["5"]), behavior: "smooth"})
                        }}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: SPACE["1"],
                            padding: `3px ${SPACE["2"]}px`,
                            borderRadius: RADIUS.sm,
                            background: "var(--dt-color-gold-tint)",
                            border: `0.5px solid var(--dt-color-gold-border)`,
                            fontSize: TYPE_SCALE.xs,
                            fontWeight: 600,
                            color: "var(--dt-color-gold-base)",
                            cursor: "pointer",
                            fontFamily: FONT.sans,
                            transition: `background ${TIMING.fast}`,
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "var(--dt-color-gold-glow)" }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "var(--dt-color-gold-tint)" }}
                    >
                        ↓ Jump to cited passage
                    </button>
                </div>
            )}

            {/* Body text — paragraph-split with citation scoring + legal term highlighting */}
            <div style={{
                display: "flex",
                flexDirection: "column",
                gap: SPACE["3"],
            }}>
                {paragraphs.map((para, pi) => {
                    // In chunk mode every paragraph is part of the retrieved chunk and is
                    // therefore fully relevant — no need to score against the AI answer.
                    const isCited = isChunkMode || fullCitationScores[pi] >= CITATION_SCORE_THRESHOLD
                    return (
                        <p
                            key={pi}
                            ref={pi === firstCitedIdx ? firstCitedRef : undefined}
                            style={{
                                fontSize: TYPE_SCALE.sm,
                                lineHeight: 1.7,
                                color: "var(--dt-text-strong)",
                                fontFamily: FONT.sans,
                                margin: 0,
                                wordBreak: "break-word",
                                ...(isCited ? {
                                    background: "var(--dt-accent-tint-faint)",
                                    borderLeft: `3px solid var(--dt-accent-highlight-strong)`,
                                    paddingLeft: SPACE["2"],
                                    paddingTop: 6,
                                    paddingBottom: 6,
                                    borderRadius: `0 ${RADIUS.xs}px ${RADIUS.xs}px 0`,
                                } : {})
                            }}
                        >
                            <HighlightedLegalText text={para} onPageClick={onPageClick}/>
                        </p>
                    )
                })}
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
                        color: "var(--dt-color-gold-base)",
                        background: "var(--dt-color-gold-tint)",
                        border: `0.5px solid var(--dt-color-gold-border)`,
                        borderRadius: RADIUS.sm,
                        cursor: "pointer",
                        transition: `all ${TIMING.instant} ${EASE.out}`,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--dt-color-gold-glow)" }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "var(--dt-color-gold-tint)" }}
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

/** Text-only source viewer — cleans, truncates, and formats raw judgment text.
 *  When source.chunk_id is available, fetches surrounding context from the backend
 *  and renders a needle-in-haystack view with dimmed surrounding chunks. */
export function TextSourceViewer({source, page, answer, isMobile, onPageClick, pdfFailed = false}: {
    source: SourceRef
    page: number
    answer: string
    isMobile: boolean
    onPageClick: (page: number) => void
    /** Set when this viewer is rendered as a fallback after PDF 404 — prevents re-entering PdfViewerWithFallback. */
    pdfFailed?: boolean
}) {
    const [chunkContext, setChunkContext] = useState<ChunkContextResult | null>(null)

    // Fetch surrounding chunk context when chunk_id is available.
    // Falls back to current single-chunk display while in-flight or on error.
    useEffect(() => {
        if (!source.chunk_id) {
            setChunkContext(null)
            return
        }
        let cancelled = false
        setChunkContext(null)
        fetch(
            `${API_BASE}/api/v1/documents/chunk-context/${encodeURIComponent(source.chunk_id)}?window=1`,
            {credentials: "include"},
        )
            .then(async (res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                return res.json() as Promise<ChunkContextResult>
            })
            .then((data) => {
                if (!cancelled) {
                    // Coerce chunk fields — prevents React #300 from non-string API values
                    const coerced = data.chunks
                        ? data.chunks.map((c: ChunkContextItem) => ({
                            ...c,
                            text: toSafeString(c.text),
                            chunk_id: toSafeString(c.chunk_id),
                            page: toSafeNumber(c.page),
                            is_target: !!c.is_target,
                        }))
                        : data.chunks
                    setChunkContext({...data, chunks: coerced})
                }
            })
            .catch(() => {
                // Silently fall back to single-chunk view
            })

        return () => { cancelled = true }
    }, [source.chunk_id])

    // Use the retrieved chunk text directly. Never fall back to the AI answer —
    // that would show the LLM's own output as if it were the source document.
    const raw = source.text ?? ""

    // Court decisions are always text-only (no PDF, no chunk context).
    // Render with the dedicated component that shows case metadata header.
    if (isCourtDecision(source) && raw.trim()) {
        return (
            <CourtDecisionTextViewer
                source={source}
                isMobile={isMobile}
                onPageClick={onPageClick}
            />
        )
    }

    // When there is no source text (e.g. PDF-only corpus without chunk text),
    // show a graceful fallback rather than rendering nothing or the AI answer.
    if (!raw.trim()) {
        return (
            <div className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
                background: "var(--gm-surface-0, var(--dt-content-card-bg))",
                border: `1px solid var(--gm-border-outer, var(--dt-content-card-border))`,
                backdropFilter: "blur(10px)",
                WebkitBackdropFilter: "blur(10px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
            }}>
                <p style={{fontSize: TYPE_SCALE.sm, fontStyle: "italic", color: "var(--dt-text-tertiary)", fontFamily: FONT.sans}}>
                    Source text not available for this document.
                </p>
            </div>
        )
    }

    // Backend confirms a PDF exists for this document — render PDF viewer with text fallback.
    // Skip if we're already a fallback from a failed PDF load (prevents infinite loop).
    // Also skip for TXT sources — they never have a PDF representation.
    if (chunkContext?.pdf_available && !pdfFailed && !isTxtSource(source)) {
        return (
            <PdfViewerWithFallback
                source={source}
                page={page}
                answer={answer}
                isMobile={isMobile}
                onPageClick={onPageClick}
            />
        )
    }

    // Once the context API call resolves, render the needle-in-haystack view
    if (chunkContext) {
        return (
            <ContextChunkView
                source={source}
                context={chunkContext}
                isMobile={isMobile}
                onPageClick={onPageClick}
            />
        )
    }

    // Single-chunk fallback — rendered as its own component to isolate hooks
    return (
        <SingleChunkView
            source={source}
            raw={raw}
            answer={answer}
            isMobile={isMobile}
            onPageClick={onPageClick}
        />
    )
}
