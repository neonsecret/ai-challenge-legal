"use client"

import {Source} from "@/components/chat/use-query-stream"
import {Globe} from "lucide-react"
import {motion} from "motion/react"
import {FONT, TYPE_SCALE, SPACE, TIMING, EASE, RADIUS} from "@/lib/tokens"
import {V3_BUTTON_PRESS} from "@/lib/v3-motion"
import {useColorMode} from "@/lib/color-mode"

/** Cubic-bezier values from EASE.out as a tuple for motion/react */
const MOTION_EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1]

/** Check if a source is a web source (doc_id starts with "web:" or has a url field). */
function isWebSource(source: Source): boolean {
    return source.doc_id.startsWith("web:") || !!source.url
}

/** Extract a corpus name from a doc_id for v3-source-card data attribute. */
function getCorpus(doc_id: string): string {
    if (doc_id.startsWith("web:")) return "web"
    const parts = doc_id.split("/")
    return parts[0] || "custom"
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
    /** @deprecated Theme is now handled via CSS variables */
    isDark?: boolean
}

export function SourcesPanel({sources, onSourceClick}: SourcesPanelProps) {
    const {isDark: isV3} = useColorMode()

    if (!sources || sources.length === 0) return null

    return (
        <div style={{marginBottom: SPACE["3"]}}>
            <p style={{
                fontSize: TYPE_SCALE.xs - 1, textTransform: "uppercase", letterSpacing: "0.14em",
                color: "var(--dt-text-tertiary)", margin: `0 0 ${SPACE["2"]}px`, fontWeight: 600,
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

                    const badgeBg = isWeb ? "var(--dt-color-teal-base)" : "var(--dt-color-gold-base)"

                    return (
                        <motion.button
                            key={`${source.doc_id}-${i}`}
                            className={isV3 ? "v3-source-card" : ""}
                            data-corpus={isV3 ? getCorpus(source.doc_id) : undefined}
                            initial={{opacity: 0, y: 4}}
                            animate={{opacity: 1, y: 0}}
                            transition={{duration: parseFloat(TIMING.fast), delay: i * 0.08, ease: MOTION_EASE_OUT}}
                            {...V3_BUTTON_PRESS}
                            onClick={() => onSourceClick(source)}
                            aria-label={title}
                            title={title}
                            style={{
                                display: "inline-flex", alignItems: "center", gap: `${SPACE["1"] + 2}px`,
                                padding: `${SPACE["1"] + 1}px ${SPACE["3"]}px ${SPACE["1"] + 1}px ${SPACE["1"] + 2}px`,
                                borderRadius: isV3 ? "8px" : RADIUS.full,
                                background: "var(--dt-chip-bg)",
                                border: "1px solid var(--dt-chip-border)",
                                backdropFilter: isV3 ? "blur(15px)" : undefined,
                                WebkitBackdropFilter: isV3 ? "blur(15px)" : undefined,
                                boxShadow: isV3 ? "inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 8px rgba(0,0,0,0.20)" : undefined,
                                cursor: "pointer",
                                transition: `background ${TIMING.fast} ${EASE.out}, border-color ${TIMING.fast} ${EASE.out}, box-shadow ${TIMING.fast} ${EASE.out}`,
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.background = "var(--dt-chip-hover-bg)"
                                e.currentTarget.style.borderColor = "var(--dt-chip-hover-border)"
                                if (isV3) e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.08), 0 4px 16px rgba(0,0,0,0.30)"
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.background = "var(--dt-chip-bg)"
                                e.currentTarget.style.borderColor = "var(--dt-chip-border)"
                                if (isV3) e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 8px rgba(0,0,0,0.20)"
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
                                fontSize: TYPE_SCALE.xs, color: "var(--dt-text-secondary)",
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
