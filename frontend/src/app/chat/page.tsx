"use client"

import { useRef, useEffect } from "react"
import { ChatInput } from "@/components/chat/chat-input"
import { ChatMessage, type Source } from "@/components/chat/chat-message"
import { useQueryStream } from "@/components/chat/use-query-stream"
import { useState } from "react"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string | null
  sources?: Source[]
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const { answer, sources, isStreaming, error, sendQuery } = useQueryStream()
  const activeAssistantId = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const handleSend = (question: string) => {
    const userId = `user-${Date.now()}`
    const assistantId = `assistant-${Date.now()}`
    activeAssistantId.current = assistantId

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: question },
      { id: assistantId, role: "assistant", content: null, sources: [] },
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
          ? { ...m, content: answer, sources: sources ?? [] }
          : m
      )
    )
  }, [answer, sources])

  // Auto-scroll to bottom as messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
              <h2 className="text-xl font-semibold mb-2">Legal Research Assistant</h2>
              <p className="text-muted-foreground text-sm max-w-sm">
                Ask a question about your legal documents. I will retrieve the relevant
                passages and provide a cited answer.
              </p>
            </div>
          ) : (
            messages.map((m) => (
              <ChatMessage
                key={m.id}
                role={m.role}
                content={m.content}
                sources={m.sources}
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
        <div className="max-w-3xl mx-auto">
          <ChatInput onSend={handleSend} disabled={isStreaming} />
        </div>
      </div>
    </div>
  )
}
