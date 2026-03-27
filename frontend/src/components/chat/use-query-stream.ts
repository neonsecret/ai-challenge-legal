"use client"

import { useState, useCallback, useRef } from "react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
// API key from env or localStorage; hardcoded fallback for dev
const DEV_API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "dev-test-key"

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
  sendQuery: (question: string) => void
}

export function useQueryStream(): UseQueryStreamReturn {
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

  const sendQuery = useCallback(
    (question: string) => {
      // Close any existing SSE connection
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      clearStatusTimer()

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

      const apiKey =
        typeof window !== "undefined"
          ? (localStorage.getItem("api_key") ?? DEV_API_KEY)
          : DEV_API_KEY

      const url = new URL(`${API_BASE}/api/v1/query/stream`)
      url.searchParams.set("question", question)
      url.searchParams.set("answer_type", "free_text")
      // EventSource cannot send custom headers; pass key as query param
      url.searchParams.set("api_key", apiKey)

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

      es.onerror = () => {
        clearStatusTimer()
        es.close()
        esRef.current = null
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          streamingStatus: null,
          // Only show error if we never received an answer
          error: prev.answer ? null : "Connection error. Please try again.",
        }))
      }
    },
    [cycleStatus]
  )

  return { ...state, sendQuery }
}
