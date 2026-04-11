"use client"

import {useState, useCallback, useRef} from "react"
import type {Template} from "@/types/documents"

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

const CACHE_TTL_MS = 5 * 60 * 1000 // 5 minutes

interface CacheEntry {
    data: Template[]
    cachedAt: number
}

// In-memory cache keyed by jurisdiction (category filtered client-side).
// Entries expire after CACHE_TTL_MS so backend template updates become visible
// within the same session without requiring a hard page reload.
const templateCache = new Map<string, CacheEntry>()

interface UseTemplatesReturn {
    templates: Template[]
    isLoading: boolean
    /** True once the first load() call has been made — use to suppress the misleading empty state. */
    hasAttempted: boolean
    error: string | null
    /** Load templates for the given jurisdiction. Category filtering is done client-side. */
    load: (jurisdiction?: string) => void
}

export function useTemplates(): UseTemplatesReturn {
    const [templates, setTemplates] = useState<Template[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [hasAttempted, setHasAttempted] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const abortRef = useRef<AbortController | null>(null)

    const load = useCallback(async (jurisdiction?: string) => {
        setHasAttempted(true)
        const key = jurisdiction ?? ""
        const cached = templateCache.get(key)
        if (cached && Date.now() - cached.cachedAt < CACHE_TTL_MS) {
            setTemplates(cached.data)
            return
        }

        // Abort any in-flight request before starting a new one
        abortRef.current?.abort()
        const controller = new AbortController()
        abortRef.current = controller

        setIsLoading(true)
        setError(null)
        try {
            const params = new URLSearchParams()
            if (jurisdiction) params.set("jurisdiction", jurisdiction)
            const qs = params.toString()
            const res = await fetch(
                `${API_BASE}/api/v1/templates${qs ? `?${qs}` : ""}`,
                {credentials: "include", signal: controller.signal},
            )
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const data: Template[] = await res.json()
            templateCache.set(key, {data, cachedAt: Date.now()})
            setTemplates(data)
        } catch (err) {
            if (err instanceof Error && err.name === "AbortError") return
            setError(err instanceof Error ? err.message : "Failed to load templates")
        } finally {
            if (!controller.signal.aborted) setIsLoading(false)
        }
    }, [])

    return {templates, isLoading, hasAttempted, error, load}
}
