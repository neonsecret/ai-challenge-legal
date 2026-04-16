"use client"

import {SquarePen, History, BookOpen} from "lucide-react"
import {type Jurisdiction} from "@/lib/jurisdictions"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {JurisdictionPills} from "./header-parts/JurisdictionPills"
import {LawSelector} from "./header-parts/LawSelector"
import {DocumentCountBadge} from "./header-parts/DocumentCountBadge"
import {CorpusBanner} from "./header-parts/CorpusBanner"

interface CorpusEntry {
    name: string
    corpus_id: string
    doc_ids?: string[]
    doc_count?: number
    indexed?: boolean
}

interface CorpusWarningData {
    corpus: string
    jurisdiction: Jurisdiction
}

export interface ChatHeaderProps {
    isStrict: boolean
    isMobile: boolean

    jurisdiction: Jurisdiction
    currentCorpora: string[]
    onSetJurisdiction: (j: Jurisdiction) => void

    useInternet: boolean
    onToggleInternet: () => void

    historyOpen: boolean
    onToggleHistory: () => void
    indexOpen: boolean
    onToggleIndex: () => void
    documentIndexCount: number

    hasMessages: boolean
    onNewChat: () => void
    onSetPreviewIndex: (i: number | null) => void

    availableLaws: {id: string; name: string; name_en: string}[]
    selectedLaws: string[]
    onSetSelectedLaws: (ids: string[] | ((prev: string[]) => string[])) => void
    lawPaneOpen: boolean
    onSetLawPaneOpen: (open: boolean | ((prev: boolean) => boolean)) => void

    corpusWarning: CorpusWarningData | null
    onSetCorpusWarning: (w: CorpusWarningData | null) => void
    hideCorpusWarning: boolean
    onSetHideCorpusWarning: (hide: boolean) => void

    corpusBlocked: boolean
    onSetCorpusBlocked: (blocked: boolean) => void
    showCorpusBlocked: () => void

    availableCorpora: CorpusEntry[]
    corporaLoading: boolean

    documentCount: number

    selectedCorporaId: string | null
    setSelectedCorporaId: (id: string | null) => void
}

export function ChatHeader({
    isStrict, isMobile,
    jurisdiction, currentCorpora, onSetJurisdiction,
    useInternet, onToggleInternet,
    historyOpen, onToggleHistory,
    indexOpen, onToggleIndex, documentIndexCount,
    hasMessages, onNewChat, onSetPreviewIndex,
    availableLaws, selectedLaws, onSetSelectedLaws, lawPaneOpen, onSetLawPaneOpen,
    corpusWarning, onSetCorpusWarning, hideCorpusWarning, onSetHideCorpusWarning,
    corpusBlocked, onSetCorpusBlocked, showCorpusBlocked,
    availableCorpora, corporaLoading,
    documentCount,
    selectedCorporaId, setSelectedCorporaId,
}: ChatHeaderProps) {
    // Derive selected collection from selectedCorporaId (single source of truth).
    // null → null, "corpusId" (no colon) → "__all__", "corpusId:name" → "name"
    const selectedCollection = selectedCorporaId === null
        ? null
        : selectedCorporaId.includes(":")
            ? selectedCorporaId.slice(selectedCorporaId.indexOf(":") + 1)
            : "__all__"

    const btnStyle = (active: boolean) => ({
        display: "flex" as const, alignItems: "center" as const, gap: SPACE[1],
        padding: `${SPACE[1]}px ${SPACE[3]}px`, borderRadius: RADIUS.md, fontSize: TYPE_SCALE.sm, fontWeight: 500,
        background: active
            ? (isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-accent-tint-subtle)")
            : (isStrict ? "var(--strict-btn-bg)" : "var(--dt-button-bg)"),
        border: active
            ? (isStrict ? "1px solid var(--strict-gold-border-active)" : "0.5px solid var(--dt-accent-border-color)")
            : (isStrict ? "1px solid var(--strict-btn-border)" : "0.5px solid var(--dt-button-border-color)"),
        color: active
            ? (isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)")
            : (isStrict ? "var(--strict-btn-text)" : "var(--dt-text-tertiary)"),
        cursor: "pointer" as const, transition: `all ${TIMING.instant}`,
        fontFamily: FONT.sans,
    })

    // pillStyle / pillHover retained for custom corpus selector
    const pillStyle = (active: boolean) => ({
        fontSize: isStrict ? TYPE_SCALE.xs : TYPE_SCALE.sm,
        fontWeight: isStrict ? 400 : (active ? 700 : 500),
        padding: `${SPACE[1]}px ${SPACE[3]}px`, borderRadius: RADIUS.sm,
        cursor: "pointer" as const, whiteSpace: "nowrap" as const, flexShrink: 0,
        userSelect: "none" as const, WebkitUserSelect: "none" as const,
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

    const truncate = (name: string, max = 25) =>
        name.length > max ? name.slice(0, max) + "\u2026" : name

    return (
        <>
            {/* ── Main header bar ── */}
            <div style={{
                padding: isMobile ? `${SPACE[3]}px ${SPACE[3]}px` : `${SPACE[4]}px ${SPACE[6]}px`,
                borderBottom: isStrict ? "1px solid var(--strict-header-border)" : "0.5px solid var(--dt-glass-border-subtle)",
                display: "flex", alignItems: "center", gap: isMobile ? SPACE[2] : SPACE[3], flexShrink: 0,
                background: isStrict ? "var(--strict-chat-header-bg)" : "var(--dt-glass-bg-subtle)",
                overflow: "visible", position: "relative", zIndex: 10,
            }}>
                {/* Logo circle */}
                <div style={{
                    width: isMobile ? 26 : 30, height: isMobile ? 26 : 30, borderRadius: "50%",
                    background: isStrict ? "transparent" : "var(--dt-accent-tint)",
                    border: isStrict ? "1px solid var(--strict-gold-border-active)" : "0.5px solid var(--dt-accent-border-color)",
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                    boxShadow: isStrict ? undefined : "inset 0 1px 0 rgba(255,255,255,0.65)",
                }}>
                    <span style={{
                        fontSize: isMobile ? TYPE_SCALE.sm : TYPE_SCALE.md,
                        fontWeight: isStrict ? "normal" : 700,
                        color: isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)",
                        lineHeight: 1,
                        fontFamily: isStrict ? "Georgia, serif" : FONT.brand,
                    }}>{isStrict ? "V" : "N"}</span>
                </div>

                {/* Brand name */}
                {!isMobile && (
                    <span style={{
                        fontWeight: isStrict ? "normal" : 700,
                        fontSize: TYPE_SCALE.md,
                        color: isStrict ? "var(--strict-text-primary)" : "var(--dt-text-primary)",
                        fontFamily: isStrict ? "Georgia, serif" : FONT.brand,
                        letterSpacing: isStrict ? "0.01em" : "-0.04em",
                    }}>
                        Vitreon Legal
                    </span>
                )}

                {/* Jurisdiction pills + document badge + internet toggle */}
                <JurisdictionPills
                    isStrict={isStrict}
                    isMobile={isMobile}
                    jurisdiction={jurisdiction}
                    currentCorpora={currentCorpora}
                    availableLaws={availableLaws}
                    useInternet={useInternet}
                    onToggleInternet={onToggleInternet}
                    onSetJurisdiction={onSetJurisdiction}
                    onSetLawPaneOpen={onSetLawPaneOpen}
                    onSetCorpusWarning={onSetCorpusWarning}
                    onSetSelectedLaws={onSetSelectedLaws}
                    hideCorpusWarning={hideCorpusWarning}
                    showCorpusBlocked={showCorpusBlocked}
                    documentCountBadge={
                        <DocumentCountBadge count={documentCount} max={3} isStrict={isStrict} />
                    }
                />

                {/* History toggle — strict mode uses sidebar rail */}
                {!isStrict && (
                    <button onClick={onToggleHistory} title="Chat history" style={btnStyle(historyOpen)}>
                        <History size={TYPE_SCALE.sm} strokeWidth={1.8} />
                    </button>
                )}

                {/* Document index toggle — hidden in strict desktop */}
                {documentIndexCount > 0 && !(isStrict && !isMobile) && (
                    <button onClick={onToggleIndex} title="Document sources index" style={{...btnStyle(indexOpen), position: "relative"}}>
                        <BookOpen size={TYPE_SCALE.sm} strokeWidth={1.8} />
                        <span style={{
                            display: "inline-flex", alignItems: "center", justifyContent: "center",
                            minWidth: SPACE[4], height: SPACE[4], borderRadius: RADIUS.md,
                            padding: `0 ${SPACE[1]}px`,
                            fontSize: TYPE_SCALE.xs, fontWeight: isStrict ? 400 : 700,
                            background: isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-accent-glow)",
                            color: isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)",
                            border: isStrict ? "1px solid var(--strict-gold-badge-border)" : undefined,
                        }}>
                            {documentIndexCount}
                        </span>
                    </button>
                )}

                {/* New chat — hidden in strict desktop */}
                {hasMessages && !(isStrict && !isMobile) && (
                    <button
                        onClick={() => {onNewChat(); onSetPreviewIndex(null)}}
                        title="New chat"
                        style={btnStyle(false)}
                        onMouseEnter={e => {
                            e.currentTarget.style.background = "var(--dt-button-bg-hover)"
                            e.currentTarget.style.color = "var(--dt-text-primary)"
                        }}
                        onMouseLeave={e => {
                            e.currentTarget.style.background = "var(--dt-button-bg)"
                            e.currentTarget.style.color = "var(--dt-text-tertiary)"
                        }}
                    >
                        <SquarePen size={TYPE_SCALE.sm} strokeWidth={1.8} />
                        New
                    </button>
                )}
            </div>

            {/* ── Corpus warning + blocked banners ── */}
            <CorpusBanner
                corpusWarning={corpusWarning}
                onSetCorpusWarning={onSetCorpusWarning}
                availableLaws={availableLaws}
                onSetJurisdiction={onSetJurisdiction}
                onSetLawPaneOpen={onSetLawPaneOpen}
                onSetHideCorpusWarning={onSetHideCorpusWarning}
                corpusBlocked={corpusBlocked}
                onSetCorpusBlocked={onSetCorpusBlocked}
                onNewChat={onNewChat}
            />

            {/* ── Law selector pills (UK/AU) ── */}
            {(jurisdiction === "uk" || jurisdiction === "au") && lawPaneOpen && availableLaws.length > 0 && (
                <LawSelector
                    isStrict={isStrict}
                    isMobile={isMobile}
                    availableLaws={availableLaws}
                    selectedLaws={selectedLaws}
                    onSetSelectedLaws={onSetSelectedLaws}
                />
            )}

            {/* ── Custom corpus collection pills (shown whenever user has collections) ── */}
            {availableCorpora.length > 0 && (
                <div style={{
                    padding: isMobile ? `${SPACE[2]}px ${SPACE[3]}px` : `${SPACE[2]}px ${SPACE[6]}px`,
                    borderBottom: isStrict ? "1px solid var(--strict-gold-border)" : "0.5px solid var(--dt-glass-border-subtle)",
                    display: "flex", alignItems: "center", gap: SPACE[2],
                    overflowX: "auto", flexShrink: 0, scrollbarWidth: "none",
                    WebkitOverflowScrolling: "touch",
                    background: isStrict ? "transparent" : "var(--dt-glass-bg-subtle)",
                }}>
                    <span style={{
                        fontSize: isStrict ? 9 : TYPE_SCALE.xs,
                        fontWeight: isStrict ? 400 : 600,
                        textTransform: "uppercase",
                        letterSpacing: isStrict ? "1.2px" : "0.08em",
                        whiteSpace: "nowrap", flexShrink: 0,
                        color: isStrict ? "var(--strict-source-label)" : "var(--dt-text-quaternary)",
                        fontFamily: isStrict ? "system-ui" : FONT.sans,
                    }}>
                        Collections
                    </span>
                    {corporaLoading ? (
                        <span style={{fontSize: TYPE_SCALE.sm, color: "var(--dt-text-quaternary)", fontFamily: FONT.sans, whiteSpace: "nowrap"}}>
                            Loading...
                        </span>
                    ) : (() => {
                        const isNoneActive = !selectedCorporaId
                        const totalDocs = availableCorpora.reduce((sum, c) => sum + (c.doc_count ?? c.doc_ids?.length ?? 0), 0)

                        return (
                            <>
                                <button
                                    key="__none__"
                                    onClick={() => {
                                        setSelectedCorporaId(null)
                                        localStorage.removeItem("neolex_selected_corpora_id")
                                        localStorage.removeItem("neolex_selected_doc_ids")
                                    }}
                                    style={pillStyle(isNoneActive)}
                                    {...pillHover(isNoneActive)}
                                >
                                    None
                                </button>
                                <button
                                    key="__all__"
                                    onClick={() => {
                                        const corpusId = availableCorpora[0]?.corpus_id ?? ""
                                        setSelectedCorporaId(corpusId)
                                        localStorage.setItem("neolex_selected_corpora_id", corpusId)
                                        localStorage.removeItem("neolex_selected_doc_ids")
                                    }}
                                    style={pillStyle(selectedCollection === "__all__" && !!selectedCorporaId)}
                                    {...pillHover(selectedCollection === "__all__" && !!selectedCorporaId)}
                                >
                                    All ({totalDocs})
                                </button>
                                {availableCorpora.map((c) => {
                                    const isActive = selectedCollection === c.name && !!selectedCorporaId
                                    const docCount = c.doc_count ?? c.doc_ids?.length ?? 0
                                    return (
                                        <button
                                            key={c.name}
                                            onClick={() => {
                                                const id = `${c.corpus_id}:${c.name}`
                                                setSelectedCorporaId(id)
                                                localStorage.setItem("neolex_selected_corpora_id", id)
                                                if (c.doc_ids?.length) localStorage.setItem("neolex_selected_doc_ids", JSON.stringify(c.doc_ids))
                                                else localStorage.removeItem("neolex_selected_doc_ids")
                                            }}
                                            title={`${c.name} (${docCount} ${docCount === 1 ? "doc" : "docs"})`}
                                            style={pillStyle(isActive)}
                                            {...pillHover(isActive)}
                                        >
                                            {truncate(c.name)}{docCount > 0 ? ` (${docCount})` : ""}
                                        </button>
                                    )
                                })}
                            </>
                        )
                    })()}
                </div>
            )}
        </>
    )
}
