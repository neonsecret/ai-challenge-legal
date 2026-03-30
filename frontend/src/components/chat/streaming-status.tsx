"use client"

import {useEffect, useRef, useState, useCallback} from "react"
import {motion, AnimatePresence} from "motion/react"
import {Sparkles, Search, Globe, BookMarked, PenLine, Wifi, Loader2} from "lucide-react"
import {STEP_COLOR, TIMING, FONT, TYPE_SCALE, SPACE, GLASS, TEXT_DARK, TEXT_LIGHT} from "@/lib/design-tokens"

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
    isDark?: boolean
}

interface StepEntry {
    label: string
    color: string
}

function getIconForStatus(label: string): { icon: typeof Sparkles; name: string; color: string } {
    const lower = label.toLowerCase()
    if (lower.includes("analyzing") || lower.includes("thinking")) {
        return {icon: Sparkles, name: "sparkles", color: STEP_COLOR.thinking}
    }
    if (lower.includes("searching legal") || lower.includes("corpus") || lower.includes("eranking") || lower.includes("andidate") || lower.includes("mbedding") || lower.includes("ybrid")) {
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

export function StreamingStatus({status, isDark = false}: StreamingStatusProps) {
    const label = status ?? "Thinking\u2026"
    const [pastSteps, setPastSteps] = useState<StepEntry[]>([])
    const prevLabel = useRef(label)

    // --- Animated dots state ---
    const [dotIndex, setDotIndex] = useState(0)

    // --- Elapsed timer state ---
    const stepStartTime = useRef(Date.now())
    const [elapsed, setElapsed] = useState(0)

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
            // For reranking progress updates, replace the last reranking step
            const prevLower = prevLabel.current.toLowerCase()
            const currLower = label.toLowerCase()
            if (currLower.includes("eranking") && prevLower.includes("eranking")) {
                setPastSteps((prev) => {
                    if (prev.length > 0 && prev[prev.length - 1].label.toLowerCase().includes("eranking")) {
                        return [...prev.slice(0, -1), {label: prevLabel.current, color: prevInfo.color}]
                    }
                    return [...prev.slice(-5), {label: prevLabel.current, color: prevInfo.color}]
                })
            } else {
                setPastSteps((prev) => {
                    if (prev.length > 0 && prev[prev.length - 1].label === prevLabel.current) return prev
                    return [...prev.slice(-5), {label: prevLabel.current, color: prevInfo.color}]
                })
            }
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

    const textColor = isDark ? TEXT_DARK.primary : TEXT_LIGHT.primary
    const dimTextColor = isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary
    const elapsedColor = isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary
    const glass = isDark ? GLASS.dark : GLASS.light
    const dotSize = SPACE["1"] + 2 // 6px filled circle

    // Glow animation: generate a CSS-compatible color with 30% opacity for the shadow
    const glowColor = iconColor + "4D" // 4D hex ≈ 30% opacity

    return (
        <div
            className="inline-flex flex-col rounded-xl"
            style={{
                gap: SPACE["1"],
                padding: `${SPACE["2"] + 2}px ${SPACE["3"] + 2}px`,
                background: glass.bg,
                border: `1px solid ${glass.border}`,
                backdropFilter: glass.blurLight,
                WebkitBackdropFilter: glass.blurLight,
                minWidth: 180,
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

            {/* Current step */}
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
                    color: textColor,
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
                                color: elapsedColor,
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

            {/* Past steps */}
            <AnimatePresence>
                {pastSteps.map((step, i) => (
                    <motion.div
                        key={`past-${i}-${step.label.slice(0, 20)}`}
                        initial={{opacity: 0, y: -6}}
                        animate={{opacity: 1, y: 0}}
                        exit={{opacity: 0, y: -4}}
                        transition={{duration: parseFloat(TIMING.fast), ease: MOTION_EASE_OUT}}
                        className="flex items-center"
                        style={{paddingLeft: 1, gap: SPACE["2"], willChange: "transform, opacity"}}
                    >
                        <div style={{
                            width: dotSize,
                            height: dotSize,
                            borderRadius: "50%",
                            flexShrink: 0,
                            background: step.color,
                        }}/>
                        <span style={{
                            fontSize: TYPE_SCALE.xs,
                            fontFamily: FONT.sans,
                            color: dimTextColor,
                            whiteSpace: "nowrap",
                        }}>
                            {step.label}
                        </span>
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    )
}
