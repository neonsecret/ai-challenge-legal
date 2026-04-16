"use client"

import {useState} from "react"
import type {Jurisdiction} from "@/lib/jurisdictions"
import {useI18n} from "@/lib/i18n"

interface PresetQuestion {
    before: string
    law: string
    after: string
    full: string
}

const DIFC_QUESTIONS: PresetQuestion[] = [
    {
        before: "What is the limitation period under ",
        law: "DIFC Law No. 5 of 2005",
        after: "?",
        full: "What is the limitation period under DIFC Law No. 5 of 2005?",
    },
    {
        before: "What are the grounds for termination under ",
        law: "DIFC Employment Law",
        after: "?",
        full: "What are the grounds for termination under DIFC Employment Law?",
    },
]

const CZ_QUESTIONS: PresetQuestion[] = [
    {
        before: "Může zaměstnavatel dát výpověď z důvodu ",
        law: "nadbytečnosti",
        after: ", pokud pracovní místo fakticky zrušeno nebylo?",
        full: "Může zaměstnavatel dát výpověď zaměstnanci z důvodu nadbytečnosti, pokud pracovní místo fakticky zrušeno nebylo?",
    },
    {
        before: "Může podnikatel požadovat ochranu jako ",
        law: "slabší smluvní strana",
        after: " při nepřiměřeně vysokých úrocích ze zápůjčky?",
        full: "Může podnikatel požadovat ochranu jako slabší smluvní strana vůči jinému podnikateli při nepřiměřeně vysokých úrocích ze zápůjčky?",
    },
]

const UK_QUESTIONS: PresetQuestion[] = [
    {
        before: "What are the statutory duties of a director under the ",
        law: "Companies Act 2006",
        after: "?",
        full: "What are the statutory duties of a director under the Companies Act 2006?",
    },
    {
        before: "What constitutes unfair dismissal under the ",
        law: "Employment Rights Act 1996",
        after: "?",
        full: "What constitutes unfair dismissal under the Employment Rights Act 1996?",
    },
]

const AU_QUESTIONS: PresetQuestion[] = [
    {
        before: "What is the insolvent trading duty under the ",
        law: "Corporations Act 2001",
        after: "?",
        full: "What is the insolvent trading duty under the Corporations Act 2001?",
    },
    {
        before: "What constitutes unconscionable conduct under ",
        law: "Australian Consumer Law",
        after: "?",
        full: "What constitutes unconscionable conduct under Australian Consumer Law?",
    },
]

const QUESTIONS_BY_JURISDICTION: Record<string, PresetQuestion[]> = {
    difc: DIFC_QUESTIONS,
    cz: CZ_QUESTIONS,
    uk: UK_QUESTIONS,
    au: AU_QUESTIONS,
}

export function getPresetQuestions(jurisdiction: Jurisdiction): PresetQuestion[] {
    return QUESTIONS_BY_JURISDICTION[jurisdiction] ?? DIFC_QUESTIONS
}

// Keep backward compat for imports that use EMPTY_STATE_QUESTIONS
export const EMPTY_STATE_QUESTIONS = DIFC_QUESTIONS

interface EmptyStateProps {
    onSelectQuestion: (q: string) => void
    onPreviewQuestion: (index: number | null) => void
    previewIndex: number | null
    isDark?: boolean
    /** @deprecated isDark now covers both dark and strict modes */
    isStrict?: boolean
    jurisdiction?: Jurisdiction
}

export function EmptyState({
                               onSelectQuestion,
                               onPreviewQuestion,
                               previewIndex,
                               isDark = false,
                               isStrict,
                               jurisdiction = "difc"
                           }: EmptyStateProps) {
    const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
    const {t} = useI18n()
    const questions = getPresetQuestions(jurisdiction)
    const dark = isDark || !!isStrict

    // Dark mode (= Strict): gold glass pills with serif text
    if (dark) {
        return (
            <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "40px 4px 90px",
                textAlign: "center",
            }}>
                <h2 style={{
                    fontFamily: "Georgia, serif",
                    fontSize: "1.4rem",
                    fontWeight: "normal",
                    color: "var(--strict-text-primary)",
                    letterSpacing: "0.01em",
                    margin: "0 0 28px",
                    opacity: 0.75,
                }}>
                    {t("chat.what_can_i_help")}
                </h2>

                <div style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    width: "100%",
                    maxWidth: "520px",
                }} className="px-2 sm:px-0">
                    {questions.map((q, i) => {
                        const isHovered = hoveredIndex === i
                        const isOpen = previewIndex === i
                        const active = isOpen || isHovered

                        return (
                            <button
                                key={`${jurisdiction}-${i}`}
                                onClick={() => onPreviewQuestion(isOpen ? null : i)}
                                onMouseEnter={() => setHoveredIndex(i)}
                                onMouseLeave={() => setHoveredIndex(null)}
                                style={{
                                    width: "100%",
                                    textAlign: "left",
                                    padding: "12px 16px",
                                    borderRadius: "10px",
                                    background: active
                                        ? "var(--strict-gold-badge-bg)"
                                        : "var(--strict-glass-bg)",
                                    border: active
                                        ? "1px solid var(--strict-gold-border-active)"
                                        : "1px solid var(--strict-gold-border)",
                                    cursor: "pointer",
                                    transition: "all 0.16s ease",
                                }}
                            >
                                <p style={{
                                    fontSize: "13px",
                                    lineHeight: 1.6,
                                    color: "var(--strict-text-secondary)",
                                    margin: 0,
                                    fontFamily: "system-ui, sans-serif",
                                    transition: "color 0.16s ease",
                                }}>
                                    {q.before}
                                    <span style={{
                                        color: "var(--strict-gold-text)",
                                        textDecoration: active ? "underline" : "none",
                                        textUnderlineOffset: "2px",
                                    }}>
                                        {q.law}
                                    </span>
                                    {q.after}
                                </p>
                            </button>
                        )
                    })}
                </div>
            </div>
        )
    }

    // Light mode: warm-tinted glass pills
    return (
        <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "40px 4px 90px",
            textAlign: "center",
        }}>
            <h2 style={{
                fontFamily: "Georgia, 'Times New Roman', serif",
                fontSize: "1.5rem",
                fontWeight: 700,
                color: "#1a0e04",
                letterSpacing: "-0.03em",
                margin: "0 0 24px",
            }}>
                {t("chat.what_can_i_help")}
            </h2>

            <div style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                width: "100%",
                maxWidth: "520px",
            }} className="px-2 sm:px-0">
                {questions.map((q, i) => {
                    const isHovered = hoveredIndex === i
                    const isOpen = previewIndex === i
                    const active = isOpen || isHovered

                    return (
                        <button
                            key={`${jurisdiction}-${i}`}
                            onClick={() => onPreviewQuestion(isOpen ? null : i)}
                            onMouseEnter={() => setHoveredIndex(i)}
                            onMouseLeave={() => setHoveredIndex(null)}
                            style={{
                                width: "100%",
                                textAlign: "left",
                                padding: "13px 16px",
                                borderRadius: "14px",
                                background: active ? "rgba(255,255,255,0.42)" : "rgba(255,255,255,0.28)",
                                border: active
                                    ? "0.5px solid rgba(255,255,255,0.70)"
                                    : "0.5px solid rgba(255,255,255,0.55)",
                                cursor: "pointer",
                                transition: "all 0.16s ease",
                                boxShadow: active
                                    ? "inset 0 1px 0 rgba(255,255,255,0.80)"
                                    : "inset 0 1px 0 rgba(255,255,255,0.55)",
                            }}
                        >
                            <p style={{
                                fontSize: "13px",
                                lineHeight: 1.5,
                                color: active ? "#1a0e04" : "rgba(46,31,8,0.72)",
                                margin: 0,
                                fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                                transition: "color 0.16s ease",
                            }}>
                                {q.before}
                                <span style={{
                                    color: "#c47c00",
                                    textDecoration: active ? "underline" : "none",
                                    textUnderlineOffset: "2px",
                                    fontWeight: 500,
                                }}>
                                    {q.law}
                                </span>
                                {q.after}
                            </p>
                        </button>
                    )
                })}
            </div>
        </div>
    )
}
