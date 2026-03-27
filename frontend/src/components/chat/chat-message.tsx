"use client"

import { useState } from "react"
import ReactMarkdown from "react-markdown"
import { cn } from "@/lib/utils"
import { Copy, Check } from "lucide-react"
import { GlassCard } from "@/components/ui/glass-card"
import { SourcesPanel } from "@/components/chat/sources-panel"
import { StreamingStatus } from "@/components/chat/streaming-status"
import { ConfidenceBadge } from "@/components/chat/confidence-badge"

// Re-export Source type (page.tsx imports it from here)
export type { Source } from "@/components/chat/use-query-stream"

interface ChatMessageProps {
  role: "user" | "assistant"
  content: string | null
  sources?: import("@/components/chat/use-query-stream").Source[]
  isStreaming?: boolean
  confidence?: number | null
  streamingStatus?: string | null
  onSourceClick?: (answer: string, sources: import("@/components/chat/use-query-stream").Source[]) => void
}

// Warm palette prose classes — espresso text on amber glass background
const WARM_PROSE_CLASSES = [
  "prose prose-sm max-w-none leading-relaxed",
  "prose-p:text-[#2e1f08] prose-p:my-2",
  "prose-headings:font-heading prose-headings:text-[#1a1006] prose-headings:font-semibold",
  "prose-strong:text-[#1a1006] prose-strong:font-semibold",
  "prose-a:text-[#c47c00] prose-a:no-underline hover:prose-a:underline",
  "prose-code:bg-[rgba(92,46,8,0.08)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-[#5c2e08] prose-code:font-mono",
  "prose-blockquote:border-l-[#c9a230]/50 prose-blockquote:text-[#7a5a20]",
  "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-[#2e1f08]",
  "prose-hr:border-[#c9a230]/20",
].join(" ")

export function ChatMessage({
  role,
  content,
  sources = [],
  isStreaming = false,
  confidence,
  streamingStatus,
  onSourceClick,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  // ── User message — section heading (NOT a bubble) ──
  if (role === "user") {
    return (
      <div className="mb-4 animate-fade-in-up">
        <h2
          className="font-heading text-xl font-bold tracking-tight"
          style={{ color: "#1e1208" }}
        >
          {content}
        </h2>
      </div>
    )
  }

  // ── Assistant message — Perplexity layout ──
  return (
    <div className="mb-8 animate-fade-in-up">
      {/* Shield avatar row */}
      <div className="flex items-center gap-2 mb-3">
        <div
          className="shrink-0 size-7 rounded-xl flex items-center justify-center"
          style={{
            background: "rgba(201,162,48,0.12)",
            border: "1px solid rgba(201,162,48,0.28)",
            boxShadow: "0 2px 8px rgba(201,162,48,0.12)",
          }}
        >
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
            <path
              d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
              stroke="#c9a230"
              strokeWidth="1.3"
              strokeLinejoin="round"
              fill="rgba(201,162,48,0.18)"
            />
          </svg>
        </div>
        <span className="text-xs font-medium" style={{ color: "#7a5a20" }}>NeoLex</span>
      </div>

      <div className="flex-1 min-w-0">

        {/* ── SOURCES ABOVE ANSWER — mandatory SRC-01 ── */}
        {sources.length > 0 && (
          <SourcesPanel
            sources={sources}
            onSourceClick={(_source) => {
              onSourceClick?.(content ?? "", sources)
            }}
          />
        )}

        {/* ── GlassCard answer panel ── */}
        <GlassCard variant="panel" className="overflow-clip">
          <div className="p-4">
            {content ? (
              <div className="group relative">
                <div className={WARM_PROSE_CLASSES}>
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
                {/* Copy button — appears on hover */}
                <button
                  onClick={handleCopy}
                  className={cn(
                    "absolute -top-1 right-0 rounded-lg p-1.5 transition-all",
                    "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                  )}
                  style={{
                    background: "rgba(255,240,215,0.30)",
                    border: "1px solid rgba(255,255,255,0.40)",
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    color: copied ? "#3576ae" : "#7a5a20",
                  }}
                  aria-label="Copy answer"
                >
                  {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                </button>
              </div>
            ) : isStreaming ? (
              <StreamingStatus status={streamingStatus} />
            ) : (
              <p className="text-sm italic" style={{ color: "#7a5a20" }}>
                No response
              </p>
            )}
          </div>
        </GlassCard>

        {/* ── Confidence badge BELOW answer card ── */}
        {confidence != null && !isStreaming && (
          <div className="mt-2 animate-fade-in-up">
            <ConfidenceBadge confidence={confidence} />
          </div>
        )}

      </div>
    </div>
  )
}
