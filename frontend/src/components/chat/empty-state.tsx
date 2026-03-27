"use client"

import { useState } from "react"

export const EMPTY_STATE_QUESTIONS = [
  {
    before: "What is the limitation period under ",
    law: "DIFC Law No. 5 of 2005",
    after: "?",
    full: "What is the limitation period under DIFC Law No. 5 of 2005?",
  },
  {
    before: "What are the grounds for termination under ",
    law: "DIFC Employment Law",
    after: "?",
    full: "What are the grounds for termination under DIFC Employment Law?",
  },
]

interface EmptyStateProps {
  onSelectQuestion: (q: string) => void
  onPreviewQuestion: (index: number | null) => void
  previewIndex: number | null
  isDark?: boolean
}

export function EmptyState({ onSelectQuestion, onPreviewQuestion, previewIndex, isDark = false }: EmptyStateProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  const headingColor = isDark ? "rgba(255,255,255,0.90)" : "#1a0e04"
  const lawColor = isDark ? "#C9A84C" : "#c47c00"
  const textColor = isDark ? "rgba(255,255,255,0.75)" : "rgba(46,31,8,0.72)"
  const activeTextColor = isDark ? "rgba(255,255,255,0.95)" : "#1a0e04"

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      padding: "40px 4px 24px",
      textAlign: "center",
    }}>
      <h2 style={{
        fontFamily: "Georgia, 'Times New Roman', serif",
        fontSize: "1.5rem",
        fontWeight: 700,
        color: headingColor,
        letterSpacing: "-0.03em",
        margin: "0 0 24px",
        transition: "color 0.3s ease",
      }}>
        What can I help you research?
      </h2>

      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        width: "100%",
        maxWidth: "520px",
      }} className="px-2 sm:px-0">
        {EMPTY_STATE_QUESTIONS.map((q, i) => {
          const isHovered = hoveredIndex === i
          const isOpen = previewIndex === i
          const active = isOpen || isHovered

          const btnBg = active
            ? isDark ? "rgba(255,255,255,0.16)" : "rgba(255,255,255,0.42)"
            : isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.28)"
          const btnBorder = active
            ? isDark ? "0.5px solid rgba(255,255,255,0.28)" : "0.5px solid rgba(255,255,255,0.70)"
            : isDark ? "0.5px solid rgba(255,255,255,0.16)" : "0.5px solid rgba(255,255,255,0.55)"

          return (
            <button
              key={i}
              onClick={() => onPreviewQuestion(isOpen ? null : i)}
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "13px 16px",
                borderRadius: "14px",
                background: btnBg,
                borderTop: btnBorder,
                borderRight: btnBorder,
                borderBottom: btnBorder,
                borderLeft: btnBorder,
                cursor: "pointer",
                transition: "all 0.16s ease",
                boxShadow: isDark
                  ? active ? "inset 0 1px 0 rgba(255,255,255,0.15)" : "none"
                  : active ? "inset 0 1px 0 rgba(255,255,255,0.80)" : "inset 0 1px 0 rgba(255,255,255,0.55)",
              }}
            >
              <p style={{
                fontSize: "13px",
                lineHeight: 1.5,
                color: active ? activeTextColor : textColor,
                margin: 0,
                fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                transition: "color 0.16s ease",
              }}>
                {q.before}
                <span style={{
                  color: lawColor,
                  textDecoration: active ? "underline" : "none",
                  textUnderlineOffset: "2px",
                  fontWeight: 500,
                }}>
                  {q.law}
                </span>
                {q.after}
              </p>
            </button>
          )
        })}
      </div>
    </div>
  )
}
