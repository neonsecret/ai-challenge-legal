"use client"

import {createContext, useContext, useState, useRef, useCallback, useEffect, type ReactNode} from "react"
import {useQueryStream, type Source, type UseQueryStreamReturn} from "./use-query-stream"
import {useJurisdiction} from "@/lib/use-jurisdiction"
import {jurisdictionToCorpus} from "@/lib/jurisdictions"

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
}

const SESSIONS_KEY = "neolex_chat_sessions"
const MAX_SESSIONS = 20
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000 // 7 days — matches cookie expiry

function loadSessions(): ChatSession[] {
    try {
        const raw = localStorage.getItem(SESSIONS_KEY)
        if (!raw) return []
        const all: ChatSession[] = JSON.parse(raw)
        // Prune expired sessions
        const now = Date.now()
        return all.filter(s => (now - s.createdAt) < SESSION_TTL_MS)
    } catch {
        return []
    }
}

function saveSessions(sessions: ChatSession[]) {
    try {
        localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)))
    } catch { /* ignore */
    }
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
    stream: UseQueryStreamReturn
    handleSend: (question: string) => void
    // Session management
    sessions: ChatSession[]
    currentSessionId: string | null
    loadSession: (id: string) => void
    newChat: () => void
    deleteSession: (id: string) => void
}

const ChatStateContext = createContext<ChatState | null>(null)

export function ChatStateProvider({children}: { children: ReactNode }) {
    const [messages, setMessages] = useState<Message[]>([])
    const [selectedCorpus, setSelectedCorpus] = useState("DIFC Law")
    const [sessions, setSessions] = useState<ChatSession[]>([])
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
    const activeAssistantId = useRef<string | null>(null)
    const traceRef = useRef<string[]>([])
    const wasStreamingRef = useRef<boolean>(false)
    const {jurisdiction} = useJurisdiction()

    const stream = useQueryStream()

    // Load sessions from localStorage on mount
    useEffect(() => {
        setSessions(loadSessions())
    }, [])

    // Auto-save current session when messages change (debounced)
    useEffect(() => {
        if (messages.length === 0) return
        // Only save messages that have content (skip empty streaming placeholders)
        const saveable = messages.filter(m => m.content !== null || m.role === "user")
        if (saveable.length === 0) return

        const id = currentSessionId ?? `chat-${Date.now()}`
        if (!currentSessionId) setCurrentSessionId(id)

        setSessions(prev => {
            const existing = prev.find(s => s.id === id)
            const session: ChatSession = {
                id,
                title: titleFromMessages(saveable),
                messages: saveable,
                createdAt: existing?.createdAt ?? Date.now(),
            }
            const updated = [session, ...prev.filter(s => s.id !== id)].slice(0, MAX_SESSIONS)
            saveSessions(updated)
            return updated
        })
    }, [messages, currentSessionId])

    const loadSession = useCallback((id: string) => {
        const session = loadSessions().find(s => s.id === id)
        if (!session) return
        setMessages(session.messages)
        setCurrentSessionId(id)
        activeAssistantId.current = null
    }, [])

    const newChat = useCallback(() => {
        setMessages([])
        setCurrentSessionId(null)
        activeAssistantId.current = null
        traceRef.current = []
    }, [])

    const deleteSession = useCallback((id: string) => {
        setSessions(prev => {
            const updated = prev.filter(s => s.id !== id)
            saveSessions(updated)
            return updated
        })
        if (currentSessionId === id) newChat()
    }, [currentSessionId, newChat])

    const handleSend = useCallback((question: string) => {
        traceRef.current = []
        const userId = `user-${Date.now()}`
        const assistantId = `assistant-${Date.now()}`
        activeAssistantId.current = assistantId

        // Ensure a session ID exists before sending — server uses it to load history
        const convId = currentSessionId ?? `chat-${Date.now()}`
        if (!currentSessionId) setCurrentSessionId(convId)

        setMessages((prev) => [
            ...prev,
            {id: userId, role: "user", content: question},
            {id: assistantId, role: "assistant", content: null, sources: [], confidence: null},
        ])
        // Map jurisdiction to backend corpus name (e.g., "cz" -> "czech", "difc" -> "difc")
        const corpus = jurisdictionToCorpus(jurisdiction)
        // Pass conversation_id so the server can load history and detect follow-ups.
        // History content stays on the server — only the opaque ID travels here.
        stream.sendQuery(question, corpus, convId)
    }, [stream.sendQuery, jurisdiction, currentSessionId])

    return (
        <ChatStateContext.Provider value={{
            messages, setMessages, activeAssistantId, traceRef, wasStreamingRef,
            selectedCorpus, setSelectedCorpus, stream, handleSend,
            sessions, currentSessionId, loadSession, newChat, deleteSession,
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
