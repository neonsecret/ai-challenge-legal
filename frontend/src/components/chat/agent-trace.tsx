"use client"

import {useState} from "react"
import {motion} from "motion/react"
import {
    Sparkles,
    FileSearch,
    Globe,
    BookMarked,
    PenLine,
    Wifi,
    Circle,
    ChevronRight,
} from "lucide-react"
import type {LucideIcon} from "lucide-react"

// ─── Types ───────────────────────────────────────────────────────────────────

interface AgentTraceProps {
    trace: string[]
    isDark?: boolean
}

// ─── Icon + color mapping ────────────────────────────────────────────────────

type GlowColor = "#3576ae" | "#38B2AC" | "#C9A84C" | "#d4956b"

interface StepStyle {
    icon: LucideIcon
    glow: GlowColor
}

function getStepStyle(step: string): StepStyle {
    const lower = step.toLowerCase()

    if (lower.includes("analyzing") || lower.includes("thinking")) {
        return {icon: Sparkles, glow: "#d4956b"}
    }
    if (lower.includes("searching legal") || lower.includes("corpus")) {
        return {icon: FileSearch, glow: "#3576ae"}
    }
    if (lower.includes("web")) {
        return {icon: Globe, glow: "#38B2AC"}
    }
    if (lower.includes("found")) {
        return {icon: BookMarked, glow: "#3576ae"}
    }
    if (lower.includes("writing") || lower.includes("answer")) {
        return {icon: PenLine, glow: "#C9A84C"}
    }
    if (lower.includes("connecting")) {
        return {icon: Wifi, glow: "#38B2AC"}
    }
    return {icon: Circle, glow: "#d4956b"}
}

// ─── Timeline node ───────────────────────────────────────────────────────────

function TraceNode({
    step,
    index,
    isDark,
}: {
    step: string
    index: number
    isDark: boolean
}) {
    const {icon: Icon, glow} = getStepStyle(step)

    return (
        <motion.div
            initial={{opacity: 0, y: 6}}
            animate={{opacity: 1, y: 0}}
            transition={{
                duration: 0.2,
                delay: index * 0.08,
                ease: [0.32, 0.72, 0, 1],
            }}
            style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                position: "relative",
            }}
        >
            {/* Icon badge */}
            <div
                style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    background: isDark
                        ? "rgba(255,255,255,0.06)"
                        : "rgba(255,252,242,0.55)",
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    border: isDark
                        ? `0.5px solid rgba(255,255,255,0.12)`
                        : `0.5px solid rgba(255,255,255,0.50)`,
                    boxShadow: `0 0 8px ${glow}33`,
                }}
            >
                <Icon
                    size={11}
                    strokeWidth={2}
                    style={{color: glow}}
                />
            </div>

            {/* Label */}
            <span
                style={{
                    fontSize: 12,
                    lineHeight: 1.5,
                    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
                    color: isDark
                        ? "rgba(255,255,255,0.52)"
                        : "rgba(46,31,8,0.55)",
                    paddingTop: 2,
                }}
            >
                {step}
            </span>
        </motion.div>
    )
}

// ─── AgentTrace ──────────────────────────────────────────────────────────────

export function AgentTrace({trace, isDark = false}: AgentTraceProps) {
    const [expanded, setExpanded] = useState(false)

    if (!trace || trace.length === 0) return null

    const hasMiddleSteps = trace.length > 2
    const middleCount = trace.length - 2

    // Determine which steps to show
    const visibleSteps = expanded
        ? trace
        : trace.length <= 2
            ? trace
            : [trace[0], trace[trace.length - 1]]

    return (
        <div className="mt-2 animate-fade-in-up">
            {/* Toggle header */}
            <button
                onClick={() => setExpanded(!expanded)}
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: isDark
                        ? "rgba(255,255,255,0.32)"
                        : "rgba(46,31,8,0.36)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: "2px 0",
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    transition: "color 0.12s",
                }}
            >
                <ChevronRight
                    size={10}
                    strokeWidth={2.5}
                    style={{
                        transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
                        transition: "transform 0.15s",
                    }}
                />
                How we found this
            </button>

            {/* Timeline */}
            <div
                style={{
                    marginTop: 8,
                    paddingLeft: 11,
                    position: "relative",
                }}
            >
                {/* Vertical connecting line */}
                <div
                    style={{
                        position: "absolute",
                        left: 21,
                        top: 22,
                        bottom: 8,
                        width: 1,
                        background: isDark
                            ? "rgba(255,255,255,0.10)"
                            : "rgba(196,124,0,0.14)",
                    }}
                />

                <div style={{display: "flex", flexDirection: "column", gap: 8}}>
                    {!expanded && hasMiddleSteps ? (
                        <>
                            {/* First step */}
                            <TraceNode
                                step={trace[0]}
                                index={0}
                                isDark={isDark}
                            />

                            {/* Collapsed separator */}
                            <motion.div
                                initial={{opacity: 0}}
                                animate={{opacity: 1}}
                                transition={{duration: 0.15, delay: 0.08}}
                                onClick={() => setExpanded(true)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 10,
                                    cursor: "pointer",
                                    paddingLeft: 0,
                                }}
                            >
                                {/* Placeholder for icon alignment */}
                                <div style={{width: 22, flexShrink: 0, textAlign: "center"}}>
                                    <span
                                        style={{
                                            fontSize: 10,
                                            color: isDark
                                                ? "rgba(255,255,255,0.22)"
                                                : "rgba(46,31,8,0.25)",
                                        }}
                                    >
                                        ...
                                    </span>
                                </div>
                                <span
                                    style={{
                                        fontSize: 11,
                                        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
                                        color: isDark
                                            ? "rgba(255,255,255,0.28)"
                                            : "rgba(46,31,8,0.30)",
                                        fontStyle: "italic",
                                        paddingTop: 1,
                                    }}
                                >
                                    {middleCount} more {middleCount === 1 ? "step" : "steps"}
                                </span>
                            </motion.div>

                            {/* Last step */}
                            <TraceNode
                                step={trace[trace.length - 1]}
                                index={1}
                                isDark={isDark}
                            />
                        </>
                    ) : (
                        visibleSteps.map((step, i) => (
                            <TraceNode
                                key={i}
                                step={step}
                                index={i}
                                isDark={isDark}
                            />
                        ))
                    )}
                </div>
            </div>
        </div>
    )
}
