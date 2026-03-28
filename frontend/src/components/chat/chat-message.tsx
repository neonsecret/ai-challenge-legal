"use client"

import { useState } from "react"
import { ChevronRight } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { cn } from "@/lib/utils"
import { Copy, Check } from "lucide-react"
import { SourcesPanel } from "@/components/chat/sources-panel"
import { StreamingStatus } from "@/components/chat/streaming-status"
import { ConfidenceBadge } from "@/components/chat/confidence-badge"

export type { Source } from "@/components/chat/use-query-stream"

interface ChatMessageProps {
  role: "user" | "assistant"
  content: string | null
  sources?: import("@/components/chat/use-query-stream").Source[]
  isStreaming?: boolean
  confidence?: number | null
  streamingStatus?: string | null
  trace?: string[]
  onSourceClick?: (answer: string, sources: import("@/components/chat/use-query-stream").Source[]) => void
  isDark?: boolean
}

const WARM_PROSE = [
  "prose prose-sm max-w-none leading-relaxed",
  "prose-p:text-[#2e1f08] prose-p:my-2",
  "prose-headings:font-heading prose-headings:text-[#1a1006] prose-headings:font-semibold",
  "prose-strong:text-[#1a1006] prose-strong:font-semibold",
  "prose-a:text-[#c47c00] prose-a:no-underline hover:prose-a:underline",
  "prose-code:bg-[rgba(92,46,8,0.08)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-[#5c2e08]",
  "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-[#2e1f08]",
].join(" ")

const DARK_PROSE = [
  "prose prose-sm max-w-none leading-relaxed prose-invert",
  "prose-p:text-[rgba(255,255,255,0.82)] prose-p:my-2",
  "prose-headings:text-[rgba(255,255,255,0.92)] prose-headings:font-semibold",
  "prose-strong:text-[rgba(255,255,255,0.92)] prose-strong:font-semibold",
  "prose-a:text-[#C9A84C] prose-a:no-underline hover:prose-a:underline",
  "prose-code:bg-[rgba(255,255,255,0.08)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-[rgba(255,255,255,0.75)]",
  "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-[rgba(255,255,255,0.80)]",
].join(" ")

export function ChatMessage({
  role,
  content,
  sources = [],
  isStreaming = false,
  confidence,
  streamingStatus,
  trace,
  onSourceClick,
  isDark = false,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const [traceOpen, setTraceOpen] = useState(false)

  const handleCopy = () => {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  // ── User message ──
  if (role === "user") {
    return (
      <div className="mb-5 animate-fade-in-up" style={{ display: "flex", justifyContent: "flex-end" }}>
        <div style={{
          maxWidth: "72%",
          background: isDark ? "rgba(201,168,76,0.16)" : "rgba(180,120,10,0.22)",
          border: isDark ? "1px solid rgba(201,168,76,0.28)" : "1px solid rgba(160,100,5,0.38)",
          borderRadius: "16px 16px 4px 16px",
          padding: "10px 14px",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
        }}>
          <p style={{
            fontSize: "13px", margin: 0, lineHeight: 1.6,
            color: isDark ? "rgba(255,255,255,0.88)" : "#2a1806",
            fontWeight: 500,
          }}>
            {content}
          </p>
        </div>
      </div>
    )
  }

  // ── Assistant message ──
  const answerGlass = isDark ? {
    background: "rgba(255,255,255,0.07)",
    backdropFilter: "blur(48px) saturate(180%)",
    WebkitBackdropFilter: "blur(48px) saturate(180%)",
    border: "0.5px solid rgba(255,255,255,0.14)",
    borderRadius: "16px",
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08)",
  } : {
    background: "rgba(255,252,242,0.52)",
    backdropFilter: "blur(32px) saturate(140%)",
    WebkitBackdropFilter: "blur(32px) saturate(140%)",
    border: "1px solid rgba(255,255,255,0.65)",
    borderRadius: "16px",
    boxShadow: "0 2px 16px rgba(100,50,0,0.08), inset 0 1.5px 0 rgba(255,255,255,0.85)",
  }

  const labelStyle = {
    fontSize: "10px",
    textTransform: "uppercase" as const,
    letterSpacing: "0.14em",
    color: isDark ? "rgba(255,255,255,0.35)" : "#7a5a20",
    margin: "0 0 8px",
    fontWeight: 600,
  }

  return (
    <div className="mb-7 animate-fade-in-up">
      {sources.length > 0 && (
        <SourcesPanel
          sources={sources}
          onSourceClick={(_source) => onSourceClick?.(content ?? "", sources)}
          isDark={isDark}
        />
      )}

      <p style={labelStyle}>Answer</p>

      <div style={answerGlass}>
        <div className="p-4">
          {content ? (
            <div className="group relative">
              <div className={isDark ? DARK_PROSE : WARM_PROSE}>
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>
              <button
                onClick={handleCopy}
                className={cn(
                  "absolute -top-1 right-0 rounded-lg p-1.5 transition-all",
                  "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                )}
                style={{
                  background: isDark ? "rgba(255,255,255,0.10)" : "rgba(255,240,215,0.30)",
                  border: isDark ? "1px solid rgba(255,255,255,0.14)" : "1px solid rgba(255,255,255,0.40)",
                  backdropFilter: "blur(8px)",
                  WebkitBackdropFilter: "blur(8px)",
                  color: copied ? "#3576ae" : isDark ? "rgba(255,255,255,0.55)" : "#7a5a20",
                }}
                aria-label="Copy answer"
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              </button>
            </div>
          ) : isStreaming ? (
            <StreamingStatus status={streamingStatus} />
          ) : (
            <p className="text-sm italic" style={{ color: isDark ? "rgba(255,255,255,0.40)" : "#7a5a20" }}>
              No response
            </p>
          )}
        </div>
      </div>

      {confidence != null && !isStreaming && (
        <div className="mt-2 animate-fade-in-up">
          <ConfidenceBadge confidence={confidence} />
        </div>
      )}

      {trace && trace.length > 0 && !isStreaming && content && (
        <div className="mt-2 animate-fade-in-up">
          <button
            onClick={() => setTraceOpen(!traceOpen)}
            style={{
              display: "flex", alignItems: "center", gap: 4,
              fontSize: 10, fontWeight: 600, letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: isDark ? "rgba(255,255,255,0.32)" : "rgba(46,31,8,0.36)",
              background: "none", border: "none", cursor: "pointer", padding: "2px 0",
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              transition: "color 0.12s",
            }}
          >
            <ChevronRight size={10} strokeWidth={2.5} style={{ transform: traceOpen ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.15s" }} />
            How we found this
          </button>
          {traceOpen && (
            <div style={{
              marginTop: 6, paddingLeft: 12,
              borderLeft: isDark ? "1.5px solid rgba(255,255,255,0.10)" : "1.5px solid rgba(196,124,0,0.18)",
            }}>
              {trace.map((step, i) => (
                <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 5 }}>
                  <span style={{ fontSize: 9, color: isDark ? "rgba(201,168,76,0.65)" : "#c47c00", marginTop: 2, flexShrink: 0 }}>✓</span>
                  <span style={{
                    fontSize: 11, lineHeight: 1.45,
                    color: isDark ? "rgba(255,255,255,0.48)" : "rgba(46,31,8,0.52)",
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                  }}>{step}</span>
                </div>
              ))}
              {sources.length > 0 && (
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ fontSize: 9, color: isDark ? "rgba(201,168,76,0.65)" : "#c47c00", marginTop: 2, flexShrink: 0 }}>→</span>
                  <span
                    onClick={() => onSourceClick?.(content ?? "", sources)}
                    style={{
                      fontSize: 11, lineHeight: 1.45,
                      color: isDark ? "rgba(201,168,76,0.72)" : "#7a4a00",
                      fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                      cursor: "pointer", textDecoration: "underline", textDecorationStyle: "dotted",
                    }}
                  >
                    {sources.length === 1 ? "1 source" : `${sources.length} sources`}: {sources.slice(0, 3).map((s) => `${s.doc_id} p.${s.page_numbers[0] ?? 1}`).join(", ")}{sources.length > 3 ? ` +${sources.length - 3} more` : ""}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
