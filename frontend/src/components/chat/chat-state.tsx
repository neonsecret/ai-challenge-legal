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
    /** Timestamp of last message activity (send/receive). Used for sidebar sort order. */
    lastMessageAt: number
    corpora: string[]
    /** True when this session was loaded from backend and messages haven't been fetched yet. */
    backendOnly?: boolean
}

const MAX_SESSIONS = 20
const SESSION_TTL_MS = 90 * 24 * 60 * 60 * 1000

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
        // Normalize: ensure corpora/lastMessageAt fields exist (backward compat)
        return all
            .filter(s => (now - (s.lastMessageAt ?? s.createdAt)) < SESSION_TTL_MS)
            .map(s => ({...s, corpora: s.corpora ?? [], lastMessageAt: s.lastMessageAt ?? s.createdAt}))
    } catch {
        return []
    }
}

function saveSessions(sessions: ChatSession[]) {
    try {
        // Don't persist backend-only stubs (empty messages) to localStorage —
        // they'll be re-fetched from the backend on next mount anyway.
        const persistable = sessions.filter(s => !s.backendOnly)
        localStorage.setItem(_userKey("neolex_chat_sessions"), JSON.stringify(persistable.slice(0, MAX_SESSIONS)))
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

/** Sort sessions by lastMessageAt descending (most recent message activity first). */
function sortSessions(sessions: ChatSession[]): ChatSession[] {
    return sessions.slice().sort((a, b) => b.lastMessageAt - a.lastMessageAt)
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
    useInternet: boolean
    setUseInternet: React.Dispatch<React.SetStateAction<boolean>>
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
    const [useInternet, setUseInternet] = useState(true)
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
    /** Mirror of currentSessionId for use in callbacks that need the latest value without re-creating closures. */
    const currentSessionIdRef = useRef<string | null>(null)
    /** Mirror of sessions for use in handleSend without adding sessions to its dependency array. */
    const sessionsRef = useRef(sessions)
    sessionsRef.current = sessions
    /** When true, the next messages change is from loading an existing session, not from new message activity. */
    const loadingSessionRef = useRef<boolean>(false)
    const {jurisdiction} = useJurisdiction()

    const stream = useQueryStream()

    // ── Mount: load from localStorage (client-only, runs once) ──
    useEffect(() => {
        let cancelled = false
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
        setSessions(sortSessions(patched))

        // Restore current session messages (not new activity — just rehydration)
        if (lastId) {
            const session = patched.find(s => s.id === lastId)
            if (session) {
                loadingSessionRef.current = true
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
                    if (cancelled) return
                    try {
                        const r = await fetch(`${API}/api/v1/conversations/${encodeURIComponent(convId)}/last-answer`, {
                            credentials: "include",
                        })
                        if (r.ok) {
                            const data = await r.json()
                            if (data?.answer) {
                                if (!cancelled) applyRecovery(convId, data.answer)
                                return
                            }
                        }
                    } catch { /* network error, keep trying */ }
                    await new Promise(r => setTimeout(r, 5000))
                }
            })()
        }

        // Merge conversations from backend — adds sessions that exist in DB but
        // not in localStorage (e.g. after logout/login or TTL expiry).
        // localStorage sessions are preferred (they have streaming state, sources, etc).
        ;(async () => {
            if (cancelled) return
            try {
                const r = await fetch(`${API}/api/v1/conversations`, {credentials: "include"})
                if (!r.ok || cancelled) return
                const data = await r.json()
                const backendConvs: Array<{id: string; title: string; last_message_at: string; message_count: number}> =
                    data?.conversations ?? []
                if (backendConvs.length === 0) return

                if (!cancelled) {
                    setSessions(prev => {
                        const localIds = new Set(prev.map(s => s.id))
                        const newFromBackend: ChatSession[] = backendConvs
                            .filter(bc => !localIds.has(bc.id))
                            .map(bc => {
                                const ts = bc.last_message_at ? new Date(bc.last_message_at).getTime() : Date.now()
                                return {
                                    id: bc.id,
                                    title: bc.title,
                                    messages: [],  // lazy-loaded when user clicks
                                    createdAt: ts,
                                    lastMessageAt: ts,
                                    corpora: [],
                                    backendOnly: true,
                                }
                            })
                        if (newFromBackend.length === 0) return prev
                        return sortSessions([...prev, ...newFromBackend]).slice(0, MAX_SESSIONS)
                    })
                }
            } catch { /* network error — not critical, localStorage sessions still work */ }
        })()

        setHydrated(true)
        return () => { cancelled = true }
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
                        const now = Date.now()
                        const session: ChatSession = {
                            id: streamSessionId,
                            title: titleFromMessages(saveable),
                            messages: saveable,
                            createdAt: existing?.createdAt ?? now,
                            lastMessageAt: now,
                            corpora: existing?.corpora ?? [],
                        }
                        return sortSessions([session, ...prev.filter(s => s.id !== streamSessionId)]).slice(0, MAX_SESSIONS)
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

    // Keep ref in sync so callbacks always read the latest value
    currentSessionIdRef.current = currentSessionId

    useEffect(() => {
        if (!hydrated) return
        if (messages.length === 0) return

        const id = currentSessionId ?? `chat-${Date.now()}`
        if (!currentSessionId) setCurrentSessionId(id)

        // Check if this messages update is from loading an existing session
        const isLoading = loadingSessionRef.current
        if (isLoading) loadingSessionRef.current = false

        setSessions(prev => {
            const existing = prev.find(s => s.id === id)
            const now = Date.now()
            // Only update lastMessageAt for genuine new message activity,
            // NOT when loading/viewing an existing session.
            const isNewActivity = !isLoading && (!existing || messages.length > existing.messages.length)
            const lastMessageAt = isNewActivity
                ? now
                : (existing?.lastMessageAt ?? existing?.createdAt ?? now)
            const session: ChatSession = {
                id,
                title: titleFromMessages(messages),
                messages,
                createdAt: existing?.createdAt ?? now,
                lastMessageAt,
                corpora: existing?.corpora ?? [],
            }
            if (existing) {
                // Update in-place, then re-sort only if lastMessageAt changed
                const updated = prev.map(s => s.id === id ? session : s)
                return isNewActivity ? sortSessions(updated) : updated
            }
            // Brand new session — insert and sort
            return sortSessions([session, ...prev]).slice(0, MAX_SESSIONS)
        })
    }, [messages, currentSessionId, hydrated])

    // ── Actions ──

    const loadSession = useCallback((id: string) => {
        if (stream.isStreaming && currentSessionId) {
            streamingMessagesRef.current = messages.slice()
        }
        loadingSessionRef.current = true
        setSessions(prev => {
            const session = prev.find(s => s.id === id)
            if (session) {
                if (session.backendOnly) {
                    // Session from backend with no local messages — fetch from server
                    setMessages([])
                    setCurrentSessionId(id)
                    if (!stream.isStreaming) {
                        activeAssistantId.current = null
                    }
                    const API = process.env.NEXT_PUBLIC_SSE_URL ?? ""
                    ;(async () => {
                        try {
                            const r = await fetch(
                                `${API}/api/v1/conversations/${encodeURIComponent(id)}/messages`,
                                {credentials: "include"},
                            )
                            if (!r.ok) return
                            const data = await r.json()
                            const msgs: Message[] = (data?.messages ?? []).map(
                                (m: {role: string; content: string; created_at: string}, i: number) => ({
                                    id: `${m.role}-loaded-${i}`,
                                    role: m.role as "user" | "assistant",
                                    content: m.content,
                                    sources: [],
                                })
                            )
                            if (msgs.length > 0) {
                                loadingSessionRef.current = true
                                setMessages(msgs)
                                setSessions(prev2 => prev2.map(s =>
                                    s.id === id ? {...s, messages: msgs, backendOnly: false} : s
                                ))
                            }
                        } catch { /* network error — session stays empty */ }
                    })()
                } else {
                    setMessages(session.messages)
                    setCurrentSessionId(id)
                    if (!stream.isStreaming) {
                        activeAssistantId.current = null
                    }
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
        // Use ref to always read the latest currentSessionId, avoiding stale closures
        if (currentSessionIdRef.current === id) newChat()
        // Fire-and-forget: tell the backend to delete persisted conversation data
        const API = process.env.NEXT_PUBLIC_SSE_URL ?? ""
        fetch(`${API}/api/v1/conversations/${encodeURIComponent(id)}`, {
            method: "DELETE",
            credentials: "include",
            headers: {"X-Requested-With": "XMLHttpRequest"},
        }).catch(() => {})
    }, [newChat])

    const handleSend = useCallback((question: string): "ok" | "blocked" => {
        const corpus = jurisdictionToCorpus(jurisdiction)
        if (!corpus) return "blocked"  // safety: at least one corpus required

        // Check corpus limit: max 2 distinct corpora per conversation
        const convId = currentSessionId ?? `chat-${Date.now()}`
        const currentSessions = sessionsRef.current
        const session = currentSessions.find(s => s.id === convId)
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
        stream.sendQuery(question, corpus, convId, laws, useInternet)
        return "ok" as const
    }, [stream.sendQuery, jurisdiction, currentSessionId, selectedLaws, useInternet])

    const currentCorpora = sessions.find(s => s.id === currentSessionId)?.corpora ?? []

    return (
        <ChatStateContext.Provider value={{
            messages, setMessages, activeAssistantId, traceRef, wasStreamingRef,
            selectedCorpus, setSelectedCorpus, selectedLaws, setSelectedLaws,
            useInternet, setUseInternet,
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
