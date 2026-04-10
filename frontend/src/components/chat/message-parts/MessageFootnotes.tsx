"use client"

import {Footnotes, type CitedEntry} from "@/components/chat/footnotes"
import {SPACE, RADIUS} from "@/lib/tokens"
import type {Source} from "@/components/chat/use-query-stream"

interface MessageFootnotesProps {
    citedSources: CitedEntry[]
    sources: Source[]
    content: string | null
    isDark: boolean
    onSourceClick?: (answer: string, sources: Source[], focusDocId?: string, focusPage?: number) => void
}

/**
 * Renders the footnote list.
 * - Dark mode: standalone below the answer card
 * - Light mode: inside the card footer (pass `position="card-footer"`)
 */
export function MessageFootnotes({citedSources, sources, content, isDark, onSourceClick}: MessageFootnotesProps) {
    if (citedSources.length === 0) return null

    const handleClick = (docId: string, page?: number) =>
        onSourceClick?.(content ?? "", sources, docId, page)

    if (isDark) {
        return (
            <Footnotes
                citedSources={citedSources}
                onSourceClick={handleClick}
                isDark={true}
            />
        )
    }

    return (
        <div style={{
            padding: `${SPACE[3]}px ${SPACE[4]}px ${SPACE[4]}px`,
            borderTop: "1px solid var(--dt-answer-border)",
            background: "var(--dt-answer-footnote-bg)",
            borderRadius: `0 0 ${RADIUS.xl}px ${RADIUS.xl}px`,
        }}>
            <Footnotes
                citedSources={citedSources}
                onSourceClick={handleClick}
                isDark={false}
            />
        </div>
    )
}
