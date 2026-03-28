"use client"

import { useRef, useEffect, useCallback, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "motion/react"
import { SquarePen } from "lucide-react"
import { useTheme } from "next-themes"
import { ChatInput } from "@/components/chat/chat-input"
import { ChatMessage, type Source } from "@/components/chat/chat-message"
import { useQueryStream } from "@/components/chat/use-query-stream"
import { EmptyState, EMPTY_STATE_QUESTIONS } from "@/components/chat/empty-state"
import { GroundingDrawer } from "@/components/grounding/grounding-drawer"
import { FakePdf } from "@/components/landing/fake-pdf"
import type { DemoScenario } from "@/components/landing/demo-panel"
import { X } from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string | null
  sources?: Source[]
  confidence?: number | null
  trace?: string[]
}

const FOLLOWUP_SUGGESTIONS = [
  "Can you cite the specific article?",
  "What are the exceptions to this rule?",
  "How does this compare to English law?",
  "What is the enforcement mechanism?",
]

const RECENT_QUERIES_KEY = "neolex_recent_queries"
const MAX_RECENT = 5

// Scenarios for the side-panel document viewer, keyed to EMPTY_STATE_QUESTIONS order
const PREVIEW_SCENARIOS: DemoScenario[] = [
  {
    jurisdiction: "DIFC",
    question: EMPTY_STATE_QUESTIONS[0].full,
    answer: "",
    pdfTitle: "DIFC Limitation Law No. 5 of 2005",
    pdfArticleHeader: "Article 4 — General Limitation Period",
    pdfClauses: [
      { id: "4(1)", text: "An action founded on contract shall not be brought after the end of six years beginning with the date on which the cause of action accrued." },
      { id: "4(2)", text: "An action in tort shall not be brought after three years beginning with the date on which the claimant first had knowledge of all relevant facts." },
      { id: "4(3)", text: "Knowledge includes facts which a claimant might reasonably be expected to acquire from observable facts or from expert advice." },
    ],
    highlightRange: [0, 1],
    sourceBadge: "DIFC Law No. 5 of 2005 · Art. 4 · p.12",
    pageBadge: "Page 12",
  },
  {
    jurisdiction: "DIFC",
    question: EMPTY_STATE_QUESTIONS[1].full,
    answer: "",
    pdfTitle: "DIFC Employment Law No. 2 of 2019",
    pdfArticleHeader: "Article 59 — Termination by Employer",
    pdfClauses: [
      { id: "59(1)", text: "An employer may terminate without notice where the employee has committed a fundamental breach of the employment contract." },
      { id: "59(2)", text: "An employer may terminate for cause by providing written notice of not less than the minimum notice period, setting out the grounds." },
      { id: "59(3)", text: "Termination shall not be on grounds related to pregnancy, maternity leave, or the exercise of any statutory right." },
    ],
    highlightRange: [0, 1],
    sourceBadge: "DIFC Employment Law · Art. 59 · p.31",
    pageBadge: "Page 31",
  },
]

function makeGlassPanel(isDark: boolean) {
  return isDark ? {
    background: "rgba(255,255,255,0.06)",
    backdropFilter: "blur(48px) saturate(180%) brightness(108%)",
    WebkitBackdropFilter: "blur(48px) saturate(180%) brightness(108%)",
    border: "0.5px solid rgba(255,255,255,0.12)",
    borderRadius: "24px",
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.10), 0 20px 60px rgba(0,0,0,0.40)",
  } : {
    background: "rgba(255,250,235,0.14)",
    backdropFilter: "blur(48px) saturate(180%) brightness(106%)",
    WebkitBackdropFilter: "blur(48px) saturate(180%) brightness(106%)",
    border: "0.5px solid rgba(255,255,255,0.32)",
    borderRadius: "24px",
    boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), inset 1px 0 0 rgba(255,255,255,0.35), 0 16px 48px rgba(100,50,0,0.14)",
  };
}

function saveRecentQuery(question: string) {
  try {
    const stored = localStorage.getItem(RECENT_QUERIES_KEY)
    const existing: string[] = stored ? JSON.parse(stored) : []
    const updated = [question, ...existing.filter((q) => q !== question)].slice(0, MAX_RECENT)
    localStorage.setItem(RECENT_QUERIES_KEY, JSON.stringify(updated))
    window.dispatchEvent(new Event("storage"))
  } catch { /* ignore */ }
}

export default function ChatPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([])
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerData, setDrawerData] = useState<{ answer: string; sources: Source[] }>({ answer: "", sources: [] })
  const [previewIndex, setPreviewIndex] = useState<number | null>(null)
  const [recentQueries, setRecentQueries] = useState<string[]>([])
  const [selectedCorpus, setSelectedCorpus] = useState("DIFC Law")
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const isDark = mounted && resolvedTheme === "dark"

  // Fix 1: redirect to landing if no API key on mount
  useEffect(() => {
    const key = localStorage.getItem("neolex_api_key")
    if (!key || key.trim() === "") {
      router.replace("/")
    }
  }, [router])

  useEffect(() => {
    const load = () => {
      try {
        const stored = localStorage.getItem(RECENT_QUERIES_KEY)
        if (stored) setRecentQueries(JSON.parse(stored).slice(0, MAX_RECENT))
      } catch { /* ignore */ }
    }
    load()
    window.addEventListener("storage", load)
    return () => window.removeEventListener("storage", load)
  }, [])

  const { answer, sources, confidence, isStreaming, streamingStatus, error, sendQuery, clearError } = useQueryStream()
  const activeAssistantId = useRef<string | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputFocusRef = useRef<(() => void) | null>(null)
  const traceRef = useRef<string[]>([])
  const wasStreamingRef = useRef(false)

  const handleSourceClick = useCallback((answer: string, sources: Source[]) => {
    setDrawerData({ answer, sources })
    setDrawerOpen(true)
  }, [])

  const handleSend = useCallback((question: string) => {
    setPreviewIndex(null)
    traceRef.current = []
    const userId = `user-${Date.now()}`
    const assistantId = `assistant-${Date.now()}`
    activeAssistantId.current = assistantId
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: question },
      { id: assistantId, role: "assistant", content: null, sources: [], confidence: null },
    ])
    saveRecentQuery(question)
    sendQuery(question, selectedCorpus)
  }, [sendQuery, selectedCorpus])

  useEffect(() => {
    const id = activeAssistantId.current
    if (id === null) return
    setMessages((prev) => prev.map((m) =>
      m.id === id ? { ...m, content: answer, sources: sources ?? [], confidence: confidence ?? null } : m
    ))
  }, [answer, sources, confidence])

  // Collect unique status messages into trace log during streaming
  useEffect(() => {
    if (isStreaming && streamingStatus && !traceRef.current.includes(streamingStatus)) {
      traceRef.current = [...traceRef.current, streamingStatus]
    }
  }, [streamingStatus, isStreaming])

  // When streaming completes, attach collected trace to the active message
  useEffect(() => {
    if (!isStreaming && wasStreamingRef.current) {
      const id = activeAssistantId.current
      const trace = traceRef.current.slice()
      if (id && trace.length > 0) {
        setMessages((prev) => prev.map((m) => m.id === id ? { ...m, trace } : m))
      }
      traceRef.current = []
    }
    wasStreamingRef.current = isStreaming
  }, [isStreaming])

  useEffect(() => {
    if (isStreaming) {
      const lastQ = messages.filter(m => m.role === "user").at(-1)?.content
      if (lastQ) { document.title = lastQ.length > 50 ? lastQ.slice(0, 50) + "…" : lastQ; return }
    }
    document.title = "Vitreon Legal — Your AI Legal Counsel"
  }, [isStreaming, messages])

  useEffect(() => {
    if (scrollAreaRef.current) scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); inputFocusRef.current?.() }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  const showPreview = messages.length === 0 && previewIndex !== null
  const lastAssistant = messages.at(-1)
  const showFollowUps = !isStreaming && lastAssistant?.role === "assistant" && lastAssistant.content

  return (
    <div className="p-2 sm:p-4" style={{
      height: "100%",
      display: "flex",
      alignItems: "stretch",
      gap: "8px",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* Ambient blobs — subtler in light, dark blue in dark */}
      <div aria-hidden style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none", overflow: "hidden" }}>
        {isDark ? (
          <>
            <div style={{ position: "absolute", width: 580, height: 580, top: "-10%", left: "5%",
              background: "radial-gradient(circle, rgba(27,43,75,0.70) 0%, rgba(27,43,75,0.22) 45%, transparent 70%)" }} />
            <div style={{ position: "absolute", width: 460, height: 460, top: "20%", right: "2%",
              background: "radial-gradient(circle, rgba(15,60,150,0.50) 0%, rgba(15,60,150,0.15) 45%, transparent 70%)" }} />
            <div style={{ position: "absolute", width: 380, height: 380, bottom: "5%", left: "22%",
              background: "radial-gradient(circle, rgba(40,30,100,0.45) 0%, rgba(40,30,100,0.12) 45%, transparent 70%)" }} />
          </>
        ) : (
          <>
            <div style={{ position: "absolute", width: 580, height: 580, top: "-10%", left: "5%",
              background: "radial-gradient(circle, rgba(190,110,30,0.30) 0%, rgba(190,110,30,0.08) 45%, transparent 70%)" }} />
            <div style={{ position: "absolute", width: 460, height: 460, top: "20%", right: "2%",
              background: "radial-gradient(circle, rgba(200,80,20,0.24) 0%, rgba(200,80,20,0.06) 45%, transparent 70%)" }} />
            <div style={{ position: "absolute", width: 380, height: 380, bottom: "5%", left: "22%",
              background: "radial-gradient(circle, rgba(175,130,20,0.22) 0%, rgba(175,130,20,0.05) 45%, transparent 70%)" }} />
          </>
        )}
      </div>

      {/* ── Chat panel ── */}
      <div className="animate-glass-in" style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        minWidth: 0,
        position: "relative",
        zIndex: 1,
        overflow: "clip",
        ...makeGlassPanel(isDark),
      }}>
        {/* Header */}
        <div style={{
          padding: "14px 22px",
          borderBottom: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.30)",
          display: "flex", alignItems: "center", gap: "10px", flexShrink: 0,
          background: isDark ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.06)",
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: 9,
            background: isDark ? "rgba(201,168,76,0.14)" : "rgba(196,124,0,0.18)",
            border: isDark ? "0.5px solid rgba(201,168,76,0.28)" : "0.5px solid rgba(196,124,0,0.38)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.65)",
          }}>
            <span style={{ fontSize: "15px", fontWeight: 700, color: "#7a4a00", lineHeight: 1,
              fontFamily: "Georgia, serif" }}>N</span>
          </div>
          <span style={{ fontWeight: 700, fontSize: "15px", color: isDark ? "rgba(255,255,255,0.90)" : "#1a0e04",
            fontFamily: "Georgia, 'Times New Roman', serif", letterSpacing: "-0.04em" }}>
            Vitreon Legal
          </span>
          {/* Corpus selector pills */}
          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 3, marginLeft: 12 }}>
            {(["DIFC Law", "EU Law", "UK Law", "All Jurisdictions"] as const).map((corpus) => {
              const isActive = selectedCorpus === corpus
              const isDisabled = corpus !== "DIFC Law"
              return (
                <button
                  key={corpus}
                  disabled={isDisabled}
                  onClick={() => !isDisabled && setSelectedCorpus(corpus)}
                  title={isDisabled ? "Coming soon" : corpus}
                  style={{
                    fontSize: 10, fontWeight: isActive ? 700 : 500,
                    padding: "3px 8px", borderRadius: 6,
                    cursor: isDisabled ? "not-allowed" : "pointer",
                    opacity: isDisabled ? 0.38 : 1,
                    background: isActive
                      ? isDark ? "rgba(201,168,76,0.22)" : "rgba(196,124,0,0.16)"
                      : isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)",
                    border: isActive
                      ? isDark ? "0.5px solid rgba(201,168,76,0.42)" : "0.5px solid rgba(196,124,0,0.36)"
                      : isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.32)",
                    color: isActive
                      ? isDark ? "rgba(201,168,76,0.90)" : "#7a4a00"
                      : isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    transition: "all 0.12s",
                    whiteSpace: "nowrap",
                  }}
                >
                  {corpus === "DIFC Law" ? "DIFC" : corpus === "EU Law" ? "EU" : corpus === "UK Law" ? "UK" : "All"}
                </button>
              )
            })}
          </div>
          {/* New chat button — only when there are messages */}
          {messages.length > 0 && (
            <button
              onClick={() => { setMessages([]); setPreviewIndex(null) }}
              title="New chat"
              style={{
                display: "flex", alignItems: "center", gap: 5,
                padding: "5px 10px", borderRadius: 9, fontSize: 12, fontWeight: 500,
                background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.18)",
                border: isDark ? "0.5px solid rgba(255,255,255,0.14)" : "0.5px solid rgba(255,255,255,0.42)",
                color: isDark ? "rgba(255,255,255,0.52)" : "rgba(46,31,8,0.55)",
                cursor: "pointer", transition: "all 0.12s",
                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.14)" : "rgba(255,255,255,0.28)"; e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.80)" : "rgba(46,31,8,0.80)" }}
              onMouseLeave={e => { e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.18)"; e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.52)" : "rgba(46,31,8,0.55)" }}
            >
              <SquarePen size={12} strokeWidth={1.8} />
              New
            </button>
          )}
        </div>

        {/* Messages */}
        <div ref={scrollAreaRef} style={{ flex: 1, overflowY: "auto", padding: "22px 24px", minHeight: 0 }}>
          {messages.length === 0 ? (
            <>
              <EmptyState
                onSelectQuestion={handleSend}
                onPreviewQuestion={setPreviewIndex}
                previewIndex={previewIndex}
                isDark={isDark}
              />
              {/* Recent queries */}
              {recentQueries.length > 0 && (
                <div style={{ maxWidth: 520, margin: "0 auto", padding: "0 4px 16px" }}>
                  <p style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.10em", color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.50)", marginBottom: 6 }}>Recent</p>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {recentQueries.map((q, i) => (
                      <button key={i} onClick={() => handleSend(q)} title={q} style={{
                        textAlign: "left", padding: "8px 12px", borderRadius: 10,
                        fontSize: 13, color: isDark ? "rgba(255,255,255,0.82)" : "rgba(46,31,8,0.80)",
                        background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.22)",
                        border: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.40)",
                        cursor: "pointer", transition: "all 0.12s",
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                      }}
                        onMouseEnter={e => { e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.36)"; e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.95)" : "rgba(46,31,8,0.92)" }}
                        onMouseLeave={e => { e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.22)"; e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.82)" : "rgba(46,31,8,0.80)" }}
                      >{q}</button>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            messages.map((m) => (
              <ChatMessage
                key={m.id}
                role={m.role}
                content={m.content}
                sources={m.sources}
                confidence={m.confidence}
                isStreaming={isStreaming && m.id === activeAssistantId.current}
                streamingStatus={isStreaming && m.id === activeAssistantId.current ? streamingStatus : null}
                trace={m.trace}
                onSourceClick={handleSourceClick}
                isDark={isDark}
              />
            ))
          )}

          {showFollowUps && (
            <div className="mb-4 animate-fade-in-up">
              <div style={{ display: "flex", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
                {FOLLOWUP_SUGGESTIONS.slice(0, 3).map((suggestion) => (
                  <button key={suggestion} onClick={() => handleSend(suggestion)} style={{
                    flexShrink: 0, fontSize: "11px", padding: "6px 14px",
                    borderRadius: "9999px", cursor: "pointer",
                    background: "rgba(255,255,255,0.22)",
                    border: "1px solid rgba(255,255,255,0.50)",
                    color: "#7a5a20", transition: "all 0.15s ease",
                  }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(233,196,106,0.22)"; e.currentTarget.style.color = "#c47c00" }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.22)"; e.currentTarget.style.color = "#7a5a20" }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div style={{ fontSize: "13px", textAlign: "center", marginTop: "8px", marginBottom: "16px",
              borderRadius: "12px", padding: "12px 16px",
              color: isDark ? "#ff8c7a" : "#8b3520",
              background: isDark ? "rgba(255,100,80,0.10)" : "rgba(139,53,32,0.10)",
              border: isDark ? "1px solid rgba(255,100,80,0.22)" : "1px solid rgba(139,53,32,0.22)",
              display: "flex", alignItems: "center", justifyContent: "center", gap: "12px",
              flexWrap: "wrap",
            }}>
              <span>{error}</span>
              <button
                onClick={() => {
                  localStorage.removeItem("neolex_api_key")
                  clearError()
                  router.replace("/")
                }}
                style={{
                  fontSize: "12px", fontWeight: 600, padding: "5px 12px",
                  borderRadius: "8px", cursor: "pointer",
                  background: isDark ? "rgba(255,100,80,0.20)" : "rgba(139,53,32,0.14)",
                  border: isDark ? "1px solid rgba(255,100,80,0.40)" : "1px solid rgba(139,53,32,0.35)",
                  color: isDark ? "#ff8c7a" : "#8b3520",
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                }}
              >
                Re-enter API key
              </button>
            </div>
          )}
        </div>

        {/* Input */}
        <div style={{ padding: "12px 22px 16px", borderTop: "0.5px solid rgba(255,255,255,0.28)",
          flexShrink: 0, background: "rgba(255,255,255,0.04)" }}>
          <ChatInput onSend={handleSend} disabled={isStreaming} onFocusRef={inputFocusRef} />
        </div>
      </div>

      {/* ── Document preview panel — same flex:1, slides in alongside chat ── */}
      <AnimatePresence>
        {showPreview && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              minWidth: 0,
              position: "relative",
              zIndex: 1,
              overflow: "clip",
              ...makeGlassPanel(isDark),
            }}
          >
            {/* Panel header */}
            <div style={{
              padding: "14px 22px",
              borderBottom: "0.5px solid rgba(255,255,255,0.30)",
              display: "flex", alignItems: "center", justifyContent: "space-between",
              flexShrink: 0, background: "rgba(255,255,255,0.06)",
            }}>
              <span style={{ fontSize: "12px", fontWeight: 600,
                color: isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.55)",
                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                textTransform: "uppercase", letterSpacing: "0.10em" }}>
                Source Document
              </span>
              <button
                onClick={() => setPreviewIndex(null)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 4,
                  color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.40)", borderRadius: 6, display: "flex" }}
              >
                <X size={14} strokeWidth={2} />
              </button>
            </div>

            {/* FakePdf fills remaining height */}
            <div style={{ flex: 1, padding: "16px", minHeight: 0, overflow: "hidden" }}>
              <div style={{ height: "100%", position: "relative" }}>
                <FakePdf
                  scenario={PREVIEW_SCENARIOS[previewIndex!]}
                  showHighlights={true}
                />
              </div>
            </div>

            {/* Ask button */}
            <div style={{ padding: "12px 20px 16px", borderTop: "0.5px solid rgba(255,255,255,0.28)",
              flexShrink: 0, background: "rgba(255,255,255,0.04)" }}>
              <button
                onClick={() => handleSend(EMPTY_STATE_QUESTIONS[previewIndex!].full)}
                style={{
                  width: "100%", padding: "11px", borderRadius: 14,
                  background: "#5c2e08", color: "#fff8ee",
                  border: "none", cursor: "pointer",
                  fontSize: "13px", fontWeight: 600,
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                  boxShadow: "0 2px 12px rgba(92,46,8,0.30)",
                  transition: "opacity 0.14s",
                }}
                onMouseEnter={e => (e.currentTarget.style.opacity = "0.88")}
                onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
              >
                Ask this question →
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <GroundingDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        answer={drawerData.answer}
        sources={drawerData.sources}
      />
    </div>
  )
}
