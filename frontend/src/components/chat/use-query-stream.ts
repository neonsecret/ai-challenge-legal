"use client"

import { useState, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"

// SSE (EventSource) needs a direct connection — can't go through Next.js rewrite proxy.
// Regular fetch calls use "" (relative, proxied by Next.js rewrites).
// SSE calls use the direct backend URL.
const SSE_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? process.env.NEXT_PUBLIC_API_URL ?? ""
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

/** Map backend stage codes to user-friendly labels. Supports "answering:N" format. */
function formatStatus(raw: string): string {
  const LABELS: Record<string, string> = {
    processing: "Processing your question...",
    routing: "Routing to relevant documents...",
    retrieving: "Searching DIFC Law corpus...",
    reranking: "Re-ranking with cross-encoder...",
  }
  if (raw.startsWith("answering")) {
    const n = raw.split(":")[1]
    return n && n !== "0" ? `Composing answer from ${n} passages...` : "Composing answer..."
  }
  return LABELS[raw] ?? raw
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
      const url = new URL(`${SSE_BASE}/api/v1/query/stream`, window.location.origin)
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
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          streamingStatus: null,
          // Show error if stream completed but no answer was received
          error: prev.answer ? null : "No answer received. Please try again.",
        }))
      })

      // Forward real SSE "status" events — backend sends {"status": "routing"}, etc.
      es.addEventListener("status", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          const raw = data.status || data.message
          if (raw) {
            setState((prev) => ({ ...prev, streamingStatus: formatStatus(raw) }))
          }
        } catch {
          // ignore
        }
      })

      // Handle SSE "error" events from the backend (pipeline failure, timeout, etc.)
      es.addEventListener("error", (e: MessageEvent) => {
        try {
          const data = JSON.parse((e as MessageEvent).data)
          es.close()
          esRef.current = null
          setState((prev) => ({
            ...prev,
            isStreaming: false,
            streamingStatus: null,
            error: data.detail || data.error || "Query failed. Please try again.",
          }))
        } catch {
          // Not a JSON error event — fall through to onerror
        }
      })

      // Handle connection-level errors — SSE errors don't carry HTTP status, so probe
      // the REST endpoint to distinguish 401 from network issues
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
