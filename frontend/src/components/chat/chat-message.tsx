import { SourceCard } from "./source-card"
import { cn } from "@/lib/utils"

export interface Source {
  doc_id: string
  page_numbers: number[]
}

interface ChatMessageProps {
  role: "user" | "assistant"
  content: string | null
  sources?: Source[]
  isStreaming?: boolean
}

export function ChatMessage({
  role,
  content,
  sources = [],
  isStreaming = false,
}: ChatMessageProps) {
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

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%]">
        <div
          className={cn(
            "rounded-2xl rounded-tl-sm px-4 py-3 text-sm",
            "bg-card ring-1 ring-foreground/10"
          )}
        >
          {content ? (
            <p className="whitespace-pre-wrap leading-relaxed">{content}</p>
          ) : isStreaming ? (
            <TypingIndicator />
          ) : (
            <p className="text-muted-foreground italic">No response</p>
          )}
        </div>

        {sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
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
