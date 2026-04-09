"use client"

import {useState, useCallback, useEffect} from "react"
import {ExternalLink} from "lucide-react"
import {cn} from "@/lib/utils"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {SourceRef, getDomain, isSafeUrl, API_BASE} from "./grounding-utils"

/** Web content preview component — fetches and displays extracted text from a URL. */
export function WebContentPreview({source, answer, isMobile}: {
    source: SourceRef
    answer: string
    isMobile: boolean
}) {
    const [content, setContent] = useState<string | null>(null)
    const [fetchedTitle, setFetchedTitle] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const url = source.url || source.doc_id.replace(/^web:/, "")
    const displayTitle = source.title || fetchedTitle || getDomain(url)
    const domain = getDomain(url)
    const snippet = source.text || ""

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        setContent(null)

        fetch(`${API_BASE}/api/v1/proxy/web-content?url=${encodeURIComponent(url)}`, {
            credentials: "include",
        })
            .then(async (res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                return res.json()
            })
            .then((data) => {
                if (cancelled) return
                setContent(data.content || "")
                if (data.title) setFetchedTitle(data.title)
                setLoading(false)
            })
            .catch(() => {
                if (cancelled) return
                setError("Could not load page content")
                setLoading(false)
            })

        return () => { cancelled = true }
    }, [url])

    // Highlight the snippet within the full content
    const renderContentWithHighlight = useCallback((fullText: string, snippetText: string) => {
        if (!snippetText || snippetText.length < 10) {
            return <span>{fullText}</span>
        }
        // Build a whitespace-flexible regex from the snippet prefix to find it in original text
        const searchPrefix = snippetText.slice(0, 60).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+")
        const re = new RegExp(searchPrefix, "i")
        const match = fullText.match(re)
        if (!match || match.index === undefined) {
            return <span>{fullText}</span>
        }

        // Use a second regex for the full snippet to get accurate highlight length in original text
        const fullPattern = snippetText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+")
        const fullRe = new RegExp(fullPattern, "i")
        const fullMatch = fullText.match(fullRe)
        const highlightLen = fullMatch ? fullMatch[0].length : match[0].length

        const idx = match.index
        const before = fullText.slice(0, idx)
        const highlighted = fullText.slice(idx, idx + highlightLen)
        const after = fullText.slice(idx + highlightLen)

        return (
            <>
                <span>{before}</span>
                <mark style={{
                    background: "var(--dt-color-gold-tint)",
                    borderBottom: `2px solid var(--dt-color-gold-border)`,
                    borderRadius: RADIUS.xs,
                    padding: `1px ${SPACE['1']}px`,
                    color: "inherit",
                }}>{highlighted}</mark>
                <span>{after}</span>
            </>
        )
    }, [])

    return (
        <div className={cn("overflow-y-auto rounded-xl", isMobile ? "h-full p-3" : "h-full p-5")} style={{
            background: "var(--gm-surface-0, var(--dt-glass-bg-subtle))",
            border: `1px solid var(--gm-border-outer, var(--dt-glass-border-subtle))`,
            backdropFilter: "blur(10px)",
            WebkitBackdropFilter: "blur(10px)",
            boxShadow: `inset 0 0 2px 1px var(--gm-border-inner-glow, rgba(222,222,222,0.14)), 0 ${SPACE['1']}px ${SPACE['6']}px rgba(0,0,0,0.30)`,
        }}>
            {/* Header: favicon + title + domain */}
            <div style={{display: "flex", alignItems: "center", gap: SPACE['3'], marginBottom: SPACE['3']}}>
                <img
                    src={`https://icons.duckduckgo.com/ip3/${domain}.ico`}
                    alt=""
                    width={SPACE['5']}
                    height={SPACE['5']}
                    style={{borderRadius: RADIUS.xs, flexShrink: 0}}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                />
                <div style={{minWidth: 0, flex: 1}}>
                    <p style={{
                        fontSize: TYPE_SCALE.sm,
                        fontWeight: 600,
                        fontFamily: FONT.sans,
                        color: "var(--dt-text-secondary)",
                        margin: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>{displayTitle}</p>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        fontFamily: FONT.sans,
                        color: "var(--dt-text-tertiary)",
                        margin: `${SPACE['1']}px 0 0`,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>{domain}</p>
                </div>
            </div>

            {/* Open original link */}
            <a
                href={isSafeUrl(url) ? url : "#"}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: SPACE['1'],
                    fontSize: TYPE_SCALE.xs,
                    fontWeight: 500,
                    fontFamily: FONT.sans,
                    color: "var(--dt-color-gold-base)",
                    textDecoration: "none",
                    marginBottom: SPACE['4'],
                    padding: `${SPACE['1']}px ${SPACE['3']}px`,
                    borderRadius: RADIUS.sm,
                    background: "var(--dt-color-gold-tint)",
                    border: `0.5px solid var(--dt-color-gold-border)`,
                    transition: `all ${TIMING.instant} ${EASE.out}`,
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--dt-color-gold-glow)"
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = "var(--dt-color-gold-tint)"
                }}
            >
                <ExternalLink size={SPACE['3']} />
                Open original page
            </a>

            {/* Snippet preview (always shown) */}
            {snippet && (
                <div style={{
                    marginBottom: SPACE['4'],
                    padding: SPACE['3'],
                    borderRadius: RADIUS.md,
                    background: "var(--dt-color-gold-tint)",
                    borderLeft: `3px solid var(--dt-color-gold-base)`,
                }}>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        fontWeight: 700,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.10em",
                        fontFamily: FONT.sans,
                        color: "var(--dt-color-gold-base)",
                        margin: `0 0 ${SPACE['2']}px`,
                    }}>Search snippet</p>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        lineHeight: 1.65,
                        color: "var(--dt-text-secondary)",
                        fontFamily: FONT.brand,
                        margin: 0,
                    }}>{snippet}</p>
                </div>
            )}

            {/* Full page content */}
            {loading ? (
                <div style={{display: "flex", flexDirection: "column", gap: SPACE['2']}}>
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} style={{
                            height: SPACE['4'],
                            borderRadius: RADIUS.xs,
                            width: `${60 + ((i * 17) % 35)}%`,
                            background: "var(--dt-glass-bg-subtle)",
                            animation: "pulse 1.5s ease-in-out infinite",
                        }} />
                    ))}
                    <style>{`@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }`}</style>
                </div>
            ) : error ? (
                <p style={{fontSize: TYPE_SCALE.xs, color: "var(--dt-text-tertiary)", fontStyle: "italic"}}>{error}</p>
            ) : content ? (
                <div>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        fontWeight: 700,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.10em",
                        fontFamily: FONT.sans,
                        color: "var(--dt-text-tertiary)",
                        margin: `0 0 ${SPACE['2']}px`,
                    }}>Page content</p>
                    <div style={{
                        fontSize: TYPE_SCALE.sm,
                        lineHeight: 1.7,
                        color: "var(--dt-text-secondary)",
                        fontFamily: FONT.sans,
                    }}>
                        {content.split(/\n{2,}/).filter(Boolean).map((para, pi) => (
                            <p key={pi} style={{margin: `0 0 ${SPACE['3']}px`}}>
                                {renderContentWithHighlight(para.replace(/\n/g, " ").trim(), snippet)}
                            </p>
                        ))}
                    </div>
                </div>
            ) : (
                <p style={{fontSize: TYPE_SCALE.xs, color: "var(--dt-text-tertiary)", fontStyle: "italic"}}>No content could be extracted from this page.</p>
            )}
        </div>
    )
}
