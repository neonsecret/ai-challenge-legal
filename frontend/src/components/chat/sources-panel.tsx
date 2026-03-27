"use client"

import { Source } from "@/components/chat/use-query-stream"

interface SourcesPanelProps {
  sources: Source[]
  onSourceClick: (source: Source) => void
}

export function SourcesPanel({ sources, onSourceClick }: SourcesPanelProps) {
  if (!sources || sources.length === 0) return null

  return (
    <div className="mb-4">
      <span
        className="text-sm font-medium mb-2 block"
        style={{ color: "#7a5a20" }}
      >
        Sources
      </span>
      <div className="flex flex-wrap gap-2">
        {sources.map((source, i) => {
          const displayId =
            source.doc_id.length > 22
              ? `${source.doc_id.slice(0, 22)}\u2026`
              : source.doc_id
          return (
            <button
              key={`${source.doc_id}-${i}`}
              data-source-chip="true"
              onClick={() => onSourceClick(source)}
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 cursor-pointer
                         transition-all duration-150
                         hover:[border-color:rgba(201,162,48,0.40)]
                         hover:[background:rgba(255,240,215,0.25)]"
              style={{
                background: "rgba(255,255,255,0.15)",
                border: "1px solid rgba(255,255,255,0.30)",
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                maxWidth: "200px",
              }}
              title={`${source.doc_id}${source.page_numbers.length > 0 ? ` \u00b7 p.${source.page_numbers.join(", ")}` : ""}`}
            >
              {/* Numbered gold badge */}
              <span
                className="flex items-center justify-center size-4 rounded text-[9px] font-bold font-mono shrink-0"
                style={{ background: "rgba(201,162,48,0.85)", color: "#2e1f08" }}
              >
                {i + 1}
              </span>
              {/* doc_id — truncated */}
              <span
                className="text-[11px] font-mono truncate max-w-[140px]"
                style={{ color: "#5c3a0a" }}
              >
                {displayId}
              </span>
              {/* Page number in caramel gold */}
              {source.page_numbers.length > 0 && (
                <>
                  <span style={{ color: "rgba(92,46,8,0.40)" }}>\u00b7</span>
                  <span
                    className="text-[11px] font-mono shrink-0"
                    style={{ color: "#c47c00" }}
                  >
                    p.{source.page_numbers.join(", ")}
                  </span>
                </>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
