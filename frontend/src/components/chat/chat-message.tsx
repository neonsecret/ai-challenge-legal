import { useState } from "react"
import ReactMarkdown from "react-markdown"
import { SourceCard } from "./source-card"
import { Badge } from "@/components/ui/badge"
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

const CONFIDENCE_STYLES: Record<
  ConfidenceLevel,
  { label: string; className: string }
> = {
  high: {
    label: "High",
    className:
      "border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400",
  },
  medium: {
    label: "Medium",
    className:
      "border-yellow-500/30 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
  },
  low: {
    label: "Low",
    className:
      "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400",
  },
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
          className={cn(
            "max-w-[70%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm",
            "bg-primary text-primary-foreground shadow-sm"
          )}
        >
          {content}
        </div>
      </div>
    )
  }

  const confidenceLevel =
    confidence != null ? getConfidenceLevel(confidence) : null
  const confidenceStyle = confidenceLevel
    ? CONFIDENCE_STYLES[confidenceLevel]
    : null

  return (
    <div className="flex justify-start mb-5 animate-fade-in-up">
      <div className="max-w-[80%]">
        <div
          className={cn(
            "group relative rounded-2xl rounded-tl-sm px-5 py-4 text-sm",
            "bg-card ring-1 ring-border shadow-sm"
          )}
        >
          {content ? (
            <>
              {/* Markdown-rendered answer */}
              <div className="prose prose-sm dark:prose-invert max-w-none pr-6 leading-relaxed text-foreground
                prose-headings:font-heading prose-headings:text-primary
                prose-strong:text-foreground prose-strong:font-semibold
                prose-a:text-[#C9A84C] prose-a:no-underline hover:prose-a:underline
                prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                prose-blockquote:border-l-[#C9A84C] prose-blockquote:text-muted-foreground
                prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5
              ">
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>
              {/* Copy button */}
              <button
                onClick={handleCopy}
                className={cn(
                  "absolute top-3 right-3 rounded-md p-1 transition-all",
                  "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                  "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                )}
                aria-label="Copy answer"
              >
                {copied ? (
                  <Check className="size-3.5 text-green-500" />
                ) : (
                  <Copy className="size-3.5" />
                )}
              </button>
            </>
          ) : isStreaming ? (
            <StreamingStatus status={streamingStatus} />
          ) : (
            <p className="text-muted-foreground italic">No response</p>
          )}
        </div>

        {/* Sources + confidence row */}
        {(sources.length > 0 || confidenceStyle) && !isStreaming && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {confidenceStyle && (
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0 h-5 font-medium",
                  confidenceStyle.className
                )}
              >
                {confidenceStyle.label} confidence
              </Badge>
            )}
            {sources.map((source, i) => (
              <SourceCard
                key={`${source.doc_id}-${i}`}
                doc_id={source.doc_id}
                page_numbers={source.page_numbers}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StreamingStatus({ status }: { status?: string | null }) {
  const label = status ?? "Thinking..."
  return (
    <div className="flex items-center gap-2 text-muted-foreground text-xs">
      <div className="flex items-center gap-1 h-5">
        <span className="size-1.5 rounded-full bg-[#C9A84C] animate-bounce [animation-delay:-0.3s]" />
        <span className="size-1.5 rounded-full bg-[#C9A84C] animate-bounce [animation-delay:-0.15s]" />
        <span className="size-1.5 rounded-full bg-[#C9A84C] animate-bounce" />
      </div>
      <span>{label}</span>
    </div>
  )
}
