"use client"

import {motion, AnimatePresence} from "motion/react"
import {X} from "lucide-react"
import {GroundingView} from "./grounding-view"
import {useIsMobile} from "@/hooks/use-mobile"
import {RADIUS, TIMING} from "@/lib/tokens"

interface SourceRef {
    doc_id: string
    page_numbers: number[]
}

interface GroundingDrawerProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    answer: string
    sources: SourceRef[]
}

export function GroundingDrawer({
                                    open,
                                    onOpenChange,
                                    answer,
                                    sources,
                                }: GroundingDrawerProps) {
    const isMobile = useIsMobile()

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
                        onClick={() => onOpenChange(false)}
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

                    {/* Drawer panel */}
                    <motion.div
                        initial={isMobile ? {y: "100%", opacity: 0.5} : {x: "100%", opacity: 0.5}}
                        animate={isMobile ? {y: 0, opacity: 1} : {x: 0, opacity: 1}}
                        exit={isMobile ? {y: "100%", opacity: 0} : {x: "100%", opacity: 0}}
                        transition={{type: "spring", damping: 30, stiffness: 300, mass: 0.8}}
                        style={{
                            position: "fixed",
                            ...(isMobile
                                ? {
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    top: "15dvh",
                                    borderRadius: "20px 20px 0 0",
                                    paddingLeft: "env(safe-area-inset-left)",
                                    paddingRight: "env(safe-area-inset-right)",
                                }
                                : {top: 8, right: 8, bottom: 8, width: "min(90vw, 1200px)", borderRadius: 20}),
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
                            flexShrink: 0,
                            background: "var(--doc-panel-header-bg)",
                        }}>
                            <span style={{
                                fontSize: 12,
                                fontWeight: 700,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: "var(--doc-text-label)",
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                            }}>
                                Source Grounding
                            </span>
                            <button
                                onClick={() => onOpenChange(false)}
                                aria-label="Close source grounding"
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: 44,
                                    height: 44,
                                    borderRadius: RADIUS.md,
                                    background: "var(--doc-close-btn-bg)",
                                    border: "0.5px solid var(--doc-close-btn-border)",
                                    cursor: "pointer",
                                    color: "var(--doc-close-btn-color)",
                                    transition: `all ${TIMING.instant}`,
                                    flexShrink: 0,
                                }}
                            >
                                <X size={14} strokeWidth={2}/>
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-hidden min-h-0">
                            <GroundingView answer={answer} sources={sources}/>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    )
}
