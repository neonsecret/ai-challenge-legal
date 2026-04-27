"use client";

import {useEffect, useState, type ReactNode} from "react";
import dynamic from "next/dynamic";
import {useColorMode} from "@/lib/color-mode";
import {motion} from "motion/react";
import {ArrowRight, Moon} from "lucide-react";
import {LanguageToggle} from "@/components/language-toggle";
import {useI18n} from "@/lib/i18n";

// StrictLanding: code-split so light-mode users skip the dark-theme chunk.
const StrictLanding = dynamic(() => import("@/components/landing/strict/strict-landing").then(m => ({ default: m.StrictLanding })), { ssr: false });
// Above-fold interactive panel: not SSR'd (client-only animation state).
const DemoPanel = dynamic(() => import("@/components/landing/demo-panel").then(m => ({ default: m.DemoPanel })), { ssr: false });
// Below-fold light-theme sections: lazy-loaded after LCP fires.
const LandingBelowFold = dynamic(() => import("./landing-below-fold").then(m => ({ default: m.LandingBelowFold })), { loading: () => null });

export function LandingClient({ heroTitle }: { heroTitle?: ReactNode }) {
    const {isDark, setMode} = useColorMode();
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const { t } = useI18n();

    useEffect(() => {
        const sseBase = process.env.NEXT_PUBLIC_SSE_URL ?? "";
        fetch(`${sseBase}/auth/me`, {credentials: "include"})
            .then(res => {
                if (res.ok) {
                    setIsAuthenticated(true);
                }
            })
            .catch(() => {});
    }, []);

    /* ══════════════════════════════════════════════════════════
       STRICT THEME — modular glassmorphism layout
    ══════════════════════════════════════════════════════════ */
    if (isDark) {
        return <StrictLanding />;
    }

    /* ══════════════════════════════════════════════════════════
       LIGHT THEME — warm Arrakis amber
    ══════════════════════════════════════════════════════════ */
    return (
        <div className="landing-light-hero" style={{fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif"}}>

            {/* ── HERO ── */}
            <section style={{
                position: "relative",
                minHeight: "100vh",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                background: "linear-gradient(145deg, #dfc090 0%, #e8d4b8 45%, #dbb870 100%)"
            }}>
                <div aria-hidden style={{position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none"}}>
                    <div style={{
                        position: "absolute",
                        width: 580,
                        height: 580,
                        top: -80,
                        left: "8%",
                        background: "radial-gradient(circle, rgba(190,110,30,0.45) 0%, rgba(190,110,30,0.15) 45%, transparent 70%)"
                    }}/>
                    <div style={{
                        position: "absolute",
                        width: 460,
                        height: 460,
                        top: 180,
                        right: "4%",
                        background: "radial-gradient(circle, rgba(200,80,20,0.38) 0%, rgba(200,80,20,0.12) 45%, transparent 70%)"
                    }}/>
                    <div style={{
                        position: "absolute",
                        width: 380,
                        height: 380,
                        bottom: 30,
                        left: "28%",
                        background: "radial-gradient(circle, rgba(175,130,20,0.35) 0%, rgba(175,130,20,0.10) 45%, transparent 70%)"
                    }}/>
                </div>

                <nav style={{
                    position: "sticky",
                    top: 0,
                    zIndex: 50,
                    background: "rgba(255,248,232,0.55)",
                    backdropFilter: "blur(24px) saturate(180%)",
                    WebkitBackdropFilter: "blur(24px) saturate(180%)",
                    borderBottom: "0.5px solid rgba(255,255,255,0.45)"
                }}>
                    <div style={{
                        maxWidth: 1100,
                        margin: "0 auto",
                        padding: "0 24px",
                        height: 56,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        position: "relative",
                        zIndex: 1
                    }}>
                        <div style={{display: "flex", alignItems: "center", gap: 9}}>
                            <div style={{
                                width: 30,
                                height: 30,
                                borderRadius: 9,
                                background: "rgba(196,124,0,0.18)",
                                border: "0.5px solid rgba(196,124,0,0.38)",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.65)"
                            }}>
                                <span style={{
                                    fontSize: 15,
                                    fontWeight: 700,
                                    color: "#7a4a00",
                                    fontFamily: "Georgia, serif",
                                    lineHeight: 1
                                }}>N</span>
                            </div>
                            <span className="hidden sm:inline" style={{
                                fontSize: 16,
                                fontWeight: 700,
                                color: "#1a0e04",
                                fontFamily: "Georgia, 'Times New Roman', serif",
                                letterSpacing: "-0.04em"
                            }}>Vitreon Legal</span>
                        </div>
                        <div style={{display: "flex", alignItems: "center", gap: 12}}>
                            <LanguageToggle />
                            <button
                                onClick={() => setMode(isDark ? "light" : "dark")}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    minWidth: 44,
                                    minHeight: 44,
                                    borderRadius: 10,
                                    border: "none",
                                    background: "transparent",
                                    cursor: "pointer",
                                    color: "#5c2e08",
                                    transition: "background 0.14s ease",
                                }}
                                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.20)" }}
                                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent" }}
                                aria-label="Toggle theme"
                            >
                                <Moon size={15} strokeWidth={2} />
                            </button>
                            {isAuthenticated ? (
                                <a href="/chat" style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: 6,
                                    padding: "7px 16px",
                                    minHeight: 44,
                                    borderRadius: "9999px",
                                    fontSize: 13,
                                    fontWeight: 600,
                                    color: "#fff8ee",
                                    background: "#5c2e08",
                                    textDecoration: "none",
                                    boxShadow: "0 2px 10px rgba(92,46,8,0.28)"
                                }}>
                                    {t("landing.go_to_chat")} <ArrowRight size={12} strokeWidth={2.5}/>
                                </a>
                            ) : (
                                <>
                                    <a href="/login" className="hidden sm:inline" style={{
                                        fontSize: 13,
                                        fontWeight: 500,
                                        color: "rgba(46,31,8,0.55)",
                                        textDecoration: "none"
                                    }}>{t("landing.sign_in")}</a>
                                    <a href="/login" style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 6,
                                        padding: "7px 16px",
                                        minHeight: 44,
                                        borderRadius: "9999px",
                                        fontSize: 13,
                                        fontWeight: 600,
                                        color: "#fff8ee",
                                        background: "#5c2e08",
                                        textDecoration: "none",
                                        boxShadow: "0 2px 10px rgba(92,46,8,0.28)"
                                    }}>
                                        {t("landing.get_started")} <ArrowRight size={12} strokeWidth={2.5}/>
                                    </a>
                                </>
                            )}
                        </div>
                    </div>
                </nav>

                <div className="pt-16 sm:pt-12 pb-12 sm:pb-8" style={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    paddingLeft: "24px",
                    paddingRight: "24px",
                    position: "relative",
                    zIndex: 1,
                    textAlign: "center"
                }}>
                    <motion.p initial={{opacity: 0, y: 6}} animate={{opacity: 1, y: 0}}
                              transition={{duration: 0.5, delay: 0.1}} style={{
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.20em",
                        fontWeight: 600,
                        color: "#5c2e08",
                        marginBottom: 20
                    }}>{t("landing.tag")}
                    </motion.p>
                    {/* heroTitle rendered immediately — no opacity:0 wrapper so the H1 is LCP-visible in SSR HTML */}
                    <div>
                        {heroTitle}
                    </div>
                    <motion.p initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}}
                              transition={{duration: 0.5, delay: 0.28}} style={{
                        fontSize: 16,
                        color: "rgba(46,31,8,0.60)",
                        lineHeight: 1.6,
                        maxWidth: 520,
                        marginBottom: 48,
                        whiteSpace: "pre-line"
                    }}>
                        {t("landing.hero_subtitle")}
                    </motion.p>
                    <motion.div initial={{opacity: 0, y: 20}} animate={{opacity: 1, y: 0}}
                                transition={{duration: 0.7, delay: 0.38}} style={{width: "100%", maxWidth: 960}}>
                        <div style={{
                            ...warmGlass,
                            borderRadius: 28,
                            padding: 16,
                            boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 24px 64px rgba(100,50,0,0.20)"
                        }}>
                            <div className="dark" style={{background: "#0d1520", borderRadius: 16, overflow: "hidden"}}><DemoPanel />
                            </div>
                        </div>
                    </motion.div>
                </div>

                <motion.div initial={{opacity: 0}} animate={{opacity: 1}} transition={{delay: 2, duration: 0.8}}
                            style={{
                                display: "flex",
                                justifyContent: "center",
                                paddingBottom: 32,
                                position: "relative",
                                zIndex: 1
                            }}>
                    <a href="#why" style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 6,
                        fontSize: 10,
                        textTransform: "uppercase",
                        letterSpacing: "0.16em",
                        color: "rgba(46,31,8,0.35)",
                        textDecoration: "none"
                    }}>
                        {t("landing.scroll_to_explore")}
                        <svg width="10" height="14" viewBox="0 0 10 14" fill="none" className="animate-float-down">
                            <path d="M5 1v12M1 9l4 4 4-4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"
                                  strokeLinejoin="round"/>
                        </svg>
                    </a>
                </motion.div>
            </section>

            {/* ── BELOW FOLD — lazy-loaded after LCP ── */}
            <LandingBelowFold />
        </div>
    );
}

/* ── warm glass style — V2 light theme only ── */
const warmGlass = {
    background: "rgba(255,250,235,0.22)",
    backdropFilter: "blur(32px) saturate(180%) brightness(105%)",
    WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(105%)",
    border: "0.5px solid rgba(255,255,255,0.45)",
    boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
} as const;
