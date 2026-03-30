"use client"

import {Source} from "@/components/chat/use-query-stream"
import {Globe} from "lucide-react"
import {motion} from "motion/react"
import {COLOR, FONT, TYPE_SCALE, SPACE, TIMING, EASE, TEXT_DARK, TEXT_LIGHT, RADIUS} from "@/lib/design-tokens"

/** Cubic-bezier values from EASE.out as a tuple for motion/react */
const MOTION_EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1]

/** Check if a source is a web source (doc_id starts with "web:" or has a url field). */
function isWebSource(source: Source): boolean {
    return source.doc_id.startsWith("web:") || !!source.url
}

/** Extract the domain from a URL string. */
function getDomain(url: string): string {
    try {
        return new URL(url).hostname
    } catch {
        return url.slice(0, 40)
    }
}

interface SourcesPanelProps {
    sources: Source[]
    onSourceClick: (source: Source) => void
    isDark?: boolean
}

export function SourcesPanel({sources, onSourceClick, isDark = false}: SourcesPanelProps) {
    if (!sources || sources.length === 0) return null

    const chipBg = isDark ? COLOR.gold.tint : "rgba(120,70,0,0.08)"
    const chipBorderColor = isDark ? COLOR.gold.border : "rgba(120,70,0,0.15)"
    const chipHoverBg = isDark ? "rgba(201,168,76,0.22)" : "rgba(120,70,0,0.14)"
    const chipHoverBorder = isDark ? "rgba(201,168,76,0.45)" : "rgba(120,70,0,0.35)"
    const textColor = isDark ? TEXT_DARK.secondary : TEXT_LIGHT.tertiary
    const labelColor = isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary

    return (
        <div style={{marginBottom: SPACE["3"]}}>
            <p style={{
                fontSize: TYPE_SCALE.xs - 1, textTransform: "uppercase", letterSpacing: "0.14em",
                color: labelColor, margin: `0 0 ${SPACE["2"]}px`, fontWeight: 600,
                fontFamily: FONT.sans,
            }}>
                Sources
            </p>
            <div style={{display: "flex", flexWrap: "wrap", gap: `${SPACE["1"] + 2}px`}}>
                {sources.map((source, i) => {
                    const isWeb = isWebSource(source)
                    let label: string
                    let title: string

                    if (isWeb) {
                        const webTitle = source.title || getDomain(source.url || source.doc_id.replace(/^web:/, ""))
                        label = webTitle.length > 28 ? webTitle.slice(0, 28) + "\u2026" : webTitle
                        title = source.url || source.doc_id.replace(/^web:/, "")
                    } else {
                        const displayId = source.doc_id.length > 24 ? `${source.doc_id.slice(0, 24)}\u2026` : source.doc_id
                        label = source.page_numbers.length > 0 ? `${displayId} · p.${source.page_numbers.join(", ")}` : displayId
                        title = `${source.doc_id}${source.page_numbers.length > 0 ? ` · p.${source.page_numbers.join(", ")}` : ""}`
                    }

                    const badgeBg = isWeb ? COLOR.teal.base : COLOR.gold.base

                    return (
                        <motion.button
                            key={`${source.doc_id}-${i}`}
                            initial={{opacity: 0, y: 4}}
                            animate={{opacity: 1, y: 0}}
                            transition={{duration: parseFloat(TIMING.fast), delay: i * 0.08, ease: MOTION_EASE_OUT}}
                            onClick={() => onSourceClick(source)}
                            title={title}
                            style={{
                                display: "inline-flex", alignItems: "center", gap: `${SPACE["1"] + 2}px`,
                                padding: `${SPACE["1"] + 1}px ${SPACE["3"]}px ${SPACE["1"] + 1}px ${SPACE["1"] + 2}px`,
                                borderRadius: RADIUS.full,
                                background: chipBg, border: `1px solid ${chipBorderColor}`,
                                cursor: "pointer",
                                transition: `background ${TIMING.fast} ${EASE.out}, border-color ${TIMING.fast} ${EASE.out}`,
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.background = chipHoverBg
                                e.currentTarget.style.borderColor = chipHoverBorder
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.background = chipBg
                                e.currentTarget.style.borderColor = chipBorderColor
                            }}
                        >
                            {isWeb ? (
                                <span style={{
                                    width: 18, height: 18, borderRadius: RADIUS.xs + 1, background: badgeBg,
                                    color: "#fff",
                                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                                }}>
                                    <Globe size={10} />
                                </span>
                            ) : (
                                <span style={{
                                    width: 18, height: 18, borderRadius: RADIUS.xs + 1, background: badgeBg,
                                    color: "#fff", fontSize: TYPE_SCALE.xs - 1, fontWeight: 700,
                                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                                }}>{i + 1}</span>
                            )}
                            <span style={{
                                fontSize: TYPE_SCALE.xs, color: textColor,
                                fontFamily: isWeb ? FONT.sans : FONT.mono,
                                fontWeight: 500, maxWidth: "200px",
                                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            }}>{label}</span>
                        </motion.button>
                    )
                })}
            </div>
        </div>
    )
}
