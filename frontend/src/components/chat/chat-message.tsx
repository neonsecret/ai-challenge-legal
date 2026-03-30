"use client"

import {useState} from "react"
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

export type {Source} from "@/components/chat/use-query-stream"

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
 *
 * Using `findAndReplace` from mdast-util-find-and-replace ensures correct
 * traversal of inline contexts (paragraphs, list items, blockquotes, etc.),
 * so citations embedded anywhere in the text are found and replaced.
 *
 * The returned objects are cast to `PhrasingContent` to satisfy the library's
 * type constraint; at runtime they carry `type: "citationRef"` which the
 * downstream rehype plugin recognises.
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
        // `citationRef` nodes are not standard HAST, but they were passed through
        // from MDAST as raw objects. Visit them by type string.
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

// ─── Shared citation button style ─────────────────────────────────────────────

function citationButtonStyle(isDark: boolean, resolvable: boolean): React.CSSProperties {
    return {
        display: "inline-flex",
        alignItems: "center",
        verticalAlign: "middle",
        gap: 3,
        padding: "1px 7px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        lineHeight: 1.6,
        cursor: resolvable ? "pointer" : "not-allowed",
        margin: "0 2px",
        background: isDark ? "rgba(201,168,76,0.15)" : "rgba(196,124,0,0.10)",
        border: isDark ? "0.5px solid rgba(201,168,76,0.40)" : "0.5px solid rgba(196,124,0,0.30)",
        color: isDark ? "#C9A84C" : "#7a4a00",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        transition: "background 0.12s",
        opacity: resolvable ? 1 : 0.35,
    }
}

// ─── Component props ──────────────────────────────────────────────────────────

interface ChatMessageProps {
    role: "user" | "assistant"
    content: string | null
    sources?: import("@/components/chat/use-query-stream").Source[]
    isStreaming?: boolean
    confidence?: number | null
    streamingStatus?: string | null
    trace?: string[]
    onSourceClick?: (answer: string, sources: import("@/components/chat/use-query-stream").Source[], focusDocId?: string, focusPage?: number) => void
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
    trace,
    onSourceClick,
    isDark = false,
}: ChatMessageProps) {
    const [copied, setCopied] = useState(false)

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
    const answerGlass = isDark ? {
        background: "rgba(255,255,255,0.07)",
        backdropFilter: "blur(48px) saturate(180%)",
        WebkitBackdropFilter: "blur(48px) saturate(180%)",
        border: "0.5px solid rgba(255,255,255,0.14)",
        borderRadius: "16px",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08)",
    } : {
        background: "rgba(255,252,242,0.52)",
        backdropFilter: "blur(32px) saturate(140%)",
        WebkitBackdropFilter: "blur(32px) saturate(140%)",
        border: "1px solid rgba(255,255,255,0.65)",
        borderRadius: "16px",
        boxShadow: "0 2px 16px rgba(100,50,0,0.08), inset 0 1.5px 0 rgba(255,255,255,0.85)",
    }

    const labelStyle = {
        fontSize: "10px",
        textTransform: "uppercase" as const,
        letterSpacing: "0.14em",
        color: isDark ? "rgba(255,255,255,0.35)" : "#7a5a20",
        margin: "0 0 8px",
        fontWeight: 600,
    }

    /**
     * Custom React component registered for the `citationbutton` HAST element
     * emitted by rehypeInlineCitations. Renders inline gold citation pills.
     * Hidden while streaming to avoid flicker on partial citation tokens.
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
            const resolvable = sources.some(s =>
                s.doc_id === resolvedDocId ||
                s.doc_id.startsWith(resolvedDocId) ||
                resolvedDocId.startsWith(s.doc_id)
            )
            return (
                <button
                    onClick={resolvable ? (e) => {
                        e.stopPropagation()
                        onSourceClick?.(content ?? "", sources, resolvedDocId, resolvedPage)
                    } : undefined}
                    title={resolvable ? undefined : "Source not found in retrieved documents"}
                    style={citationButtonStyle(isDark, resolvable)}
                >
                    p.{resolvedPage}
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
                        ? `${matchedSource.title || matchedSource.doc_id}${pageNum ? ` · p.${pageNum}` : ""}`
                        : "Source not found in retrieved documents"
                    }
                    style={citationButtonStyle(isDark, resolvable)}
                >
                    §{refindex}
                </button>
            )
        }

        return null
    }

    return (
        <div className="mb-7 animate-fade-in-up">
            {sources.length > 0 && (
                <SourcesPanel
                    sources={sources}
                    onSourceClick={(source) => onSourceClick?.(content ?? "", sources, source.doc_id, source.page_numbers[0])}
                    isDark={isDark}
                />
            )}

            <p style={labelStyle}>Answer</p>

            <div style={answerGlass}>
                <div className="p-4">
                    {content ? (
                        <div className="group relative">
                            <div className={isDark ? DARK_PROSE : WARM_PROSE}>
                                {/*
                                  * Single ReactMarkdown instance with remark + rehype plugins
                                  * that handle citation markers inline, fixing the block-break
                                  * issue caused by the previous split-and-interleave approach.
                                  *
                                  * Pipeline:
                                  *   remarkInlineCitations  → text nodes → citationRef MDAST nodes
                                  *   remarkRehypeOptions    → passThrough: ["citationRef"]
                                  *   rehypeInlineCitations  → citationRef → <citationbutton> HAST elements
                                  *   components.citationbutton → CitationButtonComponent (React)
                                  */}
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm, remarkInlineCitations]}
                                    rehypePlugins={[rehypeInlineCitations]}
                                    remarkRehypeOptions={{
                                        // "citationRef" is a custom node type not in the standard MDAST
                                        // union; the cast is intentional — passThrough accepts any string.
                                        passThrough: ["citationRef" as import("mdast").Nodes["type"]],
                                    }}
                                    components={{
                                        strong: ({node: _node, children, ...props}) => (
                                            <strong {...props}>{children}</strong>
                                        ),
                                        a: ({node: _node, children, href, ...props}) => (
                                            <a {...props} href={href} target="_blank" rel="noopener noreferrer">
                                                {children}
                                            </a>
                                        ),
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
                    ) : isStreaming ? (
                        <StreamingStatus status={streamingStatus} isDark={isDark}/>
                    ) : (
                        <p className="text-sm italic" style={{color: isDark ? "rgba(255,255,255,0.40)" : "#7a5a20"}}>
                            No response
                        </p>
                    )}
                </div>
            </div>

            {confidence != null && !isStreaming && (
                <div className="mt-2 animate-fade-in-up">
                    <ConfidenceBadge confidence={confidence} isDark={isDark}/>
                </div>
            )}

            {trace && trace.length > 0 && !isStreaming && content && (
                <AgentTrace trace={trace} isDark={isDark} />
            )}
        </div>
    )
}
