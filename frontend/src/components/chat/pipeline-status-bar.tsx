"use client"

// PipelineStatusBar — horizontal compact trace bar for dark (Strict) mode.
// Replaces the vertical AgentTrace timeline.

import {motion, AnimatePresence} from "motion/react"

interface PipelineStatusBarProps {
    trace: string[]
    isStreaming: boolean
    isDark: boolean
    onAbort?: () => void
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

// Dot — 4px gold, pulses when active; muted check-size dot when done
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
                opacity: active ? 1 : 0.45,
                transition: "opacity 0.3s ease, background 0.3s ease",
            }}
        />
    )
}

// AnimatedEllipsis — three staggered dots that cycle while a stage is active.
// Each dot fades in turn so it reads as a subtle "..." motion, not a bounce.
function AnimatedEllipsis() {
    return (
        <span aria-hidden style={{ display: "inline-flex", alignItems: "center", gap: 1, marginLeft: 1 }}>
            <span style={{
                display: "inline-block",
                width: 2,
                height: 2,
                borderRadius: "50%",
                background: "var(--strict-gold-base)",
                animation: "pipeline-dot-1 1.2s ease-in-out infinite",
                animationDelay: "0ms",
            }} />
            <span style={{
                display: "inline-block",
                width: 2,
                height: 2,
                borderRadius: "50%",
                background: "var(--strict-gold-base)",
                animation: "pipeline-dot-2 1.2s ease-in-out infinite",
                animationDelay: "0ms",
            }} />
            <span style={{
                display: "inline-block",
                width: 2,
                height: 2,
                borderRadius: "50%",
                background: "var(--strict-gold-base)",
                animation: "pipeline-dot-3 1.2s ease-in-out infinite",
                animationDelay: "0ms",
            }} />
        </span>
    )
}

// ConnectorArrow — animated › separator between steps.
// When the left stage is complete (not the active one), the arrow brightens with a brief wipe animation.
function ConnectorArrow({ leftComplete }: { leftComplete: boolean }) {
    return (
        <motion.span
            aria-hidden
            initial={{ opacity: 0.08 }}
            animate={{ opacity: leftComplete ? 0.3 : 0.12 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            style={{
                fontSize: "10px",
                color: "rgba(201,168,76, 1)",
                margin: "0 1px",
                display: "inline-block",
                transformOrigin: "left center",
            }}
        >
            ›
        </motion.span>
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

export function PipelineStatusBar({ trace, isStreaming, isDark, onAbort }: PipelineStatusBarProps) {
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
            <AnimatePresence initial={false}>
                {steps.map((label, i) => {
                    const isActive = isStreaming && i === lastIdx
                    // A step is "complete" when it's not the active one and we are still
                    // streaming (more steps may come), OR when streaming has ended.
                    const isComplete = !isActive && (i < lastIdx || !isStreaming)
                    return (
                        <motion.span
                            key={i}
                            initial={{ opacity: 0, x: -4 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
                        >
                            {i > 0 && (
                                <ConnectorArrow leftComplete={i <= lastIdx} />
                            )}
                            <Dot active={isActive} />
                            <span style={{
                                font: "10px/1 system-ui, sans-serif",
                                color: isActive
                                    ? "var(--strict-gold-text)"
                                    : isComplete
                                        ? "var(--strict-text-dim)"
                                        : "var(--strict-text-dim)",
                                letterSpacing: "0.01em",
                                transition: "color 0.3s ease, opacity 0.3s ease",
                                opacity: isComplete ? 0.65 : 1,
                            }}>
                                {label}
                            </span>
                            {/* Animated ellipsis only on the active in-progress stage */}
                            {isActive && <AnimatedEllipsis />}
                        </motion.span>
                    )
                })}
            </AnimatePresence>
            {/* Inline stop button during streaming */}
            {isStreaming && onAbort && (
                <>
                    <span style={{ flex: 1 }} />
                    <button
                        onClick={onAbort}
                        aria-label="Stop generating"
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background: "transparent",
                            border: "1px solid rgba(201,168,76, 0.1)",
                            color: "var(--strict-gold-text)",
                            cursor: "pointer",
                            fontSize: 9,
                            fontFamily: "system-ui, sans-serif",
                            transition: "background 0.15s, border-color 0.15s",
                            flexShrink: 0,
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = "rgba(201,168,76, 0.06)"
                            e.currentTarget.style.borderColor = "rgba(201,168,76, 0.2)"
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = "transparent"
                            e.currentTarget.style.borderColor = "rgba(201,168,76, 0.1)"
                        }}
                    >
                        <span aria-hidden style={{ width: 5, height: 5, borderRadius: 1, background: "var(--strict-gold-base)", flexShrink: 0 }} />
                        Stop
                    </button>
                </>
            )}
        </div>
    )
}
