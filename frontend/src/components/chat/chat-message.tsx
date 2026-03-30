"use client"

import {useState, useMemo} from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {visit} from "unist-util-visit"
import {findAndReplace} from "mdast-util-find-and-replace"
import {cn} from "@/lib/utils"
import {Copy, Check} from "lucide-react"
import {SourcesPanel} from "@/components/chat/sources-panel"
import {StreamingStatus} from "@/components/chat/streaming-status"
import {ConfidenceBadge} from "@/components/chat/confidence-badge"
import {AgentTrace} from "@/components/chat/agent-trace"
import {
    FONT, TYPE_SCALE, SPACE, COLOR, TEXT_DARK, TEXT_LIGHT,
    ANSWER_CARD, RADIUS,
} from "@/lib/design-tokens"

export type {Source} from "@/components/chat/use-query-stream"
type Source = import("@/components/chat/use-query-stream").Source

// ─── Citation patterns ────────────────────────────────────────────────────────

/** [[source:DOC_ID:PAGE]] — deterministic pipeline */
const SOURCE_LINK_PATTERN = /\[\[source:([^:\]]+):(\d+)\]\]/g

/** [DOC-N] — agent pipeline (1-indexed into sources array) */
const DOC_REF_PATTERN = /\[DOC-(\d+)\]/g

// ─── Remark plugin ────────────────────────────────────────────────────────────

/**
 * Remark plugin: replaces [DOC-N] and [[source:ID:PAGE]] patterns found in
 * MDAST text nodes with custom `citationRef` nodes. These pass through to the
 * HAST stage (via `remarkRehypeOptions.passThrough`) where the rehype plugin
 * converts them to renderable `<citationbutton>` elements.
 */
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

/**
 * Rehype plugin: converts `citationRef` nodes that passed through from MDAST
 * into standard HAST `element` nodes with `tagName: "citationbutton"`.
 * React-markdown then renders these via the `components.citationbutton` entry.
 */
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

/** Pre-scan answer content for citation markers, return ordered cited sources. */
function collectCitedSources(content: string, sources: Source[]): CitedEntry[] {
    const cited = new Map<number, CitedEntry>()

    // [DOC-N] references (agent pipeline)
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

    // [[source:ID:PAGE]] references (deterministic pipeline)
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
        fontSize: 10,
        verticalAlign: "super",
        color: COLOR.gold.base,
        cursor: resolvable ? "pointer" : "not-allowed",
        opacity: resolvable ? 1 : 0.35,
        fontWeight: 600,
        lineHeight: 1,
        background: "none",
        border: "none",
        padding: "0 1px",
        fontFamily: FONT.sans,
    }
}

// ─── Component props ──────────────────────────────────────────────────────────

interface ChatMessageProps {
    role: "user" | "assistant"
    content: string | null
    sources?: Source[]
    isStreaming?: boolean
    confidence?: number | null
    streamingStatus?: string | null
    streamingProgress?: import("@/components/chat/use-query-stream").Progress | null
    streamingThinkingPreview?: string | null
    trace?: string[]
    onSourceClick?: (answer: string, sources: Source[], focusDocId?: string, focusPage?: number) => void
    isDark?: boolean
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
}: ChatMessageProps) {
    const [copied, setCopied] = useState(false)

    // Pre-collect cited sources for the References section
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

    // ── User message ──────────────────────────────────────────────────────────
    if (role === "user") {
        return (
            <div className="mb-5 animate-fade-in-up" style={{display: "flex", justifyContent: "flex-end"}}>
                <div style={{
                    maxWidth: "72%",
                    background: isDark ? "rgba(201,168,76,0.16)" : "rgba(180,120,10,0.22)",
                    border: isDark ? "1px solid rgba(201,168,76,0.28)" : "1px solid rgba(160,100,5,0.38)",
                    borderRadius: "16px 16px 4px 16px",
                    padding: "10px 14px",
                    backdropFilter: "blur(16px)",
                    WebkitBackdropFilter: "blur(16px)",
                }}>
                    <p style={{
                        fontSize: "13px", margin: 0, lineHeight: 1.6,
                        color: isDark ? "rgba(255,255,255,0.88)" : "#2a1806",
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
        background: isDark ? ANSWER_CARD.dark.bg : ANSWER_CARD.light.bg,
        border: `0.5px solid ${isDark ? ANSWER_CARD.dark.border : ANSWER_CARD.light.border}`,
        borderRadius: RADIUS.xl,
        fontFamily: FONT.sans,
    }

    const labelStyle = {
        fontSize: 10,
        textTransform: "uppercase" as const,
        letterSpacing: "0.14em",
        color: isDark ? TEXT_DARK.tertiary : "#7a5a20",
        margin: `0 0 ${SPACE[2]}px`,
        fontWeight: 600,
    }

    /**
     * Custom React component for `citationbutton` elements.
     * Renders superscript footnote numbers. Hidden while streaming.
     */
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
                >
                    {toSuperscript(footnoteNum)}
                </button>
            )
        }

        if (citationkind === "docref") {
            const sourceIdx = (refindex ?? 0) - 1  // DOC-N is 1-indexed
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
                >
                    {toSuperscript(refindex ?? 0)}
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
                        <StreamingStatus status="Processing..." isDark={isDark}/>
                    ) : content?.startsWith("__pipeline_status:") ? (
                        <StreamingStatus status={content.slice("__pipeline_status:".length)} isDark={isDark}/>
                    ) : content ? (() => {
                        return (
                        <div className="group relative">
                            <div className={isDark ? DARK_PROSE : WARM_PROSE}>
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
                                    background: isDark ? "rgba(255,255,255,0.10)" : "rgba(255,240,215,0.30)",
                                    border: isDark ? "1px solid rgba(255,255,255,0.14)" : "1px solid rgba(255,255,255,0.40)",
                                    backdropFilter: "blur(8px)",
                                    WebkitBackdropFilter: "blur(8px)",
                                    color: copied ? "#3576ae" : isDark ? "rgba(255,255,255,0.55)" : "#7a5a20",
                                }}
                                aria-label="Copy answer"
                            >
                                {copied ? <Check className="size-3.5"/> : <Copy className="size-3.5"/>}
                            </button>
                        </div>
                        )
                    })() : isStreaming ? (
                        <StreamingStatus status={streamingStatus} progress={streamingProgress} thinkingPreview={streamingThinkingPreview} isDark={isDark}/>
                    ) : (
                        <p style={{
                            fontSize: TYPE_SCALE.sm,
                            fontStyle: "italic",
                            color: isDark ? TEXT_DARK.tertiary : "#7a5a20",
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
                        borderTop: `1px solid ${isDark ? ANSWER_CARD.dark.border : ANSWER_CARD.light.border}`,
                        background: isDark ? ANSWER_CARD.dark.footnoteBg : ANSWER_CARD.light.footnoteBg,
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
                                        color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                        fontFamily: FONT.sans,
                                        background: "none",
                                        border: "none",
                                        padding: 0,
                                        cursor: "pointer",
                                        textAlign: "left",
                                        lineHeight: 1.5,
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.color = COLOR.gold.base
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.color = isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary
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
                        isDark={isDark}
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
        </div>
    )
}
