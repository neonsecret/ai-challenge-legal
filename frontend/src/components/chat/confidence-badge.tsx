"use client"

import { ShieldCheck, AlertTriangle, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

type ConfidenceLevel = "high" | "medium" | "low"

function getConfidenceLevel(score: number): ConfidenceLevel {
  if (score >= 0.7) return "high"
  if (score >= 0.4) return "medium"
  return "low"
}

const CONFIDENCE_CONFIG: Record<ConfidenceLevel, {
  color: string
  bg: string
  border: string
  Icon: React.ElementType
  label: string
}> = {
  high: {
    color: "#1a3f6e",
    bg: "rgba(53,118,174,0.14)",
    border: "rgba(53,118,174,0.32)",
    Icon: ShieldCheck,
    label: "High confidence",
  },
  medium: {
    color: "#5a3a08",
    bg: "rgba(196,124,0,0.14)",
    border: "rgba(160,100,0,0.30)",
    Icon: AlertTriangle,
    label: "Medium confidence",
  },
  low: {
    color: "#5a1808",
    bg: "rgba(139,53,32,0.14)",
    border: "rgba(120,40,20,0.28)",
    Icon: AlertCircle,
    label: "Low confidence",
  },
}

interface ConfidenceBadgeProps {
  confidence: number
  className?: string
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const level = getConfidenceLevel(confidence)
  const conf = CONFIDENCE_CONFIG[level]
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium shrink-0",
        className
      )}
      style={{
        background: conf.bg,
        border: `1px solid ${conf.border}`,
        color: conf.color,
      }}
    >
      <conf.Icon className="size-3" />
      {conf.label}
    </div>
  )
}
