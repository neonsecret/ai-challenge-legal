"use client"

import {Source} from "@/components/chat/use-query-stream"
import {Globe} from "lucide-react"
import {motion} from "motion/react"

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

    const chipBg = isDark ? "rgba(201,168,76,0.14)" : "rgba(120,70,0,0.08)"
    const chipBorder = isDark ? "1px solid rgba(201,168,76,0.28)" : "1px solid rgba(120,70,0,0.15)"
    const chipHoverBg = isDark ? "rgba(201,168,76,0.22)" : "rgba(120,70,0,0.14)"
    const chipHoverBorder = isDark ? "rgba(201,168,76,0.45)" : "rgba(120,70,0,0.35)"
    const badgeBg = isDark ? "#b8860b" : "#c47c00"
    const textColor = isDark ? "rgba(255,255,255,0.80)" : "rgba(120,70,0,0.75)"
    const labelColor = isDark ? "rgba(255,255,255,0.35)" : "#7a5a20"

    return (
        <div style={{marginBottom: "12px"}}>
            <p style={{
                fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.14em",
                color: labelColor, margin: "0 0 8px", fontWeight: 600,
            }}>
                Sources
            </p>
            <div style={{display: "flex", flexWrap: "wrap", gap: "6px"}}>
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

                    return (
                        <motion.button
                            key={`${source.doc_id}-${i}`}
                            initial={{opacity: 0, y: 4}}
                            animate={{opacity: 1, y: 0}}
                            transition={{duration: 0.2, delay: i * 0.08}}
                            onClick={() => onSourceClick(source)}
                            title={title}
                            style={{
                                display: "inline-flex", alignItems: "center", gap: "6px",
                                padding: "5px 12px 5px 6px", borderRadius: "9999px",
                                background: chipBg, border: chipBorder,
                                cursor: "pointer", transition: "background 0.15s ease, border-color 0.15s ease",
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.background = chipHoverBg
                                e.currentTarget.style.borderColor = chipHoverBorder
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.background = chipBg
                                e.currentTarget.style.borderColor = isDark ? "rgba(201,168,76,0.28)" : "rgba(120,70,0,0.15)"
                            }}
                        >
                            {isWeb ? (
                                <span style={{
                                    width: 18, height: 18, borderRadius: 5, background: badgeBg,
                                    color: "#fff",
                                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                                }}>
                                    <Globe size={10} />
                                </span>
                            ) : (
                                <span style={{
                                    width: 18, height: 18, borderRadius: 5, background: badgeBg,
                                    color: "#fff", fontSize: "10px", fontWeight: 700,
                                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                                }}>{i + 1}</span>
                            )}
                            <span style={{
                                fontSize: "11px", color: textColor,
                                fontFamily: isWeb ? "-apple-system, BlinkMacSystemFont, system-ui, sans-serif" : "monospace",
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
