"use client"

import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

interface PdfViewerProps {
  docId: string
  page?: number
  className?: string
}

function getApiKey(): string {
  if (typeof window === "undefined") return ""
  return localStorage.getItem("api_key") ?? (process.env.NEXT_PUBLIC_API_KEY ?? "dev-test-key")
}

export function PdfViewer({ docId, page = 1, className }: PdfViewerProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const apiKey = getApiKey()
  const pdfUrl = `${API_BASE}/api/v1/documents/${encodeURIComponent(docId)}/pdf?api_key=${encodeURIComponent(apiKey)}#page=${page}`

  // When page changes, reload the iframe to jump to the correct page
  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return
    iframe.src = pdfUrl
  }, [pdfUrl])

  return (
    <div className={cn("relative flex flex-col h-full bg-[#1a1f2e]", className)}>
      {/* Page badge */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 rounded-md bg-[#0d1117]/80 px-2 py-1 text-xs font-mono text-amber-400 ring-1 ring-amber-400/20 backdrop-blur-sm">
        p.{page}
      </div>

      <iframe
        ref={iframeRef}
        src={pdfUrl}
        className="flex-1 w-full border-0"
        title={`PDF viewer — ${docId}`}
      />
    </div>
  )
}
