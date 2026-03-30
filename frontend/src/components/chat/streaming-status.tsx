"use client"

import {useEffect, useRef, useState} from "react"
import {motion, AnimatePresence} from "motion/react"
import {Sparkles, Search, Globe, BookMarked, PenLine, Wifi, Loader2} from "lucide-react"

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
        return {icon: Sparkles, name: "sparkles", color: "#d4956b"}
    }
    if (lower.includes("searching legal") || lower.includes("corpus") || lower.includes("eranking") || lower.includes("andidate") || lower.includes("mbedding") || lower.includes("ybrid")) {
        return {icon: Search, name: "search", color: "#3576ae"}
    }
    if (lower.includes("web")) {
        return {icon: Globe, name: "globe", color: "#38B2AC"}
    }
    if (lower.includes("found")) {
        return {icon: BookMarked, name: "bookmarked", color: "#C9A84C"}
    }
    if (lower.includes("writing") || lower.includes("answer")) {
        return {icon: PenLine, name: "penline", color: "#C9A84C"}
    }
    if (lower.includes("connecting")) {
        return {icon: Wifi, name: "wifi", color: "#d4956b"}
    }
    return {icon: Loader2, name: "loader", color: "#d4956b"}
}

export function StreamingStatus({status, isDark = false}: StreamingStatusProps) {
    const label = status ?? "Thinking\u2026"
    const [pastSteps, setPastSteps] = useState<StepEntry[]>([])
    const prevLabel = useRef(label)

    const {icon: Icon, name: iconName, color: iconColor} = getIconForStatus(label)

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
        }
    }, [label])

    const textColor = isDark ? "rgba(255,255,255,0.85)" : "#3a2a10"
    const dimTextColor = isDark ? "rgba(255,255,255,0.40)" : "rgba(80,60,20,0.40)"

    return (
        <div
            className="inline-flex flex-col gap-1 rounded-xl px-3.5 py-2.5"
            style={{
                background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,240,215,0.20)",
                border: isDark ? "1px solid rgba(255,255,255,0.14)" : "1px solid rgba(255,255,255,0.40)",
                backdropFilter: "blur(12px)",
                WebkitBackdropFilter: "blur(12px)",
                minWidth: 180,
                width: "auto",
            }}
        >
            {/* Current step */}
            <div className="flex items-center gap-2">
                <div style={{width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0}}>
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={iconName}
                            initial={{opacity: 0, scale: 0.85}}
                            animate={{opacity: 1, scale: 1}}
                            exit={{opacity: 0, scale: 0.85}}
                            transition={{duration: 0.2}}
                            style={{display: "flex", alignItems: "center", justifyContent: "center"}}
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
                    fontSize: 13,
                    color: textColor,
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                }}>
                    {label}
                </span>
            </div>

            {/* Past steps */}
            <AnimatePresence>
                {pastSteps.map((step, i) => (
                    <motion.div
                        key={`past-${i}-${step.label.slice(0, 20)}`}
                        initial={{opacity: 0, y: -6}}
                        animate={{opacity: 1, y: 0}}
                        exit={{opacity: 0, y: -4}}
                        transition={{duration: 0.2}}
                        className="flex items-center gap-2"
                        style={{paddingLeft: 1}}
                    >
                        <div style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            flexShrink: 0,
                            background: step.color,
                        }}/>
                        <span style={{
                            fontSize: 10,
                            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
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
