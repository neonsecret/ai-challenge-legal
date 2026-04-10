"use client"

import {motion, AnimatePresence} from "motion/react"
import {JURISDICTIONS, type Jurisdiction} from "@/lib/jurisdictions"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING} from "@/lib/tokens"
import {V3_SPRING} from "@/lib/v3-motion"

interface CorpusWarningData {
    corpus: string
    jurisdiction: Jurisdiction
}

interface CorpusBannerProps {
    corpusWarning: CorpusWarningData | null
    onSetCorpusWarning: (w: CorpusWarningData | null) => void
    availableLaws: {id: string; name: string; name_en: string}[]
    onSetJurisdiction: (j: Jurisdiction) => void
    onSetLawPaneOpen: (open: boolean | ((prev: boolean) => boolean)) => void
    onSetHideCorpusWarning: (hide: boolean) => void
    corpusBlocked: boolean
    onSetCorpusBlocked: (blocked: boolean) => void
    onNewChat: () => void
}

export function CorpusBanner({
    corpusWarning, onSetCorpusWarning,
    availableLaws, onSetJurisdiction, onSetLawPaneOpen, onSetHideCorpusWarning,
    corpusBlocked, onSetCorpusBlocked, onNewChat,
}: CorpusBannerProps) {
    return (
        <>
            {/* ── Corpus warning banner ── */}
            {corpusWarning && (
                <div style={{
                    padding: `${SPACE[3]}px ${SPACE[5]}px`,
                    background: "var(--dt-accent-tint-subtle)",
                    border: "0.5px solid var(--dt-accent-border-color)",
                    borderRadius: 0,
                    borderBottom: "0.5px solid var(--dt-accent-glow)",
                    display: "flex",
                    alignItems: "center",
                    gap: SPACE[3],
                    flexWrap: "wrap",
                    fontSize: TYPE_SCALE.sm,
                    color: "var(--dt-text-primary)",
                    fontFamily: FONT.sans,
                    flexShrink: 0,
                }}>
                    <span>
                        Adding <strong>{JURISDICTIONS[corpusWarning.jurisdiction].name}</strong> to this conversation. Cross-jurisdiction queries may be slower.
                    </span>
                    <div style={{display: "flex", gap: SPACE[2], marginLeft: "auto"}}>
                        <button
                            onClick={() => {
                                const j = corpusWarning.jurisdiction
                                const hasLawPane = (j === "uk" || j === "au") && availableLaws.length > 0
                                onSetJurisdiction(j)
                                onSetLawPaneOpen(hasLawPane)
                                onSetCorpusWarning(null)
                            }}
                            style={{
                                fontSize: TYPE_SCALE.xs,
                                fontWeight: 600,
                                padding: `${SPACE[1]}px ${SPACE[3]}px`,
                                borderRadius: RADIUS.md,
                                cursor: "pointer",
                                background: "var(--dt-accent-glow)",
                                border: "0.5px solid var(--dt-accent-border-color)",
                                color: "var(--dt-accent-color)",
                                fontFamily: FONT.sans,
                                transition: `all ${TIMING.instant}`,
                            }}
                        >
                            Continue
                        </button>
                        <button
                            onClick={() => onSetCorpusWarning(null)}
                            style={{
                                fontSize: TYPE_SCALE.xs,
                                fontWeight: 500,
                                padding: `${SPACE[1]}px ${SPACE[3]}px`,
                                borderRadius: RADIUS.md,
                                cursor: "pointer",
                                background: "var(--dt-button-bg)",
                                border: "0.5px solid var(--dt-glass-border-subtle)",
                                color: "var(--dt-text-tertiary)",
                                fontFamily: FONT.sans,
                                transition: `all ${TIMING.instant}`,
                            }}
                        >
                            Cancel
                        </button>
                    </div>
                    <label style={{
                        fontSize: TYPE_SCALE.xs,
                        opacity: 0.55,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: SPACE[1],
                        fontFamily: FONT.sans,
                    }}>
                        <input
                            type="checkbox"
                            style={{width: SPACE[3], height: SPACE[3], cursor: "pointer"}}
                            onChange={(e) => {
                                onSetHideCorpusWarning(e.target.checked)
                                localStorage.setItem("neolex_hide_corpus_warning", e.target.checked ? "1" : "")
                            }}
                        />
                        Don&apos;t show again
                    </label>
                </div>
            )}

            {/* ── Corpus blocked banner ── */}
            <AnimatePresence>
                {corpusBlocked && (
                    <motion.div
                        initial={{opacity: 0, height: 0}}
                        animate={{opacity: 1, height: "auto"}}
                        exit={{opacity: 0, height: 0}}
                        transition={{...V3_SPRING.standard, restDelta: 0.5}}
                        style={{overflow: "hidden", flexShrink: 0}}
                    >
                        <div style={{
                            padding: `${SPACE[3]}px ${SPACE[5]}px`,
                            background: "var(--dt-error-bg-subtle)",
                            borderBottom: "0.5px solid var(--dt-error-border-subtle)",
                            fontSize: TYPE_SCALE.sm,
                            color: "var(--dt-error-text)",
                            fontFamily: FONT.sans,
                            display: "flex",
                            alignItems: "center",
                            gap: SPACE[2],
                        }}>
                            <span>Maximum 2 jurisdictions per conversation. Start a new chat to use a different corpus.</span>
                            <button
                                onClick={() => {onNewChat(); onSetCorpusBlocked(false)}}
                                style={{
                                    fontSize: TYPE_SCALE.xs,
                                    fontWeight: 600,
                                    padding: `${SPACE[1]}px ${SPACE[3]}px`,
                                    borderRadius: RADIUS.md,
                                    cursor: "pointer",
                                    marginLeft: "auto",
                                    whiteSpace: "nowrap",
                                    background: "var(--dt-error-bg-interactive)",
                                    border: "0.5px solid var(--dt-error-border-active)",
                                    color: "var(--dt-error-text)",
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.instant}`,
                                }}
                            >
                                New chat
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    )
}
