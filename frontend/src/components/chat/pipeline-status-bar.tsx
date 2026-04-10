"use client"

// PipelineStatusBar — horizontal compact trace bar for dark (Strict) mode.
// Replaces the vertical AgentTrace timeline.

interface PipelineStatusBarProps {
    trace: string[]
    isStreaming: boolean
    isDark: boolean
}

// Parse raw trace strings into display labels
function parseStep(raw: string): string {
    const s = raw.toLowerCase()
    if (s.includes("query") || s.includes("formul")) return "Query formulated"
    if (s.includes("retriev") || s.includes("searching") || s.includes("passage")) {
        const match = raw.match(/(\d+)/)
        return match ? `${match[1]} passages retrieved` : "Passages retrieved"
    }
    if (s.includes("rerank")) {
        const match = raw.match(/(\d+)/)
        return match ? `Reranked to ${match[1]}` : "Reranked"
    }
    if (s.includes("answer") || s.includes("generat") || s.includes("writing")) {
        return "Answer generated"
    }
    if (s.includes("citation")) {
        const match = raw.match(/(\d+)/)
        return match ? `${match[1]} citations` : "Citations"
    }
    if (s.includes("web") || s.includes("internet")) return "Web search"
    return raw.length > 32 ? raw.slice(0, 32) + "…" : raw
}

// Dot — 4px gold, pulses when active
function Dot({ active }: { active: boolean }) {
    return (
        <span
            aria-hidden
            style={{
                display: "inline-block",
                width: 4,
                height: 4,
                borderRadius: "50%",
                background: active ? "var(--strict-gold-base)" : "var(--strict-text-dim)",
                flexShrink: 0,
                animation: active ? "pipeline-dot-pulse 1.5s ease-in-out infinite" : "none",
            }}
        />
    )
}

// Light-mode fallback: simple comma-separated text
function LightTrace({ trace }: { trace: string[] }) {
    if (!trace.length) return null
    return (
        <div style={{
            fontSize: 11,
            color: "var(--muted-foreground)",
            padding: "4px 0",
            fontFamily: "system-ui, sans-serif",
        }}>
            {trace[trace.length - 1]}
        </div>
    )
}

export function PipelineStatusBar({ trace, isStreaming, isDark }: PipelineStatusBarProps) {
    if (!trace || trace.length === 0) return null

    if (!isDark) return <LightTrace trace={trace} />

    const steps = trace.map(parseStep)
    const lastIdx = steps.length - 1

    return (
        <div
            role="status"
            aria-label="Processing pipeline"
            aria-live="polite"
            style={{
                display: "flex",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "4px 6px",
                padding: "7px 10px",
                borderRadius: 6,
                background: "rgba(201,168,76, 0.025)",
                border: "1px solid rgba(201,168,76, 0.05)",
                marginBottom: 8,
            }}
        >
            {steps.map((label, i) => {
                const isActive = isStreaming && i === lastIdx
                return (
                    <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        {i > 0 && (
                            <span aria-hidden style={{
                                fontSize: "8.5px",
                                color: "rgba(201,168,76, 0.15)",
                                margin: "0 1px",
                            }}>›</span>
                        )}
                        <Dot active={isActive} />
                        <span style={{
                            font: "8.5px/1 system-ui, sans-serif",
                            color: isActive ? "var(--strict-gold-text)" : "var(--strict-text-dim)",
                            letterSpacing: "0.01em",
                            transition: "color 0.2s ease",
                        }}>
                            {label}
                        </span>
                    </span>
                )
            })}
        </div>
    )
}
