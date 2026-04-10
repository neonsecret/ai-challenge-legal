"use client"

/**
 * Shows live intermediate reasoning text while the agent is in its <analysis> phase.
 * Only visible in dark/strict mode (light mode uses the StreamingStatus component instead).
 */
interface ThinkingPreviewProps {
    preview: string | null
}

export function ThinkingPreview({preview}: ThinkingPreviewProps) {
    if (!preview) return null

    return (
        <p style={{
            fontFamily: "Georgia, serif",
            fontSize: 12,
            fontStyle: "italic",
            color: "var(--strict-text-dim)",
            margin: "0 0 8px",
            lineHeight: 1.6,
            opacity: 0.7,
        }}>
            {preview}
        </p>
    )
}
