"use client"

import {useState, useRef, useEffect} from "react"
import {ChevronDown} from "lucide-react"
import {useColorMode} from "@/lib/color-mode"
import {useJurisdiction} from "@/lib/use-jurisdiction"
import {
    JURISDICTIONS,
    type Jurisdiction,
} from "@/lib/jurisdictions"

/** Builtin jurisdictions that have indexed corpora. */
const BUILTIN_JURISDICTIONS: Jurisdiction[] = ["difc", "cz", "uk", "au"]

interface CorpusCollection {
    name: string
    corpus_id: string
    doc_ids?: string[]
}

interface ComposeSelectorsProps {
    /** Custom corpora collections from /api/v1/corpora */
    corpora: CorpusCollection[]
    /** Currently selected corpora_id (null = none) */
    selectedCorporaId: string | null
    /** Callback when user selects a custom corpus */
    onCorporaIdChange: (corporaId: string | null) => void
    /** Hide when conversation has messages */
    visible: boolean
}

export function ComposeSelectors({
    corpora,
    selectedCorporaId,
    onCorporaIdChange,
    visible,
}: ComposeSelectorsProps) {
    const {jurisdiction, setJurisdiction} = useJurisdiction()
    const {isDark} = useColorMode()
    const isStrict = isDark
    const [corporaOpen, setCorporaOpen] = useState(false)
    const corporaRef = useRef<HTMLDivElement>(null)

    // Close corpora dropdown on outside click
    useEffect(() => {
        if (!corporaOpen) return
        const handler = (e: MouseEvent) => {
            if (corporaRef.current && !corporaRef.current.contains(e.target as Node)) {
                setCorporaOpen(false)
            }
        }
        document.addEventListener("mousedown", handler)
        return () => document.removeEventListener("mousedown", handler)
    }, [corporaOpen])

    if (!visible) return null

    const hasCorpora = corpora.length > 0
    const shownJurisdictions = hasCorpora
        ? [...BUILTIN_JURISDICTIONS, "custom" as Jurisdiction]
        : BUILTIN_JURISDICTIONS

    const selectedCollection = corpora.find(c => c.corpus_id === selectedCorporaId)

    return (
        <div
            style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 6,
                marginTop: 8,
            }}
        >
            {/* Jurisdiction chips */}
            {shownJurisdictions.map((key) => {
                const config = JURISDICTIONS[key]
                const isActive = jurisdiction === key
                const chipBg = isActive
                    ? `${config.color}22`
                    : isStrict
                        ? "rgba(255,255,255,0.03)"
                        : "var(--dt-button-bg)"
                const chipBorder = isActive
                    ? `${config.color}55`
                    : isStrict
                        ? "rgba(255,255,255,0.06)"
                        : "var(--dt-glass-border)"
                const chipColor = isActive
                    ? config.color
                    : isStrict
                        ? "rgba(255,255,255,0.45)"
                        : "var(--dt-text-tertiary)"

                return (
                    <button
                        key={key}
                        onClick={() => {
                            setJurisdiction(key)
                            // Clear corpora selection when switching away from custom
                            if (key !== "custom" && selectedCorporaId) {
                                onCorporaIdChange(null)
                            }
                        }}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "3px 8px",
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: isActive ? 600 : 500,
                            fontFamily: "system-ui, sans-serif",
                            background: chipBg,
                            border: `1px solid ${chipBorder}`,
                            color: chipColor,
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                            lineHeight: "16px",
                            whiteSpace: "nowrap",
                        }}
                        onMouseEnter={(e) => {
                            if (!isActive) {
                                e.currentTarget.style.borderColor = `${config.color}44`
                                e.currentTarget.style.color = config.color
                            }
                        }}
                        onMouseLeave={(e) => {
                            if (!isActive) {
                                e.currentTarget.style.borderColor = chipBorder
                                e.currentTarget.style.color = chipColor
                            }
                        }}
                    >
                        <span
                            style={{
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                fontSize: 9,
                                fontWeight: 700,
                                letterSpacing: "0.05em",
                                padding: "1px 3px",
                                borderRadius: 3,
                                background: isActive ? `${config.color}33` : `${config.color}15`,
                                color: config.color,
                                minWidth: 18,
                                lineHeight: "12px",
                            }}
                        >
                            {config.code}
                        </span>
                        {config.name}
                    </button>
                )
            })}

            {/* Corpora dropdown — only when user has custom collections AND custom jurisdiction is active */}
            {hasCorpora && jurisdiction === "custom" && (
                <div ref={corporaRef} style={{position: "relative"}}>
                    <button
                        onClick={() => setCorporaOpen(v => !v)}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "3px 8px",
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 500,
                            fontFamily: "system-ui, sans-serif",
                            background: isStrict ? "rgba(201,168,76,0.06)" : "var(--dt-button-bg)",
                            border: isStrict
                                ? "1px solid rgba(201,168,76,0.15)"
                                : "1px solid var(--dt-glass-border)",
                            color: isStrict ? "rgba(201,168,76,0.7)" : "var(--dt-text-tertiary)",
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                            lineHeight: "16px",
                            whiteSpace: "nowrap",
                            maxWidth: 180,
                        }}
                    >
                        <span style={{
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                        }}>
                            {selectedCollection?.name ?? "Select collection"}
                        </span>
                        <ChevronDown
                            size={12}
                            style={{
                                flexShrink: 0,
                                transition: "transform 0.15s",
                                transform: corporaOpen ? "rotate(180deg)" : "none",
                            }}
                        />
                    </button>

                    {corporaOpen && (
                        <div style={{
                            position: "absolute",
                            left: 0,
                            top: "calc(100% + 4px)",
                            zIndex: 50,
                            minWidth: 200,
                            maxWidth: 280,
                            borderRadius: 8,
                            overflow: "hidden",
                            background: isStrict ? "var(--strict-glass-bg)" : "var(--dt-glass-bg)",
                            backdropFilter: isStrict ? "var(--strict-glass-blur)" : "var(--dt-glass-blur)",
                            WebkitBackdropFilter: isStrict ? "var(--strict-glass-blur)" : "var(--dt-glass-blur)",
                            border: isStrict
                                ? "1px solid rgba(201,168,76,0.12)"
                                : "1px solid var(--dt-glass-border)",
                            boxShadow: isStrict
                                ? "0 4px 16px rgba(0,0,0,0.4)"
                                : "0 4px 16px rgba(0,0,0,0.12)",
                        }}>
                            {/* Clear selection option */}
                            {selectedCorporaId && (
                                <button
                                    onClick={() => {
                                        onCorporaIdChange(null)
                                        setCorporaOpen(false)
                                    }}
                                    style={{
                                        width: "100%",
                                        display: "flex",
                                        alignItems: "center",
                                        padding: "7px 10px",
                                        fontSize: 11,
                                        fontFamily: "system-ui, sans-serif",
                                        fontStyle: "italic",
                                        color: isStrict ? "rgba(255,255,255,0.4)" : "var(--dt-text-quaternary)",
                                        background: "transparent",
                                        border: "none",
                                        borderBottom: isStrict
                                            ? "1px solid rgba(255,255,255,0.04)"
                                            : "1px solid var(--dt-glass-border-subtle)",
                                        cursor: "pointer",
                                        textAlign: "left",
                                    }}
                                >
                                    All documents
                                </button>
                            )}
                            {corpora.map((c) => {
                                const isSelected = selectedCorporaId === c.corpus_id
                                return (
                                    <button
                                        key={c.corpus_id}
                                        onClick={() => {
                                            onCorporaIdChange(c.corpus_id)
                                            setCorporaOpen(false)
                                        }}
                                        style={{
                                            width: "100%",
                                            display: "flex",
                                            alignItems: "center",
                                            gap: 6,
                                            padding: "7px 10px",
                                            fontSize: 11,
                                            fontFamily: "system-ui, sans-serif",
                                            color: isSelected
                                                ? (isStrict ? "rgba(201,168,76,0.9)" : "var(--dt-accent-color)")
                                                : (isStrict ? "rgba(255,255,255,0.6)" : "var(--dt-text-secondary)"),
                                            background: isSelected
                                                ? (isStrict ? "rgba(201,168,76,0.06)" : "var(--dt-accent-tint)")
                                                : "transparent",
                                            border: "none",
                                            cursor: "pointer",
                                            textAlign: "left",
                                            transition: "background 0.1s",
                                        }}
                                        onMouseEnter={(e) => {
                                            if (!isSelected) {
                                                e.currentTarget.style.background = isStrict
                                                    ? "rgba(255,255,255,0.03)"
                                                    : "var(--dt-button-bg-hover)"
                                            }
                                        }}
                                        onMouseLeave={(e) => {
                                            if (!isSelected) {
                                                e.currentTarget.style.background = "transparent"
                                            }
                                        }}
                                    >
                                        <span style={{
                                            overflow: "hidden",
                                            textOverflow: "ellipsis",
                                            whiteSpace: "nowrap",
                                            flex: 1,
                                        }}>
                                            {c.name}
                                        </span>
                                        {isSelected && (
                                            <span style={{
                                                width: 5,
                                                height: 5,
                                                borderRadius: "50%",
                                                background: isStrict ? "rgba(201,168,76,0.7)" : "var(--dt-accent-color)",
                                                flexShrink: 0,
                                            }}/>
                                        )}
                                    </button>
                                )
                            })}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
