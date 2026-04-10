"use client";

/**
 * Strict design sidebar rail — the 44px left column.
 * Desktop-only; callers are responsible for hiding on mobile.
 *
 * Provides: logo link, history toggle, new-chat, doc-index toggle,
 * and a settings popover for theme + language.
 */

import { useState } from "react";
import { Menu, SquarePen, LayoutList, Settings, Sun, Moon } from "lucide-react";
import { useColorMode } from "@/lib/color-mode";
import Link from "next/link";

export interface StrictSidebarRailProps {
    onHistoryToggle?: () => void;
    onNewChat?: () => void;
    onDocIndexToggle?: () => void;
    historyOpen?: boolean;
    docIndexOpen?: boolean;
}

function RailButton({
    onClick,
    active = false,
    title,
    children,
}: {
    onClick?: () => void;
    active?: boolean;
    title: string;
    children: React.ReactNode;
}) {
    const [hovered, setHovered] = useState(false);

    const bg = active
        ? "rgba(201,168,76, 0.07)"
        : hovered
            ? "rgba(201,168,76, 0.05)"
            : "transparent";
    const border = active
        ? "1px solid rgba(201,168,76, 0.14)"
        : hovered
            ? "1px solid var(--strict-gold-border)"
            : "1px solid transparent";
    const color = active
        ? "var(--strict-gold-text)"
        : hovered
            ? "var(--strict-text-secondary)"
            : "var(--strict-text-dim)";

    return (
        <button
            onClick={onClick}
            title={title}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: bg,
                border,
                color,
                cursor: "pointer",
                flexShrink: 0,
                transition: "background 0.15s ease, border-color 0.15s ease, color 0.15s ease",
            }}
        >
            {children}
        </button>
    );
}

export function StrictSidebarRail({
    onHistoryToggle,
    onNewChat,
    onDocIndexToggle,
    historyOpen = false,
    docIndexOpen = false,
}: StrictSidebarRailProps) {
    const { setMode, resolvedMode } = useColorMode();
    const [settingsOpen, setSettingsOpen] = useState(false);

    return (
        <div
            style={{
                width: 44,
                flexShrink: 0,
                background: "var(--strict-glass-recessed)",
                borderRight: "1px solid var(--strict-gold-border)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                paddingTop: 10,
                paddingBottom: 10,
                gap: 6,
                position: "relative",
            }}
        >
            {/* Logo — home link */}
            <Link
                href="/"
                title="Vitreon Legal home"
                style={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    border: "1px solid rgba(201,168,76, 0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    marginBottom: 4,
                    color: "var(--strict-gold-text)",
                    textDecoration: "none",
                    fontSize: 9,
                    fontFamily: "Georgia, serif",
                    transition: "border-color 0.15s ease",
                }}
                onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = "rgba(201,168,76, 0.4)";
                }}
                onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = "rgba(201,168,76, 0.2)";
                }}
            >
                V
            </Link>

            {/* History toggle */}
            <RailButton
                onClick={onHistoryToggle}
                active={historyOpen}
                title="Chat history"
            >
                <Menu size={14} strokeWidth={1.8} />
            </RailButton>

            {/* New chat */}
            <RailButton onClick={onNewChat} title="New chat">
                <SquarePen size={14} strokeWidth={1.8} />
            </RailButton>

            {/* Gold divider */}
            <div
                style={{
                    width: 18,
                    height: 1,
                    background: "var(--strict-gold-border)",
                    margin: "2px 0",
                    flexShrink: 0,
                }}
            />

            {/* Document index */}
            <RailButton
                onClick={onDocIndexToggle}
                active={docIndexOpen}
                title="Document index"
            >
                <LayoutList size={14} strokeWidth={1.8} />
            </RailButton>

            {/* Spacer */}
            <div style={{ flex: 1 }} />

            {/* Settings button + inline theme toggle popover */}
            <div style={{ position: "relative" }}>
                <RailButton
                    onClick={() => setSettingsOpen((v) => !v)}
                    active={settingsOpen}
                    title="Settings"
                >
                    <Settings size={14} strokeWidth={1.8} />
                </RailButton>

                {settingsOpen && (
                    <div
                        style={{
                            position: "absolute",
                            bottom: "calc(100% + 6px)",
                            left: "50%",
                            transform: "translateX(-50%)",
                            background: "var(--strict-glass-recessed)",
                            border: "1px solid var(--strict-gold-border)",
                            borderRadius: 8,
                            padding: "8px 6px",
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                            zIndex: 50,
                            minWidth: 36,
                            backdropFilter: "blur(20px)",
                            WebkitBackdropFilter: "blur(20px)",
                            boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
                        }}
                    >
                        {/* Light mode */}
                        <button
                            onClick={() => { setMode("light"); setSettingsOpen(false); }}
                            title="Light mode"
                            style={{
                                width: 24,
                                height: 24,
                                borderRadius: 5,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                background: resolvedMode === "light" ? "rgba(201,168,76, 0.07)" : "transparent",
                                border: resolvedMode === "light" ? "1px solid rgba(201,168,76, 0.14)" : "1px solid transparent",
                                color: resolvedMode === "light" ? "var(--strict-gold-text)" : "var(--strict-text-dim)",
                                cursor: "pointer",
                            }}
                        >
                            <Sun size={12} strokeWidth={1.8} />
                        </button>
                        {/* Dark mode */}
                        <button
                            onClick={() => { setMode("dark"); setSettingsOpen(false); }}
                            title="Dark mode"
                            style={{
                                width: 24,
                                height: 24,
                                borderRadius: 5,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                background: resolvedMode === "dark" ? "rgba(201,168,76, 0.07)" : "transparent",
                                border: resolvedMode === "dark" ? "1px solid rgba(201,168,76, 0.14)" : "1px solid transparent",
                                color: resolvedMode === "dark" ? "var(--strict-gold-text)" : "var(--strict-text-dim)",
                                cursor: "pointer",
                            }}
                        >
                            <Moon size={12} strokeWidth={1.8} />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
