"use client"

import {useCallback, useState} from "react"
import dynamic from "next/dynamic"
import {motion, AnimatePresence} from "motion/react"
import {X, Download, MessageSquare, Loader2, RotateCcw} from "lucide-react"
import {useColorMode} from "@/lib/color-mode"
import {useIsMobile} from "@/hooks/use-mobile"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING} from "@/lib/tokens"
import type {DocPdfViewerProps} from "./DocPdfViewerImpl"

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

// Dynamically import to avoid SSR issues with pdfjs-dist
const DocPdfViewer = dynamic<DocPdfViewerProps>(
    () => import("./DocPdfViewerImpl"),
    {
        ssr: false,
        loading: () => (
            <div style={{flex: 1, display: "flex", alignItems: "center", justifyContent: "center"}}>
                <Loader2 size={20} style={{color: "var(--strict-gold-text)", animation: "spin 1s linear infinite"}} />
            </div>
        ),
    },
)

interface DocumentViewerProps {
    open: boolean
    onClose: () => void
    /** Called when user clicks "Ask AI to modify" — closes viewer and focuses chat input */
    onAskToModify?: () => void
    chatId: string
    docId: string | null
    docName?: string
}

export function DocumentViewer({open, onClose, onAskToModify, chatId, docId, docName}: DocumentViewerProps) {
    const {isDark} = useColorMode()
    const isMobile = useIsMobile()
    const [pdfError, setPdfError] = useState(false)
    const [retryKey, setRetryKey] = useState(0)

    const pdfUrl = docId
        ? `${API_BASE}/api/chats/${encodeURIComponent(chatId)}/documents/${encodeURIComponent(docId)}/pdf`
        : null

    const handleRetry = useCallback(() => {
        setPdfError(false)
        setRetryKey(k => k + 1)
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
                        style={{
                            position: "fixed",
                            inset: 0,
                            zIndex: 60,
                            background: isDark ? "rgba(0,0,0,0.55)" : "rgba(60,30,0,0.18)",
                            backdropFilter: "blur(4px)",
                            WebkitBackdropFilter: "blur(4px)",
                        }}
                    />

                    {/* Panel */}
                    <motion.div
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
                            background: isDark
                                ? "rgba(15,21,32,0.92)"
                                : "rgba(255,250,235,0.94)",
                            backdropFilter: "blur(32px) saturate(160%)",
                            WebkitBackdropFilter: "blur(32px) saturate(160%)",
                            border: isDark
                                ? "0.5px solid rgba(255,255,255,0.10)"
                                : "0.5px solid rgba(255,255,255,0.55)",
                            boxShadow: isDark
                                ? "0 20px 80px rgba(0,0,0,0.65), inset 0 1px 0 rgba(255,255,255,0.06)"
                                : "0 16px 64px rgba(80,40,0,0.22), inset 0 1.5px 0 rgba(255,255,255,0.85)",
                            willChange: "transform",
                        }}
                    >
                        {/* Header */}
                        <div style={{
                            padding: "14px 20px",
                            borderBottom: isDark
                                ? "0.5px solid rgba(201,168,76,0.08)"
                                : "0.5px solid rgba(255,255,255,0.45)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: SPACE[3],
                            flexShrink: 0,
                            background: isDark
                                ? "rgba(255,255,255,0.02)"
                                : "rgba(255,255,255,0.12)",
                        }}>
                            <div style={{display: "flex", flexDirection: "column", gap: 2, minWidth: 0}}>
                                <span style={{
                                    fontSize: 11,
                                    fontWeight: 700,
                                    textTransform: "uppercase",
                                    letterSpacing: "0.12em",
                                    color: isDark ? "rgba(201,168,76,0.70)" : "#7a4a00",
                                    fontFamily: FONT.sans,
                                }}>
                                    Document Preview
                                </span>
                                {docName && (
                                    <span style={{
                                        fontFamily: "Georgia, serif",
                                        fontSize: TYPE_SCALE.xs,
                                        color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a",
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
                                        background: isDark ? "rgba(201,168,76,0.06)" : "rgba(196,124,0,0.06)",
                                        border: isDark
                                            ? "1px solid rgba(201,168,76,0.12)"
                                            : "0.5px solid rgba(196,124,0,0.18)",
                                        color: isDark ? "var(--strict-gold-text)" : "#7a4a00",
                                        fontFamily: FONT.sans,
                                        fontSize: TYPE_SCALE.xs,
                                        transition: `all ${TIMING.fast}`,
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
                                            background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.35)",
                                            border: isDark
                                                ? "0.5px solid rgba(255,255,255,0.10)"
                                                : "0.5px solid rgba(255,255,255,0.55)",
                                            color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.45)",
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
                                        background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.35)",
                                        border: isDark
                                            ? "0.5px solid rgba(255,255,255,0.10)"
                                            : "0.5px solid rgba(255,255,255,0.55)",
                                        cursor: "pointer",
                                        color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.45)",
                                        transition: `all ${TIMING.instant}`,
                                    }}
                                >
                                    <X size={14} strokeWidth={2} />
                                </button>
                            </div>
                        </div>

                        {/* PDF Content */}
                        {pdfError ? (
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
                                    color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a",
                                    margin: 0,
                                    textAlign: "center",
                                }}>
                                    Failed to load document. It may still be generating.
                                </p>
                                <button
                                    onClick={handleRetry}
                                    style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: SPACE[2],
                                        padding: `${SPACE[2]}px ${SPACE[4]}px`,
                                        borderRadius: RADIUS.md,
                                        cursor: "pointer",
                                        background: isDark ? "rgba(201,168,76,0.08)" : "rgba(196,124,0,0.08)",
                                        border: isDark
                                            ? "1px solid rgba(201,168,76,0.18)"
                                            : "0.5px solid rgba(196,124,0,0.22)",
                                        color: isDark ? "var(--strict-gold-text)" : "#7a4a00",
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
                                isDark={isDark}
                                onError={() => setPdfError(true)}
                            />
                        ) : (
                            <div style={{flex: 1, display: "flex", alignItems: "center", justifyContent: "center"}}>
                                <Loader2 size={20} style={{color: "var(--strict-gold-text)", animation: "spin 1s linear infinite"}} />
                            </div>
                        )}
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    )
}
