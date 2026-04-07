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
        if (/searching\s+\d+\s+target/i.test(detail)) return "Searching target documents..."

        // "found N new sources" — capitalize but no trailing ellipsis (past-tense)
        if (/^found\s/i.test(detail)) {
            return detail.charAt(0).toUpperCase() + detail.slice(1)
        }

        // Reranking with progress — clean label (progress bar handles the numbers)
        if (/reranking/i.test(detail)) return "Reading legal documents..."
        // Scoring documents
        if (/scoring.*document/i.test(detail)) return "Evaluating relevance..."
        if (/scoring/i.test(detail)) return "Evaluating relevance..."
        // Broadening search
        if (/broadening/i.test(detail)) return "Broadening search..."

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
    // If the LLM uses <answer> tags, extract content from within them
    const answerStart = raw.indexOf("<answer>")
    if (answerStart !== -1) {
        const contentStart = answerStart + "<answer>".length
        const answerEnd = raw.indexOf("</answer>", contentStart)
        const content = answerEnd >= 0
            ? raw.slice(contentStart, answerEnd)
            : raw.slice(contentStart)
        return content.trim() || null
    }

    // No <answer> tags — strip all analysis tags (open or closed) and show the rest.
    // Claude sometimes wraps its reasoning in <analysis> tags spontaneously.
    // We strip them completely so the answer text is always visible during streaming.
    let text = raw
        .replace(/<analysis>[\s\S]*?<\/analysis>/g, "")  // Remove closed blocks
        .replace(/<analysis>[\s\S]*$/g, "")               // Remove open block (still streaming)
        .replace(/<\/?(?:analysis|answer)>/g, "")          // Clean leftover tags
        .trim()
    return text || (raw.length > 0 ? "" : null)
}

/**
 * Extracts the agent's intermediate reasoning from <analysis> tags.
 * Shown as a live "thinking" preview before <answer> appears.
 * Returns null if no analysis content found.
 */
function extractThinkingPreview(raw: string): string | null {
    const start = raw.indexOf("<analysis>")
    if (start === -1) return null
    const contentStart = start + "<analysis>".length
    const end = raw.indexOf("</analysis>", contentStart)
    const text = end >= 0 ? raw.slice(contentStart, end) : raw.slice(contentStart)
    // Take last ~120 chars to show the most recent thinking
    const trimmed = text.trim()
    if (!trimmed) return null
    if (trimmed.length > 120) return "..." + trimmed.slice(-120).trim()
    return trimmed
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
    text?: string | null          // source text for non-PDF corpora (Czech)
    url?: string | null           // web source URL
    title?: string | null         // web source title
    chunk_id?: string | null      // database chunk identifier for context window fetch
    source_type?: "statute" | "court_decision" | null
    case_number?: string | null   // e.g. "21 Cdo 1234/2023"
    decision_date?: string | null // ISO date
    court?: string | null         // e.g. "Nejvyssi soud"
    category?: string | null      // A-E
    ecli?: string | null
    legal_thesis?: string | null  // právní věta
}

export interface Progress {
    current: number
    total: number
}

interface StreamState {
    answer: string | null
    sources: Source[]
    confidence: string | null
    traceId: string | null
    isStreaming: boolean
    streamingStatus: string | null
    streamingProgress: Progress | null
    thinkingPreview: string | null
    followUps: string[] | null
    error: string | null
}

export interface UseQueryStreamReturn extends StreamState {
    sendQuery: (question: string, corpus?: string, conversationId?: string, laws?: string[], useInternet?: boolean, docIds?: string[]) => void
    clearError: () => void
    abort: () => void
}


export function useQueryStream(): UseQueryStreamReturn {
    const router = useRouter()
    const [state, setState] = useState<StreamState>({
        answer: null,
        sources: [],
        confidence: null,
        traceId: null,
        isStreaming: false,
        streamingStatus: null,
        streamingProgress: null,
        thinkingPreview: null,
        followUps: null,
        error: null,
    })
    const abortRef = useRef<AbortController | null>(null)
    const tokenBufRef = useRef<string>("")
    const conversationIdRef = useRef<string | null>(null)
    const intermediateClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
            traceId: null,
            isStreaming: false,
            streamingStatus: null,
            streamingProgress: null,
            thinkingPreview: null,
            followUps: null,
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
        (question: string, corpus?: string, conversationId?: string, laws?: string[], useInternet?: boolean, docIds?: string[]) => {
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
                traceId: null,
                isStreaming: true,
                streamingStatus: "Connecting...",
                streamingProgress: null,
                thinkingPreview: null,
                followUps: null,
                error: null,
            })

            const ctrl = new AbortController()
            abortRef.current = ctrl

            // Cancel any stale intermediate-clear timer from a previous query
            if (intermediateClearTimerRef.current) {
                clearTimeout(intermediateClearTimerRef.current)
                intermediateClearTimerRef.current = null
            }

            // --- Event processing ---

            const processEvent = (eventType: string, data: string) => {
                try {
                    if (eventType === "token") {
                        const parsed = JSON.parse(data)
                        if (typeof parsed.text === "string") {
                            tokenBufRef.current += parsed.text
                            const visible = extractAnswerContent(tokenBufRef.current)
                            if (visible !== null && visible.length > 0) {
                                // Real answer content — display it and clear status
                                setState((prev) => ({...prev, answer: visible, streamingStatus: null, streamingProgress: null, thinkingPreview: null}))
                            } else if (visible !== null) {
                                // Empty string — answer mode started but only whitespace so far.
                                // Clear the "Writing answer..." status so it doesn't persist,
                                // but don't set answer to empty (would show "No response").
                            } else {
                                // Show intermediate reasoning as a live preview
                                const preview = extractThinkingPreview(tokenBufRef.current)
                                if (preview !== null) {
                                    setState((prev) => ({...prev, thinkingPreview: preview}))
                                }
                            }
                        }
                    } else if (eventType === "answer") {
                        // Final answer — cancel any pending intermediate text clear
                        if (intermediateClearTimerRef.current) { clearTimeout(intermediateClearTimerRef.current); intermediateClearTimerRef.current = null }
                        const parsed = JSON.parse(data)
                        // Strip any leftover XML tags from the answer (safety net —
                        // backend should already strip them in pipeline_dict_to_response)
                        let cleanAnswer = parsed.answer
                        if (typeof cleanAnswer === "string") {
                            const extracted = extractAnswerContent(cleanAnswer)
                            cleanAnswer = extracted ?? cleanAnswer.replace(/<\/?(?:analysis|answer)>/g, "").trim()
                        }
                        setState((prev) => ({
                            ...prev,
                            answer: cleanAnswer ?? prev.answer,
                            sources: parsed.sources ?? [],
                            confidence: parsed.confidence ?? null,
                            traceId: parsed.trace_id ?? null,
                            streamingStatus: null,
                            streamingProgress: null,
                        }))
                    } else if (eventType === "status") {
                        const parsed = JSON.parse(data)
                        const raw = parsed.status || parsed.message
                        const progress: Progress | null = parsed.progress
                            ? {current: parsed.progress.current, total: parsed.progress.total}
                            : null
                        if (raw) {
                            const friendly = formatStatus(raw)
                            // null means "hide this status" (e.g. agent:done)
                            if (friendly !== null) {
                                // When status goes back to searching/thinking after
                                // "Writing answer...", reset the answer and token buffer.
                                // The intermediate text was from a non-final LLM call
                                // and will be discarded by the backend.
                                const isSearchPhase = raw.startsWith("retrieving:") || raw.startsWith("agent:thinking")
                                if (isSearchPhase) {
                                    // Show the new status immediately but delay clearing
                                    // the intermediate answer text so the user can read it.
                                    setState((prev) => ({
                                        ...prev,
                                        streamingStatus: friendly,
                                        streamingProgress: progress,
                                        thinkingPreview: null,
                                    }))
                                    if (intermediateClearTimerRef.current) clearTimeout(intermediateClearTimerRef.current)
                                    intermediateClearTimerRef.current = setTimeout(() => {
                                        tokenBufRef.current = ""
                                        setState((prev) => ({...prev, answer: null}))
                                        intermediateClearTimerRef.current = null
                                    }, 2000)
                                } else {
                                    setState((prev) => ({
                                        ...prev,
                                        streamingStatus: friendly,
                                        streamingProgress: progress,
                                    }))
                                }
                            } else if (progress) {
                                // Hidden status but with progress — update progress only
                                setState((prev) => ({...prev, streamingProgress: progress}))
                            }
                        }
                    } else if (eventType === "follow_ups") {
                        const parsed = JSON.parse(data)
                        const questions: string[] = Array.isArray(parsed.questions)
                            ? parsed.questions.filter((q: unknown) => typeof q === "string" && q.length > 0)
                            : []
                        if (questions.length > 0) {
                            setState((prev) => ({...prev, followUps: questions}))
                        }
                    } else if (eventType === "error") {
                        const parsed = JSON.parse(data)
                        if (intermediateClearTimerRef.current) { clearTimeout(intermediateClearTimerRef.current); intermediateClearTimerRef.current = null }
                        ctrl.abort()
                        abortRef.current = null
                        setState((prev) => ({
                            ...prev,
                            isStreaming: false,
                            streamingStatus: null,
                            error: parsed.detail || parsed.error || "Query failed. Please try again.",
                        }))
                    } else if (eventType === "done") {
                        if (intermediateClearTimerRef.current) { clearTimeout(intermediateClearTimerRef.current); intermediateClearTimerRef.current = null }
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
                            // Custom corpus document filter — restricts to specific uploaded docs.
                            ...(docIds && docIds.length > 0 ? {doc_ids: docIds} : {}),
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
