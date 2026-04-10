"use client"

import {memo} from "react"
import {FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"
import type {Source} from "@/components/chat/use-query-stream"

// ─── Superscript helpers ──────────────────────────────────────────────────────

const SUPERSCRIPT_DIGITS = ['\u2070', '\u00B9', '\u00B2', '\u00B3', '\u2074', '\u2075', '\u2076', '\u2077', '\u2078', '\u2079']

export function toSuperscript(n: number): string {
    return String(n).split('').map(d => SUPERSCRIPT_DIGITS[parseInt(d, 10)]).join('')
}

// ─── Footnote style (light-mode citation pills) ───────────────────────────────

export function footnoteStyle(resolvable: boolean): React.CSSProperties {
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

// ─── CitationButton ───────────────────────────────────────────────────────────

export interface CitationButtonProps {
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

export const CitationButton = memo(function CitationButton({
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
