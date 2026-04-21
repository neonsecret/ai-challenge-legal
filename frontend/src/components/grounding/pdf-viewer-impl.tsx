"use client"

import {useCallback, useEffect, useMemo, useRef, useState} from "react"
import {Document, Page, pdfjs} from "react-pdf"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"
import {cn} from "@/lib/utils"
import {FileX, Loader2, Maximize2, Minimize2, ZoomIn, ZoomOut} from "lucide-react"
import {useColorMode} from "@/lib/color-mode"

// Polyfill URL.parse() for browsers that predate the static method (Chrome <126,
// Safari <18, Firefox <126).  pdfjs-dist 5.x calls URL.parse() in the main
// thread bundle and in the worker; the worker gets its own copy in the bundled
// pdf.worker.min.mjs file.
if (typeof URL.parse === "undefined") {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(URL as any).parse = (url: string, base?: string): URL | null => {
        try {
            return new URL(url, base)
        } catch {
            return null
        }
    }
}

// Use locally-bundled worker (public/pdf.worker.min.mjs) to avoid CDN latency
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs"

// Backend base URL — same as SSE (points to the actual backend)
const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? process.env.NEXT_PUBLIC_API_URL ?? ""

export interface PdfViewerProps {
    docId: string
    page?: number
    highlightText?: string
    className?: string
    /** Called when the PDF fails to load (e.g. 404 — no PDF for this doc). */
    onError?: () => void
}

/**
 * Normalize a string for fuzzy matching: lowercase, collapse whitespace,
 * strip common ligatures and diacritics.
 */
function normalize(s: string): string {
    return s
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/\s+/g, " ")
        .toLowerCase()
        .trim()
}

/**
 * Walk all text spans inside the rendered text layer and apply a gold
 * highlight to those whose content is part of `highlightText`.
 */
function applyHighlights(container: HTMLDivElement | null, highlightText: string | undefined) {
    if (!container || !highlightText) return

    const target = normalize(highlightText)
    if (!target) return

    const spans = container.querySelectorAll<HTMLSpanElement>(
        ".react-pdf__Page__textContent span"
    )

    for (const span of spans) {
        const text = normalize(span.textContent ?? "")
        if (!text) continue

        if (target.includes(text) || text.includes(target)) {
            span.style.backgroundColor = "rgba(201, 168, 76, 0.35)"
            span.style.borderRadius = "2px"
            span.style.transition = "background-color 0.4s ease"
            span.style.mixBlendMode = "multiply"
        } else {
            span.style.backgroundColor = ""
            span.style.borderRadius = ""
            span.style.transition = ""
            span.style.mixBlendMode = ""
        }
    }
}

export default function PdfViewerImpl({docId, page = 1, highlightText, className, onError}: PdfViewerProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const scrollAreaRef = useRef<HTMLDivElement>(null)
    const targetPageRef = useRef<HTMLDivElement>(null)
    const [loadState, setLoadState] = useState<"loading" | "ok" | "error">("loading")
    const [errorMessage, setErrorMessage] = useState<string>("PDF unavailable")
    const [containerWidth, setContainerWidth] = useState<number | undefined>(undefined)
    const [prevPage, setPrevPage] = useState<number | null>(null)
    const [pageChanged, setPageChanged] = useState(false)
    const [numPages, setNumPages] = useState<number | null>(null)
    const [scale, setScale] = useState(1.0)
    const [fullscreen, setFullscreen] = useState(false)
    const fullscreenScrollRef = useRef<HTMLDivElement>(null)
    const fullscreenTargetPageRef = useRef<HTMLDivElement>(null)
    const [fullscreenWidth, setFullscreenWidth] = useState<number | undefined>(undefined)
    // Dedicated PDFWorker instance — created fresh on mount, destroyed on unmount.
    // This avoids the global shared-worker bug where destroy() sets messageHandler=null
    // and the next mount tries to reuse the same dead worker object.
    const workerRef = useRef<InstanceType<typeof pdfjs.PDFWorker> | null>(null)
    const [workerReady, setWorkerReady] = useState(false)
    const {isDark} = useColorMode()

    // react-pdf v10 caches PDFDocumentProxy by URL at module level.
    // When the same URL is requested again after a destroy(), it returns the
    // stale destroyed proxy → "messageHandler is null".
    // Appending a per-mount timestamp busts the cache; the backend ignores it.
    const [cacheBuster] = useState(() => Date.now())
    const pdfUrl = `${API_BASE}/api/v1/documents/${encodeURIComponent(docId)}/pdf?v=${cacheBuster}`

    // Create a dedicated worker on mount; destroy it on unmount.
    // Using a unique name per mount so the browser allocates a fresh worker context.
    useEffect(() => {
        const worker = new pdfjs.PDFWorker()
        workerRef.current = worker
        // PDFWorker.promise resolves when the worker's messageHandler is ready.
        // Setting workerReady before this causes "messageHandler is null" crashes.
        worker.promise.then(() => {
            setWorkerReady(true)
        }).catch((err) => {
            console.error("[PdfViewer] worker init failed:", err)
        })
        return () => {
            worker.destroy()
            workerRef.current = null
            setWorkerReady(false)
        }
    }, [])

    // Memoize options so react-pdf doesn't see a new object on every render.
    // Non-memoized options cause document reload → old transport destroyed → all
    // page useEffects (render, textContent, annotations) throw messageHandler=null.
    const pdfOptions = useMemo(() => ({
        withCredentials: true,
        worker: workerRef.current,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }), [workerReady])  // recreate only when the worker instance changes

    // Suppress residual "messageHandler is null" errors from in-flight promises
    // that resolve after the old worker has been destroyed.
    useEffect(() => {
        const onError = (e: ErrorEvent) => {
            if (e.message?.includes("messageHandler") || e.message?.includes("sendWithPromise")) {
                e.preventDefault()
                e.stopImmediatePropagation()
            }
        }
        const onUnhandledRejection = (e: PromiseRejectionEvent) => {
            const msg = String(e.reason?.message ?? e.reason ?? "")
            if (msg.includes("messageHandler") || msg.includes("sendWithPromise")) {
                e.preventDefault()
            }
        }
        window.addEventListener("error", onError)
        window.addEventListener("unhandledrejection", onUnhandledRejection)
        return () => {
            window.removeEventListener("error", onError)
            window.removeEventListener("unhandledrejection", onUnhandledRejection)
        }
    }, [])

    // Measure the container width so the page fills it
    useEffect(() => {
        const el = containerRef.current
        if (!el) return

        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setContainerWidth(Math.floor(entry.contentRect.width))
            }
        })
        observer.observe(el)
        return () => observer.disconnect()
    }, [])

    // Measure fullscreen scroll area width
    useEffect(() => {
        if (!fullscreen) return
        const el = fullscreenScrollRef.current
        if (!el) return
        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setFullscreenWidth(Math.floor(entry.contentRect.width))
            }
        })
        observer.observe(el)
        return () => observer.disconnect()
    }, [fullscreen])

    // Close fullscreen on Escape key
    useEffect(() => {
        if (!fullscreen) return
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setFullscreen(false)
        }
        document.addEventListener("keydown", onKey)
        return () => document.removeEventListener("keydown", onKey)
    }, [fullscreen])

    // Flash the page badge when page changes
    useEffect(() => {
        if (prevPage !== null && prevPage !== page) {
            setPageChanged(true)
            const timer = setTimeout(() => setPageChanged(false), 1200)
            return () => clearTimeout(timer)
        }
        setPrevPage(page)
    }, [page, prevPage])

    // Auto-scroll to the target page after render.
    // Double rAF ensures two paint cycles have passed — by then page-1 has
    // rendered its full height and scrollIntoView lands on the correct page
    // rather than page n-1.
    useEffect(() => {
        if (loadState === "ok" && targetPageRef.current) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    targetPageRef.current?.scrollIntoView({behavior: "smooth", block: "start"})
                })
            })
        }
    }, [loadState, page])

    // Re-apply highlights when highlightText changes (both main and fullscreen)
    useEffect(() => {
        applyHighlights(targetPageRef.current, highlightText)
        applyHighlights(fullscreenTargetPageRef.current, highlightText)
    }, [highlightText])

    const handleDocumentLoadSuccess = useCallback(({numPages: n}: {numPages: number}) => {
        setNumPages(n)
        setLoadState("ok")
    }, [])

    const handleDocumentLoadError = useCallback((error: Error) => {
        const msg = error?.message ?? ""
        // Worker destroyed mid-load (race condition on source switch) — not a real error
        if (msg.includes("messageHandler") || msg.includes("Worker was destroyed")) return
        if (msg.includes("404") || msg.includes("Unexpected server response (404)")) {
            // PDF not found — trigger fallback to text viewer (only on 404, not transient errors)
            onError?.()
            setErrorMessage("Document not found")
        } else if (msg.includes("401") || msg.includes("Unexpected server response (401)")) {
            setErrorMessage("Authentication required")
        } else {
            setErrorMessage("PDF unavailable")
        }
        setLoadState("error")
    }, [onError])

    const handleTextLayerSuccess = useCallback(() => {
        requestAnimationFrame(() => {
            applyHighlights(targetPageRef.current, highlightText)
            applyHighlights(fullscreenTargetPageRef.current, highlightText)
        })
    }, [highlightText])

    // Providing customTextRenderer suppresses react-pdf's StructTree component,
    // which calls page.getStructTree() → messageHandler.sendWithPromise() in a
    // useEffect. In React 18, that useEffect error propagates to error boundaries
    // causing the viewer to crash. The text layer itself still renders correctly.
    const customTextRenderer = useCallback((textItem: {str: string}) => textItem.str, [])

    const handleZoomIn = useCallback(() => {
        setScale(s => Math.min(3.0, parseFloat((s + 0.25).toFixed(2))))
    }, [])

    const handleZoomOut = useCallback(() => {
        setScale(s => Math.max(0.5, parseFloat((s - 0.25).toFixed(2))))
    }, [])

    const handleToggleFullscreen = useCallback(() => {
        setFullscreen(f => !f)
    }, [])

    const displayId = docId.length > 16 ? `${docId.slice(0, 8)}...${docId.slice(-8)}` : docId
    const zoomPct = Math.round(scale * 100)

    // Build the list of page numbers to render around the target page
    const pagesToRender = numPages
        ? [page - 1, page, page + 1].filter(p => p >= 1 && p <= numPages)
        : [page]

    if (loadState === "error") {
        return (
            <div
                className={cn(
                    "relative flex flex-col h-full items-center justify-center gap-3 rounded-xl",
                    className
                )}
                style={{
                    background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,252,242,0.60)",
                    border: isDark
                        ? "0.5px solid rgba(255,255,255,0.10)"
                        : "0.5px solid rgba(255,255,255,0.50)",
                }}
            >
                <FileX
                    className="size-8"
                    style={{color: isDark ? "rgba(201,168,76,0.45)" : "rgba(122,74,0,0.30)"}}
                />
                <div className="text-center px-6">
                    <p
                        className="text-sm font-medium mb-1"
                        style={{color: isDark ? "rgba(201,168,76,0.70)" : "rgba(122,74,0,0.60)"}}
                    >
                        {errorMessage}
                    </p>
                    <p
                        className="text-xs font-mono"
                        style={{color: isDark ? "rgba(255,255,255,0.30)" : "rgba(46,31,8,0.40)"}}
                    >
                        {displayId} · p.{page}
                    </p>
                </div>
            </div>
        )
    }

    return (
        <div
            ref={containerRef}
            className={cn("relative flex flex-col h-full rounded-xl overflow-hidden", className)}
            style={{
                background: isDark ? "rgba(255,255,255,0.04)" : "#fff",
                border: isDark
                    ? "0.5px solid rgba(255,255,255,0.10)"
                    : "0.5px solid rgba(0,0,0,0.08)",
                boxShadow: isDark ? "none" : "0 4px 24px rgba(100,50,0,0.10)",
            }}
        >
            {/* Page badge — gold border flash when navigating to a source page */}
            <div
                className="absolute top-3 right-3 z-10 flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] font-mono"
                style={{
                    background: isDark ? "rgba(15,22,35,0.85)" : "#1B2B4B",
                    color: pageChanged ? "#C9A84C" : isDark ? "rgba(201,168,76,0.80)" : "#fff",
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    border: pageChanged
                        ? "1.5px solid rgba(201,168,76,0.70)"
                        : "1.5px solid transparent",
                    boxShadow: pageChanged ? "0 0 12px rgba(201,168,76,0.35)" : "none",
                    transition: "border-color 0.3s ease, box-shadow 0.3s ease, color 0.3s ease",
                }}
            >
                <span
                    style={{
                        display: "inline-block",
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: pageChanged
                            ? "#C9A84C"
                            : isDark
                                ? "rgba(201,168,76,0.50)"
                                : "rgba(255,255,255,0.50)",
                        transition: "background 0.3s ease",
                    }}
                />
                Page {page}
            </div>

            {/* Zoom controls + fullscreen toggle */}
            <div
                className="absolute top-3 left-3 z-10 flex items-center gap-1 rounded-md px-1.5 py-1"
                style={{
                    background: isDark ? "rgba(15,22,35,0.85)" : "#1B2B4B",
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    border: "1.5px solid transparent",
                }}
            >
                <button
                    onClick={handleZoomOut}
                    disabled={scale <= 0.5}
                    className="flex items-center justify-center size-4 disabled:opacity-30"
                    aria-label="Zoom out"
                    style={{color: isDark ? "rgba(201,168,76,0.80)" : "#fff"}}
                >
                    <ZoomOut className="size-3" />
                </button>
                <span
                    className="text-[10px] font-mono w-8 text-center select-none"
                    style={{color: isDark ? "rgba(201,168,76,0.80)" : "#fff"}}
                >
                    {zoomPct}%
                </span>
                <button
                    onClick={handleZoomIn}
                    disabled={scale >= 3.0}
                    className="flex items-center justify-center size-4 disabled:opacity-30"
                    aria-label="Zoom in"
                    style={{color: isDark ? "rgba(201,168,76,0.80)" : "#fff"}}
                >
                    <ZoomIn className="size-3" />
                </button>
                <div
                    style={{
                        width: "1px",
                        height: 10,
                        background: isDark ? "rgba(201,168,76,0.25)" : "rgba(255,255,255,0.25)",
                        margin: "0 2px",
                    }}
                />
                <button
                    onClick={handleToggleFullscreen}
                    className="flex items-center justify-center size-4"
                    aria-label="Toggle fullscreen"
                    style={{color: isDark ? "rgba(201,168,76,0.80)" : "#fff"}}
                >
                    <Maximize2 className="size-3" />
                </button>
            </div>

            {/* Loading overlay */}
            {loadState === "loading" && (
                <div
                    className="absolute inset-0 z-20 flex items-center justify-center"
                    style={{
                        background: isDark ? "rgba(15,21,32,0.80)" : "rgba(255,255,255,0.80)",
                        backdropFilter: "blur(4px)",
                    }}
                >
                    <Loader2
                        className="size-5 animate-spin"
                        style={{color: isDark ? "rgba(201,168,76,0.60)" : "#7a4a00"}}
                    />
                </div>
            )}

            {/* PDF rendered via react-pdf — multi-page scroll */}
            <div
                ref={scrollAreaRef}
                className="flex-1 overflow-auto min-h-0"
                style={{
                    WebkitOverflowScrolling: "touch",
                    touchAction: "pan-x pan-y",
                }}
            >
                {/* Only render the Document once the dedicated worker is ready */}
                {workerReady && workerRef.current && (
                    <Document
                        file={pdfUrl}
                        options={pdfOptions}
                        onLoadSuccess={handleDocumentLoadSuccess}
                        onLoadError={handleDocumentLoadError}
                        loading={null}
                        error={null}
                    >
                        {pagesToRender.map(p => {
                            const isTarget = p === page
                            return (
                                <div
                                    key={p}
                                    ref={isTarget ? targetPageRef : undefined}
                                    style={{
                                        outline: isTarget && loadState === "ok"
                                            ? "2px solid rgba(201,168,76,0.40)"
                                            : "none",
                                        marginBottom: 8,
                                    }}
                                >
                                    <Page
                                        pageNumber={p}
                                        width={containerWidth ? Math.floor(containerWidth * scale) : undefined}
                                        renderTextLayer={true}
                                        renderAnnotationLayer={true}
                                        onRenderTextLayerSuccess={isTarget ? handleTextLayerSuccess : undefined}
                                        loading={null}
                                        customTextRenderer={customTextRenderer}
                                    />
                                </div>
                            )
                        })}
                    </Document>
                )}
            </div>

            {/* Fullscreen overlay */}
            {fullscreen && (
                <div
                    className="fixed inset-0 z-[200] flex flex-col"
                    style={{
                        background: "rgba(8,14,26,0.92)",
                        backdropFilter: "blur(12px)",
                        WebkitBackdropFilter: "blur(12px)",
                    }}
                    onClick={(e) => {
                        // Close when clicking the backdrop (not the PDF content)
                        if (e.target === e.currentTarget) setFullscreen(false)
                    }}
                >
                    {/* Fullscreen header bar */}
                    <div
                        className="shrink-0 flex items-center justify-between px-4 py-2"
                        style={{
                            background: "rgba(15,22,35,0.90)",
                            borderBottom: "1px solid rgba(201,168,76,0.18)",
                        }}
                    >
                        {/* Zoom controls inside fullscreen */}
                        <div
                            className="flex items-center gap-1 rounded-md px-1.5 py-1"
                            style={{
                                background: "rgba(27,43,75,0.80)",
                                border: "1px solid rgba(201,168,76,0.20)",
                            }}
                        >
                            <button
                                onClick={handleZoomOut}
                                disabled={scale <= 0.5}
                                className="flex items-center justify-center size-5 disabled:opacity-30"
                                aria-label="Zoom out"
                                style={{color: "rgba(201,168,76,0.85)"}}
                            >
                                <ZoomOut className="size-3.5" />
                            </button>
                            <span
                                className="text-[11px] font-mono w-9 text-center select-none"
                                style={{color: "rgba(201,168,76,0.85)"}}
                            >
                                {zoomPct}%
                            </span>
                            <button
                                onClick={handleZoomIn}
                                disabled={scale >= 3.0}
                                className="flex items-center justify-center size-5 disabled:opacity-30"
                                aria-label="Zoom in"
                                style={{color: "rgba(201,168,76,0.85)"}}
                            >
                                <ZoomIn className="size-3.5" />
                            </button>
                        </div>

                        {/* Doc info */}
                        <span
                            className="text-[10px] font-mono"
                            style={{color: "rgba(201,168,76,0.55)"}}
                        >
                            {displayId} · p.{page}
                        </span>

                        {/* Close button */}
                        <button
                            onClick={() => setFullscreen(false)}
                            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors"
                            style={{
                                background: "rgba(201,168,76,0.10)",
                                border: "1px solid rgba(201,168,76,0.25)",
                                color: "rgba(201,168,76,0.80)",
                            }}
                            aria-label="Exit fullscreen"
                        >
                            <Minimize2 className="size-3.5" />
                            <span>Exit</span>
                        </button>
                    </div>

                    {/* Fullscreen scrollable PDF area */}
                    <div
                        ref={fullscreenScrollRef}
                        className="flex-1 overflow-auto min-h-0 px-4 py-4"
                        style={{
                            WebkitOverflowScrolling: "touch",
                            touchAction: "pan-x pan-y",
                        }}
                    >
                        {workerReady && workerRef.current && (
                            <Document
                                file={pdfUrl}
                                options={pdfOptions}
                                onLoadSuccess={handleDocumentLoadSuccess}
                                onLoadError={handleDocumentLoadError}
                                loading={null}
                                error={null}
                            >
                                {pagesToRender.map(p => {
                                    const isTarget = p === page
                                    return (
                                        <div
                                            key={p}
                                            ref={isTarget ? fullscreenTargetPageRef : undefined}
                                            style={{
                                                outline: isTarget && loadState === "ok"
                                                    ? "2px solid rgba(201,168,76,0.40)"
                                                    : "none",
                                                marginBottom: 8,
                                            }}
                                        >
                                            <Page
                                                pageNumber={p}
                                                width={fullscreenWidth ? Math.floor(fullscreenWidth * scale) : undefined}
                                                renderTextLayer={true}
                                                renderAnnotationLayer={true}
                                                onRenderTextLayerSuccess={isTarget ? handleTextLayerSuccess : undefined}
                                                loading={null}
                                                customTextRenderer={customTextRenderer}
                                            />
                                        </div>
                                    )
                                })}
                            </Document>
                        )}
                    </div>
                </div>
            )}

            {/* Source badge at bottom */}
            <div
                className="absolute bottom-3 left-3 right-3 flex items-center gap-1.5 rounded-md px-2.5 py-1.5"
                style={{
                    background: isDark ? "rgba(15,22,35,0.85)" : "rgba(27,43,75,0.90)",
                    backdropFilter: "blur(8px)",
                    WebkitBackdropFilter: "blur(8px)",
                    border: pageChanged
                        ? "1px solid rgba(201,168,76,0.45)"
                        : "1px solid transparent",
                    transition: "border-color 0.3s ease",
                }}
            >
                <div
                    className="size-1.5 rounded-full shrink-0"
                    style={{
                        background: "#C9A84C",
                        boxShadow: pageChanged ? "0 0 6px rgba(201,168,76,0.50)" : "none",
                        transition: "box-shadow 0.3s ease",
                    }}
                />
                <span className="text-[9px] text-white font-mono truncate">
                    {displayId} · p.{page} · {zoomPct}%
                </span>
            </div>
        </div>
    )
}
