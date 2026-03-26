"use client"

import { useRef, useEffect } from "react"
import { ChatInput } from "@/components/chat/chat-input"
import { ChatMessage, type Source } from "@/components/chat/chat-message"
import { useQueryStream } from "@/components/chat/use-query-stream"
import { useState } from "react"
import { Scale } from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string | null
  sources?: Source[]
  confidence?: number | null
}

const DEMO_QUESTIONS = [
  "What is the limitation period under DIFC Law No. 5 of 2005?",
  "What are the grounds for terminating an employment contract under DIFC Employment Law?",
  "What fiduciary duties does a company director owe under DIFC Companies Law?",
  "How is arbitration initiated under the DIFC Arbitration Law?",
  "What are the requirements for a valid contract under DIFC Contract Law?",
]

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const { answer, sources, confidence, isStreaming, error, sendQuery } =
    useQueryStream()
  const activeAssistantId = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputFocusRef = useRef<(() => void) | null>(null)

  const handleSend = (question: string) => {
    const userId = `user-${Date.now()}`
    const assistantId = `assistant-${Date.now()}`
    activeAssistantId.current = assistantId

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: question },
      { id: assistantId, role: "assistant", content: null, sources: [], confidence: null },
    ])

    sendQuery(question)
  }

  // Sync streaming answer into the active assistant message
  useEffect(() => {
    const id = activeAssistantId.current
    if (id === null) return
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? { ...m, content: answer, sources: sources ?? [], confidence: confidence ?? null }
          : m
      )
    )
  }, [answer, sources, confidence])

  // Update browser tab title while streaming
  useEffect(() => {
    if (isStreaming) {
      const userMessages = messages.filter((m) => m.role === "user")
      const lastQ = userMessages[userMessages.length - 1]?.content
      if (lastQ) {
        const truncated = lastQ.length > 50 ? lastQ.slice(0, 50) + "\u2026" : lastQ
        document.title = truncated
        return
      }
    }
    document.title = "NeoLex \u2014 Your AI Legal Counsel"
  }, [isStreaming, messages])

  // Auto-scroll to bottom as messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Cmd+K global shortcut to focus the input
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        inputFocusRef.current?.()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {messages.length === 0 ? (
            <EmptyState onSelectQuestion={handleSend} />
          ) : (
            messages.map((m) => (
              <ChatMessage
                key={m.id}
                role={m.role}
                content={m.content}
                sources={m.sources}
                confidence={m.confidence}
                isStreaming={isStreaming && m.id === activeAssistantId.current}
              />
            ))
          )}

          {error && (
            <p className="text-destructive text-sm text-center mt-2">{error}</p>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="shrink-0 border-t border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <div className="max-w-3xl mx-auto flex flex-col gap-1.5">
          <ChatInput
            onSend={handleSend}
            disabled={isStreaming}
            onFocusRef={inputFocusRef}
          />
          <p className="text-xs text-muted-foreground/50 text-right select-none">
            Enter to send &middot; Shift+Enter for newline &middot; Cmd+K to focus
          </p>
        </div>
      </div>
    </div>
  )
}

function EmptyState({
  onSelectQuestion,
}: {
  onSelectQuestion: (q: string) => void
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-4">
      <div className="flex items-center justify-center size-14 rounded-2xl bg-[#d4af37]/10 ring-1 ring-[#d4af37]/20 mb-4">
        <Scale className="size-7 text-[#d4af37]" />
      </div>
      <h2 className="text-xl font-semibold mb-2">Legal Research Assistant</h2>
      <p className="text-muted-foreground text-sm max-w-sm mb-6">
        Ask a question about your legal documents or try one of these examples:
      </p>
      <div className="flex flex-col gap-2 w-full max-w-md">
        {DEMO_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onSelectQuestion(q)}
            className="rounded-xl border border-border bg-card px-4 py-3 text-left text-sm text-muted-foreground hover:border-[#d4af37]/40 hover:text-foreground hover:bg-muted/30 transition-all"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
