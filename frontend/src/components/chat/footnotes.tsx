"use client";

// Footnotes — renders cited sources below each assistant answer.
// Dark mode: gold-accented "SOURCES" section.
// Light mode: standard tertiary-color list.

export interface CitedEntry {
    footnoteNum: number;   // [DOC-N] 1-based
    docId: string;
    title: string;
    page?: number;
}

interface FootnotesProps {
    citedSources: CitedEntry[];
    onSourceClick?: (docId: string, page?: number) => void;
    isDark: boolean;
}

function toSuperscript(n: number): string {
    return String(n).replace(/\d/g, d => "⁰¹²³⁴⁵⁶⁷⁸⁹"[+d]);
}

export function Footnotes({ citedSources, onSourceClick, isDark }: FootnotesProps) {
    if (citedSources.length === 0) return null;

    if (isDark) {
        return (
            <div style={{
                borderTop: "1px solid var(--strict-gold-border)",
                paddingTop: 8,
                marginTop: 12,
                display: "flex",
                flexDirection: "column",
                gap: 4,
            }}>
                <span style={{
                    font: "9px/1 system-ui, sans-serif",
                    textTransform: "uppercase",
                    letterSpacing: "1.2px",
                    color: "var(--strict-text-dim)",
                    marginBottom: 2,
                }}>
                    SOURCES
                </span>
                {citedSources.map((entry) => (
                    <button
                        key={entry.footnoteNum}
                        onClick={() => onSourceClick?.(entry.docId, entry.page)}
                        style={{
                            display: "flex",
                            alignItems: "baseline",
                            gap: 5,
                            background: "none",
                            border: "none",
                            padding: 0,
                            cursor: "pointer",
                            textAlign: "left",
                        }}
                        onMouseEnter={e => {
                            (e.currentTarget.lastChild as HTMLElement).style.color = "var(--strict-text-primary)";
                        }}
                        onMouseLeave={e => {
                            (e.currentTarget.lastChild as HTMLElement).style.color = "var(--strict-text-secondary)";
                        }}
                    >
                        <span style={{ font: "10px/1 Georgia, serif", color: "var(--strict-gold-accent)", flexShrink: 0 }}>
                            {toSuperscript(entry.footnoteNum)}
                        </span>
                        <span style={{ font: "10px/1.4 system-ui, sans-serif", color: "var(--strict-text-secondary)" }}>
                            {entry.title}{entry.page ? ` · p.${entry.page}` : ""}
                        </span>
                    </button>
                ))}
            </div>
        );
    }

    // Light mode — mirrors existing dt-answer-footnote-bg style from chat-message.tsx
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 8 }}>
            {citedSources.map((entry) => (
                <button
                    key={entry.footnoteNum}
                    onClick={() => onSourceClick?.(entry.docId, entry.page)}
                    style={{
                        display: "block",
                        fontSize: 11,
                        color: "var(--dt-text-tertiary)",
                        fontFamily: "system-ui, sans-serif",
                        background: "none",
                        border: "none",
                        padding: 0,
                        cursor: "pointer",
                        textAlign: "left",
                        lineHeight: 1.5,
                    }}
                    onMouseEnter={e => { e.currentTarget.style.color = "var(--dt-accent-color)"; }}
                    onMouseLeave={e => { e.currentTarget.style.color = "var(--dt-text-tertiary)"; }}
                >
                    {toSuperscript(entry.footnoteNum)} {entry.title}{entry.page ? ` (p. ${entry.page})` : ""}
                </button>
            ))}
        </div>
    );
}
