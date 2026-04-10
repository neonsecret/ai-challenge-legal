"use client"

import {useMemo, useCallback, memo} from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {visit} from "unist-util-visit"
import {findAndReplace} from "mdast-util-find-and-replace"
import {FeedbackButtons} from "@/components/chat/feedback-buttons"
import {Footnotes, type CitedEntry} from "@/components/chat/footnotes"
import {SourcesPanel} from "@/components/chat/sources-panel"
import {StreamingStatus} from "@/components/chat/streaming-status"
import {ConfidenceBadge} from "@/components/chat/confidence-badge"
import {PipelineStatusBar} from "@/components/chat/pipeline-status-bar"
import {FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"

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

const STRICT_DARK_PROSE = [
    "prose prose-sm max-w-none prose-invert",
    "prose-p:text-[var(--strict-text-body)] prose-p:my-2",
    "prose-headings:text-[var(--strict-text-primary)] prose-headings:font-normal prose-headings:font-serif",
    "prose-strong:text-[var(--strict-text-primary)] prose-strong:font-semibold",
    "prose-a:text-[var(--strict-citation)] prose-a:no-underline hover:prose-a:underline",
    "prose-code:bg-[var(--strict-code-bg)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-[var(--strict-text-body)]",
    "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-[var(--strict-text-body)]",
    "prose-table:text-[var(--strict-text-secondary)] prose-th:text-left prose-th:text-[11px] prose-th:py-1.5 prose-th:px-2 prose-th:border-b prose-th:border-[var(--strict-table-border)]",
    "prose-td:text-[12px] prose-td:py-1.5 prose-td:px-2 prose-td:border-b prose-td:border-[var(--strict-hr-border)]",
    "prose-hr:border-[var(--strict-gold-border)] prose-hr:my-3",
    "prose-blockquote:border-l-[var(--strict-gold-base)] prose-blockquote:text-[var(--strict-text-secondary)] prose-blockquote:bg-[var(--strict-blockquote-bg)] prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:my-2",
].join(" ")

// ─── Superscript helpers ─────────────────────────────────────────────────────

const SUPERSCRIPT_DIGITS = ['\u2070', '\u00B9', '\u00B2', '\u00B3', '\u2074', '\u2075', '\u2076', '\u2077', '\u2078', '\u2079']

function toSuperscript(n: number): string {
    return String(n).split('').map(d => SUPERSCRIPT_DIGITS[parseInt(d, 10)]).join('')
}

// ─── Cited source collection ─────────────────────────────────────────────────

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

// ─── Footnote style (light-mode citation pills) ──────────────────────────────

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

// ─── Citation button ──────────────────────────────────────────────────────────

interface CitationButtonProps {
    citationkind?: string
    docid?: string
    page?: number
    refindex?: number
    isDark: boolean
    isStreaming: boolean
    sources: Source[]
    content: string | null
    onSourceClick?: (answer: string, sources: Source[], focusDocId?: string, focusPage?: number) => void
}

const CitationButton = memo(function CitationButton({
    citationkind,
    docid,
    page,
    refindex,
    isDark,
    isStreaming,
    sources,
    content,
    onSourceClick,
}: CitationButtonProps) {
    if (isStreaming) return null

    // ── Dark/Strict mode: gold superscript ───────────────────────────────
    if (isDark) {
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
                <sup
                    onClick={resolvable ? (e) => {
                        e.stopPropagation()
                        onSourceClick?.(content ?? "", sources, resolvedDocId, resolvedPage)
                    } : undefined}
                    title={resolvable
                        ? `${sources[srcIdx].title || sources[srcIdx].doc_id}${resolvedPage ? ` \u00B7 p.${resolvedPage}` : ""}`
                        : "Source not found in retrieved documents"
                    }
                    style={{color: "var(--strict-citation)", cursor: resolvable ? "pointer" : "not-allowed", fontSize: "0.7em", fontFamily: "system-ui", verticalAlign: "super"}}
                >
                    {footnoteNum}
                </sup>
            )
        }
        if (citationkind === "docref") {
            const sourceIdx = (refindex ?? 0) - 1
            const matchedSource = sources[sourceIdx]
            const resolvable = !!matchedSource
            const pageNum = matchedSource?.page_numbers[0]
            return (
                <sup
                    onClick={resolvable ? (e) => {
                        e.stopPropagation()
                        onSourceClick?.(content ?? "", sources, matchedSource.doc_id, pageNum)
                    } : undefined}
                    title={resolvable
                        ? `${matchedSource.title || matchedSource.doc_id}${pageNum ? ` \u00B7 p.${pageNum}` : ""}`
                        : "Source not found in retrieved documents"
                    }
                    style={{color: "var(--strict-citation)", cursor: resolvable ? "pointer" : "not-allowed", fontSize: "0.7em", fontFamily: "system-ui", verticalAlign: "super"}}
                >
                    {refindex ?? 0}
                </sup>
            )
        }
        return null
    }

    // ── Light mode: pill button ───────────────────────────────────────────
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
})

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
    onAbort?: () => void
    isDark?: boolean
    /** @deprecated isDark covers this — kept for backward compat with page.tsx until task #16 */
    isStrict?: boolean
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
    onAbort,
    isDark = false,
    isStrict,
    messageId,
    traceId,
    conversationId,
    feedback,
    onFeedback,
}: ChatMessageProps) {
    // After theme migration, isStrict === isDark. Prefer explicitly-passed isStrict.
    const dark = isStrict ?? isDark

    const citedSources = useMemo(
        () => (content && sources.length > 0 && !isStreaming)
            ? collectCitedSources(content, sources)
            : [],
        [content, sources, isStreaming],
    )

    const citationButtonComponent = useCallback(
        (props: Record<string, unknown>) => (
            <CitationButton
                {...(props as Omit<CitationButtonProps, "isDark" | "sources" | "content" | "onSourceClick" | "isStreaming">)}
                isDark={dark}
                sources={sources}
                content={content}
                onSourceClick={onSourceClick}
                isStreaming={isStreaming}
            />
        ),
        [dark, sources, content, onSourceClick, isStreaming],
    )

    // ── User message ──────────────────────────────────────────────────────────
    if (role === "user") {
        if (dark) {
            return (
                <div className="mb-5 animate-fade-in-up">
                    <p style={{
                        fontFamily: "Georgia, serif",
                        fontSize: "12px",
                        fontStyle: "italic",
                        color: "var(--strict-text-question)",
                        margin: 0,
                        marginBottom: 14,
                        paddingBottom: 10,
                        borderBottom: "1px solid var(--strict-gold-border)",
                        lineHeight: 1.7,
                    }}>
                        {content}
                    </p>
                </div>
            )
        }
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
                }}>
                    <p style={{fontSize: "13px", margin: 0, lineHeight: 1.6, color: "var(--dt-confidence-text)", fontWeight: 500}}>
                        {content}
                    </p>
                </div>
            </div>
        )
    }

    // ── Assistant message ─────────────────────────────────────────────────────

    const answerCardStyle: React.CSSProperties = dark ? {
        fontFamily: "var(--strict-prose-font)",
    } : {
        background: "var(--dt-answer-bg)",
        border: "0.5px solid var(--dt-answer-border)",
        borderRadius: RADIUS.xl,
        fontFamily: FONT.sans,
    }

    return (
        <div className="mb-7 animate-fade-in-up">
            {!dark && (
                <p style={{
                    fontSize: TYPE_SCALE.xs,
                    textTransform: "uppercase",
                    letterSpacing: "0.14em",
                    color: "var(--dt-vote-text)",
                    margin: `0 0 ${SPACE[2]}px`,
                    fontWeight: 600,
                }}>
                    Answer
                </p>
            )}

            {/* Pipeline status (trace) — above the card */}
            {trace && trace.length > 0 && !isStreaming && content && (
                <PipelineStatusBar trace={trace} isStreaming={isStreaming} isDark={dark} />
            )}

            {/* Answer card */}
            <div style={answerCardStyle}>
                <div style={dark ? {paddingBottom: SPACE[4]} : {padding: SPACE[4]}}>
                    {content === "__polling_pipeline_status__" ? (
                        <StreamingStatus status="Processing..."/>
                    ) : content?.startsWith("__pipeline_status:") ? (
                        <StreamingStatus status={content.slice("__pipeline_status:".length)}/>
                    ) : content ? (
                        <div
                            className={dark ? STRICT_DARK_PROSE : isDark ? DARK_PROSE : WARM_PROSE}
                            style={dark ? {
                                fontFamily: "var(--strict-prose-font)",
                                lineHeight: "var(--strict-prose-lh)",
                                letterSpacing: "var(--strict-prose-tracking)",
                                fontSize: "var(--strict-prose-size)",
                            } : undefined}
                        >
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm, remarkInlineCitations]}
                                rehypePlugins={[rehypeInlineCitations]}
                                remarkRehypeOptions={{
                                    passThrough: ["citationRef" as import("mdast").Nodes["type"]],
                                }}
                                components={{
                                    h2: ({node: _node, children, ...props}) => (
                                        <h2 {...props} style={{
                                            fontSize: TYPE_SCALE.lg,
                                            fontFamily: dark ? "Georgia, serif" : FONT.sans,
                                            color: dark ? "var(--strict-text-primary)" : undefined,
                                            fontWeight: dark ? "normal" : undefined,
                                        }}>{children}</h2>
                                    ),
                                    h3: ({node: _node, children, ...props}) => (
                                        <h3 {...props} style={{
                                            fontSize: TYPE_SCALE.md,
                                            fontFamily: dark ? "Georgia, serif" : FONT.sans,
                                            color: dark ? "var(--strict-text-primary)" : undefined,
                                            fontWeight: dark ? "normal" : undefined,
                                        }}>{children}</h3>
                                    ),
                                    strong: ({node: _node, children, ...props}) => (
                                        <strong {...props}>{children}</strong>
                                    ),
                                    a: ({node: _node, children, href, ...props}) => {
                                        const safe = href && /^https?:\/\//i.test(href) ? href : undefined
                                        return <a {...props} href={safe} target="_blank" rel="noopener noreferrer">{children}</a>
                                    },
                                    // @ts-expect-error — citationbutton is a custom element from our rehype plugin
                                    citationbutton: citationButtonComponent,
                                }}
                            >
                                {content}
                            </ReactMarkdown>
                            {/* Typewriter cursor — dark mode only, visible while streaming */}
                            {isStreaming && dark && (
                                <span
                                    aria-hidden
                                    style={{
                                        display: "inline-block",
                                        width: "1.5px",
                                        height: "1em",
                                        background: "var(--strict-gold-base)",
                                        verticalAlign: "text-bottom",
                                        animation: "cursor-blink 0.8s ease-in-out infinite",
                                        marginLeft: "2px",
                                    }}
                                />
                            )}
                        </div>
                    ) : isStreaming ? (
                        <StreamingStatus status={streamingStatus} progress={streamingProgress} thinkingPreview={streamingThinkingPreview}/>
                    ) : (
                        <p style={{fontSize: TYPE_SCALE.sm, fontStyle: "italic", color: "var(--dt-vote-text)", margin: 0}}>
                            No response
                        </p>
                    )}
                </div>

                {/* Light-mode cited sources inside the card footer */}
                {citedSources.length > 0 && !dark && !isStreaming && (
                    <div style={{
                        padding: `${SPACE[3]}px ${SPACE[4]}px ${SPACE[4]}px`,
                        borderTop: "1px solid var(--dt-answer-border)",
                        background: "var(--dt-answer-footnote-bg)",
                        borderRadius: `0 0 ${RADIUS.xl}px ${RADIUS.xl}px`,
                    }}>
                        <Footnotes
                            citedSources={citedSources}
                            onSourceClick={(docId, page) => onSourceClick?.(content ?? "", sources, docId, page)}
                            isDark={false}
                        />
                    </div>
                )}
            </div>

            {/* Stop button — shown below answer while streaming */}
            {isStreaming && onAbort && (
                <button
                    onClick={onAbort}
                    aria-label="Stop generating"
                    style={{
                        marginTop: 10,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "5px 10px",
                        borderRadius: 5,
                        background: dark ? "rgba(201,168,76, 0.06)" : "var(--dt-button-bg-hover)",
                        border: dark ? "1px solid rgba(201,168,76, 0.15)" : "1px solid var(--dt-glass-border)",
                        color: dark ? "var(--strict-gold-text)" : "var(--dt-text-secondary)",
                        cursor: "pointer",
                        fontSize: 10,
                        fontFamily: "system-ui, sans-serif",
                        letterSpacing: "0.01em",
                        transition: "background 0.15s, border-color 0.15s",
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.background = dark ? "rgba(201,168,76, 0.1)" : "var(--dt-accent-tint-hover)"
                        e.currentTarget.style.borderColor = dark ? "rgba(201,168,76, 0.25)" : "var(--dt-accent-border-strong)"
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = dark ? "rgba(201,168,76, 0.06)" : "var(--dt-button-bg-hover)"
                        e.currentTarget.style.borderColor = dark ? "rgba(201,168,76, 0.15)" : "var(--dt-glass-border)"
                    }}
                >
                    {/* Gold square stop icon */}
                    <span
                        aria-hidden
                        style={{
                            width: 6,
                            height: 6,
                            borderRadius: 1,
                            background: dark ? "var(--strict-gold-base)" : "currentColor",
                            flexShrink: 0,
                        }}
                    />
                    Stop generating
                </button>
            )}

            {/* Dark-mode: Footnotes below the card */}
            {dark && citedSources.length > 0 && !isStreaming && (
                <Footnotes
                    citedSources={citedSources}
                    onSourceClick={(docId, page) => onSourceClick?.(content ?? "", sources, docId, page)}
                    isDark={true}
                />
            )}

            {/* Source chips — light mode only (dark uses StrictSourceMargin / SourcePanelV2) */}
            {sources.length > 0 && !dark && (
                <div style={{marginTop: SPACE[3]}}>
                    <SourcesPanel
                        sources={sources}
                        onSourceClick={(source) => onSourceClick?.(content ?? "", sources, source.doc_id, source.page_numbers[0])}
                    />
                </div>
            )}

            {confidence != null && !isStreaming && (
                <div style={{marginTop: SPACE[2]}} className="animate-fade-in-up">
                    <ConfidenceBadge confidence={confidence} isDark={dark}/>
                </div>
            )}

            {/* Feedback: dark = copy+thumbs+comment row; light = thumbs only */}
            {!isStreaming && traceId && (
                <div style={{marginTop: dark ? 0 : SPACE[2]}}>
                    <FeedbackButtons
                        messageId={messageId}
                        traceId={traceId}
                        conversationId={conversationId}
                        content={content}
                        feedback={feedback}
                        onFeedback={onFeedback}
                        isStrict={dark}
                    />
                </div>
            )}
        </div>
    )
}

// Keep toSuperscript in module scope so it's accessible if needed elsewhere
export {toSuperscript}
