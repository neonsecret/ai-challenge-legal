"use client";

// Footnotes — renders cited sources below each assistant answer (dark mode).
// Light mode: delegates to existing inline rendering in chat-message.tsx.

export interface CitedEntry {
    index: number;       // [DOC-N] 1-based
    docId: string;
    title: string;
    snippet: string;
}

interface FootnotesProps {
    citedSources: CitedEntry[];
    onSourceClick: (index: number, docId: string) => void;
    isDark: boolean;
}

export function Footnotes({ citedSources, onSourceClick, isDark }: FootnotesProps) {
    if (!isDark || citedSources.length === 0) return null;

    return (
        <div style={{
            borderTop: "1px solid var(--strict-gold-border)",
            paddingTop: 8,
            marginTop: 12,
        }}>
            {/* "SOURCES" label */}
            <span style={{
                display: "block",
                font: "6px/1 system-ui",
                textTransform: "uppercase",
                letterSpacing: 1,
                color: "var(--strict-text-dim)",
                marginBottom: 6,
            }}>
                SOURCES
            </span>

            {citedSources.map((entry) => (
                <div key={entry.index} style={{ display: "flex", gap: 6, marginBottom: 4 }}>
                    {/* Gold numbered button */}
                    <button
                        onClick={() => onSourceClick(entry.index, entry.docId)}
                        style={{
                            flexShrink: 0,
                            font: "8px/1 Georgia, serif",
                            color: "var(--strict-gold-text)",
                            background: "none",
                            border: "none",
                            padding: 0,
                            cursor: "pointer",
                            minWidth: 14,
                            textAlign: "right",
                        }}
                    >
                        {entry.index}
                    </button>
                    {/* Source title + snippet */}
                    <span style={{
                        font: "8px/1.4 system-ui",
                        color: "var(--strict-text-secondary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>
                        {entry.title}
                    </span>
                </div>
            ))}
        </div>
    );
}
