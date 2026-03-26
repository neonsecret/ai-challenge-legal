import { useState } from "react"
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
      "border-green-500/30 bg-green-500/10 text-green-400",
  },
  medium: {
    label: "Medium",
    className:
      "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  },
  low: {
    label: "Low",
    className:
      "border-red-500/30 bg-red-500/10 text-red-400",
  },
}

export function ChatMessage({
  role,
  content,
  sources = [],
  isStreaming = false,
  confidence,
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
      <div className="flex justify-end mb-4">
        <div
          className={cn(
            "max-w-[70%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm",
            "bg-primary text-primary-foreground"
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
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%]">
        <div
          className={cn(
            "group relative rounded-2xl rounded-tl-sm px-4 py-3 text-sm",
            "bg-card ring-1 ring-foreground/10"
          )}
        >
          {content ? (
            <>
              <p className="whitespace-pre-wrap leading-relaxed pr-6">{content}</p>
              {/* Copy button */}
              <button
                onClick={handleCopy}
                className={cn(
                  "absolute top-2.5 right-2.5 rounded-md p-1 transition-all",
                  "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                  "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                )}
                aria-label="Copy answer"
              >
                {copied ? (
                  <Check className="size-3.5 text-green-400" />
                ) : (
                  <Copy className="size-3.5" />
                )}
              </button>
            </>
          ) : isStreaming ? (
            <TypingIndicator />
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

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 h-5">
      <span className="size-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
      <span className="size-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
      <span className="size-1.5 rounded-full bg-muted-foreground animate-bounce" />
    </div>
  )
}
