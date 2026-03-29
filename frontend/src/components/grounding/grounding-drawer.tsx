"use client"

import {useTheme} from "next-themes"
import {useEffect, useState} from "react"
import {motion, AnimatePresence} from "motion/react"
import {X} from "lucide-react"
import {GroundingView} from "./grounding-view"

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
    const {resolvedTheme} = useTheme()
    const [mounted, setMounted] = useState(false)
    useEffect(() => setMounted(true), [])
    const isDark = mounted && resolvedTheme === "dark"

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
                        style={{
                            position: "fixed",
                            inset: 0,
                            zIndex: 60,
                            background: isDark ? "rgba(0,0,0,0.50)" : "rgba(60,30,0,0.18)",
                            backdropFilter: "blur(4px)",
                            WebkitBackdropFilter: "blur(4px)",
                        }}
                    />

                    {/* Drawer panel */}
                    <motion.div
                        initial={{x: "100%", opacity: 0.5}}
                        animate={{x: 0, opacity: 1}}
                        exit={{x: "100%", opacity: 0}}
                        transition={{type: "spring", damping: 30, stiffness: 300, mass: 0.8}}
                        style={{
                            position: "fixed",
                            top: 8,
                            right: 8,
                            bottom: 8,
                            width: "min(90vw, 1200px)",
                            zIndex: 61,
                            display: "flex",
                            flexDirection: "column",
                            overflow: "clip",
                            borderRadius: "20px",
                            background: isDark
                                ? "rgba(15,21,32,0.88)"
                                : "rgba(255,250,235,0.92)",
                            backdropFilter: "blur(32px) saturate(160%)",
                            WebkitBackdropFilter: "blur(32px) saturate(160%)",
                            border: isDark
                                ? "0.5px solid rgba(255,255,255,0.12)"
                                : "0.5px solid rgba(255,255,255,0.50)",
                            boxShadow: isDark
                                ? "0 20px 80px rgba(0,0,0,0.60), inset 0 1px 0 rgba(255,255,255,0.08)"
                                : "0 16px 64px rgba(80,40,0,0.20), inset 0 1.5px 0 rgba(255,255,255,0.80)",
                            willChange: "transform",
                        }}
                    >
                        {/* Header */}
                        <div style={{
                            padding: "14px 20px",
                            borderBottom: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.40)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            flexShrink: 0,
                            background: isDark ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.10)",
                        }}>
              <span style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: isDark ? "rgba(201,168,76,0.80)" : "#7a4a00",
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              }}>
                Source Grounding
              </span>
                            <button
                                onClick={() => onOpenChange(false)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: 28,
                                    height: 28,
                                    borderRadius: 8,
                                    background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.30)",
                                    border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.50)",
                                    cursor: "pointer",
                                    color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.50)",
                                    transition: "all 0.12s",
                                }}
                            >
                                <X size={14} strokeWidth={2}/>
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-hidden min-h-0">
                            <GroundingView answer={answer} sources={sources} isDark={isDark}/>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    )
}
