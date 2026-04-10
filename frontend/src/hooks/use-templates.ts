"use client"

import {useState, useCallback} from "react"
import type {Template} from "@/types/documents"

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

// In-memory cache keyed by "jurisdiction|category"
const templateCache = new Map<string, Template[]>()

interface UseTemplatesReturn {
    templates: Template[]
    isLoading: boolean
    error: string | null
    /** Call on first panel open, optionally filtered by jurisdiction and category. */
    load: (jurisdiction?: string, category?: string) => void
}

export function useTemplates(): UseTemplatesReturn {
    const [templates, setTemplates] = useState<Template[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async (jurisdiction?: string, category?: string) => {
        const key = `${jurisdiction ?? ""}|${category ?? ""}`
        const cached = templateCache.get(key)
        if (cached) {
            setTemplates(cached)
            return
        }
        setIsLoading(true)
        setError(null)
        try {
            const params = new URLSearchParams()
            if (jurisdiction) params.set("jurisdiction", jurisdiction)
            if (category) params.set("category", category)
            const qs = params.toString()
            const res = await fetch(
                `${API_BASE}/api/v1/templates${qs ? `?${qs}` : ""}`,
                {credentials: "include"},
            )
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const data: Template[] = await res.json()
            templateCache.set(key, data)
            setTemplates(data)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load templates")
        } finally {
            setIsLoading(false)
        }
    }, [])

    return {templates, isLoading, error, load}
}
