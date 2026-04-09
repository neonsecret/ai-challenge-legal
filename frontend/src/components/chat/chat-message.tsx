"use client"

import {useState, useRef, useMemo, useEffect} from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {visit} from "unist-util-visit"
import {findAndReplace} from "mdast-util-find-and-replace"
import {cn} from "@/lib/utils"
import {Copy, Check, ThumbsUp, ThumbsDown} from "lucide-react"
import {motion, AnimatePresence} from "motion/react"
import {SourcesPanel} from "@/components/chat/sources-panel"
import {StreamingStatus} from "@/components/chat/streaming-status"
import {ConfidenceBadge} from "@/components/chat/confidence-badge"
import {AgentTrace} from "@/components/chat/agent-trace"
import {FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"
import {useDesignVersion} from "@/lib/design-version"

export type {Source} from "@/components/chat/use-query-stream"
type Source = import("@/components/chat/use-query-stream").Source

// ─── Citation patterns ────────────────────────────────────────────────────────

/** [[source:DOC_ID:PAGE]] — deterministic pipeline */
const SOURCE_LINK_PATTERN = /\[\[source:([^:\]]+):(\d+)\]\]/g

/** [DOC-N] — agent pipeline (1-indexed into sources array) */
const DOC_REF_PATTERN = /\[DOC-(\d+)\]/g

// ─── Remark plugin ────────────────────────────────────────────────────────────

function remarkInlineCitations() {
    return (tree: import("mdast").Root) => {
        findAndReplace(tree, [
            [
                new RegExp(SOURCE_LINK_PATTERN.source, "g"),
                (_match: string, docId: string, pageStr: string) => ({
                    type: "citationRef",
                    data: {citationKind: "source", docId, page: parseInt(pageStr, 10)},
                } as unknown as import("mdast").PhrasingContent),
            ],
            [
                new RegExp(DOC_REF_PATTERN.source, "g"),
                (_match: string, indexStr: string) => ({
                    type: "citationRef",
                    data: {citationKind: "docref", index: parseInt(indexStr, 10)},
                } as unknown as import("mdast").PhrasingContent),
            ],
        ])
    }
}

// ─── Rehype plugin ────────────────────────────────────────────────────────────

function rehypeInlineCitations() {
    return (tree: import("hast").Root) => {
        visit(tree, "citationRef", (node: import("hast").Node, index, parent) => {
            if (!parent || index == null) return

            interface CitationRefData {
                citationKind: string
                docId?: string
                page?: number
                index?: number
            }
            const raw = node as unknown as {data?: CitationRefData}
            const data: CitationRefData = raw.data ?? {citationKind: ""}

            const element: import("hast").Element = {
                type: "element",
                tagName: "citationbutton",
                properties: {
                    citationkind: data.citationKind ?? "",
                    docid: data.docId ?? "",
                    page: data.page ?? 0,
                    refindex: data.index ?? 0,
                },
                children: [],
            }

            ;(parent as import("hast").Parent).children.splice(index, 1, element)
        })
    }
}

// ─── Prose style constants ────────────────────────────────────────────────────

const WARM_PROSE = [
    "prose prose-sm max-w-none leading-relaxed font-sans",
    "prose-p:text-[#2e1f08] prose-p:my-2",
    "prose-headings:font-sans prose-headings:text-[#1a1006] prose-headings:font-semibold",
    "prose-strong:text-[#1a1006] prose-strong:font-semibold",
    "prose-a:text-[#c47c00] prose-a:no-underline hover:prose-a:underline",
    "prose-code:bg-[rgba(92,46,8,0.08)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-[#5c2e08]",
    "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-[#2e1f08]",
    "prose-table:text-[#2e1f08] prose-th:text-left prose-th:text-[11px] prose-th:font-semibold prose-th:py-1.5 prose-th:px-2 prose-th:border-b prose-th:border-[rgba(92,46,8,0.15)]",
    "prose-td:text-[12px] prose-td:py-1.5 prose-td:px-2 prose-td:border-b prose-td:border-[rgba(92,46,8,0.08)]",
    "prose-hr:border-[rgba(92,46,8,0.12)] prose-hr:my-3",
    "prose-blockquote:border-l-[#c47c00] prose-blockquote:text-[#5c2e08] prose-blockquote:bg-[rgba(196,124,0,0.04)] prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:my-2",
].join(" ")

const DARK_PROSE = [
    "prose prose-sm max-w-none leading-relaxed prose-invert font-sans",
    "prose-p:text-[rgba(255,255,255,0.82)] prose-p:my-2",
    "prose-headings:font-sans prose-headings:text-[rgba(255,255,255,0.92)] prose-headings:font-semibold",
    "prose-strong:text-[rgba(255,255,255,0.92)] prose-strong:font-semibold",
    "prose-a:text-[#C9A84C] prose-a:no-underline hover:prose-a:underline",
    "prose-code:bg-[rgba(255,255,255,0.08)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-[rgba(255,255,255,0.75)]",
    "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-[rgba(255,255,255,0.80)]",
    "prose-table:text-[rgba(255,255,255,0.80)] prose-th:text-left prose-th:text-[11px] prose-th:font-semibold prose-th:py-1.5 prose-th:px-2 prose-th:border-b prose-th:border-[rgba(255,255,255,0.15)]",
    "prose-td:text-[12px] prose-td:py-1.5 prose-td:px-2 prose-td:border-b prose-td:border-[rgba(255,255,255,0.08)]",
    "prose-hr:border-[rgba(255,255,255,0.12)] prose-hr:my-3",
    "prose-blockquote:border-l-[#C9A84C] prose-blockquote:text-[rgba(255,255,255,0.70)] prose-blockquote:bg-[rgba(201,168,76,0.04)] prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:my-2",
].join(" ")

// V3 glassmorphism dark prose — achromatic palette, iris accent replaces gold
const V3_DARK_PROSE = [
    "prose prose-sm max-w-none leading-relaxed prose-invert font-sans",
    "prose-p:text-[var(--gm-text-primary)] prose-p:my-2",
    "prose-headings:font-sans prose-headings:text-[var(--gm-text-primary)] prose-headings:font-semibold",
    "prose-strong:text-[var(--gm-text-primary)] prose-strong:font-semibold",
    "prose-a:text-[var(--gm-accent)] prose-a:no-underline hover:prose-a:underline",
    "prose-code:bg-[rgba(255,255,255,0.06)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-[var(--gm-text-secondary)]",
    "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-[var(--gm-text-primary)]",
    "prose-table:text-[var(--gm-text-secondary)] prose-th:text-left prose-th:text-[11px] prose-th:font-semibold prose-th:py-1.5 prose-th:px-2 prose-th:border-b prose-th:border-[rgba(222,222,222,0.12)]",
    "prose-td:text-[12px] prose-td:py-1.5 prose-td:px-2 prose-td:border-b prose-td:border-[rgba(222,222,222,0.08)]",
    "prose-hr:border-[rgba(222,222,222,0.10)] prose-hr:my-3",
    "prose-blockquote:border-l-[var(--gm-accent)] prose-blockquote:text-[var(--gm-text-secondary)] prose-blockquote:bg-[rgba(139,111,212,0.04)] prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:my-2",
].join(" ")

// ─── Superscript helpers ─────────────────────────────────────────────────────

const SUPERSCRIPT_DIGITS = ['\u2070', '\u00B9', '\u00B2', '\u00B3', '\u2074', '\u2075', '\u2076', '\u2077', '\u2078', '\u2079']

function toSuperscript(n: number): string {
    return String(n).split('').map(d => SUPERSCRIPT_DIGITS[parseInt(d, 10)]).join('')
}

// ─── Cited source collection ─────────────────────────────────────────────────

interface CitedEntry {
    footnoteNum: number
    docId: string
    title: string
    page?: number
}

function collectCitedSources(content: string, sources: Source[]): CitedEntry[] {
    const cited = new Map<number, CitedEntry>()

    for (const m of content.matchAll(/\[DOC-(\d+)\]/g)) {
        const n = parseInt(m[1], 10)
        const idx = n - 1
        if (idx >= 0 && idx < sources.length && !cited.has(n)) {
            cited.set(n, {
                footnoteNum: n,
                docId: sources[idx].doc_id,
                title: sources[idx].title || sources[idx].doc_id,
                page: sources[idx].page_numbers[0],
            })
        }
    }

    for (const m of content.matchAll(/\[\[source:([^:\]]+):(\d+)\]\]/g)) {
        const docId = m[1]
        const page = parseInt(m[2], 10)
        const srcIdx = sources.findIndex(s =>
            s.doc_id === docId || s.doc_id.startsWith(docId) || docId.startsWith(s.doc_id)
        )
        if (srcIdx >= 0) {
            const n = srcIdx + 1
            if (!cited.has(n)) {
                cited.set(n, {
                    footnoteNum: n,
                    docId: sources[srcIdx].doc_id,
                    title: sources[srcIdx].title || sources[srcIdx].doc_id,
                    page,
                })
            }
        }
    }

    return [...cited.values()].sort((a, b) => a.footnoteNum - b.footnoteNum)
}

// ─── Footnote style ──────────────────────────────────────────────────────────

function footnoteStyle(resolvable: boolean): React.CSSProperties {
    return {
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: TYPE_SCALE.xs,
        lineHeight: 1,
        fontWeight: 700,
        fontFamily: FONT.sans,
        color: resolvable ? "var(--dt-citation-resolvable-color)" : "var(--dt-text-quaternary)",
        background: resolvable ? "var(--dt-citation-resolvable-tint)" : "var(--dt-citation-default-tint)",
        border: `0.5px solid ${resolvable ? "var(--dt-citation-resolvable-border)" : "var(--dt-citation-default-border)"}`,
        borderRadius: RADIUS.sm,
        padding: `0 ${SPACE[1]}px`,
        minWidth: SPACE[4],
        height: SPACE[4],
        cursor: resolvable ? "pointer" : "not-allowed",
        verticalAlign: "middle",
        position: "relative",
        top: -1,
        margin: "0 1px",
        transition: "background 0.15s, border-color 0.15s, color 0.15s",
    }
}

// ─── Component props ──────────────────────────────────────────────────────────

interface ChatMessageProps {
    role: "user" | "assistant"
    content: string | null
    sources?: Source[]
    isStreaming?: boolean
    confidence?: string | null
    streamingStatus?: string | null
    streamingProgress?: import("@/components/chat/use-query-stream").Progress | null
    streamingThinkingPreview?: string | null
    trace?: string[]
    onSourceClick?: (answer: string, sources: Source[], focusDocId?: string, focusPage?: number) => void
    /** isDark is retained for prose class selection and child components not yet migrated */
    isDark?: boolean
    messageId?: string
    traceId?: string | null
    conversationId?: string | null
    feedback?: { rating: "positive" | "negative"; comment?: string } | null
    onFeedback?: (messageId: string, rating: "positive" | "negative", comment?: string) => void
}

// ─── ChatMessage ──────────────────────────────────────────────────────────────

export function ChatMessage({
    role,
    content,
    sources = [],
    isStreaming = false,
    confidence,
    streamingStatus,
    streamingProgress,
    streamingThinkingPreview,
    trace,
    onSourceClick,
    isDark = false,
    messageId,
    traceId,
    conversationId,
    feedback,
    onFeedback,
}: ChatMessageProps) {
    const {version: designVersion} = useDesignVersion()
    const [v3Mounted, setV3Mounted] = useState(false)
    useEffect(() => { setV3Mounted(true) }, [])
    const isV3 = v3Mounted && designVersion === "strict"

    const [copied, setCopied] = useState(false)
    const [commentOpen, setCommentOpen] = useState(false)
    const [commentText, setCommentText] = useState("")
    const [submitting, setSubmitting] = useState(false)
    const [feedbackError, setFeedbackError] = useState<string | null>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const citedSources = useMemo(
        () => (content && sources.length > 0 && !isStreaming)
            ? collectCitedSources(content, sources)
            : [],
        [content, sources, isStreaming],
    )

    const handleCopy = () => {
        if (!content) return
        navigator.clipboard.writeText(content).then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        })
    }

    const postFeedback = async (rating: "positive" | "negative", comment?: string, keepPanelOpen = false) => {
        if (!messageId || !traceId || !conversationId) return
        const API = process.env.NEXT_PUBLIC_SSE_URL ?? ""
        setSubmitting(true)
        setFeedbackError(null)
        try {
            const res = await fetch(`${API}/api/feedback`, {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                credentials: "include",
                body: JSON.stringify({
                    trace_id: traceId,
                    message_id: messageId,
                    conversation_id: conversationId,
                    rating,
                    ...(comment ? {comment} : {}),
                }),
            })
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            onFeedback?.(messageId, rating, comment)
            if (!keepPanelOpen) {
                setCommentOpen(false)
                setCommentText("")
            }
        } catch {
            setFeedbackError("Couldn't save feedback. Try again.")
        } finally {
            setSubmitting(false)
        }
    }

    const handleThumbsUp = () => {
        if (feedback?.rating === "positive") return
        postFeedback("positive")
    }

    const handleThumbsDown = () => {
        if (feedback?.rating === "negative") return
        postFeedback("negative", undefined, true)
        setCommentOpen(true)
        setTimeout(() => textareaRef.current?.focus(), 50)
    }

    const handleCommentSubmit = () => {
        postFeedback("negative", commentText.trim() || undefined)
    }

    // ── User message ──────────────────────────────────────────────────────────
    if (role === "user") {
        return (
            <div className="mb-5 animate-fade-in-up" style={{display: "flex", justifyContent: "flex-end"}}>
                <div style={{
                    maxWidth: "72%",
                    background: "var(--dt-confidence-bg)",
                    border: "1px solid var(--dt-confidence-border)",
                    borderRadius: "16px 16px 4px 16px",
                    padding: "10px 14px",
                    backdropFilter: "blur(15px)",
                    WebkitBackdropFilter: "blur(15px)",
                    ...(isV3 ? {
                        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 12px rgba(0,0,0,0.25)",
                    } : {}),
                }}>
                    <p style={{
                        fontSize: "13px", margin: 0, lineHeight: 1.6,
                        color: "var(--dt-confidence-text)",
                        fontWeight: 500,
                    }}>
                        {content}
                    </p>
                </div>
            </div>
        )
    }

    // ── Assistant message ─────────────────────────────────────────────────────

    const answerCardStyle: React.CSSProperties = {
        background: "var(--dt-answer-bg)",
        border: `${isV3 ? "1px" : "0.5px"} solid var(--dt-answer-border)`,
        borderRadius: RADIUS.xl,
        fontFamily: FONT.sans,
        ...(isV3 ? {
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04), 0 2px 8px rgba(0,0,0,0.20)",
        } : {}),
    }

    const labelStyle = {
        fontSize: 10,
        textTransform: "uppercase" as const,
        letterSpacing: "0.14em",
        color: "var(--dt-vote-text)",
        margin: `0 0 ${SPACE[2]}px`,
        fontWeight: 600,
    }

    function CitationButtonComponent({
        citationkind,
        docid,
        page,
        refindex,
    }: {
        citationkind?: string
        docid?: string
        page?: number
        refindex?: number
    }) {
        if (isStreaming) return null

        const hoverHandlers = {
            onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => {
                e.currentTarget.style.background = "var(--dt-accent-highlight)"
                e.currentTarget.style.borderColor = "var(--dt-accent-border-strong)"
                e.currentTarget.style.color = "var(--dt-accent-color)"
            },
            onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => {
                const style = footnoteStyle(true)
                e.currentTarget.style.background = style.background as string
                e.currentTarget.style.borderColor = ""
                e.currentTarget.style.color = style.color as string
            },
        }

        if (citationkind === "source") {
            const resolvedDocId = docid ?? ""
            const resolvedPage = page ?? 0
            const srcIdx = sources.findIndex(s =>
                s.doc_id === resolvedDocId ||
                s.doc_id.startsWith(resolvedDocId) ||
                resolvedDocId.startsWith(s.doc_id)
            )
            const resolvable = srcIdx >= 0
            const footnoteNum = srcIdx + 1
            return (
                <button
                    onClick={resolvable ? (e) => {
                        e.stopPropagation()
                        onSourceClick?.(content ?? "", sources, resolvedDocId, resolvedPage)
                    } : undefined}
                    title={resolvable
                        ? `${sources[srcIdx].title || sources[srcIdx].doc_id}${resolvedPage ? ` \u00B7 p.${resolvedPage}` : ""}`
                        : "Source not found in retrieved documents"
                    }
                    style={footnoteStyle(resolvable)}
                    {...(resolvable ? hoverHandlers : {})}
                >
                    {footnoteNum}
                </button>
            )
        }

        if (citationkind === "docref") {
            const sourceIdx = (refindex ?? 0) - 1
            const matchedSource = sources[sourceIdx]
            const resolvable = !!matchedSource
            const pageNum = matchedSource?.page_numbers[0]
            return (
                <button
                    onClick={resolvable ? (e) => {
                        e.stopPropagation()
                        onSourceClick?.(content ?? "", sources, matchedSource.doc_id, pageNum)
                    } : undefined}
                    title={resolvable
                        ? `${matchedSource.title || matchedSource.doc_id}${pageNum ? ` \u00B7 p.${pageNum}` : ""}`
                        : "Source not found in retrieved documents"
                    }
                    style={footnoteStyle(resolvable)}
                    {...(resolvable ? hoverHandlers : {})}
                >
                    {refindex ?? 0}
                </button>
            )
        }

        return null
    }

    return (
        <div className="mb-7 animate-fade-in-up">
            <p style={labelStyle}>Answer</p>

            {/* Answer card */}
            <div style={answerCardStyle}>
                <div style={{padding: SPACE[4]}}>
                    {content === "__polling_pipeline_status__" ? (
                        <StreamingStatus status="Processing..."/>
                    ) : content?.startsWith("__pipeline_status:") ? (
                        <StreamingStatus status={content.slice("__pipeline_status:".length)}/>
                    ) : content ? (() => {
                        return (
                        <div className="group relative">
                            <div className={isV3 && isDark ? V3_DARK_PROSE : isDark ? DARK_PROSE : WARM_PROSE}>
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm, remarkInlineCitations]}
                                    rehypePlugins={[rehypeInlineCitations]}
                                    remarkRehypeOptions={{
                                        passThrough: ["citationRef" as import("mdast").Nodes["type"]],
                                    }}
                                    components={{
                                        h2: ({node: _node, children, ...props}) => (
                                            <h2 {...props} style={{fontSize: TYPE_SCALE.lg, fontFamily: FONT.sans}}>{children}</h2>
                                        ),
                                        h3: ({node: _node, children, ...props}) => (
                                            <h3 {...props} style={{fontSize: TYPE_SCALE.md, fontFamily: FONT.sans}}>{children}</h3>
                                        ),
                                        strong: ({node: _node, children, ...props}) => (
                                            <strong {...props}>{children}</strong>
                                        ),
                                        a: ({node: _node, children, href, ...props}) => {
                                            const safe = href && /^https?:\/\//i.test(href) ? href : undefined
                                            return <a {...props} href={safe} target="_blank" rel="noopener noreferrer">
                                                {children}
                                            </a>
                                        },
                                        // @ts-expect-error — citationbutton is a custom element from our rehype plugin
                                        citationbutton: CitationButtonComponent,
                                    }}
                                >
                                    {content}
                                </ReactMarkdown>
                            </div>
                            <button
                                onClick={handleCopy}
                                className={cn(
                                    "absolute -top-1 right-0 rounded-lg p-1.5 transition-all",
                                    "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                                )}
                                style={{
                                    background: "var(--dt-code-bg)",
                                    border: "1px solid var(--dt-code-border)",
                                    backdropFilter: "blur(8px)",
                                    WebkitBackdropFilter: "blur(8px)",
                                    color: copied ? "var(--dt-color-blue-base)" : "var(--dt-code-copy-color)",
                                }}
                                aria-label="Copy answer"
                            >
                                {copied ? <Check className="size-3.5"/> : <Copy className="size-3.5"/>}
                            </button>
                        </div>
                        )
                    })() : isStreaming ? (
                        <StreamingStatus status={streamingStatus} progress={streamingProgress} thinkingPreview={streamingThinkingPreview}/>
                    ) : (
                        <p style={{
                            fontSize: TYPE_SCALE.sm,
                            fontStyle: "italic",
                            color: "var(--dt-vote-text)",
                            margin: 0,
                        }}>
                            No response
                        </p>
                    )}
                </div>

                {/* References — inside the answer card, at the bottom */}
                {citedSources.length > 0 && (
                    <div style={{
                        padding: `${SPACE[3]}px ${SPACE[4]}px ${SPACE[4]}px`,
                        borderTop: "1px solid var(--dt-answer-border)",
                        background: "var(--dt-answer-footnote-bg)",
                        borderRadius: `0 0 ${RADIUS.xl}px ${RADIUS.xl}px`,
                    }}>
                        <div style={{display: "flex", flexDirection: "column", gap: SPACE[1]}}>
                            {citedSources.map((entry) => (
                                <button
                                    key={entry.footnoteNum}
                                    onClick={() => onSourceClick?.(
                                        content ?? "",
                                        sources,
                                        entry.docId,
                                        entry.page,
                                    )}
                                    style={{
                                        display: "block",
                                        fontSize: TYPE_SCALE.xs,
                                        color: "var(--dt-text-tertiary)",
                                        fontFamily: FONT.sans,
                                        background: "none",
                                        border: "none",
                                        padding: 0,
                                        cursor: "pointer",
                                        textAlign: "left",
                                        lineHeight: 1.5,
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.color = "var(--dt-accent-color)"
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.color = "var(--dt-text-tertiary)"
                                    }}
                                >
                                    {toSuperscript(entry.footnoteNum)} {entry.title}{entry.page ? ` (p. ${entry.page})` : ""}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Source chips — below the answer card */}
            {sources.length > 0 && (
                <div style={{marginTop: SPACE[3]}}>
                    <SourcesPanel
                        sources={sources}
                        onSourceClick={(source) => onSourceClick?.(content ?? "", sources, source.doc_id, source.page_numbers[0])}
                    />
                </div>
            )}

            {confidence != null && !isStreaming && (
                <div style={{marginTop: SPACE[2]}} className="animate-fade-in-up">
                    <ConfidenceBadge confidence={confidence} isDark={isDark}/>
                </div>
            )}

            {trace && trace.length > 0 && !isStreaming && content && (
                <AgentTrace trace={trace} isDark={isDark} />
            )}

            {/* Feedback bar */}
            {role === "assistant" && !isStreaming && traceId && (
                <div style={{marginTop: SPACE[2]}}>
                    <div style={{display: "flex", alignItems: "center", gap: SPACE[2]}}>
                        <button
                            onClick={handleThumbsUp}
                            disabled={submitting || feedback?.rating === "positive"}
                            aria-label="Helpful"
                            style={{
                                display: "flex", alignItems: "center", justifyContent: "center",
                                width: 28, height: 28, borderRadius: RADIUS.md,
                                border: `1px solid ${feedback?.rating === "positive"
                                    ? "var(--dt-accent-highlight)"
                                    : "var(--dt-divider-border)"}`,
                                background: feedback?.rating === "positive"
                                    ? "var(--dt-citation-resolvable-tint)"
                                    : "transparent",
                                color: feedback?.rating === "positive"
                                    ? "var(--dt-accent-color)"
                                    : feedback?.rating === "negative"
                                        ? "var(--dt-text-quaternary)"
                                        : "var(--dt-text-tertiary)",
                                cursor: feedback?.rating === "positive" ? "default" : "pointer",
                                transition: "all 0.15s",
                                padding: 0,
                            }}
                        >
                            <ThumbsUp size={13} fill={feedback?.rating === "positive" ? "currentColor" : "none"} />
                        </button>
                        <button
                            onClick={handleThumbsDown}
                            disabled={submitting || feedback?.rating === "negative"}
                            aria-label="Not helpful"
                            style={{
                                display: "flex", alignItems: "center", justifyContent: "center",
                                width: 28, height: 28, borderRadius: RADIUS.md,
                                border: `1px solid ${feedback?.rating === "negative"
                                    ? "var(--dt-accent-highlight)"
                                    : "var(--dt-divider-border)"}`,
                                background: feedback?.rating === "negative"
                                    ? "var(--dt-citation-resolvable-tint)"
                                    : "transparent",
                                color: feedback?.rating === "negative"
                                    ? "var(--dt-accent-color)"
                                    : feedback?.rating === "positive"
                                        ? "var(--dt-text-quaternary)"
                                        : "var(--dt-text-tertiary)",
                                cursor: feedback?.rating === "negative" ? "default" : "pointer",
                                transition: "all 0.15s",
                                padding: 0,
                            }}
                        >
                            <ThumbsDown size={13} fill={feedback?.rating === "negative" ? "currentColor" : "none"} />
                        </button>
                    </div>

                    {!commentOpen && feedbackError && (
                        <span style={{
                            display: "block",
                            marginTop: SPACE[1],
                            fontSize: TYPE_SCALE.xs,
                            color: "var(--dt-error-text)",
                            fontFamily: FONT.sans,
                        }}>
                            {feedbackError}
                        </span>
                    )}

                    {feedback?.rating === "negative" && feedback.comment && !commentOpen && (
                        <p style={{
                            margin: `${SPACE[1]}px 0 0`,
                            fontSize: TYPE_SCALE.xs,
                            color: "var(--dt-text-tertiary)",
                            fontFamily: FONT.sans,
                            lineHeight: 1.5,
                            fontStyle: "italic",
                            maxWidth: "40ch",
                            wordBreak: "break-word",
                        }}>
                            {feedback.comment}
                        </p>
                    )}

                    <AnimatePresence>
                        {commentOpen && (
                            <motion.div
                                initial={{height: 0, opacity: 0}}
                                animate={{height: "auto", opacity: 1}}
                                exit={{height: 0, opacity: 0}}
                                transition={{duration: 0.2, ease: [0.32, 0.72, 0, 1]}}
                                style={{overflow: "hidden"}}
                            >
                                <div style={{marginTop: SPACE[2], display: "flex", flexDirection: "column", gap: SPACE[2]}}>
                                    <textarea
                                        ref={textareaRef}
                                        value={commentText}
                                        onChange={e => setCommentText(e.target.value)}
                                        maxLength={2000}
                                        rows={3}
                                        placeholder="What could be improved? (optional)"
                                        style={{
                                            width: "100%",
                                            resize: "none",
                                            fontFamily: FONT.sans,
                                            fontSize: TYPE_SCALE.xs,
                                            padding: `${SPACE[2]}px ${SPACE[3]}px`,
                                            borderRadius: RADIUS.md,
                                            border: "1px solid var(--dt-divider-border)",
                                            background: "var(--dt-glass-bg-subtle)",
                                            color: "var(--dt-text-strong)",
                                            outline: "none",
                                            lineHeight: 1.5,
                                            boxSizing: "border-box",
                                        }}
                                    />
                                    <div style={{display: "flex", alignItems: "center", gap: SPACE[2]}}>
                                        <button
                                            onClick={handleCommentSubmit}
                                            disabled={submitting}
                                            style={{
                                                fontFamily: FONT.sans,
                                                fontSize: TYPE_SCALE.xs,
                                                fontWeight: 600,
                                                padding: `${SPACE[1]}px ${SPACE[3]}px`,
                                                borderRadius: RADIUS.md,
                                                border: "1px solid var(--dt-accent-border-strong)",
                                                background: "var(--dt-accent-tint-subtle)",
                                                color: "var(--dt-accent-color)",
                                                cursor: submitting ? "not-allowed" : "pointer",
                                                opacity: submitting ? 0.6 : 1,
                                                transition: "all 0.15s",
                                            }}
                                        >
                                            {submitting ? "Sending…" : "Submit"}
                                        </button>
                                        <button
                                            onClick={() => {
                                                setCommentOpen(false)
                                                setCommentText("")
                                                setFeedbackError(null)
                                            }}
                                            disabled={submitting}
                                            style={{
                                                fontFamily: FONT.sans,
                                                fontSize: TYPE_SCALE.xs,
                                                padding: `${SPACE[1]}px ${SPACE[2]}px`,
                                                borderRadius: RADIUS.md,
                                                border: "none",
                                                background: "transparent",
                                                color: "var(--dt-text-tertiary)",
                                                cursor: "pointer",
                                            }}
                                        >
                                            Cancel
                                        </button>
                                        {feedbackError && (
                                            <span style={{
                                                fontSize: TYPE_SCALE.xs,
                                                color: "var(--dt-error-text)",
                                                fontFamily: FONT.sans,
                                            }}>
                                                {feedbackError}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            )}
        </div>
    )
}
