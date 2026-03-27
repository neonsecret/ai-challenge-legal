"use client"

import { useRef, useEffect, useCallback } from "react"
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
]

const FOLLOWUP_SUGGESTIONS = [
  "Can you cite the specific article?",
  "What are the exceptions to this rule?",
  "How does this compare to English law?",
  "What is the enforcement mechanism?",
]

const RECENT_QUERIES_KEY = "neolex_recent_queries"
const MAX_RECENT = 5

function saveRecentQuery(question: string) {
  try {
    const stored = localStorage.getItem(RECENT_QUERIES_KEY)
    const existing: string[] = stored ? JSON.parse(stored) : []
    const updated = [question, ...existing.filter((q) => q !== question)].slice(0, MAX_RECENT)
    localStorage.setItem(RECENT_QUERIES_KEY, JSON.stringify(updated))
  } catch {
    // ignore
  }
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const { answer, sources, confidence, isStreaming, streamingStatus, error, sendQuery } =
    useQueryStream()
  const activeAssistantId = useRef<string | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputFocusRef = useRef<(() => void) | null>(null)

  const handleSend = useCallback(
    (question: string) => {
      const userId = `user-${Date.now()}`
      const assistantId = `assistant-${Date.now()}`
      activeAssistantId.current = assistantId

      setMessages((prev) => [
        ...prev,
        { id: userId, role: "user", content: question },
        { id: assistantId, role: "assistant", content: null, sources: [], confidence: null },
      ])

      saveRecentQuery(question)
      sendQuery(question)
    },
    [sendQuery]
  )

  // Sync streaming answer into active assistant message
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
        document.title = lastQ.length > 50 ? lastQ.slice(0, 50) + "…" : lastQ
        return
      }
    }
    document.title = "NeoLex \u2014 Your AI Legal Counsel"
  }, [isStreaming, messages])

  // Auto-scroll to bottom (scoped to scroll container)
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [messages])

  // Cmd+K global shortcut
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

  const lastAssistant = messages[messages.length - 1]
  const showFollowUps =
    !isStreaming && lastAssistant?.role === "assistant" && lastAssistant.content

  return (
    <div className="flex flex-col h-full" style={{ background: "oklch(0.12 0.03 240)" }}>
      {/* Messages area */}
      <div ref={scrollAreaRef} className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-8">
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
                streamingStatus={
                  isStreaming && m.id === activeAssistantId.current ? streamingStatus : null
                }
              />
            ))
          )}

          {/* Follow-up suggestions */}
          {showFollowUps && (
            <div className="ml-9 mb-6 animate-fade-in-up">
              <div className="flex flex-wrap gap-2">
                {FOLLOWUP_SUGGESTIONS.slice(0, 3).map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => handleSend(suggestion)}
                    className="text-xs px-3 py-1.5 rounded-full transition-all"
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      color: "rgba(255,255,255,0.45)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.border = "1px solid rgba(201,168,76,0.35)"
                      e.currentTarget.style.color = "#C9A84C"
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.border = "1px solid rgba(255,255,255,0.08)"
                      e.currentTarget.style.color = "rgba(255,255,255,0.45)"
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && (
            <p className="text-sm text-center mt-2" style={{ color: "rgba(248,113,113,0.8)" }}>
              {error}
            </p>
          )}
        </div>
      </div>

      {/* Input bar */}
      <div
        className="shrink-0 px-4 py-4"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="max-w-3xl mx-auto flex flex-col gap-2">
          <ChatInput onSend={handleSend} disabled={isStreaming} onFocusRef={inputFocusRef} />
          <p
            className="text-[11px] text-center select-none"
            style={{ color: "rgba(255,255,255,0.15)" }}
          >
            Enter to send · Shift+Enter for newline · ⌘K to focus
          </p>
        </div>
      </div>
    </div>
  )
}

function EmptyState({ onSelectQuestion }: { onSelectQuestion: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div
        className="flex items-center justify-center size-16 rounded-2xl mb-6"
        style={{
          background: "rgba(201,168,76,0.10)",
          border: "1px solid rgba(201,168,76,0.22)",
          boxShadow: "0 0 40px rgba(201,168,76,0.08)",
        }}
      >
        <Scale className="size-8" style={{ color: "#C9A84C" }} />
      </div>

      <h2
        className="font-heading text-2xl font-bold mb-2"
        style={{ color: "rgba(255,255,255,0.92)" }}
      >
        What can I help you research?
      </h2>
      <p className="text-sm mb-10" style={{ color: "rgba(255,255,255,0.32)" }}>
        Ask about any legal document, clause, or jurisdiction
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-2xl">
        {DEMO_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onSelectQuestion(q)}
            className="text-left rounded-xl px-4 py-3 text-sm transition-all"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.07)",
              color: "rgba(255,255,255,0.55)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.border = "1px solid rgba(201,168,76,0.3)"
              e.currentTarget.style.background = "rgba(201,168,76,0.06)"
              e.currentTarget.style.color = "rgba(255,255,255,0.8)"
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.border = "1px solid rgba(255,255,255,0.07)"
              e.currentTarget.style.background = "rgba(255,255,255,0.04)"
              e.currentTarget.style.color = "rgba(255,255,255,0.55)"
            }}
          >
            <span className="line-clamp-2 leading-relaxed">{q}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
