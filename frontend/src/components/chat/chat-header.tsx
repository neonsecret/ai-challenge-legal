"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { SquarePen, History, BookOpen, Globe } from "lucide-react";
import { JURISDICTIONS, jurisdictionToCorpus, type Jurisdiction } from "@/lib/jurisdictions";
import { FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE } from "@/lib/tokens";
import { V3_SPRING } from "@/lib/v3-motion";

interface CorpusEntry {
    name: string;
    corpus_id: string;
    doc_ids?: string[];
    doc_count?: number;
    indexed?: boolean;
}

interface CorpusWarningData {
    corpus: string;
    jurisdiction: Jurisdiction;
}

export interface ChatHeaderProps {
    isStrict: boolean;
    isMobile: boolean;

    jurisdiction: Jurisdiction;
    currentCorpora: string[];
    onSetJurisdiction: (j: Jurisdiction) => void;

    useInternet: boolean;
    onToggleInternet: () => void;

    historyOpen: boolean;
    onToggleHistory: () => void;
    indexOpen: boolean;
    onToggleIndex: () => void;
    documentIndexCount: number;

    hasMessages: boolean;
    onNewChat: () => void;
    onSetPreviewIndex: (i: number | null) => void;

    availableLaws: { id: string; name: string; name_en: string }[];
    selectedLaws: string[];
    onSetSelectedLaws: (ids: string[] | ((prev: string[]) => string[])) => void;
    lawPaneOpen: boolean;
    onSetLawPaneOpen: (open: boolean | ((prev: boolean) => boolean)) => void;

    corpusWarning: CorpusWarningData | null;
    onSetCorpusWarning: (w: CorpusWarningData | null) => void;
    hideCorpusWarning: boolean;
    onSetHideCorpusWarning: (hide: boolean) => void;

    corpusBlocked: boolean;
    onSetCorpusBlocked: (blocked: boolean) => void;
    showCorpusBlocked: () => void;

    availableCorpora: CorpusEntry[];
    corporaLoading: boolean;
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
}: ChatHeaderProps) {
    const router = useRouter();
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const longPressFiredRef = useRef(false);

    const handleJurisdictionClick = (key: Jurisdiction) => {
        if (longPressFiredRef.current) {
            longPressFiredRef.current = false;
            return;
        }
        if (key === "custom") {
            if (jurisdiction !== key) onSetJurisdiction(key);
            onSetLawPaneOpen(false);
            return;
        }
        const newCorpus = jurisdictionToCorpus(key);
        const hasLawPane = (key === "uk" || key === "au") && availableLaws.length > 0 && jurisdiction === key;

        if (currentCorpora.length === 0 || currentCorpora.includes(newCorpus)) {
            if (jurisdiction === key && hasLawPane) {
                onSetLawPaneOpen(o => !o);
            } else {
                onSetJurisdiction(key);
                if ((key === "uk" || key === "au") && availableLaws.length > 0) onSetLawPaneOpen(true);
                else onSetLawPaneOpen(false);
            }
            return;
        }
        if (currentCorpora.length >= 2) { showCorpusBlocked(); return; }
        if (hideCorpusWarning) {
            onSetJurisdiction(key);
            if ((key === "uk" || key === "au") && availableLaws.length > 0) onSetLawPaneOpen(true);
            else onSetLawPaneOpen(false);
        } else {
            onSetCorpusWarning({ corpus: newCorpus, jurisdiction: key });
        }
    };

    const handleLongPressStart = (key: Jurisdiction) => {
        const hasLawPane = (key === "uk" || key === "au") && availableLaws.length > 0 && jurisdiction === key;
        longPressFiredRef.current = false;
        if (hasLawPane) {
            longPressTimerRef.current = setTimeout(() => {
                longPressFiredRef.current = true;
                onSetSelectedLaws(availableLaws.map(l => l.id));
                longPressTimerRef.current = null;
            }, 500);
        }
    };

    const handleLongPressEnd = () => {
        if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current);
            longPressTimerRef.current = null;
        }
    };

    const btnStyle = (active: boolean) => ({
        display: "flex" as const, alignItems: "center" as const, gap: SPACE["1"],
        padding: `${SPACE["1"]}px ${SPACE["3"]}px`, borderRadius: RADIUS.md, fontSize: TYPE_SCALE.sm, fontWeight: 500,
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
    });

    const pillStyle = (active: boolean) => ({
        fontSize: TYPE_SCALE.sm, fontWeight: active ? 700 : 500,
        padding: `${SPACE["1"]}px ${SPACE["3"]}px`, borderRadius: RADIUS.sm,
        cursor: "pointer" as const, whiteSpace: "nowrap" as const, flexShrink: 0,
        userSelect: "none" as const, WebkitUserSelect: "none" as const,
        background: active ? "var(--dt-color-gold-solid)" : "var(--dt-pill-bg-subtle)",
        border: active ? "0.5px solid var(--dt-color-gold-border)" : "0.5px solid var(--dt-pill-border-color)",
        color: active ? "var(--dt-text-primary)" : "var(--dt-text-tertiary)",
        fontFamily: FONT.sans,
        transition: `all ${TIMING.fast} ${EASE.spring}`,
    });

    const pillHover = (active: boolean) => ({
        onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => {
            if (!active) {
                e.currentTarget.style.background = "var(--dt-glass-bg-hover)";
                e.currentTarget.style.borderColor = "var(--dt-glass-border)";
            }
        },
        onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => {
            if (!active) {
                e.currentTarget.style.background = "var(--dt-pill-bg-subtle)";
                e.currentTarget.style.borderColor = "var(--dt-pill-border-color)";
            }
        },
    });

    const truncate = (name: string, max = 25) =>
        name.length > max ? name.slice(0, max) + "\u2026" : name;

    return (
        <>
            {/* ── Main header bar ── */}
            <div style={{
                padding: isMobile ? `${SPACE["3"]}px ${SPACE["3"]}px` : `${SPACE["4"]}px ${SPACE["6"]}px`,
                borderBottom: isStrict ? "1px solid var(--strict-header-border)" : "0.5px solid var(--dt-glass-border-subtle)",
                display: "flex", alignItems: "center", gap: isMobile ? SPACE["2"] : SPACE["3"], flexShrink: 0,
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

                {/* Jurisdiction pills + Internet toggle */}
                <div style={{
                    flex: 1, display: "flex", alignItems: "center",
                    gap: isMobile ? 2 : 3,
                    marginLeft: isMobile ? SPACE["1"] : SPACE["3"],
                    overflowX: "auto", minWidth: 0, scrollbarWidth: "none",
                    WebkitOverflowScrolling: "touch",
                }}>
                    {(["difc", "cz", "uk", "au", "custom"] as Jurisdiction[]).map((key) => {
                        const config = JURISDICTIONS[key];
                        const isActive = jurisdiction === key;
                        const isEnabled = true;
                        const hasLawPane = (key === "uk" || key === "au") && availableLaws.length > 0 && jurisdiction === key;

                        return (
                            <button
                                key={key}
                                disabled={!isEnabled}
                                onClick={() => handleJurisdictionClick(key)}
                                title={config.description}
                                onMouseDown={(e) => {
                                    if (isEnabled) e.currentTarget.style.transform = "scale(0.97)";
                                    handleLongPressStart(key);
                                }}
                                onMouseUp={(e) => {
                                    e.currentTarget.style.transform = "scale(1)";
                                    handleLongPressEnd();
                                }}
                                onTouchStart={() => handleLongPressStart(key)}
                                onTouchEnd={handleLongPressEnd}
                                onContextMenu={(e) => e.preventDefault()}
                                onMouseEnter={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.background = isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-pill-bg-hover)";
                                        e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border-active)" : "var(--dt-glass-border)";
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.transform = "scale(1)";
                                    if (!isActive) {
                                        e.currentTarget.style.background = isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg)";
                                        e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border)" : "var(--dt-glass-border)";
                                    }
                                }}
                                style={{
                                    display: "inline-flex", alignItems: "center", gap: 2,
                                    fontSize: TYPE_SCALE.xs, fontWeight: isActive ? (isStrict ? 400 : 700) : 500,
                                    padding: isMobile ? `2px ${SPACE["2"]}px` : `3px ${SPACE["2"]}px`, borderRadius: RADIUS.sm,
                                    cursor: "pointer", opacity: 1,
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
                                    whiteSpace: "nowrap", userSelect: "none", WebkitUserSelect: "none",
                                }}
                            >
                                {config.name}
                            </button>
                        );
                    })}

                    {/* Active corpora indicator */}
                    {currentCorpora.length > 0 && (
                        <span style={{
                            fontSize: TYPE_SCALE.xs, color: "var(--dt-text-quaternary)",
                            whiteSpace: "nowrap", flexShrink: 0, fontFamily: FONT.sans,
                        }}>
                            {currentCorpora.join(" + ")}
                        </span>
                    )}

                    {/* Internet toggle */}
                    <button
                        onClick={onToggleInternet}
                        title={useInternet ? "Web search enabled — click to disable" : "Web search disabled — click to enable"}
                        style={{
                            display: "inline-flex", alignItems: "center", gap: 3,
                            padding: isMobile ? `2px ${SPACE["2"]}px` : `3px ${SPACE["2"]}px`, borderRadius: RADIUS.sm,
                            fontSize: TYPE_SCALE.xs, fontWeight: useInternet ? (isStrict ? 400 : 700) : 500, lineHeight: 1,
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
                            cursor: "pointer", transition: `all ${TIMING.fast} ${EASE.spring}`,
                            userSelect: "none", WebkitUserSelect: "none", whiteSpace: "nowrap", flexShrink: 0,
                        }}
                    >
                        <Globe size={TYPE_SCALE.xs} strokeWidth={useInternet ? 2 : 1.5} />
                        Internet
                    </button>
                </div>

                {/* History toggle */}
                <button
                    onClick={onToggleHistory}
                    title="Chat history"
                    style={btnStyle(historyOpen)}
                    onMouseEnter={e => { if (!historyOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border-hover)"; }}
                    onMouseLeave={e => { if (!historyOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border)"; }}
                >
                    <History size={TYPE_SCALE.sm} strokeWidth={1.8} />
                </button>

                {/* Document index toggle */}
                {documentIndexCount > 0 && (
                    <button
                        onClick={onToggleIndex}
                        title="Document sources index"
                        style={{ ...btnStyle(indexOpen), position: "relative" }}
                        onMouseEnter={e => { if (!indexOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border-hover)"; }}
                        onMouseLeave={e => { if (!indexOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border)"; }}
                    >
                        <BookOpen size={TYPE_SCALE.sm} strokeWidth={1.8} />
                        <span style={{
                            display: "inline-flex", alignItems: "center", justifyContent: "center",
                            minWidth: SPACE["4"], height: SPACE["4"], borderRadius: RADIUS.md,
                            padding: `0 ${SPACE["1"]}px`,
                            fontSize: TYPE_SCALE.xs, fontWeight: isStrict ? 400 : 700,
                            background: isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-accent-glow)",
                            color: isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)",
                            border: isStrict ? "1px solid var(--strict-gold-badge-border)" : undefined,
                        }}>
                            {documentIndexCount}
                        </span>
                    </button>
                )}

                {/* New chat */}
                {hasMessages && (
                    <button
                        onClick={() => { onNewChat(); onSetPreviewIndex(null); }}
                        title="New chat"
                        style={btnStyle(false)}
                        onMouseEnter={e => {
                            if (isStrict) { e.currentTarget.style.borderColor = "var(--strict-btn-border-hover)"; e.currentTarget.style.color = "var(--strict-text-secondary)"; }
                            else { e.currentTarget.style.background = "var(--dt-button-bg-hover)"; e.currentTarget.style.color = "var(--dt-text-primary)"; }
                        }}
                        onMouseLeave={e => {
                            if (isStrict) { e.currentTarget.style.borderColor = "var(--strict-btn-border)"; e.currentTarget.style.color = "var(--strict-btn-text)"; }
                            else { e.currentTarget.style.background = "var(--dt-button-bg)"; e.currentTarget.style.color = "var(--dt-text-tertiary)"; }
                        }}
                    >
                        <SquarePen size={TYPE_SCALE.sm} strokeWidth={1.8} />
                        New
                    </button>
                )}
            </div>

            {/* ── Corpus warning banner ── */}
            {corpusWarning && (
                <div style={{
                    padding: `${SPACE["3"]}px ${SPACE["5"]}px`,
                    background: "var(--dt-accent-tint-subtle)",
                    border: "0.5px solid var(--dt-accent-border-color)",
                    borderRadius: 0, borderBottom: "0.5px solid var(--dt-accent-glow)",
                    display: "flex", alignItems: "center", gap: SPACE["3"], flexWrap: "wrap",
                    fontSize: TYPE_SCALE.sm, color: "var(--dt-text-primary)", fontFamily: FONT.sans, flexShrink: 0,
                }}>
                    <span>
                        Adding <strong>{JURISDICTIONS[corpusWarning.jurisdiction].name}</strong> to this conversation. Cross-jurisdiction queries may be slower.
                    </span>
                    <div style={{ display: "flex", gap: SPACE["2"], marginLeft: "auto" }}>
                        <button
                            onClick={() => {
                                const j = corpusWarning.jurisdiction;
                                const hasLawPane = (j === "uk" || j === "au") && availableLaws.length > 0;
                                onSetJurisdiction(j);
                                onSetLawPaneOpen(hasLawPane);
                                onSetCorpusWarning(null);
                            }}
                            style={{
                                fontSize: TYPE_SCALE.xs, fontWeight: 600,
                                padding: `${SPACE["1"]}px ${SPACE["3"]}px`, borderRadius: RADIUS.md, cursor: "pointer",
                                background: "var(--dt-accent-glow)", border: "0.5px solid var(--dt-accent-border-color)",
                                color: "var(--dt-accent-color)", fontFamily: FONT.sans, transition: `all ${TIMING.instant}`,
                            }}
                        >
                            Continue
                        </button>
                        <button
                            onClick={() => onSetCorpusWarning(null)}
                            style={{
                                fontSize: TYPE_SCALE.xs, fontWeight: 500,
                                padding: `${SPACE["1"]}px ${SPACE["3"]}px`, borderRadius: RADIUS.md, cursor: "pointer",
                                background: "var(--dt-button-bg)", border: "0.5px solid var(--dt-glass-border-subtle)",
                                color: "var(--dt-text-tertiary)", fontFamily: FONT.sans, transition: `all ${TIMING.instant}`,
                            }}
                        >
                            Cancel
                        </button>
                    </div>
                    <label style={{
                        fontSize: TYPE_SCALE.xs, opacity: 0.55, cursor: "pointer",
                        display: "flex", alignItems: "center", gap: SPACE["1"], fontFamily: FONT.sans,
                    }}>
                        <input
                            type="checkbox"
                            style={{ width: SPACE["3"], height: SPACE["3"], cursor: "pointer" }}
                            onChange={(e) => {
                                onSetHideCorpusWarning(e.target.checked);
                                localStorage.setItem("neolex_hide_corpus_warning", e.target.checked ? "1" : "");
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
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ ...V3_SPRING.standard, restDelta: 0.5 }}
                        style={{ overflow: "hidden", flexShrink: 0 }}
                    >
                        <div style={{
                            padding: `${SPACE["3"]}px ${SPACE["5"]}px`,
                            background: "var(--dt-error-bg-subtle)", borderBottom: "0.5px solid var(--dt-error-border-subtle)",
                            fontSize: TYPE_SCALE.sm, color: "var(--dt-error-text)", fontFamily: FONT.sans,
                            display: "flex", alignItems: "center", gap: SPACE["2"],
                        }}>
                            <span>Maximum 2 jurisdictions per conversation. Start a new chat to use a different corpus.</span>
                            <button
                                onClick={() => { onNewChat(); onSetCorpusBlocked(false); }}
                                style={{
                                    fontSize: TYPE_SCALE.xs, fontWeight: 600,
                                    padding: `${SPACE["1"]}px ${SPACE["3"]}px`, borderRadius: RADIUS.md,
                                    cursor: "pointer", marginLeft: "auto", whiteSpace: "nowrap",
                                    background: "var(--dt-error-bg-interactive)", border: "0.5px solid var(--dt-error-border-active)",
                                    color: "var(--dt-error-text)", fontFamily: FONT.sans, transition: `all ${TIMING.instant}`,
                                }}
                            >
                                New chat
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Law selector pills (UK/AU) ── */}
            {(jurisdiction === "uk" || jurisdiction === "au") && lawPaneOpen && availableLaws.length > 0 && (
                <div style={{
                    padding: isMobile ? `${SPACE["1"]}px ${SPACE["3"]}px` : `${SPACE["1"]}px ${SPACE["6"]}px`,
                    borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
                    display: "flex", alignItems: "center", gap: isMobile ? 3 : SPACE["1"],
                    overflowX: "auto", flexShrink: 0, scrollbarWidth: "none",
                    WebkitOverflowScrolling: "touch", background: "var(--dt-glass-bg-subtle)",
                }}>
                    <span style={{
                        fontSize: TYPE_SCALE.xs, fontWeight: 600, textTransform: "uppercase",
                        letterSpacing: "0.08em", whiteSpace: "nowrap", flexShrink: 0,
                        color: "var(--dt-text-quaternary)", fontFamily: FONT.sans,
                    }}>
                        {selectedLaws.length === availableLaws.length ? "All" : `${selectedLaws.length}/${availableLaws.length}`}
                    </span>
                    {availableLaws.map((law) => {
                        const isActive = selectedLaws.includes(law.id);
                        return (
                            <button
                                key={law.id}
                                onClick={() => {
                                    if (longPressFiredRef.current) { longPressFiredRef.current = false; return; }
                                    onSetSelectedLaws(prev =>
                                        prev.includes(law.id) ? prev.filter(l => l !== law.id) : [...prev, law.id]
                                    );
                                }}
                                onMouseDown={() => {
                                    longPressFiredRef.current = false;
                                    longPressTimerRef.current = setTimeout(() => {
                                        longPressFiredRef.current = true;
                                        onSetSelectedLaws([law.id]);
                                        longPressTimerRef.current = null;
                                    }, 500);
                                }}
                                onMouseUp={handleLongPressEnd}
                                onTouchStart={() => {
                                    longPressFiredRef.current = false;
                                    longPressTimerRef.current = setTimeout(() => {
                                        longPressFiredRef.current = true;
                                        onSetSelectedLaws([law.id]);
                                        longPressTimerRef.current = null;
                                    }, 500);
                                }}
                                onTouchEnd={handleLongPressEnd}
                                onContextMenu={(e) => e.preventDefault()}
                                title={law.name_en}
                                style={pillStyle(isActive)}
                                {...pillHover(isActive)}
                            >
                                {law.name}
                            </button>
                        );
                    })}
                    {selectedLaws.length < availableLaws.length && (
                        <button
                            onClick={() => onSetSelectedLaws(availableLaws.map(l => l.id))}
                            title="Select all laws"
                            style={{ ...pillStyle(false), background: "var(--dt-pill-bg)", border: "0.5px solid var(--dt-glass-border)", color: "var(--dt-text-tertiary)" }}
                        >
                            All
                        </button>
                    )}
                </div>
            )}

            {/* ── Custom corpus selector pills ── */}
            {jurisdiction === "custom" && (
                <div style={{
                    padding: isMobile ? `${SPACE["2"]}px ${SPACE["3"]}px` : `${SPACE["2"]}px ${SPACE["6"]}px`,
                    borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
                    display: "flex", alignItems: "center", gap: SPACE["2"],
                    overflowX: "auto", flexShrink: 0, scrollbarWidth: "none",
                    WebkitOverflowScrolling: "touch", background: "var(--dt-glass-bg-subtle)",
                }}>
                    <span style={{
                        fontSize: TYPE_SCALE.xs, fontWeight: 600, textTransform: "uppercase",
                        letterSpacing: "0.08em", whiteSpace: "nowrap", flexShrink: 0,
                        color: "var(--dt-text-quaternary)", fontFamily: FONT.sans,
                    }}>
                        Collections
                    </span>
                    {corporaLoading ? (
                        <span style={{ fontSize: TYPE_SCALE.sm, color: "var(--dt-text-quaternary)", fontFamily: FONT.sans, whiteSpace: "nowrap" }}>
                            Loading...
                        </span>
                    ) : availableCorpora.length > 0 ? (() => {
                        const storedCollection = typeof window !== "undefined"
                            ? localStorage.getItem("neolex_selected_collection") : null;
                        const isAllActive = !storedCollection;
                        const corpusId = availableCorpora[0]?.corpus_id ?? "";
                        const totalDocs = availableCorpora.reduce((sum, c) => sum + (c.doc_count ?? c.doc_ids?.length ?? 0), 0);

                        return (
                            <>
                                <button
                                    key="__all__"
                                    onClick={() => {
                                        localStorage.setItem("neolex_custom_corpus", corpusId);
                                        localStorage.setItem("neolex_custom_corpus_name", "All Documents");
                                        localStorage.removeItem("neolex_selected_collection");
                                        localStorage.removeItem("neolex_selected_doc_ids");
                                    }}
                                    style={pillStyle(isAllActive)}
                                    {...pillHover(isAllActive)}
                                >
                                    All ({totalDocs})
                                </button>
                                {availableCorpora.map((c) => {
                                    const isActive = storedCollection === c.name;
                                    const docCount = c.doc_count ?? c.doc_ids?.length ?? 0;
                                    return (
                                        <button
                                            key={c.name}
                                            onClick={() => {
                                                localStorage.setItem("neolex_custom_corpus", c.corpus_id);
                                                localStorage.setItem("neolex_custom_corpus_name", c.name);
                                                localStorage.setItem("neolex_selected_collection", c.name);
                                                if (c.doc_ids?.length) localStorage.setItem("neolex_selected_doc_ids", JSON.stringify(c.doc_ids));
                                                else localStorage.removeItem("neolex_selected_doc_ids");
                                            }}
                                            title={`${c.name} (${docCount} ${docCount === 1 ? "doc" : "docs"})`}
                                            style={pillStyle(isActive)}
                                            {...pillHover(isActive)}
                                        >
                                            {truncate(c.name)}{docCount > 0 ? ` (${docCount})` : ""}
                                        </button>
                                    );
                                })}
                            </>
                        );
                    })() : (
                        <button
                            onClick={() => router.push("/documents")}
                            style={{ ...pillStyle(false), background: "var(--dt-pill-bg-subtle)", border: "0.5px solid var(--dt-pill-border-color)", color: "var(--dt-text-tertiary)" }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--dt-glass-bg-hover)"; e.currentTarget.style.borderColor = "var(--dt-glass-border)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "var(--dt-pill-bg-subtle)"; e.currentTarget.style.borderColor = "var(--dt-pill-border-color)"; }}
                        >
                            Upload documents to get started
                        </button>
                    )}
                </div>
            )}
        </>
    );
}
