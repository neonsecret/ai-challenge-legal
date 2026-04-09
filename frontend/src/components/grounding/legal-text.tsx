"use client"

import {useState, useEffect, useRef, useMemo} from "react"
import {ChevronDown, ChevronUp} from "lucide-react"
import {cn} from "@/lib/utils"
import {toSafeString} from "@/lib/utils"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {
    SourceRef,
    stripChunkPrefix,
    deduplicateChunkTexts,
    cleanJudgmentText,
    TEXT_TRUNCATE_LIMIT,
} from "./grounding-utils"

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

export function HighlightedLegalText({text: rawText, onPageClick}: {
    text: string
    onPageClick?: (page: number) => void
}) {
    const text = toSafeString(rawText)
    const segments = tokenizeLegalText(text)
    if (segments.length <= 1 && segments[0]?.kind === "text") return <>{text}</>

    return (
        <>
            {segments.map((seg, i) => {
                if (seg.kind === "text") return <span key={i}>{seg.text}</span>

                if (seg.kind === "page" && onPageClick) {
                    const pageNum = parseInt(seg.text.match(/\d+/)?.[0] ?? "", 10)
                    return (
                        <span
                            key={i}
                            onClick={() => !isNaN(pageNum) && onPageClick(pageNum)}
                            style={{
                                color: "var(--dt-color-gold-base)",
                                fontWeight: 600,
                                cursor: "pointer",
                                textDecoration: "underline",
                                textDecorationStyle: "dotted",
                                textUnderlineOffset: "2px",
                                textDecorationColor: "var(--dt-color-gold-border)",
                            }}
                        >
              {seg.text}
            </span>
                    )
                }

                return (
                    <span key={i} style={{color: "var(--dt-color-gold-base)", fontWeight: 600}}>
            {seg.text}
          </span>
                )
            })}
        </>
    )
}

// ── Helper sub-component: renders a single chunk's text body ─────────────────

export function ChunkBody({
    text,
    isTarget,
    expanded,
    onExpandToggle,
    onPageClick,
}: {
    text: string
    isTarget: boolean
    expanded: boolean
    onExpandToggle: () => void
    onPageClick: (page: number) => void
}) {
    const safeText = toSafeString(text)
    const stripped = stripChunkPrefix(safeText) ?? safeText
    const cleanedBody = useMemo(() => cleanJudgmentText(stripped), [stripped])
    const needsTruncation = isTarget && cleanedBody.length > TEXT_TRUNCATE_LIMIT
    const displayBody = isTarget && needsTruncation && !expanded
        ? cleanedBody.slice(0, TEXT_TRUNCATE_LIMIT)
        : cleanedBody

    const paragraphs = useMemo(
        () => displayBody.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean),
        [displayBody],
    )

    return (
        <>
            <div style={{
                display: "flex",
                flexDirection: "column",
                gap: SPACE["3"],
                opacity: isTarget ? 1 : 0.45,
            }}>
                {paragraphs.map((para, pi) => (
                    <p
                        key={pi}
                        style={{
                            fontSize: TYPE_SCALE.sm,
                            lineHeight: 1.7,
                            color: "var(--dt-text-strong)",
                            fontFamily: FONT.sans,
                            margin: 0,
                            wordBreak: "break-word",
                            ...(isTarget ? {
                                background: "var(--dt-accent-tint-faint)",
                                borderLeft: `3px solid var(--dt-accent-highlight-strong)`,
                                paddingLeft: SPACE["2"],
                                paddingTop: 6,
                                paddingBottom: 6,
                                borderRadius: `0 ${RADIUS.xs}px ${RADIUS.xs}px 0`,
                            } : {}),
                        }}
                    >
                        <HighlightedLegalText text={para} onPageClick={onPageClick} />
                    </p>
                ))}
            </div>
            {needsTruncation && (
                <button
                    onClick={onExpandToggle}
                    style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: SPACE["1"],
                        marginTop: SPACE["3"],
                        padding: `${SPACE["1"]}px ${SPACE["3"]}px`,
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
                        <><ChevronUp size={SPACE["3"]} />Show less</>
                    ) : (
                        <><ChevronDown size={SPACE["3"]} />Show more ({Math.round(cleanedBody.length / 1000)}k chars)</>
                    )}
                </button>
            )}
        </>
    )
}

// ── Context view: needle-in-haystack rendering when chunk_id is available ────

export interface ChunkContextItem {
    chunk_id: string
    page: number
    text: string
    is_target: boolean
}

export interface ChunkContextResult {
    doc_id: string
    corpus: string
    pdf_available: boolean
    chunks: ChunkContextItem[]
}

export function ContextChunkView({
    source,
    context,
    isMobile,
    onPageClick,
}: {
    source: SourceRef
    context: ChunkContextResult
    isMobile: boolean
    onPageClick: (page: number) => void
}) {
    const [expanded, setExpanded] = useState(false)
    const scrollContainerRef = useRef<HTMLDivElement>(null)
    const targetRef = useRef<HTMLDivElement>(null)

    // Parse header from the target chunk's raw text for the law name/breadcrumb
    const targetChunk = context.chunks.find((c) => c.is_target)
    const headerRaw = toSafeString(targetChunk?.text ?? source.text ?? "")
    const headerMatch = headerRaw.match(/^\[([^\]]+)\]\s*([^\n]*)\n?([\s\S]*)$/)
    const lawName = headerMatch?.[1] ?? ""
    const breadcrumb = headerMatch?.[2]?.trim() ?? ""

    const targetIdx = context.chunks.findIndex((c) => c.is_target)
    const hasPrecedingContext = targetIdx > 0

    // Deduplicate overlapping text between consecutive chunks (200-char retrieval overlap)
    const dedupedTexts = useMemo(() => {
        const stripped = context.chunks.map(c => stripChunkPrefix(c.text) ?? c.text)
        return deduplicateChunkTexts(stripped)
    }, [context.chunks])

    // Scroll to the target chunk after mount
    useEffect(() => {
        const t = setTimeout(() => {
            const container = scrollContainerRef.current
            const el = targetRef.current
            if (!container || !el) return
            const relTop = el.getBoundingClientRect().top
                - container.getBoundingClientRect().top
                + container.scrollTop
            container.scrollTo({top: Math.max(0, relTop - SPACE["5"]), behavior: "smooth"})
        }, 200)
        return () => clearTimeout(t)
    }, [source.chunk_id])

    return (
        <div
            ref={scrollContainerRef}
            className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")}
            style={{
                background: "var(--dt-content-card-bg)",
                border: `0.5px solid var(--dt-content-card-border)`,
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                boxShadow: `var(--dt-glass-inner-glow), 0 ${SPACE["1"]}px ${SPACE["6"]}px rgba(100,50,0,0.08)`,
            }}
        >
            {/* Header: law name + breadcrumb from target chunk */}
            {(lawName || breadcrumb) && (
                <div style={{marginBottom: SPACE["3"]}}>
                    {lawName && (
                        <p style={{
                            fontSize: TYPE_SCALE.xs,
                            fontWeight: 700,
                            textTransform: "uppercase" as const,
                            letterSpacing: "0.10em",
                            color: "var(--dt-color-gold-base)",
                            margin: `0 0 ${SPACE["1"]}px`,
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

            {/* Jump to cited passage button — only when there is preceding context */}
            {hasPrecedingContext && (
                <div style={{marginBottom: SPACE["3"]}}>
                    <button
                        onClick={() => {
                            const container = scrollContainerRef.current
                            const el = targetRef.current
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

            {/* Context label above non-target preceding chunks */}
            {hasPrecedingContext && (
                <p style={{
                    fontSize: TYPE_SCALE.xs,
                    fontWeight: 600,
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.09em",
                    color: "var(--dt-text-tertiary)",
                    margin: `0 0 ${SPACE["2"]}px`,
                    fontFamily: FONT.sans,
                }}>Surrounding context</p>
            )}

            {/* Render all chunks in order, visually separating context from target */}
            <div style={{display: "flex", flexDirection: "column", gap: SPACE["4"]}}>
                {context.chunks.map((chunk, ci) => {
                    const isTarget = chunk.is_target
                    const showDivider = isTarget && ci > 0

                    return (
                        <div
                            key={chunk.chunk_id}
                            ref={isTarget ? targetRef : undefined}
                        >
                            {/* Visual divider between context and target chunk */}
                            {showDivider && (
                                <div style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: SPACE["2"],
                                    marginBottom: SPACE["4"],
                                }}>
                                    <div style={{
                                        flex: 1,
                                        height: 1,
                                        background: "var(--dt-accent-tint-faint)",
                                    }} />
                                    <span style={{
                                        fontSize: TYPE_SCALE.xs,
                                        fontWeight: 600,
                                        color: "var(--dt-color-gold-base)",
                                        fontFamily: FONT.sans,
                                        whiteSpace: "nowrap",
                                        textTransform: "uppercase" as const,
                                        letterSpacing: "0.09em",
                                    }}>Cited passage</span>
                                    <div style={{
                                        flex: 1,
                                        height: 1,
                                        background: "var(--dt-accent-tint-faint)",
                                    }} />
                                </div>
                            )}

                            {/* Page indicator for each chunk */}
                            <p style={{
                                fontSize: TYPE_SCALE.xs,
                                color: "var(--dt-text-tertiary)",
                                fontFamily: FONT.sans,
                                margin: `0 0 ${SPACE["2"]}px`,
                                opacity: isTarget ? 1 : 0.45,
                            }}>
                                <span
                                    style={{
                                        cursor: "pointer",
                                        textDecoration: "underline",
                                        textDecorationStyle: "dotted",
                                        textUnderlineOffset: "2px",
                                        textDecorationColor: "var(--dt-text-tertiary)",
                                    }}
                                    onClick={() => onPageClick(chunk.page)}
                                >
                                    p. {chunk.page}
                                </span>
                            </p>

                            <ChunkBody
                                text={dedupedTexts[ci]}
                                isTarget={isTarget}
                                expanded={expanded}
                                onExpandToggle={() => setExpanded((v) => !v)}
                                onPageClick={onPageClick}
                            />
                        </div>
                    )
                })}
            </div>

            {/* Trailing context label after the target chunk when there are following chunks */}
            {targetIdx !== -1 && targetIdx < context.chunks.length - 1 && (
                <p style={{
                    fontSize: TYPE_SCALE.xs,
                    fontWeight: 600,
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.09em",
                    color: "var(--dt-text-tertiary)",
                    margin: `${SPACE["2"]}px 0 0`,
                    fontFamily: FONT.sans,
                    opacity: 0.65,
                }}>Surrounding context (continued)</p>
            )}
        </div>
    )
}
