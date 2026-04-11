"use client"

import {useRef} from "react"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"

interface Law {
    id: string
    name: string
    name_en: string
}

interface LawSelectorProps {
    isStrict: boolean
    isMobile: boolean
    availableLaws: Law[]
    selectedLaws: string[]
    onSetSelectedLaws: (ids: string[] | ((prev: string[]) => string[])) => void
}

export function LawSelector({isStrict, isMobile, availableLaws, selectedLaws, onSetSelectedLaws}: LawSelectorProps) {
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const longPressFiredRef = useRef(false)

    const handleLongPressEnd = () => {
        if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current)
            longPressTimerRef.current = null
        }
    }

    const pillStyle = (active: boolean) => ({
        fontSize: isStrict ? TYPE_SCALE.xs : TYPE_SCALE.sm,
        fontWeight: isStrict ? 400 : (active ? 700 : 500),
        padding: `${SPACE["1"]}px ${SPACE["3"]}px`,
        borderRadius: RADIUS.sm,
        cursor: "pointer" as const,
        whiteSpace: "nowrap" as const,
        flexShrink: 0,
        userSelect: "none" as const,
        WebkitUserSelect: "none" as const,
        background: active
            ? (isStrict ? "var(--strict-pill-active-bg)" : "var(--dt-color-gold-solid)")
            : (isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg-subtle)"),
        border: active
            ? (isStrict ? "1px solid var(--strict-pill-active-border)" : "0.5px solid var(--dt-color-gold-border)")
            : (isStrict ? "1px solid var(--strict-gold-border)" : "0.5px solid var(--dt-pill-border-color)"),
        color: active
            ? (isStrict ? "var(--strict-text-primary)" : "var(--dt-text-primary)")
            : (isStrict ? "var(--strict-gold-text)" : "var(--dt-text-tertiary)"),
        fontFamily: FONT.sans,
        transition: `all ${TIMING.fast} ${EASE.spring}`,
    })

    const pillHover = (active: boolean) => ({
        onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => {
            if (!active) {
                e.currentTarget.style.background = isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-glass-bg-hover)"
                e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border-active)" : "var(--dt-glass-border)"
            }
        },
        onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => {
            if (!active) {
                e.currentTarget.style.background = isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg-subtle)"
                e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border)" : "var(--dt-pill-border-color)"
            }
        },
    })

    return (
        <div style={{
            padding: isMobile ? `${SPACE["1"]}px ${SPACE["3"]}px` : `${SPACE["1"]}px ${SPACE["6"]}px`,
            borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
            display: "flex",
            alignItems: "center",
            gap: isMobile ? 3 : SPACE["1"],
            overflowX: "auto",
            flexShrink: 0,
            scrollbarWidth: "none",
            WebkitOverflowScrolling: "touch",
            background: "var(--dt-glass-bg-subtle)",
        }}>
            <span style={{
                fontSize: TYPE_SCALE.xs,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                whiteSpace: "nowrap",
                flexShrink: 0,
                color: "var(--dt-text-quaternary)",
                fontFamily: FONT.sans,
            }}>
                {selectedLaws.length === availableLaws.length ? "All" : `${selectedLaws.length}/${availableLaws.length}`}
            </span>
            {availableLaws.map((law) => {
                const isActive = selectedLaws.includes(law.id)
                return (
                    <button
                        key={law.id}
                        onClick={() => {
                            if (longPressFiredRef.current) { longPressFiredRef.current = false; return }
                            onSetSelectedLaws(prev =>
                                prev.includes(law.id) ? prev.filter(l => l !== law.id) : [...prev, law.id]
                            )
                        }}
                        onMouseDown={() => {
                            longPressFiredRef.current = false
                            longPressTimerRef.current = setTimeout(() => {
                                longPressFiredRef.current = true
                                onSetSelectedLaws([law.id])
                                longPressTimerRef.current = null
                            }, 500)
                        }}
                        onMouseUp={handleLongPressEnd}
                        onTouchStart={() => {
                            longPressFiredRef.current = false
                            longPressTimerRef.current = setTimeout(() => {
                                longPressFiredRef.current = true
                                onSetSelectedLaws([law.id])
                                longPressTimerRef.current = null
                            }, 500)
                        }}
                        onTouchEnd={handleLongPressEnd}
                        onContextMenu={(e) => e.preventDefault()}
                        title={law.name_en}
                        style={pillStyle(isActive)}
                        {...pillHover(isActive)}
                    >
                        {law.name}
                    </button>
                )
            })}
            {selectedLaws.length < availableLaws.length && (
                <button
                    onClick={() => onSetSelectedLaws(availableLaws.map(l => l.id))}
                    title="Select all laws"
                    style={{
                        ...pillStyle(false),
                        background: "var(--dt-pill-bg)",
                        border: "0.5px solid var(--dt-glass-border)",
                        color: "var(--dt-text-tertiary)",
                    }}
                >
                    All
                </button>
            )}
        </div>
    )
}
