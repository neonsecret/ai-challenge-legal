"use client"

import {useState, useCallback} from "react"
import {Document, Page, pdfjs} from "react-pdf"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"
import {Loader2, FileX, ChevronLeft, ChevronRight} from "lucide-react"
import {FONT, TYPE_SCALE, SPACE, RADIUS} from "@/lib/tokens"

// Use locally-bundled worker — avoids CDN latency (same as grounding viewer)
if (typeof pdfjs !== "undefined") {
    pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs"
}

export interface DocPdfViewerProps {
    pdfUrl: string
    isDark: boolean
    onError?: () => void
}

export default function DocPdfViewerImpl({pdfUrl, isDark, onError}: DocPdfViewerProps) {
    const [numPages, setNumPages] = useState<number | null>(null)
    const [page, setPage] = useState(1)
    const [error, setError] = useState(false)

    const handleLoadSuccess = useCallback(({numPages}: {numPages: number}) => {
        setNumPages(numPages)
        setError(false)
    }, [])

    const handleLoadError = useCallback(() => {
        setError(true)
        onError?.()
    }, [onError])

    const textColor = isDark ? "var(--strict-text-secondary)" : "#5c3d1a"

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
                <FileX size={32} style={{color: textColor, opacity: 0.5}} />
                <p style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.sm, color: textColor, margin: 0}}>
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
                    borderBottom: isDark
                        ? "0.5px solid rgba(255,255,255,0.05)"
                        : "0.5px solid rgba(255,255,255,0.40)",
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
                            color: textColor,
                        }}
                    >
                        <ChevronLeft size={16} />
                    </button>
                    <span style={{fontFamily: FONT.sans, fontSize: TYPE_SCALE.xs, color: textColor}}>
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
                            color: textColor,
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
                    loading={
                        <div style={{display: "flex", alignItems: "center", justifyContent: "center", padding: SPACE[8]}}>
                            <Loader2 size={20} style={{color: "var(--strict-gold-text)", animation: "spin 1s linear infinite"}} />
                        </div>
                    }
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
