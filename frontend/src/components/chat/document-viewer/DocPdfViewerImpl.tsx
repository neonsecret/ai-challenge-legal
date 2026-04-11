"use client"

import {useState, useCallback, useEffect, useRef} from "react"
import {Document, Page, pdfjs} from "react-pdf"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"
import {FileX, ChevronLeft, ChevronRight} from "lucide-react"
import {FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"

// Use locally-bundled worker — avoids CDN latency (same as grounding viewer)
if (typeof pdfjs !== "undefined") {
    pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs"
}

export interface DocPdfViewerProps {
    pdfUrl: string
    onError?: (kind: "timeout" | "error") => void
}

export default function DocPdfViewerImpl({pdfUrl, onError}: DocPdfViewerProps) {
    const [numPages, setNumPages] = useState<number | null>(null)
    const [page, setPage] = useState(1)
    const [error, setError] = useState(false)
    const headCheckedRef = useRef<string | null>(null)

    // Pre-check HTTP status via HEAD before react-pdf attempts to load.
    // This lets us surface a 503 timeout as a distinct error kind.
    useEffect(() => {
        if (!pdfUrl || headCheckedRef.current === pdfUrl) return
        headCheckedRef.current = pdfUrl
        fetch(pdfUrl, {method: "HEAD", credentials: "include"})
            .then(r => { if (!r.ok) onError?.(r.status === 503 ? "timeout" : "error") })
            .catch(() => onError?.("error"))
    }, [pdfUrl, onError])

    const handleLoadSuccess = useCallback(({numPages}: {numPages: number}) => {
        setNumPages(numPages)
        setError(false)
    }, [])

    const handleLoadError = useCallback(() => {
        setError(true)
        onError?.("error")
    }, [onError])

    if (error) {
        return (
            <div style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: SPACE[3],
                padding: SPACE[8],
            }}>
                <FileX size={32} style={{color: "var(--doc-text-secondary)", opacity: 0.5}} />
                <p style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.sm, color: "var(--doc-text-secondary)", margin: 0}}>
                    Failed to load document
                </p>
            </div>
        )
    }

    return (
        <div style={{flex: 1, display: "flex", flexDirection: "column", overflow: "hidden"}}>
            {/* Page controls */}
            {numPages && numPages > 1 && (
                <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: SPACE[2],
                    padding: `${SPACE[2]}px ${SPACE[4]}px`,
                    borderBottom: "var(--doc-page-nav-border)",
                    flexShrink: 0,
                }}>
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page <= 1}
                        style={{
                            padding: SPACE[1],
                            borderRadius: RADIUS.sm,
                            background: "transparent",
                            border: "none",
                            cursor: page <= 1 ? "not-allowed" : "pointer",
                            opacity: page <= 1 ? 0.3 : 1,
                            color: "var(--doc-text-secondary)",
                            minHeight: 44,
                            minWidth: 44,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        <ChevronLeft size={16} />
                    </button>
                    <span style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.xs, color: "var(--doc-text-secondary)"}}>
                        {page} / {numPages}
                    </span>
                    <button
                        onClick={() => setPage(p => Math.min(numPages, p + 1))}
                        disabled={page >= numPages}
                        style={{
                            padding: SPACE[1],
                            borderRadius: RADIUS.sm,
                            background: "transparent",
                            border: "none",
                            cursor: page >= numPages ? "not-allowed" : "pointer",
                            opacity: page >= numPages ? 0.3 : 1,
                            color: "var(--doc-text-secondary)",
                            minHeight: 44,
                            minWidth: 44,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        <ChevronRight size={16} />
                    </button>
                </div>
            )}

            {/* PDF content */}
            <div style={{flex: 1, overflowY: "auto", display: "flex", justifyContent: "center", padding: SPACE[3]}}>
                <Document
                    file={pdfUrl}
                    onLoadSuccess={handleLoadSuccess}
                    onLoadError={handleLoadError}
                    loading={null}
                >
                    <Page
                        pageNumber={page}
                        width={Math.min(typeof window !== "undefined" ? window.innerWidth * 0.75 : 600, 700)}
                        renderTextLayer={true}
                        renderAnnotationLayer={false}
                    />
                </Document>
            </div>
        </div>
    )
}
