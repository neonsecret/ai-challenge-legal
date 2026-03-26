"use client"

import { useState, useCallback, useRef } from "react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
// API key from env or localStorage; hardcoded fallback for dev
const DEV_API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "dev-test-key"

export interface Source {
  doc_id: string
  page_numbers: number[]
}

interface StreamState {
  answer: string | null
  sources: Source[]
  confidence: number | null
  isStreaming: boolean
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
    error: null,
  })
  const esRef = useRef<EventSource | null>(null)

  const sendQuery = useCallback((question: string) => {
    // Close any existing SSE connection
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    setState({
      answer: null,
      sources: [],
      confidence: null,
      isStreaming: true,
      error: null,
    })

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
        setState((prev) => ({
          ...prev,
          answer: data.answer ?? null,
          sources: data.sources ?? [],
          confidence: data.confidence ?? null,
        }))
      } catch {
        // ignore JSON parse errors
      }
    })

    es.addEventListener("done", () => {
      es.close()
      esRef.current = null
      setState((prev) => ({ ...prev, isStreaming: false }))
    })

    // "status" events are informational; no state change needed
    es.addEventListener("status", () => {})

    es.onerror = () => {
      es.close()
      esRef.current = null
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        // Only show error if we never received an answer
        error: prev.answer ? null : "Connection error. Please try again.",
      }))
    }
  }, [])

  return { ...state, sendQuery }
}
