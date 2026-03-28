"use client"

import { useState, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

// Human-readable labels for backend status codes
const STATUS_LABELS: Record<string, string> = {
  processing: "Processing your question...",
  routing: "Routing to relevant documents...",
  retrieving: "Retrieving relevant passages...",
  reranking: "Re-ranking results...",
  answering: "Composing answer...",
}

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

      const apiKey = getStoredApiKey()

      if (!apiKey) {
        clearApiKeyAndRedirect(router)
        return
      }

      setState({
        answer: null,
        sources: [],
        confidence: null,
        isStreaming: true,
        streamingStatus: "Connecting...",
        error: null,
      })

      // Fix: relative URLs require a base when using new URL()
      const url = new URL(`${API_BASE}/api/v1/query/stream`, window.location.origin)
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
        es.close()
        esRef.current = null
        setState((prev) => ({ ...prev, isStreaming: false, streamingStatus: null }))
      })

      // Forward real SSE "status" events — backend sends {"status": "processing"}
      es.addEventListener("status", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          const raw = data.status || data.message
          if (raw) {
            const label = STATUS_LABELS[raw as string] ?? raw
            setState((prev) => ({ ...prev, streamingStatus: label }))
          }
        } catch {
          // ignore
        }
      })

      // Handle auth errors — SSE errors don't carry HTTP status, so probe the
      // REST endpoint to distinguish 401 from network issues
      es.onerror = () => {
        es.close()
        esRef.current = null

        const probeUrl = `${API_BASE}/api/v1/query/stream?question=ping&answer_type=free_text&api_key=${encodeURIComponent(apiKey)}`
        fetch(probeUrl, { method: "HEAD" })
          .then((res) => {
            if (res.status === 401 || res.status === 403) {
              clearApiKeyAndRedirect(router)
            } else {
              setState((prev) => ({
                ...prev,
                isStreaming: false,
                streamingStatus: null,
                error: prev.answer ? null : "Connection error. Please try again.",
              }))
            }
          })
          .catch(() => {
            setState((prev) => ({
              ...prev,
              isStreaming: false,
              streamingStatus: null,
              error: prev.answer ? null : "Connection error. Please try again.",
            }))
          })
      }
    },
    [router]
  )

  return { ...state, sendQuery, clearError }
}
