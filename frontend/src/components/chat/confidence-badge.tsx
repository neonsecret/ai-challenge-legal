"use client"

import {ShieldCheck, AlertTriangle, AlertCircle} from "lucide-react"
import {cn} from "@/lib/utils"

type ConfidenceLevel = "high" | "medium" | "low"

function getConfidenceLevel(score: number | string): ConfidenceLevel {
    if (typeof score === "string") {
        if (score === "high") return "high"
        if (score === "degraded") return "medium"
        return "low"
    }
    if (score >= 0.7) return "high"
    if (score >= 0.4) return "medium"
    return "low"
}

type ThemeConfig = { color: string; bg: string; border: string }

const CONFIDENCE_CONFIG: Record<ConfidenceLevel, {
    light: ThemeConfig
    dark: ThemeConfig
    Icon: React.ElementType
    label: string
}> = {
    high: {
        light: {color: "#1b5c9e", bg: "rgba(53,118,174,0.12)", border: "rgba(53,118,174,0.28)"},
        dark: {color: "#7eb8f7", bg: "rgba(53,118,174,0.18)", border: "rgba(53,118,174,0.38)"},
        Icon: ShieldCheck,
        label: "High confidence",
    },
    medium: {
        light: {color: "#7a4a00", bg: "rgba(196,124,0,0.12)", border: "rgba(160,100,0,0.28)"},
        dark: {color: "#e6b84a", bg: "rgba(230,168,23,0.16)", border: "rgba(230,168,23,0.34)"},
        Icon: AlertTriangle,
        label: "Medium confidence",
    },
    low: {
        light: {color: "#7a2010", bg: "rgba(139,53,32,0.12)", border: "rgba(120,40,20,0.26)"},
        dark: {color: "#f28b6e", bg: "rgba(224,92,58,0.16)", border: "rgba(224,92,58,0.34)"},
        Icon: AlertCircle,
        label: "Low confidence",
    },
}

interface ConfidenceBadgeProps {
    confidence: number | string
    className?: string
    isDark?: boolean
    /** @deprecated Use isDark instead */
    isStrict?: boolean
}

export function ConfidenceBadge({confidence, className, isDark = false, isStrict}: ConfidenceBadgeProps) {
    const level = getConfidenceLevel(confidence)
    const conf = CONFIDENCE_CONFIG[level]
    const dark = isDark || isStrict

    // Dark mode (Strict): unified gold badge per spec section 3.2
    if (dark) {
        return (
            <div
                className={cn("inline-flex items-center gap-1 shrink-0", className)}
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    height: 18,
                    padding: "0 7px",
                    borderRadius: 4,
                    background: "rgba(201,168,76, 0.06)",
                    border: "1px solid rgba(201,168,76, 0.1)",
                    font: "8px/1 system-ui, sans-serif",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                    color: "rgba(201,168,76, 0.55)",
                }}
            >
                {/* 5px gold dot indicator */}
                <span
                    aria-hidden
                    style={{
                        display: "inline-block",
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        background: "rgba(201,168,76, 0.55)",
                        flexShrink: 0,
                    }}
                />
                {conf.label}
            </div>
        )
    }

    // Light mode: colored confidence badges (unchanged)
    const theme = conf.light
    return (
        <div
            className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium shrink-0",
                className
            )}
            style={{
                background: theme.bg,
                border: `1px solid ${theme.border}`,
                color: theme.color,
            }}
        >
            <conf.Icon className="size-3"/>
            {conf.label}
        </div>
    )
}
