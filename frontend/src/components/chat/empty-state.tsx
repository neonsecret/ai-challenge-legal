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
        before: "Jaká je výpovědní doba podle ",
        law: "zákoníku práce",
        after: "?",
        full: "Jaká je výpovědní doba podle zákoníku práce?",
    },
    {
        before: "Jak je upraveno bezdůvodné obohacení v ",
        law: "občanském zákoníku",
        after: "?",
        full: "Jak je upraveno bezdůvodné obohacení v občanském zákoníku?",
    },
]

const QUESTIONS_BY_JURISDICTION: Record<string, PresetQuestion[]> = {
    difc: DIFC_QUESTIONS,
    cz: CZ_QUESTIONS,
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
    jurisdiction?: Jurisdiction
}

export function EmptyState({
                               onSelectQuestion,
                               onPreviewQuestion,
                               previewIndex,
                               isDark = false,
                               jurisdiction = "difc"
                           }: EmptyStateProps) {
    const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
    const {t} = useI18n()
    const questions = getPresetQuestions(jurisdiction)

    const headingColor = isDark ? "rgba(255,255,255,0.90)" : "#1a0e04"
    const lawColor = isDark ? "#C9A84C" : "#c47c00"
    const textColor = isDark ? "rgba(255,255,255,0.75)" : "rgba(46,31,8,0.72)"
    const activeTextColor = isDark ? "rgba(255,255,255,0.95)" : "#1a0e04"

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
                color: headingColor,
                letterSpacing: "-0.03em",
                margin: "0 0 24px",
                transition: "color 0.3s ease",
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

                    const btnBg = active
                        ? isDark ? "rgba(255,255,255,0.16)" : "rgba(255,255,255,0.42)"
                        : isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.28)"
                    const btnBorder = active
                        ? isDark ? "0.5px solid rgba(255,255,255,0.28)" : "0.5px solid rgba(255,255,255,0.70)"
                        : isDark ? "0.5px solid rgba(255,255,255,0.16)" : "0.5px solid rgba(255,255,255,0.55)"

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
                                background: btnBg,
                                borderTop: btnBorder,
                                borderRight: btnBorder,
                                borderBottom: btnBorder,
                                borderLeft: btnBorder,
                                cursor: "pointer",
                                transition: "all 0.16s ease",
                                boxShadow: isDark
                                    ? active ? "inset 0 1px 0 rgba(255,255,255,0.15)" : "none"
                                    : active ? "inset 0 1px 0 rgba(255,255,255,0.80)" : "inset 0 1px 0 rgba(255,255,255,0.55)",
                            }}
                        >
                            <p style={{
                                fontSize: "13px",
                                lineHeight: 1.5,
                                color: active ? activeTextColor : textColor,
                                margin: 0,
                                fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                                transition: "color 0.16s ease",
                            }}>
                                {q.before}
                                <span style={{
                                    color: lawColor,
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
