"use client";

import { SquarePen, Trash2, X } from "lucide-react";
import { FONT, TYPE_SCALE, SPACE, RADIUS, TIMING } from "@/lib/tokens";
import { useColorMode } from "@/lib/color-mode";
import type { ChatSession } from "@/components/chat/chat-state";

interface HistoryPanelProps {
    sessions: ChatSession[];
    currentSessionId: string | null;
    onLoadSession: (id: string) => void;
    onNewChat: () => void;
    onDeleteSession: (id: string) => void;
    onClose: () => void;
    isMobile: boolean;
}

/**
 * History panel inner content — session list with header controls.
 * Wrapping AnimatePresence/motion.div is handled by the caller (chat/page.tsx)
 * so the entrance animation stays co-located with the layout logic.
 */
export function HistoryPanel({
    sessions,
    currentSessionId,
    onLoadSession,
    onNewChat,
    onDeleteSession,
    onClose,
    isMobile,
}: HistoryPanelProps) {
    const {isDark} = useColorMode();
    return (
        <>
            {/* Header */}
            <div style={{
                padding: `${SPACE["4"]}px ${SPACE["4"]}px`,
                paddingTop: isMobile ? `max(${SPACE["4"]}px, env(safe-area-inset-top))` : SPACE["4"],
                borderBottom: isDark ? "1px solid var(--strict-gold-border)" : "0.5px solid var(--dt-glass-border-subtle)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexShrink: 0,
                background: isDark ? "linear-gradient(180deg, rgba(255,255,255,0.015) 0%, transparent 100%)" : "var(--dt-glass-bg-subtle)",
            }}>
                <span style={{
                    fontSize: isDark ? 9 : TYPE_SCALE.xs,
                    fontWeight: isDark ? 400 : 700,
                    textTransform: "uppercase",
                    letterSpacing: isDark ? "1.2px" : "0.12em",
                    color: isDark ? "var(--strict-source-label)" : "var(--dt-text-quaternary)",
                    fontFamily: isDark ? "system-ui" : FONT.sans,
                }}>
                    Chats
                </span>

                <div style={{ display: "flex", alignItems: "center", gap: SPACE["2"] }}>
                    <button
                        onClick={() => { onNewChat(); onClose(); }}
                        title="New chat"
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: SPACE["1"],
                            padding: isDark ? "4px 10px" : `${SPACE["1"]}px ${SPACE["2"]}px`,
                            borderRadius: isDark ? 5 : RADIUS.md,
                            fontSize: isDark ? 10 : TYPE_SCALE.xs,
                            fontWeight: 500,
                            background: isDark ? "var(--strict-gold-badge-bg)" : "var(--dt-glass-bg)",
                            border: isDark ? "1px solid var(--strict-gold-badge-border)" : "0.5px solid var(--dt-glass-border)",
                            color: isDark ? "var(--strict-gold-text)" : "var(--dt-text-tertiary)",
                            cursor: "pointer",
                            transition: `all ${TIMING.instant}`,
                            fontFamily: isDark ? "system-ui" : FONT.sans,
                        }}
                    >
                        <SquarePen size={isDark ? 10 : TYPE_SCALE.xs} strokeWidth={1.8} />
                        New
                    </button>

                    {isMobile && (
                        <button
                            onClick={onClose}
                            title="Close"
                            style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                width: 28,
                                height: 28,
                                borderRadius: RADIUS.md,
                                background: "var(--dt-glass-bg)",
                                border: "0.5px solid var(--dt-glass-border)",
                                cursor: "pointer",
                                color: "var(--dt-text-tertiary)",
                            }}
                        >
                            <X size={14} strokeWidth={2} />
                        </button>
                    )}
                </div>
            </div>

            {/* Sessions list */}
            <div style={{ flex: 1, overflowY: "auto", padding: SPACE["2"] }}>
                {sessions.length === 0 ? (
                    <div style={{
                        display: "flex", alignItems: "center", justifyContent: "center",
                        height: "100%", padding: "24px 12px",
                    }}>
                        <p style={{
                            fontSize: isDark ? 12 : TYPE_SCALE.sm,
                            textAlign: "center",
                            color: isDark ? "var(--strict-text-dim)" : "var(--dt-text-quaternary)",
                            fontFamily: isDark ? "Georgia, serif" : FONT.sans,
                            fontStyle: isDark ? "italic" : undefined,
                            margin: 0,
                        }}>
                            No chats yet
                        </p>
                    </div>
                ) : (
                    sessions.map((s) => {
                        const isActive = s.id === currentSessionId;
                        return (
                            <div key={s.id} style={{ position: "relative", marginBottom: 2 }} className="group">
                                <button
                                    onClick={() => { onLoadSession(s.id); if (isMobile) onClose(); }}
                                    style={{
                                        display: "block",
                                        width: "100%",
                                        textAlign: "left",
                                        padding: `${SPACE["2"]}px ${SPACE["8"]}px ${SPACE["2"]}px ${SPACE["3"]}px`,
                                        borderRadius: RADIUS.lg,
                                        fontSize: isDark ? 12 : TYPE_SCALE.sm,
                                        color: isDark
                                            ? (isActive ? "var(--strict-text-primary)" : "var(--strict-text-secondary)")
                                            : (isActive ? "var(--dt-text-primary)" : "var(--dt-text-secondary)"),
                                        background: isDark
                                            ? (isActive ? "var(--strict-gold-badge-bg)" : "transparent")
                                            : (isActive ? "var(--dt-active-item-bg)" : "transparent"),
                                        border: isDark
                                            ? (isActive ? "1px solid var(--strict-gold-border)" : "1px solid transparent")
                                            : (isActive ? "0.5px solid var(--dt-accent-border-color)" : "0.5px solid transparent"),
                                        cursor: "pointer",
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                        fontFamily: isDark ? "system-ui, sans-serif" : FONT.sans,
                                        fontWeight: isDark ? (isActive ? 500 : 400) : (isActive ? 600 : 400),
                                        transition: `background ${TIMING.instant}, border-color ${TIMING.instant}, box-shadow ${TIMING.instant}, color ${TIMING.instant}`,
                                    }}
                                    onMouseEnter={e => {
                                        if (!isActive) {
                                            if (isDark) {
                                                e.currentTarget.style.background = "var(--strict-glass-bg)";
                                                e.currentTarget.style.borderColor = "var(--strict-gold-border)";
                                            } else {
                                                e.currentTarget.style.background = "var(--dt-glass-bg)";
                                                e.currentTarget.style.borderColor = "var(--dt-glass-border-subtle)";
                                                e.currentTarget.style.boxShadow = "var(--dt-glass-inner-glow), 0 2px 8px rgba(0,0,0,0.15)";
                                                e.currentTarget.style.backdropFilter = "var(--dt-glass-blur-light)";
                                            }
                                        }
                                    }}
                                    onMouseLeave={e => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = "transparent";
                                            e.currentTarget.style.borderColor = "transparent";
                                            if (!isDark) {
                                                e.currentTarget.style.boxShadow = "none";
                                                e.currentTarget.style.backdropFilter = "none";
                                            }
                                        }
                                    }}
                                >
                                    {s.title}
                                </button>

                                <button
                                    onPointerDown={e => { e.stopPropagation(); e.preventDefault(); }}
                                    onMouseDown={e => e.stopPropagation()}
                                    onClick={e => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        onDeleteSession(s.id);
                                    }}
                                    title="Delete chat"
                                    className="opacity-0 group-hover:opacity-100 no-press-scale"
                                    style={{
                                        position: "absolute",
                                        right: SPACE["2"],
                                        top: "50%",
                                        transform: "translateY(-50%)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        width: 22,
                                        height: 22,
                                        borderRadius: RADIUS.sm,
                                        background: isDark ? "rgba(239,68,68,0.04)" : "var(--dt-glass-bg)",
                                        border: isDark ? "1px solid rgba(239,68,68,0.08)" : "0.5px solid var(--dt-glass-border)",
                                        cursor: "pointer",
                                        color: isDark ? "rgba(248,113,113,0.5)" : "var(--dt-text-quaternary)",
                                        padding: 0,
                                        zIndex: 1,
                                        flexShrink: 0,
                                        transition: `opacity ${TIMING.instant}, background ${TIMING.instant}, color ${TIMING.instant}`,
                                    }}
                                    onMouseEnter={e => {
                                        e.currentTarget.style.background = isDark ? "rgba(239,68,68,0.08)" : "var(--dt-error-bg-interactive)";
                                        e.currentTarget.style.color = isDark ? "#f87171" : "var(--dt-error-text-hover)";
                                    }}
                                    onMouseLeave={e => {
                                        e.currentTarget.style.background = isDark ? "rgba(239,68,68,0.04)" : "var(--dt-glass-bg)";
                                        e.currentTarget.style.color = isDark ? "rgba(248,113,113,0.5)" : "var(--dt-text-quaternary)";
                                    }}
                                >
                                    <Trash2 size={11} strokeWidth={1.8} />
                                </button>
                            </div>
                        );
                    })
                )}
            </div>
        </>
    );
}
