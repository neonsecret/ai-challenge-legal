"use client"

import {useState, useCallback, useEffect, useRef} from "react"
import type {ChatDocument} from "@/types/documents"

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

interface UseDocumentStateReturn {
    documents: ChatDocument[]
    count: number
    isLoading: boolean
    /** Optimistically append a newly generated document from SSE. */
    addDocument: (doc: ChatDocument) => void
}

export function useDocumentState(chatId: string | null | undefined): UseDocumentStateReturn {
    const [documents, setDocuments] = useState<ChatDocument[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const prevChatIdRef = useRef<string | null | undefined>(undefined)

    useEffect(() => {
        if (chatId === prevChatIdRef.current) return
        prevChatIdRef.current = chatId

        if (!chatId) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setDocuments([])
            return
        }

        setIsLoading(true)
        fetch(`${API_BASE}/api/v1/conversations/${encodeURIComponent(chatId)}/documents`, {
            credentials: "include",
        })
            .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                return res.json() as Promise<ChatDocument[]>
            })
            .then((data) => setDocuments(data))
            .catch(() => setDocuments([]))
            .finally(() => setIsLoading(false))
    }, [chatId])

    const addDocument = useCallback((doc: ChatDocument) => {
        setDocuments((prev) => {
            // Replace if same doc_id already present (version bump), otherwise append
            const exists = prev.some((d) => d.doc_id === doc.doc_id)
            if (exists) return prev.map((d) => (d.doc_id === doc.doc_id ? doc : d))
            return [...prev, doc]
        })
    }, [])

    return {documents, count: documents.length, isLoading, addDocument}
}
