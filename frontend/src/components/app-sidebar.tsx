"use client";

import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {MessageSquare, FileText, Settings, LogOut, Clock} from "lucide-react";
import {
    Sidebar,
    SidebarContent,
    SidebarHeader,
    SidebarFooter,
} from "@/components/ui/sidebar";
import {useEffect, useState} from "react";
import {useTheme} from "@/lib/theme";

const navItems = [
    {href: "/chat", label: "Chat", icon: MessageSquare},
    {href: "/documents", label: "Documents", icon: FileText},
    {href: "/settings", label: "Settings", icon: Settings},
];

const RECENT_QUERIES_KEY = "neolex_recent_queries";
const MAX_RECENT = 5;

// macOS Tahoe Liquid Glass sidebar — transparent enough to see through, distinct enough to read
function makeLiquidGlass(isDark: boolean) {
    if (isDark) {
        return {
            background: "rgba(255,255,255,0.07)",
            backdropFilter: "blur(32px) saturate(180%) brightness(108%)",
            WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(108%)",
            borderRadius: "18px",
            boxShadow: [
                "inset 0 1.5px 0 rgba(255,255,255,0.10)",
                "inset 1px 0 0 rgba(255,255,255,0.06)",
                "inset -1px 0 0 rgba(255,255,255,0.04)",
                "inset 0 -1px 0 rgba(0,0,0,0.08)",
                "0 8px 40px rgba(0,0,0,0.40)",
                "0 1px 3px rgba(0,0,0,0.20)",
            ].join(", "),
            border: "0.5px solid rgba(255,255,255,0.14)",
        };
    }
    // Light — cool grey-slate palette, subtler blur (matches .design-neon sidebar tokens)
    return {
        background: "rgba(248, 250, 252, 0.88)",
        backdropFilter: "blur(16px) saturate(130%) brightness(103%)",
        WebkitBackdropFilter: "blur(16px) saturate(130%) brightness(103%)",
        borderRadius: "18px",
        boxShadow: [
            "inset 0 1.5px 0 rgba(255,255,255,0.90)",
            "inset 1px 0 0 rgba(255,255,255,0.60)",
            "inset -1px 0 0 rgba(255,255,255,0.30)",
            "inset 0 -1px 0 rgba(30,50,100,0.04)",
            "0 8px 32px rgba(30,50,100,0.10)",
            "0 1px 3px rgba(30,50,100,0.06)",
        ].join(", "),
        border: "0.5px solid rgba(99,102,241,0.18)",
    };
}

// Active item — glass pill inside glass sidebar
function makeActiveItemStyle(isDark: boolean) {
    if (isDark) {
        return {
            background: "rgba(201,168,76,0.14)",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 1px 3px rgba(0,0,0,0.20)",
            border: "0.5px solid rgba(201,168,76,0.28)",
        };
    }
    // Light — indigo accent
    return {
        background: "rgba(99,102,241,0.10)",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.80), 0 1px 3px rgba(30,50,100,0.08)",
        border: "0.5px solid rgba(99,102,241,0.22)",
    };
}

export function AppSidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const [recentQueries, setRecentQueries] = useState<string[]>([]);
    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    const isDark = mounted && resolvedTheme === "dark";

    useEffect(() => {
        fetch(`/api/v1/demo/config`).catch(() => {
        });
    }, []);

    useEffect(() => {
        const loadRecent = () => {
            try {
                const stored = localStorage.getItem(RECENT_QUERIES_KEY);
                if (stored) setRecentQueries(JSON.parse(stored).slice(0, MAX_RECENT));
            } catch { /* ignore */
            }
        };
        loadRecent();
        window.addEventListener("storage", loadRecent);
        return () => window.removeEventListener("storage", loadRecent);
    }, []);

    const handleLogout = () => {
        const API = process.env.NEXT_PUBLIC_SSE_URL ?? "";
        fetch(`${API}/auth/logout`, {method: "POST", credentials: "include", headers: {"X-Requested-With": "XMLHttpRequest"}}).catch(() => {
        });
        router.push("/");
    };

    return (
        <Sidebar
            className="border-0"
            style={makeLiquidGlass(isDark)}
        >
            {/* ── App name ── */}
            <SidebarHeader style={{padding: "16px 14px 12px"}}>
                <div style={{display: "flex", alignItems: "center", gap: "8px"}}>
                    {/* Glass icon pill */}
                    <div style={{
                        width: 28, height: 28, borderRadius: 9,
                        background: isDark ? "rgba(201,168,76,0.14)" : "rgba(99,102,241,0.10)",
                        boxShadow: isDark
                            ? "inset 0 1px 0 rgba(255,255,255,0.08), 0 1px 4px rgba(0,0,0,0.20)"
                            : "inset 0 1px 0 rgba(255,255,255,0.80), 0 1px 4px rgba(30,50,100,0.08)",
                        border: isDark ? "0.5px solid rgba(201,168,76,0.28)" : "0.5px solid rgba(99,102,241,0.22)",
                        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                    }}>
                        <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                            <path d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
                                  stroke={isDark ? "#C9A84C" : "rgba(79,70,229,0.75)"} strokeWidth="1.3" strokeLinejoin="round"
                                  fill={isDark ? "rgba(201,168,76,0.20)" : "rgba(99,102,241,0.15)"}/>
                        </svg>
                    </div>
                    <span style={{
                        fontSize: "13px", fontWeight: 600,
                        color: isDark ? "rgba(255,255,255,0.85)" : "rgba(30,18,8,0.80)",
                        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                        letterSpacing: "-0.01em",
                    }}>
            Vitreon Legal
          </span>
                </div>
            </SidebarHeader>

            <SidebarContent style={{padding: "2px 8px 0"}}>
                {/* ── Nav items ── */}
                <div style={{display: "flex", flexDirection: "column", gap: "2px"}}>
                    {navItems.map(({href, label, icon: Icon}) => {
                        const isActive = pathname.startsWith(href);
                        return (
                            <Link
                                key={href}
                                href={href}
                                style={{
                                    display: "flex", alignItems: "center", gap: "8px",
                                    padding: "7px 10px", borderRadius: "10px",
                                    fontSize: "13px",
                                    fontWeight: isActive ? 500 : 400,
                                    color: isActive
                                        ? isDark ? "rgba(255,255,255,0.92)" : "rgba(46,20,4,0.90)"
                                        : isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.52)",
                                    textDecoration: "none",
                                    transition: "all 0.12s ease",
                                    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                                    ...(isActive ? makeActiveItemStyle(isDark) : {}),
                                }}
                                onMouseEnter={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.14)";
                                        e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.72)" : "rgba(46,31,8,0.72)";
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.background = "transparent";
                                        e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.52)";
                                    }
                                }}
                            >
                                <Icon size={15} strokeWidth={isActive ? 2 : 1.6}
                                      style={{opacity: isActive ? 0.80 : 0.40, flexShrink: 0}}/>
                                {label}
                            </Link>
                        );
                    })}
                </div>

                {/* ── Recent queries ── */}
                <div style={{marginTop: "22px"}}>
                    <div style={{
                        display: "flex", alignItems: "center", gap: "5px",
                        padding: "0 10px", marginBottom: "6px",
                    }}>
                        <Clock size={10} style={{opacity: 0.28, color: isDark ? "rgba(255,255,255,0.50)" : "#2e1f08"}}/>
                        <span style={{
                            fontSize: "10px", fontWeight: 600, textTransform: "uppercase",
                            letterSpacing: "0.10em", color: isDark ? "rgba(255,255,255,0.28)" : "rgba(46,31,8,0.28)",
                            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        }}>
              Recent
            </span>
                    </div>
                    {recentQueries.length === 0 ? (
                        <p style={{
                            fontSize: "11px", color: isDark ? "rgba(255,255,255,0.22)" : "rgba(46,31,8,0.25)", padding: "0 10px",
                            fontStyle: "italic", margin: 0,
                        }}>
                            Queries appear here
                        </p>
                    ) : (
                        <div style={{display: "flex", flexDirection: "column", gap: "0"}}>
                            {recentQueries.map((q, i) => (
                                <button
                                    key={i}
                                    onClick={() => router.push(`/chat?q=${encodeURIComponent(q)}`)}
                                    title={q}
                                    style={{
                                        width: "100%", textAlign: "left", cursor: "pointer",
                                        fontSize: "11.5px", color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
                                        padding: "5px 10px", borderRadius: "8px",
                                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                        background: "transparent", border: "none",
                                        transition: "all 0.10s ease",
                                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.16)";
                                        e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.72)" : "rgba(46,31,8,0.70)";
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.background = "transparent";
                                        e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)";
                                    }}
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </SidebarContent>

            {/* ── Footer ── */}
            <SidebarFooter style={{
                padding: "8px",
                borderTop: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.25)",
            }}>
                <button
                    onClick={handleLogout}
                    style={{
                        display: "flex", alignItems: "center", gap: "7px",
                        width: "100%", padding: "7px 10px", borderRadius: "10px",
                        fontSize: "12.5px", color: isDark ? "rgba(255,255,255,0.35)" : "rgba(46,31,8,0.38)",
                        background: "transparent", border: "none", cursor: "pointer",
                        transition: "all 0.12s ease",
                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.16)";
                        e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.62)" : "rgba(46,31,8,0.62)";
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.35)" : "rgba(46,31,8,0.38)";
                    }}
                    aria-label="Sign out"
                >
                    <LogOut size={13} strokeWidth={1.6} style={{opacity: 0.45}}/>
                    Sign out
                </button>
            </SidebarFooter>
        </Sidebar>
    );
}
