"use client"

import {useRef} from "react"
import {Globe} from "lucide-react"
import {JURISDICTIONS, jurisdictionToCorpus, type Jurisdiction} from "@/lib/jurisdictions"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"

interface JurisdictionPillsProps {
    isStrict: boolean
    isMobile: boolean
    jurisdiction: Jurisdiction
    currentCorpora: string[]
    availableLaws: {id: string; name: string; name_en: string}[]
    useInternet: boolean
    onToggleInternet: () => void
    onSetJurisdiction: (j: Jurisdiction) => void
    onSetLawPaneOpen: (open: boolean | ((prev: boolean) => boolean)) => void
    onSetCorpusWarning: (w: {corpus: string; jurisdiction: Jurisdiction} | null) => void
    onSetSelectedLaws: (ids: string[] | ((prev: string[]) => string[])) => void
    hideCorpusWarning: boolean
    showCorpusBlocked: () => void
    documentCountBadge?: React.ReactNode
}

export function JurisdictionPills({
    isStrict, isMobile,
    jurisdiction, currentCorpora, availableLaws, useInternet,
    onToggleInternet, onSetJurisdiction, onSetLawPaneOpen,
    onSetCorpusWarning, onSetSelectedLaws, hideCorpusWarning, showCorpusBlocked,
    documentCountBadge,
}: JurisdictionPillsProps) {
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const longPressFiredRef = useRef(false)

    const handleJurisdictionClick = (key: Jurisdiction) => {
        if (longPressFiredRef.current) {
            longPressFiredRef.current = false
            return
        }
        if (key === "custom") {
            if (jurisdiction !== key) onSetJurisdiction(key)
            onSetLawPaneOpen(false)
            return
        }
        const newCorpus = jurisdictionToCorpus(key)
        const hasLawPane = (key === "uk" || key === "au") && availableLaws.length > 0 && jurisdiction === key

        if (currentCorpora.length === 0 || currentCorpora.includes(newCorpus)) {
            if (jurisdiction === key && hasLawPane) {
                onSetLawPaneOpen(o => !o)
            } else {
                onSetJurisdiction(key)
                if ((key === "uk" || key === "au") && availableLaws.length > 0) onSetLawPaneOpen(true)
                else onSetLawPaneOpen(false)
            }
            return
        }
        if (currentCorpora.length >= 2) { showCorpusBlocked(); return }
        if (hideCorpusWarning) {
            onSetJurisdiction(key)
            if ((key === "uk" || key === "au") && availableLaws.length > 0) onSetLawPaneOpen(true)
            else onSetLawPaneOpen(false)
        } else {
            onSetCorpusWarning({corpus: newCorpus, jurisdiction: key})
        }
    }

    const handleLongPressStart = (key: Jurisdiction) => {
        const hasLawPane = (key === "uk" || key === "au") && availableLaws.length > 0 && jurisdiction === key
        longPressFiredRef.current = false
        if (hasLawPane) {
            longPressTimerRef.current = setTimeout(() => {
                longPressFiredRef.current = true
                longPressTimerRef.current = null
                onSetSelectedLaws(availableLaws.map(l => l.id))
            }, 500)
        }
    }

    const handleLongPressEnd = () => {
        if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current)
            longPressTimerRef.current = null
        }
    }

    return (
        <div style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: isMobile ? 2 : 3,
            marginLeft: isMobile ? SPACE["1"] : SPACE["3"],
            overflowX: "auto",
            minWidth: 0,
            scrollbarWidth: "none",
            WebkitOverflowScrolling: "touch",
        }}>
            {(["difc", "cz", "uk", "au", "custom"] as Jurisdiction[]).map((key) => {
                const config = JURISDICTIONS[key]
                const isActive = jurisdiction === key

                return (
                    <button
                        key={key}
                        onClick={() => handleJurisdictionClick(key)}
                        title={config.description}
                        onMouseDown={(e) => {
                            e.currentTarget.style.transform = "scale(0.97)"
                            handleLongPressStart(key)
                        }}
                        onMouseUp={(e) => {
                            e.currentTarget.style.transform = "scale(1)"
                            handleLongPressEnd()
                        }}
                        onTouchStart={() => handleLongPressStart(key)}
                        onTouchEnd={handleLongPressEnd}
                        onContextMenu={(e) => e.preventDefault()}
                        onMouseEnter={(e) => {
                            if (!isActive) {
                                e.currentTarget.style.background = isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-pill-bg-hover)"
                                e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border-active)" : "var(--dt-glass-border)"
                            }
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.transform = "scale(1)"
                            if (!isActive) {
                                e.currentTarget.style.background = isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg)"
                                e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border)" : "var(--dt-glass-border)"
                            }
                        }}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 2,
                            fontSize: TYPE_SCALE.xs,
                            fontWeight: isActive ? (isStrict ? 400 : 700) : 500,
                            padding: isMobile ? `2px ${SPACE["2"]}px` : `3px ${SPACE["2"]}px`,
                            borderRadius: RADIUS.sm,
                            cursor: "pointer",
                            opacity: 1,
                            background: isActive
                                ? (isStrict ? "var(--strict-pill-active-bg)" : "var(--dt-color-gold-solid)")
                                : (isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg)"),
                            border: isActive
                                ? (isStrict ? "1px solid var(--strict-pill-active-border)" : "0.5px solid var(--dt-color-gold-border)")
                                : (isStrict ? "1px solid var(--strict-gold-border)" : "0.5px solid var(--dt-glass-border)"),
                            color: isActive
                                ? (isStrict ? "var(--strict-text-primary)" : "var(--dt-text-primary)")
                                : (isStrict ? "var(--strict-gold-text)" : "var(--dt-text-tertiary)"),
                            fontFamily: FONT.sans,
                            transition: `all ${TIMING.fast} ${EASE.spring}`,
                            whiteSpace: "nowrap",
                            userSelect: "none",
                            WebkitUserSelect: "none",
                        }}
                    >
                        {config.name}
                    </button>
                )
            })}

            {/* Active corpora indicator */}
            {currentCorpora.length > 0 && (
                <span style={{
                    fontSize: TYPE_SCALE.xs,
                    color: "var(--dt-text-quaternary)",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                    fontFamily: FONT.sans,
                }}>
                    {currentCorpora.join(" + ")}
                </span>
            )}

            {/* Document count badge (injected from parent) */}
            {documentCountBadge}

            {/* Internet toggle */}
            <button
                onClick={onToggleInternet}
                title={useInternet ? "Web search enabled — click to disable" : "Web search disabled — click to enable"}
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 3,
                    padding: isMobile ? `2px ${SPACE["2"]}px` : `3px ${SPACE["2"]}px`,
                    borderRadius: RADIUS.sm,
                    fontSize: TYPE_SCALE.xs,
                    fontWeight: useInternet ? (isStrict ? 400 : 700) : 500,
                    lineHeight: 1,
                    fontFamily: FONT.sans,
                    background: useInternet
                        ? (isStrict ? "var(--strict-internet-active-bg)" : "var(--dt-teal-tint)")
                        : (isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg)"),
                    border: useInternet
                        ? (isStrict ? "1px solid var(--strict-internet-active-border)" : "0.5px solid var(--dt-teal-border-color)")
                        : (isStrict ? "1px solid var(--strict-gold-border)" : "0.5px solid var(--dt-glass-border)"),
                    color: useInternet
                        ? (isStrict ? "var(--strict-gold-text)" : "var(--dt-teal-on-surface)")
                        : (isStrict ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)"),
                    cursor: "pointer",
                    transition: `all ${TIMING.fast} ${EASE.spring}`,
                    userSelect: "none",
                    WebkitUserSelect: "none",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                }}
            >
                <Globe size={TYPE_SCALE.xs} strokeWidth={useInternet ? 2 : 1.5} />
                Internet
            </button>
        </div>
    )
}
