"use client"

import {useEffect, useRef, useState} from "react"

interface StreamingStatusProps {
    status?: string | null
    isDark?: boolean
}

// Parse "Reranking passages (16/40)..." into {done, total}
function parseProgress(label: string): { done: number; total: number } | null {
    const m = label.match(/\((\d+)\/(\d+)\)/)
    if (!m) return null
    return {done: parseInt(m[1]), total: parseInt(m[2])}
}

export function StreamingStatus({status, isDark = false}: StreamingStatusProps) {
    const label = status ?? "Thinking\u2026"
    const isRetrieving = label.includes("earch") || label.includes("andidate") || label.includes("eranking") || label.includes("mbedding") || label.includes("ound") || label.includes("allback") || label.includes("ybrid")
    const [steps, setSteps] = useState<string[]>([])
    const prevLabel = useRef(label)

    useEffect(() => {
        if (label !== prevLabel.current) {
            prevLabel.current = label
            if (isRetrieving) {
                setSteps((prev) => {
                    if (prev.length > 0 && prev[prev.length - 1] === label) return prev
                    // For reranking progress updates, replace the last reranking step
                    if (label.includes("eranking") && prev.length > 0 && prev[prev.length - 1].includes("eranking")) {
                        return [...prev.slice(0, -1), label]
                    }
                    return [...prev.slice(-5), label]
                })
            }
        }
    }, [label, isRetrieving])

    useEffect(() => {
        if (!isRetrieving && steps.length > 0) {
            const timeout = setTimeout(() => setSteps([]), 500)
            return () => clearTimeout(timeout)
        }
    }, [isRetrieving, steps.length])

    const accentColor = isDark ? "#C9A84C" : "#c9a230"
    const dimColor = isDark ? "rgba(255,255,255,0.25)" : "rgba(122,90,32,0.30)"
    const textColor = isDark ? "rgba(255,255,255,0.72)" : "#7a5a20"
    const progress = parseProgress(label)

    return (
        <div
            className="inline-flex items-center gap-2.5 rounded-xl px-3.5 py-2.5"
            style={{
                background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,240,215,0.20)",
                border: isDark ? "1px solid rgba(255,255,255,0.14)" : "1px solid rgba(255,255,255,0.40)",
                backdropFilter: "blur(12px)",
                WebkitBackdropFilter: "blur(12px)",
                animation: "gentle-pulse 2.5s ease-in-out infinite",
            }}
        >
            {steps.length > 0 ? (
                <div style={{display: "flex", flexDirection: "column", gap: 4, minWidth: 200}}>
                    {steps.map((step, i) => {
                        const isLatest = i === steps.length - 1
                        const stepProgress = isLatest ? parseProgress(step) : null

                        return (
                            <div key={`${i}-${step.slice(0, 20)}`}>
                                <div
                                    style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: 8,
                                        opacity: isLatest ? 1 : 0.35,
                                        transition: "opacity 0.3s ease",
                                    }}
                                >
                                    <div style={{
                                        width: 5, height: 5, borderRadius: "50%", flexShrink: 0,
                                        background: isLatest ? accentColor : dimColor,
                                        boxShadow: isLatest ? `0 0 6px ${accentColor}50, 0 0 12px ${accentColor}25` : "none",
                                        animation: isLatest ? "gentle-pulse 1.5s ease-in-out infinite" : "none",
                                    }}/>
                                    <span style={{
                                        fontSize: 10, fontFamily: "monospace",
                                        color: isLatest ? textColor : dimColor,
                                        whiteSpace: "nowrap",
                                    }}>
                    {step}
                  </span>
                                </div>
                                {/* Real progress bar for reranking */}
                                {stepProgress && isLatest && (
                                    <div style={{
                                        marginTop: 4, marginLeft: 13,
                                        height: 3, borderRadius: 2, overflow: "hidden",
                                        background: dimColor,
                                    }}>
                                        <div style={{
                                            height: "100%", borderRadius: 2,
                                            background: accentColor,
                                            width: `${(stepProgress.done / stepProgress.total) * 100}%`,
                                            transition: "width 0.4s ease-out",
                                        }}/>
                                    </div>
                                )}
                            </div>
                        )
                    })}
                </div>
            ) : (
                <>
                    <div className="flex items-center gap-1">
                        {[0, 1, 2].map((i) => (
                            <span
                                key={i}
                                className="size-1.5 rounded-full animate-bounce"
                                style={{
                                    background: accentColor,
                                    animationDelay: `${i * 0.15}s`,
                                    animationDuration: "0.8s",
                                }}
                            />
                        ))}
                    </div>
                    <span className="text-xs" style={{color: textColor}}>
            {label}
          </span>
                </>
            )}
        </div>
    )
}
