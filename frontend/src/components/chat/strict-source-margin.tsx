"use client"

import { motion } from "motion/react"
import { V3_SPRING } from "@/lib/v3-motion"

export interface StrictSourceMarginSource {
    id: string
    label: string
    detail: string
}

interface StrictSourceMarginProps {
    sources: StrictSourceMarginSource[]
    onSourceClick?: (id: string) => void
    visible?: boolean
    /** When true, renders inline (no fixed width/border) for the mobile bottom panel */
    mobile?: boolean
}

export function StrictSourceMargin({ sources, onSourceClick, visible = false, mobile = false }: StrictSourceMarginProps) {
    return (
        <div
            style={
                mobile
                    ? {
                          padding: "12px 14px 14px",
                      }
                    : {
                          width: 160,
                          flexShrink: 0,
                          background: "var(--strict-glass-recessed)",
                          borderLeft: "1px solid var(--strict-gold-border)",
                          padding: "18px 12px",
                          overflowY: "auto",
                      }
            }
        >
            <p
                style={{
                    color: "var(--strict-source-label)",
                    fontSize: 8,
                    letterSpacing: "0.5px",
                    textTransform: "uppercase",
                    marginBottom: 12,
                }}
            >
                SOURCES
            </p>

            {sources.length === 0 ? (
                <p
                    style={{
                        color: "var(--strict-source-text)",
                        fontSize: 9,
                        lineHeight: 1.4,
                        opacity: 0.5,
                        fontStyle: "italic",
                    }}
                >
                    Sources appear here
                </p>
            ) : (
                sources.map((src, idx) => (
                    <div key={src.id}>
                        <motion.div
                            initial={mobile
                                ? { opacity: 0, scale: 0.95, y: 8 }
                                : { opacity: 0, scale: 0.95, x: 12 }
                            }
                            animate={
                                visible
                                    ? { opacity: 1, scale: 1, x: 0, y: 0 }
                                    : mobile
                                        ? { opacity: 0, scale: 0.95, y: 8 }
                                        : { opacity: 0, scale: 0.95, x: 12 }
                            }
                            transition={{
                                ...V3_SPRING.standard,
                                delay: visible ? idx * 0.25 : 0,
                            }}
                            onClick={() => onSourceClick?.(src.id)}
                            style={{
                                cursor: onSourceClick ? "pointer" : "default",
                            }}
                        >
                            <p
                                style={{
                                    color: "var(--strict-source-num)",
                                    fontSize: 9,
                                    marginBottom: 2,
                                }}
                            >
                                {idx + 1}
                            </p>
                            <p
                                style={{
                                    color: "var(--strict-source-text)",
                                    fontSize: 9,
                                    lineHeight: 1.4,
                                }}
                            >
                                {src.label}
                            </p>
                            {src.detail && (
                                <p
                                    style={{
                                        color: "var(--strict-source-text)",
                                        fontSize: 8,
                                        lineHeight: 1.3,
                                        opacity: 0.6,
                                        marginTop: 2,
                                    }}
                                >
                                    {src.detail}
                                </p>
                            )}
                        </motion.div>

                        {idx < sources.length - 1 && (
                            <div
                                style={{
                                    height: 1,
                                    background: "var(--strict-gold-sep)",
                                    margin: "10px 0",
                                }}
                            />
                        )}
                    </div>
                ))
            )}
        </div>
    )
}
