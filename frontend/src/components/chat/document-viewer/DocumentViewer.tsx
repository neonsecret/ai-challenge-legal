"use client"

import {useCallback, useState, useEffect, useRef, useId} from "react"
import dynamic from "next/dynamic"
import {motion, AnimatePresence} from "motion/react"
import {X, Download, MessageSquare, RotateCcw} from "lucide-react"
import {useIsMobile} from "@/hooks/use-mobile"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING} from "@/lib/tokens"
import type {DocPdfViewerProps} from "./DocPdfViewerImpl"

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

function PdfLoadingSkeleton() {
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
            <div style={{
                width: "100%",
                maxWidth: 480,
                aspectRatio: "0.707",
                borderRadius: RADIUS.md,
                background: "var(--doc-skeleton-bg)",
                border: `1px solid var(--doc-skeleton-border)`,
                position: "relative",
                overflow: "hidden",
            }}>
                <div style={{
                    position: "absolute",
                    inset: 0,
                    background: "linear-gradient(90deg, transparent 0%, var(--doc-skeleton-shimmer) 50%, transparent 100%)",
                    backgroundSize: "200% 100%",
                    animation: "shimmer 1.8s ease-in-out infinite",
                }} />
            </div>
            <span style={{
                fontFamily: FONT.sans,
                fontSize: TYPE_SCALE.xs,
                color: "var(--doc-text-secondary)",
                letterSpacing: "0.04em",
            }}>
                Generating PDF&hellip;
            </span>
        </div>
    )
}

const DocPdfViewer = dynamic<DocPdfViewerProps>(
    () => import("./DocPdfViewerImpl"),
    {ssr: false, loading: () => <PdfLoadingSkeleton />},
)

interface DocumentViewerProps {
    open: boolean
    onClose: () => void
    onAskToModify?: () => void
    chatId: string
    docId: string | null
    docName?: string
}

export function DocumentViewer({open, onClose, onAskToModify, chatId, docId, docName}: DocumentViewerProps) {
    const isMobile = useIsMobile()
    const [pdfErrorKind, setPdfErrorKind] = useState<"timeout" | "error" | null>(null)
    const [retryKey, setRetryKey] = useState(0)
    const [retryDisabled, setRetryDisabled] = useState(false)
    const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const panelRef = useRef<HTMLDivElement>(null)
    const titleId = useId()

    const pdfUrl = docId
        ? `${API_BASE}/api/v1/conversations/${encodeURIComponent(chatId)}/documents/${encodeURIComponent(docId)}/pdf`
        : null

    // Escape key + focus trap
    useEffect(() => {
        if (!open) return
        const el = panelRef.current
        if (!el) return

        const FOCUSABLE = "button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])"
        // Initial focus — re-query so elements rendered after dialog open are included.
        el.querySelectorAll<HTMLElement>(FOCUSABLE)[0]?.focus()

        const handleKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") { e.preventDefault(); onClose(); return }
            if (e.key !== "Tab") return
            // Re-query live on every Tab press — DocPdfViewerImpl renders async,
            // so pagination buttons are absent from any snapshot taken at open time.
            const live = el.querySelectorAll<HTMLElement>(FOCUSABLE)
            const first = live[0]
            const last = live[live.length - 1]
            if (e.shiftKey) {
                if (document.activeElement === first) { e.preventDefault(); last?.focus() }
            } else {
                if (document.activeElement === last) { e.preventDefault(); first?.focus() }
            }
        }
        document.addEventListener("keydown", handleKey)
        return () => document.removeEventListener("keydown", handleKey)
    }, [open, onClose])

    // Cleanup retry back-off timer on unmount
    useEffect(() => () => {
        if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    }, [])

    const handleRetry = useCallback(() => {
        setPdfErrorKind(null)
        setRetryDisabled(true)
        setRetryKey(k => k + 1)
        retryTimerRef.current = setTimeout(() => setRetryDisabled(false), 12_000)
    }, [])

    const handleAskToModify = useCallback(() => {
        onClose()
        onAskToModify?.()
    }, [onClose, onAskToModify])

    return (
        <AnimatePresence>
            {open && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{opacity: 0}}
                        animate={{opacity: 1}}
                        exit={{opacity: 0}}
                        transition={{duration: 0.2}}
                        onClick={onClose}
                        aria-hidden="true"
                        style={{
                            position: "fixed",
                            inset: 0,
                            zIndex: 60,
                            background: "var(--doc-overlay-bg)",
                            backdropFilter: "blur(4px)",
                            WebkitBackdropFilter: "blur(4px)",
                        }}
                    />

                    {/* Panel */}
                    <motion.div
                        ref={panelRef}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby={titleId}
                        initial={isMobile ? {y: "100%", opacity: 0.5} : {x: "100%", opacity: 0.5}}
                        animate={isMobile ? {y: 0, opacity: 1} : {x: 0, opacity: 1}}
                        exit={isMobile ? {y: "100%", opacity: 0} : {x: "100%", opacity: 0}}
                        transition={{type: "spring", damping: 30, stiffness: 300, mass: 0.8}}
                        style={{
                            position: "fixed",
                            ...(isMobile
                                ? {left: 0, right: 0, bottom: 0, top: "5dvh", borderRadius: "20px 20px 0 0"}
                                : {top: 8, right: 8, bottom: 8, width: "min(90vw, 680px)", borderRadius: 20}),
                            zIndex: 61,
                            display: "flex",
                            flexDirection: "column",
                            overflow: "clip",
                            background: "var(--doc-panel-bg)",
                            backdropFilter: "blur(32px) saturate(160%)",
                            WebkitBackdropFilter: "blur(32px) saturate(160%)",
                            border: "0.5px solid var(--doc-panel-border)",
                            boxShadow: "var(--doc-panel-shadow)",
                            willChange: "transform",
                        }}
                    >
                        {/* Header */}
                        <div style={{
                            padding: "14px 20px",
                            borderBottom: "0.5px solid var(--doc-panel-header-border)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: SPACE[3],
                            flexShrink: 0,
                            background: "var(--doc-panel-header-bg)",
                        }}>
                            <div style={{display: "flex", flexDirection: "column", gap: 2, minWidth: 0}}>
                                <span id={titleId} style={{
                                    fontSize: 11,
                                    fontWeight: 700,
                                    textTransform: "uppercase",
                                    letterSpacing: "0.12em",
                                    color: "var(--doc-text-label)",
                                    fontFamily: FONT.sans,
                                }}>
                                    Document Preview
                                </span>
                                {docName && (
                                    <span style={{
                                        fontFamily: "Georgia, serif",
                                        fontSize: TYPE_SCALE.xs,
                                        color: "var(--doc-text-secondary)",
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                    }}>
                                        {docName}
                                    </span>
                                )}
                            </div>
                            <div style={{display: "flex", alignItems: "center", gap: SPACE[2], flexShrink: 0}}>
                                {/* Ask AI to modify */}
                                <button
                                    onClick={handleAskToModify}
                                    title="Ask AI to modify this document"
                                    style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: SPACE[1],
                                        padding: `${SPACE[1]}px ${SPACE[2]}px`,
                                        borderRadius: RADIUS.sm,
                                        cursor: "pointer",
                                        background: "var(--doc-gold-action-bg)",
                                        border: "1px solid var(--doc-gold-action-border)",
                                        color: "var(--doc-gold-action-color)",
                                        fontFamily: FONT.sans,
                                        fontSize: TYPE_SCALE.xs,
                                        transition: `all ${TIMING.fast}`,
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.background = "var(--doc-gold-action-hover-bg)"
                                        e.currentTarget.style.borderColor = "var(--doc-gold-action-hover-border)"
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.background = "var(--doc-gold-action-bg)"
                                        e.currentTarget.style.borderColor = "var(--doc-gold-action-border)"
                                    }}
                                >
                                    <MessageSquare size={12} strokeWidth={1.8} />
                                    Modify
                                </button>

                                {/* Download */}
                                {pdfUrl && (
                                    <a
                                        href={pdfUrl}
                                        download={docName ? `${docName}.pdf` : "document.pdf"}
                                        title="Download PDF"
                                        style={{
                                            display: "inline-flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            width: 28,
                                            height: 28,
                                            borderRadius: 8,
                                            background: "var(--doc-close-btn-bg)",
                                            border: "0.5px solid var(--doc-close-btn-border)",
                                            color: "var(--doc-close-btn-color)",
                                        }}
                                    >
                                        <Download size={13} strokeWidth={1.8} />
                                    </a>
                                )}

                                {/* Close */}
                                <button
                                    onClick={onClose}
                                    aria-label="Close document viewer"
                                    style={{
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        width: 28,
                                        height: 28,
                                        borderRadius: 8,
                                        background: "var(--doc-close-btn-bg)",
                                        border: "0.5px solid var(--doc-close-btn-border)",
                                        cursor: "pointer",
                                        color: "var(--doc-close-btn-color)",
                                        transition: `all ${TIMING.instant}`,
                                    }}
                                >
                                    <X size={14} strokeWidth={2} />
                                </button>
                            </div>
                        </div>

                        {/* PDF Content */}
                        {pdfErrorKind !== null ? (
                            <div style={{
                                flex: 1,
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: SPACE[4],
                                padding: SPACE[8],
                            }}>
                                <p style={{
                                    fontFamily: FONT.sans,
                                    fontSize: TYPE_SCALE.sm,
                                    color: "var(--doc-text-secondary)",
                                    margin: 0,
                                    textAlign: "center",
                                }}>
                                    {pdfErrorKind === "timeout"
                                        ? "Document generation timed out — try again in a moment."
                                        : "Could not load document. Try again."}
                                </p>
                                <button
                                    onClick={handleRetry}
                                    disabled={retryDisabled}
                                    style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: SPACE[2],
                                        padding: `${SPACE[2]}px ${SPACE[4]}px`,
                                        borderRadius: RADIUS.md,
                                        cursor: retryDisabled ? "not-allowed" : "pointer",
                                        opacity: retryDisabled ? 0.4 : 1,
                                        background: "var(--doc-retry-btn-bg)",
                                        border: "1px solid var(--doc-retry-btn-border)",
                                        color: "var(--doc-gold-action-color)",
                                        fontFamily: FONT.sans,
                                        fontSize: TYPE_SCALE.sm,
                                    }}
                                >
                                    <RotateCcw size={14} strokeWidth={1.8} />
                                    Retry
                                </button>
                            </div>
                        ) : pdfUrl ? (
                            <DocPdfViewer
                                key={retryKey}
                                pdfUrl={pdfUrl}
                                onError={(kind) => setPdfErrorKind(kind)}
                            />
                        ) : (
                            <PdfLoadingSkeleton />
                        )}
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    )
}
