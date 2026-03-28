"use client"

import { useState, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

/** Returns the stored API key, or null if absent/empty. Never returns "". */
function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null
  const key = localStorage.getItem("neolex_api_key")
  return key && key.trim() !== "" ? key.trim() : null
}

function clearApiKeyAndRedirect(router: ReturnType<typeof useRouter>) {
  if (typeof window !== "undefined") {
    localStorage.removeItem("neolex_api_key")
  }
  router.replace("/")
}

// Streaming status messages shown while waiting for the answer
const STREAMING_STATUS_SEQUENCE = [
  "Searching legal database...",
  "Retrieving relevant sources...",
  "Reading sources...",
  "Composing answer...",
]

export interface Source {
  doc_id: string
  page_numbers: number[]
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
  sendQuery: (question: string, corpus?: string) => void
  clearError: () => void
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
  const esRef = useRef<EventSource | null>(null)
  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearStatusTimer = () => {
    if (statusTimerRef.current) {
      clearTimeout(statusTimerRef.current)
      statusTimerRef.current = null
    }
  }

  const cycleStatus = useCallback((index: number) => {
    const next = STREAMING_STATUS_SEQUENCE[index % STREAMING_STATUS_SEQUENCE.length]
    setState((prev) => ({ ...prev, streamingStatus: next }))
    statusTimerRef.current = setTimeout(() => cycleStatus(index + 1), 1800)
  }, [])

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }))
  }, [])

  const sendQuery = useCallback(
    (question: string, corpus?: string) => {
      // Close any existing SSE connection
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      clearStatusTimer()

      // Fix 5: treat empty string as absent
      const apiKey = getStoredApiKey()

      // Fix 1/3: if no key, redirect immediately instead of sending a bad request
      if (!apiKey) {
        clearApiKeyAndRedirect(router)
        return
      }

      setState({
        answer: null,
        sources: [],
        confidence: null,
        isStreaming: true,
        streamingStatus: STREAMING_STATUS_SEQUENCE[0],
        error: null,
      })

      // Start cycling status messages
      statusTimerRef.current = setTimeout(() => cycleStatus(1), 1800)

      // Fix 3: also handle non-streaming POST /api/v1/query for 401
      // The SSE path is used here; 401 detection happens in onerror via error event
      const url = new URL(`${API_BASE}/api/v1/query/stream`)
      url.searchParams.set("question", question)
      url.searchParams.set("answer_type", "free_text")
      // EventSource cannot send custom headers; pass key as query param
      url.searchParams.set("api_key", apiKey)
      if (corpus) url.searchParams.set("corpus", corpus)

      const es = new EventSource(url.toString())
      esRef.current = es

      es.addEventListener("answer", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          clearStatusTimer()
          setState((prev) => ({
            ...prev,
            answer: data.answer ?? null,
            sources: data.sources ?? [],
            confidence: data.confidence ?? null,
            streamingStatus: null,
          }))
        } catch {
          // ignore JSON parse errors
        }
      })

      es.addEventListener("done", () => {
        clearStatusTimer()
        es.close()
        esRef.current = null
        setState((prev) => ({ ...prev, isStreaming: false, streamingStatus: null }))
      })

      // Forward SSE "status" events to UI
      es.addEventListener("status", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          if (data.message) {
            clearStatusTimer()
            setState((prev) => ({ ...prev, streamingStatus: data.message }))
          }
        } catch {
          // ignore
        }
      })

      // Fix 2: handle auth errors — SSE errors don't carry HTTP status, so probe
      // the REST endpoint when we get an error without an answer to distinguish 401 from network issues
      es.onerror = () => {
        clearStatusTimer()
        es.close()
        esRef.current = null

        // Probe auth by hitting a lightweight authenticated endpoint
        const probeUrl = `${API_BASE}/api/v1/query/stream?question=ping&answer_type=free_text&api_key=${encodeURIComponent(apiKey)}`
        fetch(probeUrl, { method: "HEAD" })
          .then((res) => {
            if (res.status === 401 || res.status === 403) {
              // Auth failure — clear key and redirect
              clearApiKeyAndRedirect(router)
            } else {
              setState((prev) => ({
                ...prev,
                isStreaming: false,
                streamingStatus: null,
                // Only show error if we never received an answer
                error: prev.answer ? null : "Connection error. Please try again.",
              }))
            }
          })
          .catch(() => {
            // Network is down — show generic error, do not redirect
            setState((prev) => ({
              ...prev,
              isStreaming: false,
              streamingStatus: null,
              error: prev.answer ? null : "Connection error. Please try again.",
            }))
          })
      }
    },
    [cycleStatus, router]
  )

  return { ...state, sendQuery, clearError }
}
