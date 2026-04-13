"use client";

import Link from "next/link";
import {usePathname} from "next/navigation";
import {useColorMode} from "@/lib/color-mode";
import {MessageSquare, FileText, Settings, CreditCard, Sun, Moon} from "lucide-react";
import {useIsMobile} from "@/hooks/use-mobile";
import {useI18n} from "@/lib/i18n";
import {LanguageToggle} from "@/components/language-toggle";

const navItemDefs = [
    {href: "/chat", labelKey: "nav.chat", icon: MessageSquare},
    {href: "/documents", labelKey: "nav.documents", icon: FileText},
    {href: "/billing", labelKey: "nav.billing", icon: CreditCard},
    {href: "/settings", labelKey: "nav.settings", icon: Settings},
];

export function BottomNav() {
    const pathname = usePathname();
    const {isDark, setMode} = useColorMode();
    const isMobile = useIsMobile();
    const {t} = useI18n();

    // Dark desktop: navigation lives in the sidebar rail
    if (isDark && !isMobile) return null;

    return (
        <div
            className="bottom-nav-pill"
            suppressHydrationWarning
            style={{
                position: "fixed",
                bottom: isMobile
                    ? "calc(env(safe-area-inset-bottom, 0px) + 12px)"
                    : "20px",
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 50,
                display: "flex",
                alignItems: "center",
                gap: "1px",
                padding: isMobile ? "3px 3px" : "4px 5px",
                backdropFilter: "var(--nav-pill-blur)",
                WebkitBackdropFilter: "var(--nav-pill-blur)",
                borderRadius: "22px",
                maxWidth: "calc(100vw - 24px)",
                background: "var(--nav-pill-bg)",
                border: "1px solid var(--nav-pill-border)",
                boxShadow: "var(--nav-pill-shadow)",
            }}
        >
            {navItemDefs.map(({href, labelKey, icon: Icon}) => {
                const isActive = pathname.startsWith(href);
                return (
                    <Link
                        key={href}
                        href={href}
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: isMobile ? "2px" : "3px",
                            padding: isMobile ? "6px 10px" : "7px 14px",
                            borderRadius: "16px",
                            textDecoration: "none",
                            transition: "all 0.14s ease",
                            background: isActive ? "var(--nav-active-bg)" : "transparent",
                            boxShadow: isActive ? "var(--nav-active-shadow)" : "none",
                            border: isActive ? "var(--nav-active-border)" : "0.5px solid transparent",
                        }}
                        onMouseEnter={(e) => {
                            if (!isActive) e.currentTarget.style.background = "var(--dt-button-bg-hover)";
                        }}
                        onMouseLeave={(e) => {
                            if (!isActive) e.currentTarget.style.background = "transparent";
                        }}
                    >
                        <Icon
                            size={isMobile ? 16 : 18}
                            strokeWidth={isActive ? 2 : 1.6}
                            style={{color: isActive ? "var(--nav-active-color)" : "var(--nav-inactive-color)"}}
                        />
                        <span suppressHydrationWarning style={{
                            fontSize: isMobile ? "9px" : "10px",
                            fontWeight: isActive ? 600 : 400,
                            color: isActive ? "var(--nav-active-color)" : "var(--nav-inactive-color)",
                            fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                            letterSpacing: "0.01em",
                        }}>
                            {t(labelKey)}
                        </span>
                    </Link>
                );
            })}

            {/* Separator */}
            <div style={{
                width: 1,
                height: 28,
                background: "var(--nav-sep-color)",
                margin: "0 2px"
            }}/>

            {/* Theme toggle */}
            <button
                type="button"
                onClick={() => setMode(isDark ? "light" : "dark")}
                title={isDark ? "Switch to light mode" : "Switch to dark mode"}
                style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: isMobile ? "2px" : "3px",
                    padding: isMobile ? "6px 10px" : "8px 14px",
                    borderRadius: "16px",
                    background: "transparent",
                    border: "0.5px solid transparent",
                    cursor: "pointer",
                    transition: "all 0.14s ease",
                    color: "var(--nav-toggle-color)",
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--dt-button-bg-hover)";
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                }}
            >
                {isDark
                    ? <Sun size={isMobile ? 16 : 18} strokeWidth={1.6}/>
                    : <Moon size={isMobile ? 16 : 18} strokeWidth={1.6}/>
                }
                <span suppressHydrationWarning style={{
                    fontSize: isMobile ? "9px" : "10px",
                    fontWeight: 400,
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    letterSpacing: "0.01em"
                }}>
                    {isDark ? t("theme_toggle.light") : t("theme_toggle.dark")}
                </span>
            </button>

            {/* Language toggle */}
            <LanguageToggle />
        </div>
    );
}
