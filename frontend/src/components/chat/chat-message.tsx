import { useState } from "react"
import ReactMarkdown from "react-markdown"
import { cn } from "@/lib/utils"
import { Copy, Check, ShieldCheck, AlertTriangle, AlertCircle } from "lucide-react"

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
  onSourceClick?: (answer: string, sources: Source[]) => void
}

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
    color: "rgba(74,222,128,0.85)",
    bg: "rgba(74,222,128,0.08)",
    border: "rgba(74,222,128,0.2)",
    Icon: ShieldCheck,
    label: "High confidence",
  },
  medium: {
    color: "rgba(250,204,21,0.85)",
    bg: "rgba(250,204,21,0.08)",
    border: "rgba(250,204,21,0.2)",
    Icon: AlertTriangle,
    label: "Medium confidence",
  },
  low: {
    color: "rgba(248,113,113,0.85)",
    bg: "rgba(248,113,113,0.08)",
    border: "rgba(248,113,113,0.2)",
    Icon: AlertCircle,
    label: "Low confidence",
  },
}

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

  if (role === "user") {
    return (
      <div className="flex justify-end mb-6 animate-fade-in-up">
        <div
          className="max-w-[75%] rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed"
          style={{
            background: "linear-gradient(135deg, rgba(201,168,76,0.15) 0%, rgba(201,168,76,0.08) 100%)",
            border: "1px solid rgba(201,168,76,0.25)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            color: "rgba(255,255,255,0.90)",
          }}
        >
          {content}
        </div>
      </div>
    )
  }

  const confidenceLevel = confidence != null ? getConfidenceLevel(confidence) : null
  const conf = confidenceLevel ? CONFIDENCE_CONFIG[confidenceLevel] : null

  return (
    <div className="flex gap-3 mb-8 animate-fade-in-up">
      {/* NeoLex shield avatar */}
      <div
        className="shrink-0 mt-0.5 size-7 rounded-xl flex items-center justify-center"
        style={{
          background: "rgba(201,168,76,0.10)",
          border: "1px solid rgba(201,168,76,0.25)",
          boxShadow: "0 2px 8px rgba(201,168,76,0.1)",
        }}
      >
        <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
          <path
            d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
            stroke="#C9A84C"
            strokeWidth="1.3"
            strokeLinejoin="round"
            fill="rgba(201,168,76,0.15)"
          />
        </svg>
      </div>

      <div className="flex-1 min-w-0">
        {content ? (
          <>
            <div className="group relative">
              <div
                className={cn(
                  "prose prose-sm max-w-none leading-relaxed",
                  "prose-p:text-white/80 prose-p:my-2",
                  "prose-headings:font-heading prose-headings:text-white/90 prose-headings:font-semibold",
                  "prose-strong:text-white/90 prose-strong:font-semibold",
                  "prose-a:text-[#C9A84C] prose-a:no-underline hover:prose-a:underline",
                  "prose-code:bg-white/[0.08] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:text-white/75 prose-code:font-mono",
                  "prose-blockquote:border-l-[#C9A84C]/50 prose-blockquote:text-white/55 prose-blockquote:not-italic",
                  "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-white/75",
                  "prose-hr:border-white/10"
                )}
              >
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>

              <button
                onClick={handleCopy}
                className={cn(
                  "absolute -top-1 right-0 rounded-lg p-1.5 transition-all",
                  "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                )}
                style={{
                  background: "rgba(255,255,255,0.07)",
                  border: "1px solid rgba(255,255,255,0.10)",
                  backdropFilter: "blur(8px)",
                  WebkitBackdropFilter: "blur(8px)",
                  color: copied ? "rgba(74,222,128,0.9)" : "rgba(255,255,255,0.45)",
                }}
                aria-label="Copy answer"
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              </button>
            </div>

            {(sources.length > 0 || conf) && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {conf && (
                  <div
                    className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium shrink-0"
                    style={{
                      background: conf.bg,
                      border: `1px solid ${conf.border}`,
                      color: conf.color,
                    }}
                  >
                    <conf.Icon className="size-3" />
                    {conf.label}
                  </div>
                )}

                {sources.map((source, i) => {
                  const displayId =
                    source.doc_id.length > 22
                      ? `${source.doc_id.slice(0, 22)}…`
                      : source.doc_id
                  return (
                    <div
                      key={`${source.doc_id}-${i}`}
                      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5"
                      style={{
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.09)",
                        backdropFilter: "blur(8px)",
                        WebkitBackdropFilter: "blur(8px)",
                      }}
                      title={`${source.doc_id}${source.page_numbers.length > 0 ? ` · p.${source.page_numbers.join(", ")}` : ""}`}
                    >
                      <span
                        className="flex items-center justify-center size-4 rounded text-[9px] font-bold shrink-0"
                        style={{ background: "rgba(201,168,76,0.85)", color: "#0F1623" }}
                      >
                        {i + 1}
                      </span>
                      <span
                        className="text-[11px] font-mono truncate max-w-[140px]"
                        style={{ color: "rgba(255,255,255,0.55)" }}
                      >
                        {displayId}
                      </span>
                      {source.page_numbers.length > 0 && (
                        <>
                          <span style={{ color: "rgba(255,255,255,0.2)" }}>·</span>
                          <span
                            className="text-[11px] font-mono shrink-0"
                            style={{ color: "rgba(201,168,76,0.75)" }}
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
    <div
      className="inline-flex items-center gap-2.5 rounded-xl px-3.5 py-2.5"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 rounded-full bg-[#C9A84C] animate-bounce"
            style={{ animationDelay: `${i * 0.15}s`, animationDuration: "0.8s" }}
          />
        ))}
      </div>
      <span className="text-xs" style={{ color: "rgba(255,255,255,0.45)" }}>
        {label}
      </span>
    </div>
  )
}
