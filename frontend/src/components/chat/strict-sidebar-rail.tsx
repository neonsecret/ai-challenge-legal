"use client";

/**
 * Strict design sidebar rail — the 44px left column.
 * Desktop-only; callers are responsible for hiding on mobile.
 *
 * Provides: logo link, app nav (Chat/Documents/Billing), history toggle,
 * new-chat, doc-index toggle, theme toggle, and settings link.
 */

import { useState } from "react";
import { Menu, SquarePen, LayoutList, Settings, Sun, Moon, MessageSquare, FileText, CreditCard } from "lucide-react";
import { useColorMode } from "@/lib/color-mode";
import Link from "next/link";
import { usePathname } from "next/navigation";

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

function RailNavLink({
    href,
    title,
    active,
    children,
}: {
    href: string;
    title: string;
    active: boolean;
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
        <Link
            href={href}
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
                textDecoration: "none",
                flexShrink: 0,
                transition: "background 0.15s ease, border-color 0.15s ease, color 0.15s ease",
            }}
        >
            {children}
        </Link>
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
    const pathname = usePathname();

    const isDark = resolvedMode === "dark";

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

            {/* App navigation: Chat, Documents, Billing */}
            <RailNavLink href="/chat" title="Chat" active={pathname.startsWith("/chat")}>
                <MessageSquare size={14} strokeWidth={1.8} />
            </RailNavLink>

            <RailNavLink href="/documents" title="Documents" active={pathname.startsWith("/documents")}>
                <FileText size={14} strokeWidth={1.8} />
            </RailNavLink>

            <RailNavLink href="/billing" title="Billing" active={pathname.startsWith("/billing")}>
                <CreditCard size={14} strokeWidth={1.8} />
            </RailNavLink>

            {/* Chat-specific actions — only show on /chat */}
            {pathname.startsWith("/chat") && (
                <>
                    <div
                        style={{
                            width: 18,
                            height: 1,
                            background: "var(--strict-gold-border)",
                            margin: "2px 0",
                            flexShrink: 0,
                        }}
                    />
                    <RailButton
                        onClick={onHistoryToggle}
                        active={historyOpen}
                        title="Chat history"
                    >
                        <Menu size={14} strokeWidth={1.8} />
                    </RailButton>
                    <RailButton onClick={onNewChat} title="New chat">
                        <SquarePen size={14} strokeWidth={1.8} />
                    </RailButton>
                    <RailButton
                        onClick={onDocIndexToggle}
                        active={docIndexOpen}
                        title="Document index"
                    >
                        <LayoutList size={14} strokeWidth={1.8} />
                    </RailButton>
                </>
            )}

            {/* Spacer */}
            <div style={{ flex: 1 }} />

            {/* Theme toggle — direct button */}
            <RailButton
                onClick={() => setMode(isDark ? "light" : "dark")}
                title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            >
                {isDark ? <Sun size={14} strokeWidth={1.8} /> : <Moon size={14} strokeWidth={1.8} />}
            </RailButton>

            {/* Settings link */}
            <RailNavLink href="/settings" title="Settings" active={pathname.startsWith("/settings")}>
                <Settings size={14} strokeWidth={1.8} />
            </RailNavLink>
        </div>
    );
}
