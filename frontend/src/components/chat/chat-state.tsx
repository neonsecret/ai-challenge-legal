"use client"

import {createContext, useContext, useState, useRef, useCallback, useEffect, type ReactNode} from "react"
import {useQueryStream, type Source, type UseQueryStreamReturn} from "./use-query-stream"
import {useJurisdiction} from "@/lib/use-jurisdiction"
import {jurisdictionToCorpus} from "@/lib/jurisdictions"

export type {Source}

export interface Message {
    id: string
    role: "user" | "assistant"
    content: string | null
    sources?: Source[]
    confidence?: number | null
    trace?: string[]
}

export interface ChatSession {
    id: string
    title: string
    messages: Message[]
    createdAt: number
    corpora: string[]
}

const MAX_SESSIONS = 20
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000

/** Get user-scoped localStorage key to prevent cross-account session leaks. */
function _userKey(base: string): string {
    const uid = typeof window !== "undefined" ? localStorage.getItem("neolex_uid") : null
    return uid ? `${base}_${uid}` : base
}

function loadSessions(): ChatSession[] {
    try {
        // Clean up any legacy unscoped keys (pre user-scoping)
        localStorage.removeItem("neolex_chat_sessions")
        localStorage.removeItem("neolex_current_session")

        const raw = localStorage.getItem(_userKey("neolex_chat_sessions"))
        if (!raw) return []
        const all: ChatSession[] = JSON.parse(raw)
        const now = Date.now()
        // Normalize: ensure corpora field exists (backward compat with pre-corpora sessions)
        return all
            .filter(s => (now - s.createdAt) < SESSION_TTL_MS)
            .map(s => ({...s, corpora: s.corpora ?? []}))
    } catch {
        return []
    }
}

function saveSessions(sessions: ChatSession[]) {
    try {
        localStorage.setItem(_userKey("neolex_chat_sessions"), JSON.stringify(sessions.slice(0, MAX_SESSIONS)))
    } catch { /* ignore */ }
}

function loadCurrentSessionId(): string | null {
    return typeof window !== "undefined" ? localStorage.getItem(_userKey("neolex_current_session")) : null
}

function saveCurrentSessionId(id: string | null) {
    const key = _userKey("neolex_current_session")
    if (id) localStorage.setItem(key, id)
    else localStorage.removeItem(key)
}

function titleFromMessages(msgs: Message[]): string {
    const firstUser = msgs.find(m => m.role === "user")
    if (!firstUser?.content) return "New chat"
    const text = firstUser.content
    return text.length > 50 ? text.slice(0, 50) + "…" : text
}

interface ChatState {
    messages: Message[]
    setMessages: React.Dispatch<React.SetStateAction<Message[]>>
    activeAssistantId: React.MutableRefObject<string | null>
    traceRef: React.MutableRefObject<string[]>
    wasStreamingRef: React.MutableRefObject<boolean>
    selectedCorpus: string
    setSelectedCorpus: (c: string) => void
    selectedLaws: string[]
    setSelectedLaws: React.Dispatch<React.SetStateAction<string[]>>
    stream: UseQueryStreamReturn
    handleSend: (question: string) => "ok" | "blocked"
    sessions: ChatSession[]
    currentSessionId: string | null
    currentCorpora: string[]
    loadSession: (id: string) => void
    newChat: () => void
    deleteSession: (id: string) => void
}

const ChatStateContext = createContext<ChatState | null>(null)

export function ChatStateProvider({children}: { children: ReactNode }) {
    const [messages, setMessages] = useState<Message[]>([])
    const [selectedCorpus, setSelectedCorpus] = useState("DIFC Law")
    const [selectedLaws, setSelectedLaws] = useState<string[]>([])
    const [sessions, setSessions] = useState<ChatSession[]>([])
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
    // Hydration gate: false during SSR and first client render.
    // Sync effects skip when false, preventing them from writing initial empty state to localStorage.
    // The mount effect loads from localStorage and sets this to true, triggering a re-render
    // where sync effects see the loaded data.
    const [hydrated, setHydrated] = useState(false)
    const activeAssistantId = useRef<string | null>(null)
    const traceRef = useRef<string[]>([])
    const wasStreamingRef = useRef<boolean>(false)
    const streamingSessionIdRef = useRef<string | null>(null)
    const streamingMessagesRef = useRef<Message[]>([])
    const {jurisdiction} = useJurisdiction()

    const stream = useQueryStream()

    // ── Mount: load from localStorage (client-only, runs once) ──
    useEffect(() => {
        const loaded = loadSessions()
        const lastId = loadCurrentSessionId()
        const API = process.env.NEXT_PUBLIC_SSE_URL ?? ""

        // Mark interrupted messages across ALL sessions and recover from server
        const INTERRUPTED = "*Response was interrupted. Please ask again.*"
        const patched = loaded.map(s => {
            const hasNull = s.messages.some(m => m.role === "assistant" && m.content === null)
            if (!hasNull) return s
            return {
                ...s,
                messages: s.messages.map(m =>
                    m.role === "assistant" && m.content === null
                        ? {...m, content: INTERRUPTED}
                        : m
                ),
            }
        })
        setSessions(patched)

        // Restore current session messages
        if (lastId) {
            const session = patched.find(s => s.id === lastId)
            if (session) {
                setMessages(session.messages)
                setCurrentSessionId(lastId)
            }
        }

        // Poll to recover interrupted answers from server for ALL affected sessions.
        // Backend may still be processing (60-90s pipeline), so poll every 5s for up to 3 min.
        const interruptedIds = loaded
            .filter(s => s.messages.some(m => m.role === "assistant" && m.content === null))
            .map(s => s.id)

        const applyRecovery = (convId: string, answer: string) => {
            setSessions(prev => prev.map(s => {
                if (s.id !== convId) return s
                return {
                    ...s,
                    messages: s.messages.map(m =>
                        m.role === "assistant" && m.content === INTERRUPTED
                            ? {...m, content: answer}
                            : m
                    ),
                }
            }))
            if (convId === lastId) {
                setMessages(prev => prev.map(m =>
                    m.role === "assistant" && m.content === INTERRUPTED
                        ? {...m, content: answer}
                        : m
                ))
            }
        }

        for (const convId of interruptedIds) {
            ;(async () => {
                for (let attempt = 0; attempt < 36; attempt++) {
                    try {
                        const r = await fetch(`${API}/api/v1/conversations/${encodeURIComponent(convId)}/last-answer`, {
                            credentials: "include",
                        })
                        if (r.ok) {
                            const data = await r.json()
                            if (data?.answer) {
                                applyRecovery(convId, data.answer)
                                return
                            }
                        }
                    } catch { /* network error, keep trying */ }
                    await new Promise(r => setTimeout(r, 5000))
                }
            })()
        }

        setHydrated(true)
    }, [])

    // ── Streaming sync effects ──

    useEffect(() => {
        const id = activeAssistantId.current
        if (id === null) return
        const onStreamingSession = streamingSessionIdRef.current === currentSessionId || streamingSessionIdRef.current === null
        if (onStreamingSession) {
            setMessages((prev) => prev.map((m) =>
                m.id === id
                    ? {...m, content: stream.answer, sources: stream.sources ?? [], confidence: stream.confidence ?? null}
                    : m
            ))
        } else {
            streamingMessagesRef.current = streamingMessagesRef.current.map((m) =>
                m.id === id
                    ? {...m, content: stream.answer, sources: stream.sources ?? [], confidence: stream.confidence ?? null}
                    : m
            )
        }
    }, [stream.answer, stream.sources, stream.confidence, currentSessionId]) // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        if (stream.isStreaming && stream.streamingStatus && !traceRef.current.includes(stream.streamingStatus)) {
            traceRef.current = [...traceRef.current, stream.streamingStatus]
        }
    }, [stream.streamingStatus, stream.isStreaming]) // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        if (!stream.isStreaming && wasStreamingRef.current) {
            const id = activeAssistantId.current
            const trace = traceRef.current.slice()
            const streamSessionId = streamingSessionIdRef.current

            if (streamSessionId && streamSessionId !== currentSessionId) {
                const finalMessages = streamingMessagesRef.current.map(m =>
                    m.id === id ? {...m, trace: trace.length > 0 ? trace : m.trace} : m
                )
                const saveable = finalMessages.filter(m => m.content !== null || m.role === "user")
                if (saveable.length > 0) {
                    setSessions(prev => {
                        const existing = prev.find(s => s.id === streamSessionId)
                        const session: ChatSession = {
                            id: streamSessionId,
                            title: titleFromMessages(saveable),
                            messages: saveable,
                            createdAt: existing?.createdAt ?? Date.now(),
                            corpora: existing?.corpora ?? [],
                        }
                        return [session, ...prev.filter(s => s.id !== streamSessionId)].slice(0, MAX_SESSIONS)
                    })
                }
            } else {
                if (id && trace.length > 0) {
                    setMessages((prev) => prev.map((m) => m.id === id ? {...m, trace} : m))
                }
            }

            traceRef.current = []
            streamingSessionIdRef.current = null
            streamingMessagesRef.current = []
        }
        wasStreamingRef.current = stream.isStreaming
    }, [stream.isStreaming, currentSessionId]) // eslint-disable-line react-hooks/exhaustive-deps

    // ── Persistence effects (all gated by hydrated) ──

    useEffect(() => {
        if (!hydrated) return
        saveSessions(sessions)
    }, [sessions, hydrated])

    useEffect(() => {
        if (!hydrated) return
        saveCurrentSessionId(currentSessionId)
    }, [currentSessionId, hydrated])

    useEffect(() => {
        if (!hydrated) return
        if (messages.length === 0) return

        const id = currentSessionId ?? `chat-${Date.now()}`
        if (!currentSessionId) setCurrentSessionId(id)

        setSessions(prev => {
            const existing = prev.find(s => s.id === id)
            const session: ChatSession = {
                id,
                title: titleFromMessages(messages),
                messages,
                createdAt: existing?.createdAt ?? Date.now(),
                corpora: existing?.corpora ?? [],
            }
            return [session, ...prev.filter(s => s.id !== id)].slice(0, MAX_SESSIONS)
        })
    }, [messages, currentSessionId, hydrated])

    // ── Actions ──

    const loadSession = useCallback((id: string) => {
        if (stream.isStreaming && currentSessionId) {
            streamingMessagesRef.current = messages.slice()
        }
        setSessions(prev => {
            const session = prev.find(s => s.id === id)
            if (session) {
                setMessages(session.messages)
                setCurrentSessionId(id)
                if (!stream.isStreaming) {
                    activeAssistantId.current = null
                }
            }
            return prev
        })
    }, [stream.isStreaming, currentSessionId, messages])

    const newChat = useCallback(() => {
        setMessages([])
        setCurrentSessionId(null)
        activeAssistantId.current = null
        traceRef.current = []
    }, [])

    const deleteSession = useCallback((id: string) => {
        setSessions(prev => prev.filter(s => s.id !== id))
        if (currentSessionId === id) newChat()
    }, [currentSessionId, newChat])

    const handleSend = useCallback((question: string): "ok" | "blocked" => {
        const corpus = jurisdictionToCorpus(jurisdiction)
        if (!corpus) return "blocked"  // safety: at least one corpus required

        // Check corpus limit: max 2 distinct corpora per conversation
        const convId = currentSessionId ?? `chat-${Date.now()}`
        const session = sessions.find(s => s.id === convId)
        const existingCorpora = session?.corpora ?? []
        if (existingCorpora.length >= 2 && !existingCorpora.includes(corpus)) {
            // Blocked — max 2 corpora per conversation
            return "blocked" as const
        }

        traceRef.current = []
        const userId = `user-${Date.now()}`
        const assistantId = `assistant-${Date.now()}`
        activeAssistantId.current = assistantId

        if (!currentSessionId) setCurrentSessionId(convId)
        streamingSessionIdRef.current = convId

        // Add corpus to session if new
        if (!existingCorpora.includes(corpus)) {
            setSessions(prev => prev.map(s =>
                s.id === convId
                    ? {...s, corpora: [...(s.corpora ?? []), corpus]}
                    : s
            ))
        }

        setMessages((prev) => [
            ...prev,
            {id: userId, role: "user", content: question},
            {id: assistantId, role: "assistant", content: null, sources: [], confidence: null},
        ])
        const laws = jurisdiction === "cz" && selectedLaws.length > 0 ? selectedLaws : undefined
        stream.sendQuery(question, corpus, convId, laws)
        return "ok" as const
    }, [stream.sendQuery, jurisdiction, currentSessionId, selectedLaws, sessions])

    const currentCorpora = sessions.find(s => s.id === currentSessionId)?.corpora ?? []

    return (
        <ChatStateContext.Provider value={{
            messages, setMessages, activeAssistantId, traceRef, wasStreamingRef,
            selectedCorpus, setSelectedCorpus, selectedLaws, setSelectedLaws,
            stream, handleSend,
            sessions, currentSessionId, currentCorpora, loadSession, newChat, deleteSession,
        }}>
            {children}
        </ChatStateContext.Provider>
    )
}

export function useChatState(): ChatState {
    const ctx = useContext(ChatStateContext)
    if (!ctx) throw new Error("useChatState must be used inside ChatStateProvider")
    return ctx
}
