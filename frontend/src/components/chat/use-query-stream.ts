"use client"

import {useState, useCallback, useRef} from "react"
import {useRouter} from "next/navigation"
import {createParser} from "eventsource-parser"

// SSE goes direct to backend — CORS configured via ALLOWED_ORIGINS.
const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

/** Map backend stage codes to user-friendly labels.
 *  Returns null for statuses that should be hidden (e.g. agent:done). */
export function formatStatus(raw: string): string | null {
    // ── Agent lifecycle ──
    if (raw === "agent:done") return null
    if (raw === "agent:thinking") return "Analyzing your question..."
    if (raw.startsWith("agent:")) {
        // Unknown agent sub-status — strip prefix and capitalize
        const detail = raw.slice("agent:".length).trim()
        return detail.charAt(0).toUpperCase() + detail.slice(1) + "..."
    }

    // ── Answering (N is internal source count, not useful for display) ──
    if (raw.startsWith("answering")) return "Writing answer..."

    // ── Retrieval sub-steps ──
    if (raw.startsWith("retrieving:")) {
        const detail = raw.slice("retrieving:".length).trim()

        // Map known retrieval sub-steps to friendlier text
        if (/searching\s+corpus/i.test(detail)) return "Searching legal documents..."
        if (/searching\s+the\s+web/i.test(detail)) return "Searching the web..."

        // "found N new sources" — capitalize but no trailing ellipsis (past-tense)
        if (/^found\s/i.test(detail)) {
            return detail.charAt(0).toUpperCase() + detail.slice(1)
        }

        // Other retrieval details — capitalize and add ellipsis
        return detail.charAt(0).toUpperCase() + detail.slice(1) + "..."
    }

    // ── Top-level stages ──
    const LABELS: Record<string, string> = {
        processing: "Processing...",
        routing: "Routing to relevant documents...",
        retrieving: "Searching legal documents...",
        reranking: "Evaluating relevance...",
    }
    // Unknown status — return null to avoid leaking internal stage names
    return LABELS[raw] ?? null
}

/**
 * Extracts visible answer text from raw LLM output that may contain
 * <analysis>...</analysis> and <answer>...</answer> tags.
 * Returns null if <answer> hasn't appeared yet.
 */
function extractAnswerContent(raw: string): string | null {
    const answerStart = raw.indexOf("<answer>")
    if (answerStart === -1) return null
    const contentStart = answerStart + "<answer>".length
    const answerEnd = raw.indexOf("</answer>", contentStart)
    const content = answerEnd >= 0
        ? raw.slice(contentStart, answerEnd)
        : raw.slice(contentStart)
    return content.trim() || null
}

function clearSessionAndRedirect(router: ReturnType<typeof useRouter>) {
    const API = process.env.NEXT_PUBLIC_SSE_URL ?? ""
    fetch(`${API}/auth/logout`, {method: "POST", credentials: "include", headers: {"X-Requested-With": "XMLHttpRequest"}}).catch(() => {
    })
    router.replace("/")
}

export interface Source {
    doc_id: string
    page_numbers: number[]
    text?: string | null  // source text for non-PDF corpora (Czech)
    url?: string | null   // web source URL
    title?: string | null // web source title
}

interface StreamState {
    answer: string | null
    sources: Source[]
    confidence: number | null
    isStreaming: boolean
    streamingStatus: string | null
    error: string | null
}

export interface UseQueryStreamReturn extends StreamState {
    sendQuery: (question: string, corpus?: string, conversationId?: string, laws?: string[], useInternet?: boolean) => void
    clearError: () => void
    abort: () => void
}

export function useQueryStream(): UseQueryStreamReturn {
    const router = useRouter()
    const [state, setState] = useState<StreamState>({
        answer: null,
        sources: [],
        confidence: null,
        isStreaming: false,
        streamingStatus: null,
        error: null,
    })
    const abortRef = useRef<AbortController | null>(null)
    const tokenBufRef = useRef<string>("")
    const conversationIdRef = useRef<string | null>(null)

    const clearError = useCallback(() => {
        setState((prev) => ({...prev, error: null}))
    }, [])

    const abort = useCallback(() => {
        if (abortRef.current) {
            abortRef.current.abort()
            abortRef.current = null
        }
        tokenBufRef.current = ""
        setState({
            answer: null,
            sources: [],
            confidence: null,
            isStreaming: false,
            streamingStatus: null,
            error: null,
        })
    }, [])

    /** Poll the backend for a completed answer after SSE connection drops.
     *  The pipeline saves Q&A to PostgreSQL even when the SSE stream breaks,
     *  so we can recover the answer by polling the last-answer endpoint. */
    const pollForAnswer = useCallback(async (convId: string) => {
        const MAX_POLLS = 36  // 36 * 5s = 3 minutes
        for (let i = 0; i < MAX_POLLS; i++) {
            await new Promise(r => setTimeout(r, 5000))
            try {
                const res = await fetch(
                    `${API_BASE}/api/v1/conversations/${encodeURIComponent(convId)}/last-answer`,
                    {credentials: "include"},
                )
                if (res.ok) {
                    const data = await res.json()
                    if (data.answer) {
                        setState(prev => ({
                            ...prev,
                            answer: data.answer,
                            isStreaming: false,
                            streamingStatus: null,
                            error: null,
                        }))
                        return  // recovered
                    }
                } else if (res.status === 401 || res.status === 403) {
                    clearSessionAndRedirect(router)
                    return
                }
                // 404 = not ready yet, keep polling
            } catch {
                // network error, keep trying
            }
        }
        // Gave up — show error
        setState(prev => ({
            ...prev,
            isStreaming: false,
            streamingStatus: null,
            error: prev.answer ? null : "Connection lost. Answer may still be processing — check back later.",
        }))
    }, [router])

    const sendQuery = useCallback(
        (question: string, corpus?: string, conversationId?: string, laws?: string[], useInternet?: boolean) => {
            // Abort any existing SSE connection
            if (abortRef.current) {
                abortRef.current.abort()
                abortRef.current = null
            }

            tokenBufRef.current = ""
            conversationIdRef.current = conversationId ?? null

            setState({
                answer: null,
                sources: [],
                confidence: null,
                isStreaming: true,
                streamingStatus: "Connecting...",
                error: null,
            })

            const ctrl = new AbortController()
            abortRef.current = ctrl

            // --- Event processing ---

            const processEvent = (eventType: string, data: string) => {
                try {
                    if (eventType === "token") {
                        const parsed = JSON.parse(data)
                        if (typeof parsed.text === "string") {
                            tokenBufRef.current += parsed.text
                            const visible = extractAnswerContent(tokenBufRef.current)
                            if (visible !== null) {
                                setState((prev) => ({...prev, answer: visible, streamingStatus: null}))
                            }
                        }
                    } else if (eventType === "answer") {
                        const parsed = JSON.parse(data)
                        setState((prev) => ({
                            ...prev,
                            answer: parsed.answer ?? prev.answer,
                            sources: parsed.sources ?? [],
                            confidence: parsed.confidence ?? null,
                            streamingStatus: null,
                        }))
                    } else if (eventType === "status") {
                        const parsed = JSON.parse(data)
                        const raw = parsed.status || parsed.message
                        if (raw) {
                            const friendly = formatStatus(raw)
                            // null means "hide this status" (e.g. agent:done)
                            if (friendly !== null) {
                                setState((prev) => ({...prev, streamingStatus: friendly}))
                            }
                        }
                    } else if (eventType === "error") {
                        const parsed = JSON.parse(data)
                        ctrl.abort()
                        abortRef.current = null
                        setState((prev) => ({
                            ...prev,
                            isStreaming: false,
                            streamingStatus: null,
                            error: parsed.detail || parsed.error || "Query failed. Please try again.",
                        }))
                    } else if (eventType === "done") {
                        ctrl.abort()
                        abortRef.current = null
                        tokenBufRef.current = ""
                        setState((prev) => ({
                            ...prev,
                            isStreaming: false,
                            streamingStatus: null,
                            error: prev.answer ? null : "No answer received. Please try again.",
                        }))
                    }
                } catch {
                    // ignore parse errors for individual events
                }
            }

            const handleConnectionError = () => {
                abortRef.current = null
                const convId = conversationIdRef.current
                // Check if auth expired first
                fetch(`${API_BASE}/auth/me`, {method: "GET", credentials: "include"})
                    .then((res) => {
                        if (res.status === 401 || res.status === 403) {
                            clearSessionAndRedirect(router)
                        } else if (convId) {
                            // Auth OK — start polling for the completed answer
                            setState(prev => ({
                                ...prev,
                                isStreaming: false,
                                streamingStatus: "Reconnecting \u2014 answer still processing...",
                            }))
                            pollForAnswer(convId)
                        } else {
                            setState(prev => ({
                                ...prev,
                                isStreaming: false,
                                streamingStatus: null,
                                error: prev.answer ? null : "Connection error. Please try again.",
                            }))
                        }
                    })
                    .catch(() => {
                        // Network totally down — still try polling if we have a convId
                        if (convId) {
                            setState(prev => ({
                                ...prev,
                                isStreaming: false,
                                streamingStatus: "Reconnecting \u2014 answer still processing...",
                            }))
                            pollForAnswer(convId)
                        } else {
                            setState(prev => ({
                                ...prev,
                                isStreaming: false,
                                streamingStatus: null,
                                error: prev.answer ? null : "Connection error. Please try again.",
                            }))
                        }
                    })
            }

            ;(async () => {
                try {
                    const response = await fetch(`${API_BASE}/api/v1/query/stream`, {
                        method: "POST",
                        headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                        body: JSON.stringify({
                            question,
                            answer_type: "free_text",
                            corpus: corpus ?? "difc",
                            // Opaque session pointer — server loads history from DB.
                            // History content never travels in the request body.
                            conversation_id: conversationId ?? null,
                            // Czech law corpus filter — only sent when user selects specific laws.
                            ...(laws && laws.length > 0 ? {laws} : {}),
                            // Agent is the production path — deterministic pipeline is for benchmarks only.
                            use_agent: true,
                            use_internet: useInternet ?? true,
                        }),
                        credentials: "include",  // sends HttpOnly cookie automatically
                        signal: ctrl.signal,
                    })

                    if (response.status === 401 || response.status === 403) {
                        clearSessionAndRedirect(router)
                        return
                    }
                    if (!response.ok) {
                        // Try to extract error detail from JSON body
                        let detail = `HTTP ${response.status}`
                        try {
                            const errBody = await response.json()
                            detail = errBody.detail || errBody.error || detail
                        } catch { /* body not JSON */ }
                        setState(prev => ({
                            ...prev,
                            isStreaming: false,
                            streamingStatus: null,
                            error: detail,
                        }))
                        return
                    }

                    if (!response.body) {
                        setState(prev => ({
                            ...prev,
                            isStreaming: false,
                            streamingStatus: null,
                            error: "No response stream available.",
                        }))
                        return
                    }

                    // --- Use eventsource-parser for robust SSE parsing ---
                    // This replaces the manual \n\n-splitting parser that silently
                    // failed on chunked boundaries and multi-line data fields.
                    const parser = createParser({
                        onEvent(event) {
                            processEvent(event.event ?? "message", event.data)
                        },
                    })

                    const reader = response.body.getReader()
                    const decoder = new TextDecoder()

                    while (true) {
                        const {done, value} = await reader.read()
                        if (done) break
                        parser.feed(decoder.decode(value, {stream: true}))
                    }

                    // Stream ended normally — if no "done" event was received, finalize
                    if (abortRef.current) {
                        abortRef.current = null
                        tokenBufRef.current = ""
                        setState((prev) => ({
                            ...prev,
                            isStreaming: false,
                            streamingStatus: null,
                            error: prev.answer ? null : "No answer received. Please try again.",
                        }))
                    }
                } catch (err: unknown) {
                    // AbortError is expected when user cancels — ignore it
                    if (err instanceof DOMException && err.name === "AbortError") return
                    handleConnectionError()
                }
            })()
        },
        [router, pollForAnswer]
    )

    return {...state, sendQuery, clearError, abort}
}
