"use client";

import Link from "next/link";
import {usePathname} from "next/navigation";
import {useTheme} from "@/lib/theme";
import {useEffect, useState} from "react";
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
    const {resolvedTheme, setTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    const isMobile = useIsMobile();
    const {t} = useI18n();
    useEffect(() => setMounted(true), []);

    const isDark = mounted && resolvedTheme === "dark";

    const pill = isDark ? {
        background: "rgba(15,22,35,0.80)",
        border: "0.5px solid rgba(255,255,255,0.12)",
        boxShadow: [
            "inset 0 1px 0 rgba(255,255,255,0.08)",
            "0 8px 40px rgba(0,0,0,0.40)",
            "0 2px 6px rgba(0,0,0,0.30)",
        ].join(", "),
    } : {
        // Light — cool grey-slate (matches sidebar token --glass-bg-nav)
        background: "rgba(248,250,252,0.88)",
        border: "0.5px solid rgba(99,102,241,0.18)",
        boxShadow: [
            "inset 0 1.5px 0 rgba(255,255,255,0.90)",
            "inset 1px 0 0 rgba(255,255,255,0.50)",
            "inset -1px 0 0 rgba(255,255,255,0.20)",
            "0 4px 20px rgba(30,50,100,0.10)",
            "0 1px 3px rgba(30,50,100,0.06)",
        ].join(", "),
    };

    const activeColor = isDark ? "#C9A84C" : "#4F46E5";
    const inactiveColor = isDark ? "rgba(255,255,255,0.42)" : "rgba(30,50,100,0.45)";
    const activeBg = isDark ? "rgba(201,168,76,0.16)" : "rgba(99,102,241,0.12)";
    const activeBorder = isDark ? "0.5px solid rgba(201,168,76,0.30)" : "0.5px solid rgba(99,102,241,0.22)";

    return (
        <div
            suppressHydrationWarning
            style={{
                position: "fixed",
                bottom: isMobile ? "12px" : "20px",
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 50,
                display: "flex",
                alignItems: "center",
                gap: "1px",
                padding: isMobile ? "3px 3px" : "4px 5px",
                backdropFilter: "blur(32px) saturate(180%)",
                WebkitBackdropFilter: "blur(32px) saturate(180%)",
                borderRadius: "22px",
                maxWidth: "calc(100vw - 24px)",
                ...pill,
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
                            background: isActive ? activeBg : "transparent",
                            boxShadow: isActive && !isDark ? "inset 0 1px 0 rgba(255,255,255,0.80), 0 1px 4px rgba(30,50,100,0.08)" : "none",
                            border: isActive ? activeBorder : "0.5px solid transparent",
                        }}
                        onMouseEnter={(e) => {
                            if (!isActive) e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)";
                        }}
                        onMouseLeave={(e) => {
                            if (!isActive) e.currentTarget.style.background = "transparent";
                        }}
                    >
                        <Icon size={isMobile ? 16 : 18} strokeWidth={isActive ? 2 : 1.6}
                              style={{color: isActive ? activeColor : inactiveColor}}/>
                        <span suppressHydrationWarning style={{
                            fontSize: isMobile ? "9px" : "10px",
                            fontWeight: isActive ? 600 : 400,
                            color: isActive ? activeColor : inactiveColor,
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
                background: isDark ? "rgba(255,255,255,0.10)" : "rgba(46,31,8,0.12)",
                margin: "0 2px"
            }}/>

            {/* Theme toggle */}
            <button
                onClick={() => setTheme(isDark ? "light" : "dark")}
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
                    color: isDark ? "rgba(255,255,255,0.42)" : "rgba(46,31,8,0.48)",
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)";
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
