"use client"

import {useMemo, useCallback} from "react"
import {AnimatePresence, motion} from "motion/react"
import {useI18n} from "@/lib/i18n"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {visit} from "unist-util-visit"
import {findAndReplace} from "mdast-util-find-and-replace"
import {FeedbackButtons} from "@/components/chat/feedback-buttons"
import {SourcesPanel} from "@/components/chat/sources-panel"
import {ConfidenceBadge} from "@/components/chat/confidence-badge"
import {PipelineStatusBar} from "@/components/chat/pipeline-status-bar"
import {DocumentCard} from "@/components/chat/document-card/DocumentCard"
import {CitationButton} from "@/components/chat/message-parts/MessageCitations"
import {MessageFootnotes} from "@/components/chat/message-parts/MessageFootnotes"
import {MessageStatus} from "@/components/chat/message-parts/MessageStatus"
import {FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"
import type {CitedEntry} from "@/components/chat/footnotes"
import type {ChatDocument} from "@/types/documents"

export type {Source} from "@/components/chat/use-query-stream"
type Source = import("@/components/chat/use-query-stream").Source

// ─── Citation patterns ────────────────────────────────────────────────────────

const SOURCE_LINK_PATTERN = /\[\[source:([^:\]]+):(\d+)\]\]/g
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

// ─── Cited source collection ─────────────────────────────────────────────────

function collectCitedSources(content: string, sources: Source[]): CitedEntry[] {
    const cited = new Map<number, CitedEntry>()

    for (const m of content.matchAll(/\[DOC-(\d+)\]/g)) {
        const n = parseInt(m[1], 10)
        const src = sources[n - 1]
        if (src && !cited.has(n)) {
            cited.set(n, {
                footnoteNum: n,
                docId: src.doc_id,
                title: src.title || src.doc_id,
                page: src.page_numbers[0],
            })
        }
    }

    for (const m of content.matchAll(/\[\[source:([^:\]]+):(\d+)\]\]/g)) {
        const docId = m[1]
        const page = parseInt(m[2], 10)
        const srcIdx = sources.findIndex(s =>
            s && (s.doc_id === docId || s.doc_id.startsWith(docId) || docId.startsWith(s.doc_id))
        )
        if (srcIdx >= 0) {
            const src = sources[srcIdx]
            const n = srcIdx + 1
            if (src && !cited.has(n)) {
                cited.set(n, {
                    footnoteNum: n,
                    docId: src.doc_id,
                    title: src.title || src.doc_id,
                    page,
                })
            }
        }
    }

    return [...cited.values()].sort((a, b) => a.footnoteNum - b.footnoteNum)
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
    onAbort?: () => void
    isDark?: boolean
    /** @deprecated isDark covers this — kept for backward compat with page.tsx until task #16 */
    isStrict?: boolean
    messageId?: string
    traceId?: string | null
    conversationId?: string | null
    feedback?: { rating: "positive" | "negative"; comment?: string } | null
    onFeedback?: (messageId: string, rating: "positive" | "negative", comment?: string) => void
    /** Documents generated by the agent in this message turn */
    documents?: ChatDocument[]
    /** chatId needed for document preview/download URLs */
    chatId?: string
    onDocumentPreview?: (docId: string) => void
    /** True while streaming in drafting mode and no document has arrived yet */
    isDraftingMode?: boolean
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
    documents = [],
    chatId,
    onDocumentPreview,
    isDraftingMode = false,
}: ChatMessageProps) {
    const dark = isStrict ?? isDark
    const { t } = useI18n()

    const citedSources = useMemo(
        () => (content && sources.length > 0 && !isStreaming)
            ? collectCitedSources(content, sources)
            : [],
        [content, sources, isStreaming],
    )

    const citationButtonComponent = useCallback(
        (props: Record<string, unknown>) => (
            <CitationButton
                {...(props as Omit<import("@/components/chat/message-parts/MessageCitations").CitationButtonProps, "isDark" | "sources" | "content" | "onSourceClick" | "isStreaming">)}
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
                        fontSize: "14px",
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

    // Determine if we show a streaming status placeholder instead of content
    const statusNode = (
        <MessageStatus
            content={content}
            isStreaming={isStreaming}
            streamingStatus={streamingStatus}
            streamingProgress={streamingProgress}
            streamingThinkingPreview={streamingThinkingPreview}
        />
    )

    const hasPipelineBar = trace && trace.length > 0
    const isStatusOnly = content === "__polling_pipeline_status__" ||
        content?.startsWith("__pipeline_status:") ||
        (!content && isStreaming && !hasPipelineBar)

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

            {/* Pipeline status (trace) */}
            {trace && trace.length > 0 && (
                <PipelineStatusBar trace={trace} isStreaming={isStreaming} isDark={dark} onAbort={isStreaming ? onAbort : undefined} />
            )}

            {/* Answer card */}
            <div style={answerCardStyle}>
                <div style={dark ? {paddingBottom: SPACE[4]} : {padding: SPACE[4]}}>
                    {/*
                     * AnimatePresence wraps ALL three content states so that when the
                     * intermediate answer (pre-tool-call text) is cleared it fades out
                     * smoothly instead of vanishing instantly (Bug 1 fix).
                     * Each state has a distinct key so framer-motion runs the exit animation
                     * before mounting the next state.
                     *
                     * "status"         — streaming status spinner / no answer text yet
                     * "answer-content" — real or intermediate answer text
                     * "no-response"    — done streaming but answer is empty
                     */}
                    <AnimatePresence mode="wait">
                    {isStatusOnly ? (
                        <motion.div
                            key="status"
                            initial={{opacity: 0}}
                            animate={{opacity: 1}}
                            exit={{opacity: 0}}
                            transition={{duration: 0.2, ease: "easeOut"}}
                        >
                            {statusNode}
                        </motion.div>
                    ) : content ? (
                        <motion.div
                            key="answer-content"
                            initial={{opacity: 0}}
                            animate={{opacity: 1}}
                            exit={{opacity: 0}}
                            transition={{duration: 0.2, ease: "easeOut"}}
                            className={`${dark ? STRICT_DARK_PROSE : isDark ? DARK_PROSE : WARM_PROSE}${isStreaming && dark ? " strict-streaming-cursor" : ""}${isStreaming && !dark ? " warm-streaming-cursor" : ""}`}
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
                            {isStreaming && dark && (
                                <style>{`
                                    .strict-streaming-cursor > p:last-child::after,
                                    .strict-streaming-cursor > h2:last-child::after,
                                    .strict-streaming-cursor > h3:last-child::after,
                                    .strict-streaming-cursor > h4:last-child::after,
                                    .strict-streaming-cursor > blockquote:last-child > p:last-child::after,
                                    .strict-streaming-cursor > ul:last-child > li:last-child::after,
                                    .strict-streaming-cursor > ol:last-child > li:last-child::after {
                                        content: "";
                                        display: inline-block;
                                        width: 1.5px;
                                        height: 1em;
                                        background: var(--strict-gold-base);
                                        vertical-align: text-bottom;
                                        margin-left: 2px;
                                        animation: cursor-blink 0.8s ease-in-out infinite;
                                    }
                                `}</style>
                            )}
                            {isStreaming && !dark && (
                                <style>{`
                                    .warm-streaming-cursor > p:last-child::after,
                                    .warm-streaming-cursor > h2:last-child::after,
                                    .warm-streaming-cursor > h3:last-child::after,
                                    .warm-streaming-cursor > h4:last-child::after,
                                    .warm-streaming-cursor > blockquote:last-child > p:last-child::after,
                                    .warm-streaming-cursor > ul:last-child > li:last-child::after,
                                    .warm-streaming-cursor > ol:last-child > li:last-child::after {
                                        content: "";
                                        display: inline-block;
                                        width: 1.5px;
                                        height: 1em;
                                        background: var(--dt-color-gold-base);
                                        vertical-align: text-bottom;
                                        margin-left: 2px;
                                        animation: cursor-blink 0.8s ease-in-out infinite;
                                    }
                                `}</style>
                            )}
                        </motion.div>
                    ) : !isStreaming ? (
                        <motion.p
                            key="no-response"
                            initial={{opacity: 0}}
                            animate={{opacity: 1}}
                            exit={{opacity: 0}}
                            transition={{duration: 0.2, ease: "easeOut"}}
                            style={{fontSize: TYPE_SCALE.sm, fontStyle: "italic", color: "var(--dt-vote-text)", margin: 0}}
                        >
                            No response
                        </motion.p>
                    ) : null}
                    </AnimatePresence>
                </div>

                {/* Light-mode footnotes inside card footer */}
                {!dark && (
                    <MessageFootnotes
                        citedSources={citedSources}
                        sources={sources}
                        content={content}
                        isDark={false}
                        onSourceClick={onSourceClick}
                    />
                )}
            </div>

            {/* Drafting-in-progress indicator — shown while streaming with a template selected, before document_generated fires */}
            {isStreaming && isDraftingMode && documents.length === 0 && (
                <div data-testid="drafting-indicator" style={{
                    display: "flex",
                    alignItems: "center",
                    gap: SPACE[2],
                    marginTop: SPACE[3],
                    padding: `${SPACE[2]}px ${SPACE[3]}px`,
                    borderRadius: RADIUS.md,
                    background: "var(--doc-skeleton-bg)",
                    border: "1px solid var(--doc-skeleton-border)",
                }}>
                    <span style={{
                        width: 8,
                        height: 8,
                        borderRadius: RADIUS.full,
                        background: "var(--doc-text-label)",
                        flexShrink: 0,
                        animation: "gentle-pulse 1.5s ease-in-out infinite",
                    }} />
                    <span style={{
                        fontSize: "var(--text-xs, 11px)",
                        color: "var(--doc-text-secondary)",
                        fontWeight: 500,
                        letterSpacing: "0.02em",
                    }}>
                        {t("template.drafting")}
                    </span>
                </div>
            )}

            {/* Document cards — generated by agent in this turn */}
            {documents.length > 0 && chatId && (
                <div style={{display: "flex", flexDirection: "column", gap: SPACE[2], marginTop: SPACE[3]}}>
                    {documents.map((doc) => (
                        <DocumentCard
                            key={doc.doc_id}
                            doc={doc}
                            chatId={chatId}
                            onPreview={onDocumentPreview ?? (() => {})}
                        />
                    ))}
                </div>
            )}

            {/* Stop button — light mode only */}
            {isStreaming && onAbort && !dark && (
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
                        background: "var(--dt-button-bg-hover)",
                        border: "1px solid var(--dt-glass-border)",
                        color: "var(--dt-text-secondary)",
                        cursor: "pointer",
                        fontSize: 10,
                        fontFamily: "system-ui, sans-serif",
                        letterSpacing: "0.01em",
                        transition: "background 0.15s, border-color 0.15s",
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.background = "var(--dt-accent-tint-hover)"
                        e.currentTarget.style.borderColor = "var(--dt-accent-border-strong)"
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = "var(--dt-button-bg-hover)"
                        e.currentTarget.style.borderColor = "var(--dt-glass-border)"
                    }}
                >
                    <span aria-hidden style={{width: 6, height: 6, borderRadius: 1, background: "currentColor", flexShrink: 0}} />
                    Stop generating
                </button>
            )}

            {/* Dark-mode footnotes below the card */}
            {dark && (
                <MessageFootnotes
                    citedSources={citedSources}
                    sources={sources}
                    content={content}
                    isDark={true}
                    onSourceClick={onSourceClick}
                />
            )}

            {/* Source chips — light mode only */}
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
                    <ConfidenceBadge confidence={confidence} isDark={dark} />
                </div>
            )}

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

// Re-export for backward compat
export {toSuperscript} from "@/components/chat/message-parts/MessageCitations"
export {footnoteStyle} from "@/components/chat/message-parts/MessageCitations"
