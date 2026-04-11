"use client"

import {useEffect, useRef, useState, useCallback} from "react"
import {motion, AnimatePresence} from "motion/react"
import {Sparkles, Search, Globe, BookMarked, PenLine, Wifi, Loader2} from "lucide-react"
import {STEP_COLOR, TIMING, FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"
import type {Progress} from "./use-query-stream"

/** Cubic-bezier values from EASE.out as a tuple for motion/react */
const MOTION_EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1]

/** Threshold in ms before elapsed timer appears */
const ELAPSED_SHOW_THRESHOLD = 2000

/** Interval for dots cycling */
const DOTS_INTERVAL_MS = 500

/** Interval for elapsed counter updates */
const ELAPSED_INTERVAL_MS = 1000

interface StreamingStatusProps {
    status?: string | null
    progress?: Progress | null
    thinkingPreview?: string | null
    /** @deprecated Theme is now handled via CSS variables */
    isDark?: boolean
}

interface StepEntry {
    label: string
    color: string
}

function getIconForStatus(label: string): { icon: typeof Sparkles; name: string; color: string } {
    const lower = label.toLowerCase()
    if (lower.includes("analyzing") || lower.includes("thinking") || lower.includes("reasoning")) {
        return {icon: Sparkles, name: "sparkles", color: STEP_COLOR.thinking}
    }
    if (lower.includes("searching legal") || lower.includes("corpus") || lower.includes("reading legal") || lower.includes("evaluating") || lower.includes("broadening")) {
        return {icon: Search, name: "search", color: STEP_COLOR.search}
    }
    if (lower.includes("web")) {
        return {icon: Globe, name: "globe", color: STEP_COLOR.web}
    }
    if (lower.includes("found")) {
        return {icon: BookMarked, name: "bookmarked", color: STEP_COLOR.found}
    }
    if (lower.includes("writing") || lower.includes("answer")) {
        return {icon: PenLine, name: "penline", color: STEP_COLOR.answer}
    }
    if (lower.includes("connecting")) {
        return {icon: Wifi, name: "wifi", color: STEP_COLOR.connecting}
    }
    return {icon: Loader2, name: "loader", color: STEP_COLOR.default}
}

/** Strip trailing dots/ellipsis from a label so we can append our own animated dots */
function stripTrailingDots(text: string): string {
    return text.replace(/[\u2026.]+$/, "")
}

/** Format elapsed seconds into a human-readable string */
function formatElapsed(seconds: number): string {
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
}

const DOT_CYCLE = [".", "..", "..."] as const

export function StreamingStatus({status, progress}: StreamingStatusProps) {
    const label = status ?? "Thinking\u2026"
    const [pastSteps, setPastSteps] = useState<StepEntry[]>([])
    const prevLabel = useRef(label)

    // --- Animated dots state ---
    const [dotIndex, setDotIndex] = useState(0)

    // --- Elapsed timer state ---
    const stepStartTime = useRef(0)
    const [elapsed, setElapsed] = useState(0)

    // Initialize stepStartTime on mount (avoids calling Date.now during render)
    useEffect(() => {
        stepStartTime.current = Date.now()
    }, [])

    const {icon: Icon, name: iconName, color: iconColor} = getIconForStatus(label)

    // Reset timers when label changes
    const resetStepTimers = useCallback(() => {
        stepStartTime.current = Date.now()
        setElapsed(0)
        setDotIndex(0)
    }, [])

    useEffect(() => {
        if (label !== prevLabel.current) {
            const prevInfo = getIconForStatus(prevLabel.current)
            // Don't duplicate past steps if the label is the same (e.g. progress updates
            // on "Reading legal documents..." keep the same label)
            setPastSteps((prev) => {
                if (prev.length > 0 && prev[prev.length - 1].label === prevLabel.current) return prev
                return [...prev.slice(-2), {label: prevLabel.current, color: prevInfo.color}]
            })
            prevLabel.current = label
            resetStepTimers()
        }
    }, [label, resetStepTimers])

    // Dots cycling interval
    useEffect(() => {
        const id = setInterval(() => {
            setDotIndex((prev) => (prev + 1) % DOT_CYCLE.length)
        }, DOTS_INTERVAL_MS)
        return () => clearInterval(id)
    }, [])

    // Elapsed counter interval
    useEffect(() => {
        const id = setInterval(() => {
            const now = Date.now()
            setElapsed(Math.floor((now - stepStartTime.current) / 1000))
        }, ELAPSED_INTERVAL_MS)
        return () => clearInterval(id)
    }, [])

    const showElapsed = elapsed >= Math.ceil(ELAPSED_SHOW_THRESHOLD / 1000)
    const displayLabel = stripTrailingDots(label) + DOT_CYCLE[dotIndex]
    const dotSize = SPACE["1"] + 2 // 6px filled circle

    // Glow animation: generate a CSS-compatible color with 30% opacity for the shadow
    // STEP_COLOR values are hardcoded hex so string concatenation for hex opacity works.
    const glowColor = iconColor + "4D" // 4D hex ≈ 30% opacity

    return (
        <div
            className="inline-flex flex-wrap items-center rounded-xl"
            style={{
                gap: SPACE["2"],
                padding: `${SPACE["2"] + 2}px ${SPACE["3"] + 2}px`,
                background: "var(--dt-glass-bg)",
                border: "1px solid var(--dt-glass-border)",
                backdropFilter: "var(--dt-glass-blur-light)",
                WebkitBackdropFilter: "var(--dt-glass-blur-light)",
                width: "auto",
            }}
        >
            {/* Inline keyframes for the gentle glow pulse */}
            <style>{`
                @keyframes gentle-glow {
                    0%, 100% { box-shadow: 0 0 ${SPACE["1"]}px transparent; }
                    50% { box-shadow: 0 0 ${SPACE["2"]}px ${glowColor}; }
                }
            `}</style>

            {/* Past steps — dots only, no text labels */}
            {pastSteps.map((step, i) => (
                <div
                    key={`past-${i}-${step.label.slice(0, 20)}`}
                    style={{
                        width: dotSize,
                        height: dotSize,
                        borderRadius: "50%",
                        flexShrink: 0,
                        background: step.color,
                        opacity: 0.5,
                    }}
                />
            ))}

            {/* Current step: icon + label + elapsed timer — all inline */}
            <div className="flex items-center" style={{gap: SPACE["2"]}}>
                <div style={{
                    width: 18,
                    height: 18,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    borderRadius: SPACE["1"],
                    animation: "gentle-glow 2s ease-in-out infinite",
                }}>
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={iconName}
                            initial={{opacity: 0, scale: 0.85}}
                            animate={{opacity: 1, scale: 1}}
                            exit={{opacity: 0, scale: 0.85}}
                            transition={{duration: parseFloat(TIMING.fast), ease: MOTION_EASE_OUT}}
                            style={{display: "flex", alignItems: "center", justifyContent: "center", willChange: "transform, opacity"}}
                        >
                            <Icon
                                size={16}
                                color={iconColor}
                                className={iconName === "loader" ? "animate-spin" : undefined}
                            />
                        </motion.div>
                    </AnimatePresence>
                </div>
                <span style={{
                    fontSize: TYPE_SCALE.sm,
                    color: "var(--dt-text-primary)",
                    fontFamily: FONT.sans,
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                }}>
                    {displayLabel}
                </span>

                {/* Elapsed timer — fades in after threshold */}
                <AnimatePresence>
                    {showElapsed && (
                        <motion.span
                            initial={{opacity: 0}}
                            animate={{opacity: 1}}
                            exit={{opacity: 0}}
                            transition={{duration: parseFloat(TIMING.medium), ease: MOTION_EASE_OUT}}
                            style={{
                                fontSize: TYPE_SCALE.xs,
                                color: "var(--dt-text-quaternary)",
                                fontFamily: FONT.mono,
                                fontWeight: 400,
                                whiteSpace: "nowrap",
                                marginLeft: SPACE["1"],
                            }}
                        >
                            {formatElapsed(elapsed)}
                        </motion.span>
                    )}
                </AnimatePresence>
            </div>

            {/* Progress bar — rendered as a full-width row below when active */}
            <AnimatePresence>
                {progress && progress.total > 0 && (
                    <motion.div
                        initial={{opacity: 0}}
                        animate={{opacity: 1}}
                        exit={{opacity: 0}}
                        transition={{duration: parseFloat(TIMING.fast), ease: MOTION_EASE_OUT}}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: SPACE["2"],
                            width: "100%",
                            willChange: "opacity",
                            overflow: "hidden",
                        }}
                    >
                        <div style={{
                            flex: 1,
                            height: 4,
                            background: "var(--dt-progress-track-bg)",
                            borderRadius: RADIUS.full,
                            overflow: "hidden",
                        }}>
                            <motion.div
                                key={`bar-${progress.total}`}
                                initial={{width: 0}}
                                animate={{width: `${Math.min(100, (progress.current / progress.total) * 100)}%`}}
                                transition={{duration: 0.4, ease: MOTION_EASE_OUT}}
                                style={{
                                    height: "100%",
                                    background: iconColor,
                                    borderRadius: RADIUS.full,
                                    willChange: "width",
                                }}
                            />
                        </div>
                        <span style={{
                            fontSize: TYPE_SCALE.xs,
                            fontFamily: FONT.mono,
                            color: "var(--dt-text-tertiary)",
                            whiteSpace: "nowrap",
                        }}>
                            {progress.current}/{progress.total}
                        </span>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
