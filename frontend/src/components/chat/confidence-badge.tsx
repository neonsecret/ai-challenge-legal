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
}

export function ConfidenceBadge({confidence, className, isDark = false}: ConfidenceBadgeProps) {
    const level = getConfidenceLevel(confidence)
    const conf = CONFIDENCE_CONFIG[level]
    const theme = isDark ? conf.dark : conf.light
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
