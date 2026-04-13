"use client"

import { useRef, useState, useEffect, useCallback } from "react"
import { X } from "lucide-react"
import { GroundingView } from "@/components/grounding/grounding-view"
import type { Source } from "@/components/chat/chat-message"

interface MobileSourceSheetProps {
    sources: Source[]
    answer: string
    focusDocId?: string
    focusPage?: number
    focusSeq: number
    onClose: () => void
}

/**
 * Mobile-only bottom sheet for source grounding.
 * Starts at 50% screen height; drag up to expand to full, drag down to dismiss.
 * Touch events are attached via addEventListener for passive:false support on scroll prevention.
 */
export function MobileSourceSheet({
    sources,
    answer,
    focusDocId,
    focusPage,
    focusSeq,
    onClose,
}: MobileSourceSheetProps) {
    const [expanded, setExpanded] = useState(false)
    const sheetRef = useRef<HTMLDivElement>(null)
    const handleRef = useRef<HTMLDivElement>(null)

    // Refs for drag state — avoids re-renders during gesture
    const dragStartY = useRef(0)
    const currentOffset = useRef(0)
    const isDragging = useRef(false)
    const expandedRef = useRef(false)

    // Keep expandedRef in sync with state
    useEffect(() => { expandedRef.current = expanded }, [expanded])

    const applyTransform = useCallback((offset: number, animate: boolean) => {
        const el = sheetRef.current
        if (!el) return
        el.style.transition = animate ? "transform 0.3s ease" : "none"
        el.style.transform = `translateY(${Math.max(0, offset)}px)`
    }, [])

    // Attach touch listeners to drag handle with proper cleanup
    useEffect(() => {
        const handle = handleRef.current
        if (!handle) return

        const onTouchStart = (e: TouchEvent) => {
            dragStartY.current = e.touches[0].clientY
            currentOffset.current = 0
            isDragging.current = true
            applyTransform(0, false)
        }

        const onTouchMove = (e: TouchEvent) => {
            if (!isDragging.current) return
            e.preventDefault() // prevent page scroll during drag
            const delta = e.touches[0].clientY - dragStartY.current
            currentOffset.current = delta
            applyTransform(delta, false)
        }

        const onTouchEnd = () => {
            if (!isDragging.current) return
            isDragging.current = false
            const offset = currentOffset.current
            currentOffset.current = 0

            if (offset < -80) {
                // Dragged up → expand to full screen
                setExpanded(true)
                applyTransform(0, true)
            } else if (offset > 80) {
                if (expandedRef.current) {
                    // Collapse from full → half
                    setExpanded(false)
                    applyTransform(0, true)
                } else {
                    // Dismiss from half
                    applyTransform(window.innerHeight, true)
                    setTimeout(onClose, 300)
                }
            } else {
                // Snap back
                applyTransform(0, true)
            }
        }

        handle.addEventListener("touchstart", onTouchStart, { passive: true })
        handle.addEventListener("touchmove", onTouchMove, { passive: false })
        handle.addEventListener("touchend", onTouchEnd)

        return () => {
            handle.removeEventListener("touchstart", onTouchStart)
            handle.removeEventListener("touchmove", onTouchMove)
            handle.removeEventListener("touchend", onTouchEnd)
        }
    }, [applyTransform, onClose])

    // Lock body scroll while sheet is open
    useEffect(() => {
        const prev = document.body.style.overflow
        document.body.style.overflow = "hidden"
        return () => { document.body.style.overflow = prev }
    }, [])

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: "fixed",
                    inset: 0,
                    zIndex: 199,
                    background: "rgba(0,0,0,0.55)",
                }}
            />

            {/* Sheet */}
            <div
                ref={sheetRef}
                style={{
                    position: "fixed",
                    left: 0,
                    right: 0,
                    bottom: 0,
                    height: expanded ? "100%" : "50%",
                    zIndex: 200,
                    background: "rgba(13,10,18,0.95)",
                    backdropFilter: "blur(24px)",
                    WebkitBackdropFilter: "blur(24px)",
                    borderTop: "1px solid var(--strict-glass-border)",
                    borderRadius: expanded ? 0 : "16px 16px 0 0",
                    display: "flex",
                    flexDirection: "column",
                    overflow: "hidden",
                    transition: "height 0.3s ease, border-radius 0.3s ease",
                    willChange: "transform",
                    paddingBottom: "env(safe-area-inset-bottom)",
                }}
            >
                {/* Drag handle */}
                <div
                    ref={handleRef}
                    style={{
                        display: "flex",
                        justifyContent: "center",
                        alignItems: "center",
                        padding: "12px 0 8px",
                        flexShrink: 0,
                        touchAction: "none",
                        cursor: "grab",
                    }}
                >
                    <div style={{
                        width: 24,
                        height: 3,
                        borderRadius: 1,
                        background: "rgba(201,168,76,0.3)",
                    }} />
                </div>

                {/* Header */}
                <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "4px 16px 10px",
                    borderBottom: "1px solid var(--strict-gold-border)",
                    flexShrink: 0,
                }}>
                    <span style={{
                        font: "8px/1 system-ui",
                        textTransform: "uppercase",
                        letterSpacing: "1px",
                        color: "var(--strict-gold-text)",
                    }}>
                        Source Grounding
                    </span>
                    <button
                        onClick={onClose}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: 28,
                            height: 28,
                            borderRadius: 6,
                            background: "rgba(201,168,76,0.05)",
                            border: "1px solid var(--strict-gold-border)",
                            cursor: "pointer",
                            color: "var(--strict-text-dim)",
                        }}
                    >
                        <X size={14} strokeWidth={2} />
                    </button>
                </div>

                {/* Content */}
                <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>
                    <GroundingView
                        answer={answer}
                        sources={sources}
                        isMobile={true}
                        focusDocId={focusDocId}
                        focusPage={focusPage}
                        focusSeq={focusSeq}
                    />
                </div>
            </div>
        </>
    )
}
