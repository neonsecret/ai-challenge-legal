"use client"

import { Source } from "@/components/chat/use-query-stream"

interface SourcesPanelProps {
  sources: Source[]
  onSourceClick: (source: Source) => void
  isDark?: boolean
}

export function SourcesPanel({ sources, onSourceClick, isDark = false }: SourcesPanelProps) {
  if (!sources || sources.length === 0) return null

  const chipBg = isDark ? "rgba(201,168,76,0.14)" : "rgba(233,196,106,0.22)"
  const chipBorder = isDark ? "1px solid rgba(201,168,76,0.28)" : "1px solid rgba(233,196,106,0.48)"
  const chipHoverBg = isDark ? "rgba(201,168,76,0.22)" : "rgba(233,196,106,0.34)"
  const chipHoverBorder = isDark ? "rgba(201,168,76,0.45)" : "rgba(200,160,50,0.65)"
  const badgeBg = isDark ? "#b8860b" : "#c47c00"
  const textColor = isDark ? "rgba(255,255,255,0.80)" : "#1e1208"
  const labelColor = isDark ? "rgba(255,255,255,0.35)" : "#7a5a20"

  return (
    <div style={{ marginBottom: "12px" }}>
      <p style={{
        fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.14em",
        color: labelColor, margin: "0 0 8px", fontWeight: 600,
      }}>
        Sources
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
        {sources.map((source, i) => {
          const displayId = source.doc_id.length > 24 ? `${source.doc_id.slice(0, 24)}\u2026` : source.doc_id
          const label = source.page_numbers.length > 0 ? `${displayId} · p.${source.page_numbers.join(", ")}` : displayId
          return (
            <button
              key={`${source.doc_id}-${i}`}
              onClick={() => onSourceClick(source)}
              title={`${source.doc_id}${source.page_numbers.length > 0 ? ` · p.${source.page_numbers.join(", ")}` : ""}`}
              style={{
                display: "inline-flex", alignItems: "center", gap: "6px",
                padding: "5px 12px 5px 6px", borderRadius: "9999px",
                background: chipBg, border: chipBorder,
                cursor: "pointer", transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = chipHoverBg
                e.currentTarget.style.borderColor = chipHoverBorder
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = chipBg
                e.currentTarget.style.borderColor = isDark ? "rgba(201,168,76,0.28)" : "rgba(233,196,106,0.48)"
              }}
            >
              <span style={{
                width: 18, height: 18, borderRadius: 5, background: badgeBg,
                color: "#fff", fontSize: "10px", fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>{i + 1}</span>
              <span style={{
                fontSize: "11px", color: textColor, fontFamily: "monospace",
                fontWeight: 500, maxWidth: "200px",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>{label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
