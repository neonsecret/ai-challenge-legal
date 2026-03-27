import { useState } from "react"
import ReactMarkdown from "react-markdown"
import { cn } from "@/lib/utils"
import { Copy, Check } from "lucide-react"

export interface Source {
  doc_id: string
  page_numbers: number[]
}

interface ChatMessageProps {
  role: "user" | "assistant"
  content: string | null
  sources?: Source[]
  isStreaming?: boolean
  confidence?: number | null
  streamingStatus?: string | null
}

type ConfidenceLevel = "high" | "medium" | "low"

function getConfidenceLevel(score: number): ConfidenceLevel {
  if (score >= 0.7) return "high"
  if (score >= 0.4) return "medium"
  return "low"
}

const CONFIDENCE_COLORS: Record<ConfidenceLevel, string> = {
  high: "rgba(74,222,128,0.7)",
  medium: "rgba(250,204,21,0.7)",
  low: "rgba(248,113,113,0.7)",
}

export function ChatMessage({
  role,
  content,
  sources = [],
  isStreaming = false,
  confidence,
  streamingStatus,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  if (role === "user") {
    return (
      <div className="flex justify-end mb-5 animate-fade-in-up">
        <div
          className="max-w-[72%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed"
          style={{
            background: "rgba(255,255,255,0.07)",
            border: "1px solid rgba(255,255,255,0.10)",
            color: "rgba(255,255,255,0.88)",
          }}
        >
          {content}
        </div>
      </div>
    )
  }

  const confidenceLevel =
    confidence != null ? getConfidenceLevel(confidence) : null

  return (
    <div className="flex gap-3 mb-8 animate-fade-in-up">
      {/* NeoLex avatar dot */}
      <div
        className="shrink-0 mt-1 size-6 rounded-full flex items-center justify-center"
        style={{
          background: "rgba(201,168,76,0.12)",
          border: "1px solid rgba(201,168,76,0.28)",
        }}
      >
        <div className="size-1.5 rounded-full bg-[#C9A84C]" />
      </div>

      <div className="flex-1 min-w-0">
        {content ? (
          <>
            <div className="group relative">
              {/* Markdown answer */}
              <div
                className={cn(
                  "prose prose-sm max-w-none leading-relaxed",
                  "prose-p:text-white/80 prose-p:my-2",
                  "prose-headings:font-heading prose-headings:text-white/90 prose-headings:font-semibold",
                  "prose-strong:text-white/90 prose-strong:font-semibold",
                  "prose-a:text-[#C9A84C] prose-a:no-underline hover:prose-a:underline",
                  "prose-code:bg-white/8 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-white/75 prose-code:font-mono",
                  "prose-blockquote:border-l-[#C9A84C]/50 prose-blockquote:text-white/55 prose-blockquote:not-italic",
                  "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-white/75",
                  "prose-hr:border-white/10"
                )}
              >
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>

              {/* Copy button */}
              <button
                onClick={handleCopy}
                className={cn(
                  "absolute -top-1 right-0 rounded-md p-1.5 transition-all",
                  "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                )}
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: "rgba(255,255,255,0.4)",
                }}
                aria-label="Copy answer"
              >
                {copied ? (
                  <Check className="size-3 text-green-400" />
                ) : (
                  <Copy className="size-3" />
                )}
              </button>
            </div>

            {/* Sources + confidence */}
            {(sources.length > 0 || confidenceLevel) && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                {/* Confidence dot */}
                {confidenceLevel && (
                  <div className="flex items-center gap-1.5 mr-1">
                    <div
                      className="size-1.5 rounded-full"
                      style={{ backgroundColor: CONFIDENCE_COLORS[confidenceLevel] }}
                    />
                    <span
                      className="text-[11px] font-medium"
                      style={{ color: CONFIDENCE_COLORS[confidenceLevel] }}
                    >
                      {confidenceLevel.charAt(0).toUpperCase() + confidenceLevel.slice(1)} confidence
                    </span>
                  </div>
                )}

                {/* Source chips — numbered, Perplexity-style */}
                {sources.map((source, i) => {
                  const displayId =
                    source.doc_id.length > 20
                      ? `${source.doc_id.slice(0, 20)}…`
                      : source.doc_id
                  return (
                    <div
                      key={`${source.doc_id}-${i}`}
                      className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1"
                      style={{
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.08)",
                      }}
                    >
                      <span
                        className="flex items-center justify-center size-3.5 rounded text-[9px] font-bold shrink-0"
                        style={{ background: "rgba(201,168,76,0.9)", color: "#0F1623" }}
                      >
                        {i + 1}
                      </span>
                      <span
                        className="text-[11px] font-mono truncate max-w-[120px]"
                        style={{ color: "rgba(255,255,255,0.5)" }}
                        title={source.doc_id}
                      >
                        {displayId}
                      </span>
                      {source.page_numbers.length > 0 && (
                        <>
                          <span style={{ color: "rgba(255,255,255,0.2)" }}>·</span>
                          <span
                            className="text-[11px] font-mono shrink-0"
                            style={{ color: "rgba(201,168,76,0.7)" }}
                          >
                            p.{source.page_numbers.join(", ")}
                          </span>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </>
        ) : isStreaming ? (
          <StreamingStatus status={streamingStatus} />
        ) : (
          <p className="text-sm italic" style={{ color: "rgba(255,255,255,0.3)" }}>
            No response
          </p>
        )}
      </div>
    </div>
  )
}

function StreamingStatus({ status }: { status?: string | null }) {
  const label = status ?? "Thinking…"
  return (
    <div className="flex items-center gap-2" style={{ color: "rgba(255,255,255,0.4)" }}>
      <div className="flex items-center gap-1 h-5">
        <span className="size-1.5 rounded-full bg-[#C9A84C] animate-bounce [animation-delay:-0.3s]" />
        <span className="size-1.5 rounded-full bg-[#C9A84C] animate-bounce [animation-delay:-0.15s]" />
        <span className="size-1.5 rounded-full bg-[#C9A84C] animate-bounce" />
      </div>
      <span className="text-xs">{label}</span>
    </div>
  )
}
