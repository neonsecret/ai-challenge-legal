"use client"

import { useRef, useEffect, useCallback, useState } from "react"
import { ChatInput } from "@/components/chat/chat-input"
import { ChatMessage, type Source } from "@/components/chat/chat-message"
import { useQueryStream } from "@/components/chat/use-query-stream"
import { EmptyState } from "@/components/chat/empty-state"
import { GroundingDrawer } from "@/components/grounding/grounding-drawer"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string | null
  sources?: Source[]
  confidence?: number | null
}

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
    window.dispatchEvent(new Event("storage"))
  } catch {
    // ignore
  }
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerData, setDrawerData] = useState<{ answer: string; sources: Source[] }>({
    answer: "",
    sources: [],
  })
  const { answer, sources, confidence, isStreaming, streamingStatus, error, sendQuery } =
    useQueryStream()
  const activeAssistantId = useRef<string | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputFocusRef = useRef<(() => void) | null>(null)

  const handleSourceClick = useCallback((answer: string, sources: Source[]) => {
    setDrawerData({ answer, sources })
    setDrawerOpen(true)
  }, [])

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

  useEffect(() => {
    if (isStreaming) {
      const userMessages = messages.filter((m) => m.role === "user")
      const lastQ = userMessages[userMessages.length - 1]?.content
      if (lastQ) {
        document.title = lastQ.length > 50 ? lastQ.slice(0, 50) + "…" : lastQ
        return
      }
    }
    document.title = "NeoLex — Your AI Legal Counsel"
  }, [isStreaming, messages])

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [messages])

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
    <div
      className="flex flex-col h-full relative overflow-clip"
      style={{ background: "linear-gradient(145deg, #dfc090 0%, #e8d4b8 45%, #dbb870 100%)" }}
    >

      {/* ── Warm amber background blobs — give backdrop-filter colour to blur ── */}
      <div aria-hidden className="pointer-events-none absolute inset-0" style={{ zIndex: 0 }}>
        {/* Warm amber top-right */}
        <div className="absolute rounded-full" style={{
          width: "580px", height: "580px",
          top: "-80px", right: "8%",
          background: "radial-gradient(circle, rgba(190,110,30,0.45) 0%, rgba(190,110,30,0.15) 45%, transparent 70%)",
        }} />
        {/* Deep sienna right */}
        <div className="absolute rounded-full" style={{
          width: "460px", height: "460px",
          top: "180px", right: "4%",
          background: "radial-gradient(circle, rgba(200,80,20,0.38) 0%, rgba(200,80,20,0.12) 45%, transparent 70%)",
        }} />
        {/* Spice gold bottom-center */}
        <div className="absolute rounded-full" style={{
          width: "380px", height: "380px",
          bottom: "30px", left: "28%",
          background: "radial-gradient(circle, rgba(175,130,20,0.35) 0%, rgba(175,130,20,0.10) 45%, transparent 70%)",
        }} />
      </div>

      {/* ── Messages ── */}
      <div ref={scrollAreaRef} className="flex-1 min-h-0 overflow-y-auto relative" style={{ zIndex: 10 }}>
        <div className="max-w-2xl mx-auto px-4 py-8 pb-4">
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
                onSourceClick={handleSourceClick}
              />
            ))
          )}

          {showFollowUps && (
            <div className="ml-10 mb-4 animate-fade-in-up">
              <div className="flex gap-2 overflow-x-auto pb-1">
                {FOLLOWUP_SUGGESTIONS.slice(0, 3).map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => handleSend(suggestion)}
                    className="shrink-0 text-xs px-3.5 py-1.5 rounded-full transition-all cursor-pointer
                               hover:border-[rgba(201,168,76,0.4)] hover:[background:rgba(201,168,76,0.08)]
                               hover:text-[#c47c00]"
                    style={{
                      background: "rgba(255,255,255,0.15)",
                      backdropFilter: "blur(12px)",
                      WebkitBackdropFilter: "blur(12px)",
                      border: "1px solid rgba(255,255,255,0.30)",
                      color: "#7a5a20",
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div
              className="text-sm text-center mt-2 mb-4 rounded-xl px-4 py-3"
              style={{
                color: "#8b3520",
                background: "rgba(139,53,32,0.10)",
                backdropFilter: "blur(12px)",
                WebkitBackdropFilter: "blur(12px)",
                border: "1px solid rgba(139,53,32,0.22)",
              }}
            >
              {error}
            </div>
          )}
        </div>
      </div>

      {/* ── Input bar — warm glass over the amber background ── */}
      <div
        className="relative shrink-0 px-4 py-4"
        style={{
          background: "rgba(255,240,215,0.30)",
          backdropFilter: "blur(32px) saturate(140%)",
          WebkitBackdropFilter: "blur(32px) saturate(140%)",
          borderTop: "1px solid rgba(255,255,255,0.50)",
          zIndex: 30,
        }}
      >
        <div className="max-w-2xl mx-auto">
          <ChatInput onSend={handleSend} disabled={isStreaming} onFocusRef={inputFocusRef} />
        </div>
      </div>

      {/* ── Grounding drawer ── */}
      <GroundingDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        answer={drawerData.answer}
        sources={drawerData.sources}
      />
    </div>
  )
}
