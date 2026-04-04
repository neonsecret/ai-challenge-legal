"use client";

import {useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {useTheme} from "@/lib/theme";
import {motion, AnimatePresence} from "motion/react";
import {ArrowRight, FileSearch, Globe, ShieldCheck, Lock, Loader2, Sun, Moon} from "lucide-react";
import {DemoPanel, SCENARIOS} from "@/components/landing/demo-panel";
import {ValuePillars} from "@/components/landing/value-pillars";
import {HowItWorks} from "@/components/landing/how-it-works";
import {TrustSection} from "@/components/landing/trust-section";
import {CzechCaselawSection} from "@/components/landing/czech-caselaw-section";
import {LanguageToggle} from "@/components/language-toggle";
import {useI18n} from "@/lib/i18n";

/* ── shared warm glass constant ── */
const warmGlass = {
    background: "rgba(255,250,235,0.22)",
    backdropFilter: "blur(32px) saturate(180%) brightness(105%)",
    WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(105%)",
    border: "0.5px solid rgba(255,255,255,0.45)",
    boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
} as const;

const LIGHT_PILLAR_ICONS = [ShieldCheck, FileSearch, ShieldCheck] as const;

const LIGHT_STEP_NUMBERS = ["01", "02", "03"] as const;

const LIGHT_TRUST_ICONS = [Globe, ShieldCheck, Lock] as const;
const LIGHT_TRUST_KEYS = [
    {label: "landing.trust_jurisdictions", sub: "landing.trust_jurisdictions_sub"},
    {label: "landing.trust_soc2", sub: "landing.trust_soc2_sub"},
    {label: "landing.trust_privacy", sub: "landing.trust_privacy_sub"},
] as const;

type BenchmarkData = {
    name: string;
    description: string;
    ourScore: number;
    sota: number;
    improvement: string;
    url: string;
};

const BENCHMARKS: BenchmarkData[] = [
    {
        name: "GaRAGe RAF",
        description: "Retrieval-augmented fact verification on legal documents",
        ourScore: 0.824,
        sota: 0.607,
        improvement: "+36% vs SOTA",
        url: "https://huggingface.co/spaces/garage-bAIern/garage-leaderboard",
    },
    {
        name: "ContractNLI F1",
        description: "Natural language inference over legal contracts",
        ourScore: 0.630,
        sota: 0.357,
        improvement: "+76% vs SOTA",
        url: "https://stanfordnlp.github.io/contract-nli/",
    },
    {
        name: "LEXam Open EN",
        description: "Open-ended legal exam questions across multiple jurisdictions",
        ourScore: 0.691,
        sota: 0.572,
        improvement: "+21% vs SOTA",
        url: "https://huggingface.co/datasets/LEXTREME/LEXam",
    },
];

export default function LandingPage() {
    const router = useRouter();
    const {resolvedTheme, setTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    const [loading, setLoading] = useState(true);
    const [activeStep, setActiveStep] = useState(0);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const { locale, t } = useI18n();
    const isCzech = locale === "cs";
    const czScenarioIdx = SCENARIOS.findIndex(s => s.jurisdiction === "CZ");

    useEffect(() => {
        setMounted(true);
    }, []);

    useEffect(() => {
        // Check if we have a valid session cookie by probing the verify endpoint
        const sseBase = process.env.NEXT_PUBLIC_SSE_URL ?? "";
        fetch(`${sseBase}/auth/me`, {credentials: "include"})
            .then(res => {
                if (res.ok) {
                    setIsAuthenticated(true);
                }
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const lightSteps = LIGHT_STEP_NUMBERS.map((num, i) => ({
        number: num,
        title: t(`landing.step${i + 1}_title`),
        body: t(`landing.step${i + 1}_body`),
    }));

    useEffect(() => {
        const id = setInterval(() => setActiveStep(p => (p + 1) % LIGHT_STEP_NUMBERS.length), 5000);
        return () => clearInterval(id);
    }, []);

    // Avoid hydration flash — render dark version until mounted
    const isDark = !mounted || resolvedTheme === "dark";

    if (!mounted || loading) {
        return (
            <div className="flex items-center justify-center min-h-screen" style={{background: "#0F1623"}}>
                <Loader2 className="size-6 animate-spin" style={{color: "#C9A84C"}}/>
            </div>
        );
    }

    /* ══════════════════════════════════════════════════════════
       DARK THEME — original navy layout
    ══════════════════════════════════════════════════════════ */
    if (isDark) {
        return (
            <div className="dark landing-sections">
                <section className="hero-aurora relative min-h-screen flex flex-col overflow-hidden"
                         style={{color: "rgba(255,255,255,0.9)"}}>
                    <nav className="sticky top-0 z-50 w-full" style={{
                        background: "rgba(15,22,35,0.85)",
                        backdropFilter: "blur(16px)",
                        WebkitBackdropFilter: "blur(16px)",
                        borderBottom: "1px solid rgba(255,255,255,0.06)"
                    }}>
                        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                                <div className="flex items-center justify-center size-7 rounded-lg" style={{
                                    background: "rgba(201,168,76,0.12)",
                                    border: "1px solid rgba(201,168,76,0.25)"
                                }}>
                                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                                        <path d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z" stroke="#C9A84C"
                                              strokeWidth="1.2" strokeLinejoin="round" fill="rgba(201,168,76,0.15)"/>
                                    </svg>
                                </div>
                                <span className="font-heading text-lg font-bold tracking-tight"
                                      style={{color: "rgba(255,255,255,0.95)"}}>Vitreon Legal</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <LanguageToggle />
                                <button
                                    onClick={() => setTheme(isDark ? "light" : "dark")}
                                    style={{
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        width: 32,
                                        height: 32,
                                        borderRadius: 10,
                                        border: "none",
                                        background: "transparent",
                                        cursor: "pointer",
                                        color: "#C9A84C",
                                        transition: "background 0.14s ease",
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.06)" }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent" }}
                                    aria-label="Toggle theme"
                                >
                                    {mounted ? (isDark ? <Sun size={15} strokeWidth={2} /> : <Moon size={15} strokeWidth={2} />) : <Moon size={15} strokeWidth={2} />}
                                </button>
                                {isAuthenticated ? (
                                    <a href="/chat"
                                       className="inline-flex items-center gap-1.5 text-sm font-medium px-4 py-1.5 rounded-full transition-all"
                                       style={{
                                           background: "rgba(201,168,76,0.12)",
                                           border: "1px solid rgba(201,168,76,0.3)",
                                           color: "#C9A84C"
                                       }}>
                                        {t("landing.go_to_chat")} <ArrowRight size={13}/>
                                    </a>
                                ) : (
                                    <>
                                        <a href="/login" className="text-sm font-medium transition-colors"
                                           style={{color: "rgba(255,255,255,0.55)"}}>{t("landing.sign_in")}</a>
                                        <a href="/login"
                                           className="inline-flex items-center gap-1.5 text-sm font-medium px-4 py-1.5 rounded-full transition-all"
                                           style={{
                                               background: "rgba(201,168,76,0.12)",
                                               border: "1px solid rgba(201,168,76,0.3)",
                                               color: "#C9A84C"
                                           }}>
                                            {t("landing.get_started")}
                                        </a>
                                    </>
                                )}
                            </div>
                        </div>
                    </nav>

                    <div className="flex-1 flex flex-col items-center justify-center px-6 pt-12 pb-8">
                        <motion.p initial={{opacity: 0, y: 6}} animate={{opacity: 1, y: 0}}
                                  transition={{duration: 0.5, delay: 0.1}}
                                  className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-5"
                                  style={{color: "rgba(201,168,76,0.75)"}}>{t("landing.tag")}
                        </motion.p>
                        <motion.h1 initial={{opacity: 0, y: 12}} animate={{opacity: 1, y: 0}}
                                   transition={{duration: 0.6, delay: 0.18}}
                                   className="font-heading text-center font-bold mb-5 max-w-3xl" style={{
                            fontSize: "clamp(2.2rem, 5vw, 4.5rem)",
                            letterSpacing: "-0.03em",
                            lineHeight: 1.1,
                            color: "rgba(255,255,255,0.95)"
                        }}>
                            {t("landing.hero_title_prefix")}{" "}<span style={{
                                background: "linear-gradient(90deg, #C9A84C 0%, #e8cc7a 50%, #C9A84C 100%)",
                                backgroundSize: "200% auto",
                                WebkitBackgroundClip: "text",
                                backgroundClip: "text",
                                WebkitTextFillColor: "transparent",
                                animation: "shimmer 3s linear infinite"
                            }}>{t("landing.hero_title_highlight")}</span>
                        </motion.h1>
                        <motion.p initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}}
                                  transition={{duration: 0.5, delay: 0.28}}
                                  className="text-base text-center mb-10 max-w-xl"
                                  style={{color: "rgba(255,255,255,0.48)", lineHeight: 1.6, whiteSpace: "pre-line"}}>
                            {t("landing.hero_subtitle")}
                        </motion.p>
                        <motion.div initial={{opacity: 0, y: 20}} animate={{opacity: 1, y: 0}}
                                    transition={{duration: 0.7, delay: 0.38}} className="w-full max-w-5xl">
                            <DemoPanel defaultScenarioIndex={isCzech && czScenarioIdx >= 0 ? czScenarioIdx : 0}/>
                        </motion.div>
                    </div>

                    <motion.div initial={{opacity: 0}} animate={{opacity: 1}} transition={{delay: 2, duration: 0.8}}
                                className="flex justify-center pb-8">
                        <a href="#why"
                           className="flex flex-col items-center gap-1.5 text-[10px] uppercase tracking-widest"
                           style={{color: "rgba(255,255,255,0.25)"}}>
                            {t("landing.scroll_to_explore")}
                            <svg width="10" height="14" viewBox="0 0 10 14" fill="none" className="animate-float-down">
                                <path d="M5 1v12M1 9l4 4 4-4" stroke="currentColor" strokeWidth="1.2"
                                      strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                        </a>
                    </motion.div>

                    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden"
                         style={{zIndex: 0}}>
                        <div className="absolute rounded-full" style={{
                            width: "600px",
                            height: "600px",
                            top: "-200px",
                            left: "50%",
                            transform: "translateX(-50%)",
                            background: "radial-gradient(circle, rgba(201,168,76,0.06) 0%, transparent 70%)",
                            filter: "blur(40px)"
                        }}/>
                        <div className="absolute rounded-full" style={{
                            width: "400px",
                            height: "400px",
                            bottom: "-100px",
                            right: "10%",
                            background: "radial-gradient(circle, rgba(27,43,75,0.8) 0%, transparent 70%)",
                            filter: "blur(60px)"
                        }}/>
                    </div>
                </section>

                {isCzech && <CzechCaselawSection/>}

                <div id="why"><ValuePillars/></div>
                <HowItWorks/>
                <TrustSection demoMode={false} initialApiKey=""/>

                {/* ── BENCHMARK PERFORMANCE (dark) ── */}
                <section style={{
                    padding: "80px 24px",
                    background: "#0A1120",
                    position: "relative",
                    overflow: "hidden"
                }}>
                    <div aria-hidden style={{position: "absolute", inset: 0, pointerEvents: "none"}}>
                        <div style={{
                            position: "absolute",
                            width: 600,
                            height: 600,
                            top: "50%",
                            left: "50%",
                            transform: "translate(-50%,-50%)",
                            background: "radial-gradient(circle, rgba(201,168,76,0.05) 0%, transparent 70%)",
                            filter: "blur(60px)"
                        }}/>
                    </div>
                    <div className="max-w-5xl mx-auto" style={{position: "relative"}}>
                        <motion.p initial={{opacity: 0, y: 12}} whileInView={{opacity: 1, y: 0}}
                                  viewport={{once: true, margin: "-80px"}} transition={{duration: 0.5}}
                                  className="text-center text-[11px] uppercase tracking-[0.16em] font-semibold mb-2.5"
                                  style={{color: "rgba(201,168,76,0.60)"}}>
                            {t("landing.bench_label")}
                        </motion.p>
                        <motion.h2 initial={{opacity: 0, y: 12}} whileInView={{opacity: 1, y: 0}}
                                   viewport={{once: true, margin: "-80px"}} transition={{duration: 0.5, delay: 0.08}}
                                   className="font-heading text-center font-bold mb-2"
                                   style={{
                                       fontSize: "clamp(1.8rem,3vw,2.4rem)",
                                       letterSpacing: "-0.03em",
                                       color: "rgba(255,255,255,0.90)"
                                   }}>
                            {t("landing.bench_heading")}
                        </motion.h2>
                        <motion.p initial={{opacity: 0}} whileInView={{opacity: 1}}
                                  viewport={{once: true, margin: "-80px"}} transition={{duration: 0.5, delay: 0.14}}
                                  className="text-center text-sm mb-10"
                                  style={{color: "rgba(255,255,255,0.38)"}}>
                            {t("landing.bench_subtitle")}
                        </motion.p>
                        <div style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                            gap: 16
                        }}>
                            {BENCHMARKS.map((b, i) => (
                                <motion.div key={b.name} initial={{opacity: 0, y: 24}}
                                            whileInView={{opacity: 1, y: 0}}
                                            viewport={{once: true, margin: "-60px"}}
                                            transition={{duration: 0.5, delay: i * 0.1}}>
                                    <DarkBenchmarkCard benchmark={b}/>
                                </motion.div>
                            ))}
                        </div>
                    </div>
                </section>

                <footer className="py-8 px-6"
                        style={{background: "#0A1120", borderTop: "1px solid rgba(255,255,255,0.06)"}}>
                    <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                            <div className="flex items-center justify-center size-5 rounded"
                                 style={{background: "rgba(201,168,76,0.12)"}}>
                                <svg width="10" height="10" viewBox="0 0 14 14" fill="none">
                                    <path d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z" stroke="#C9A84C"
                                          strokeWidth="1.2" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <span className="font-heading text-sm font-semibold"
                                  style={{color: "rgba(255,255,255,0.6)"}}>Vitreon Legal</span>
                        </div>
                        <p className="text-[11px]" style={{color: "rgba(255,255,255,0.28)"}}>
                            {new Date().getFullYear()} Vitreon Legal
                            <span className="mx-2" style={{color: "rgba(255,255,255,0.15)"}}>·</span>
                            <a href="/privacy" className="hover:text-white/50 transition-colors">{t("landing.privacy")}</a>
                            <span className="mx-2" style={{color: "rgba(255,255,255,0.15)"}}>·</span>
                            <a href="/terms" className="hover:text-white/50 transition-colors">{t("landing.terms")}</a>
                        </p>
                    </div>
                </footer>
            </div>
        );
    }

    /* ══════════════════════════════════════════════════════════
       LIGHT THEME — warm Arrakis amber
    ══════════════════════════════════════════════════════════ */
    return (
        <div style={{fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif"}}>

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
                            <span style={{
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
                                onClick={() => setTheme(isDark ? "light" : "dark")}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: 32,
                                    height: 32,
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
                                {mounted ? (isDark ? <Sun size={15} strokeWidth={2} /> : <Moon size={15} strokeWidth={2} />) : <Moon size={15} strokeWidth={2} />}
                            </button>
                            {isAuthenticated ? (
                                <a href="/chat" style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: 6,
                                    padding: "7px 16px",
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
                                    <a href="/login" style={{
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

                <div style={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "48px 24px 32px",
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
                    <motion.h1 initial={{opacity: 0, y: 12}} animate={{opacity: 1, y: 0}}
                               transition={{duration: 0.6, delay: 0.18}} style={{
                        fontFamily: "Georgia, 'Times New Roman', serif",
                        fontSize: "clamp(2.2rem, 5vw, 4.5rem)",
                        fontWeight: 700,
                        letterSpacing: "-0.03em",
                        lineHeight: 1.1,
                        color: "#1a0e04",
                        marginBottom: 20,
                        maxWidth: 780
                    }}>
                        {t("landing.hero_title_prefix")}{" "}<span style={{
                            background: "linear-gradient(90deg, #c47c00 0%, #e8a020 50%, #c47c00 100%)",
                            backgroundSize: "200% auto",
                            WebkitBackgroundClip: "text",
                            backgroundClip: "text",
                            WebkitTextFillColor: "transparent",
                            animation: "shimmer 3s linear infinite"
                        }}>{t("landing.hero_title_highlight")}</span>
                    </motion.h1>
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
                            <div style={{background: "#0d1520", borderRadius: 16, overflow: "hidden"}}><DemoPanel defaultScenarioIndex={isCzech && czScenarioIdx >= 0 ? czScenarioIdx : 0}/>
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

            {/* ── VALUE PILLARS ── */}
            <section id="why" style={{
                position: "relative",
                padding: "80px 24px",
                background: "linear-gradient(180deg, #dbb870 0%, #e8d4b8 100%)",
                overflow: "hidden"
            }}>
                <div aria-hidden style={{position: "absolute", inset: 0, pointerEvents: "none"}}>
                    <div style={{
                        position: "absolute",
                        width: 600,
                        height: 600,
                        top: -100,
                        right: "5%",
                        background: "radial-gradient(circle, rgba(175,130,20,0.30) 0%, transparent 65%)"
                    }}/>
                </div>
                <div style={{maxWidth: 1000, margin: "0 auto", position: "relative"}}>
                    <motion.p initial={{opacity: 0, y: 12}} whileInView={{opacity: 1, y: 0}}
                              viewport={{once: true, margin: "-80px"}} transition={{duration: 0.5}} style={{
                        textAlign: "center",
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.16em",
                        fontWeight: 600,
                        color: "rgba(46,31,8,0.45)",
                        marginBottom: 10
                    }}>{t("landing.why_label")}
                    </motion.p>
                    <motion.h2 initial={{opacity: 0, y: 12}} whileInView={{opacity: 1, y: 0}}
                               viewport={{once: true, margin: "-80px"}} transition={{duration: 0.5, delay: 0.08}}
                               style={{
                                   textAlign: "center",
                                   fontFamily: "Georgia, serif",
                                   fontSize: "clamp(1.8rem,3vw,2.6rem)",
                                   fontWeight: 700,
                                   letterSpacing: "-0.03em",
                                   color: "#1a0e04",
                                   marginBottom: 52
                               }}>{t("landing.light_why_heading")}
                    </motion.h2>
                    <div
                        style={{display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16}}>
                        {[1, 2, 3].map((n, i) => {
                            const stat = t(`landing.light_pillar${n}_stat`);
                            const statLabel = t(`landing.light_pillar${n}_stat_label`);
                            const title = t(`landing.light_pillar${n}_title`);
                            const body = t(`landing.light_pillar${n}_body`);
                            const Icon = LIGHT_PILLAR_ICONS[i];
                            return (
                            <motion.div key={title} initial={{opacity: 0, y: 28}} whileInView={{opacity: 1, y: 0}}
                                        viewport={{once: true, margin: "-80px"}}
                                        transition={{duration: 0.55, delay: i * 0.12}}
                                        whileHover={{y: -4, transition: {duration: 0.2}}}
                                        style={{
                                            ...warmGlass,
                                            borderRadius: 20,
                                            padding: "24px",
                                            display: "flex",
                                            flexDirection: "column",
                                            borderTop: "2px solid rgba(196,124,0,0.40)"
                                        }}>
                                <p style={{
                                    fontFamily: "Georgia, serif",
                                    fontSize: "2.4rem",
                                    fontWeight: 700,
                                    lineHeight: 1,
                                    background: "linear-gradient(135deg, #c47c00 0%, #e8a020 100%)",
                                    WebkitBackgroundClip: "text",
                                    backgroundClip: "text",
                                    WebkitTextFillColor: "transparent",
                                    marginBottom: 2
                                }}>{stat}</p>
                                <p style={{
                                    fontSize: 11,
                                    textTransform: "uppercase",
                                    letterSpacing: "0.10em",
                                    fontWeight: 600,
                                    color: "rgba(92,46,8,0.50)",
                                    marginBottom: 16
                                }}>{statLabel}</p>
                                <div style={{
                                    height: 1,
                                    background: "linear-gradient(90deg, rgba(196,124,0,0.25) 0%, transparent 100%)",
                                    marginBottom: 16
                                }}/>
                                <div style={{display: "flex", alignItems: "center", gap: 10, marginBottom: 10}}>
                                    <div style={{
                                        width: 34,
                                        height: 34,
                                        borderRadius: 10,
                                        background: "rgba(196,124,0,0.14)",
                                        border: "0.5px solid rgba(196,124,0,0.28)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center"
                                    }}>
                                        <Icon size={16} style={{color: "#c47c00"}} strokeWidth={1.7}/>
                                    </div>
                                    <h3 style={{fontSize: 15, fontWeight: 600, color: "#1a0e04"}}>{title}</h3>
                                </div>
                                <p style={{fontSize: 13, lineHeight: 1.65, color: "rgba(46,31,8,0.60)"}}>{body}</p>
                            </motion.div>
                        ); })}
                    </div>
                </div>
            </section>

            {/* ── HOW IT WORKS ── */}
            <section style={{
                padding: "80px 24px",
                background: "linear-gradient(180deg, #e8d4b8 0%, #dfc090 100%)",
                position: "relative"
            }}>
                <div aria-hidden style={{position: "absolute", inset: 0, pointerEvents: "none"}}>
                    <div style={{
                        position: "absolute",
                        width: 500,
                        height: 500,
                        bottom: -80,
                        left: "15%",
                        background: "radial-gradient(circle, rgba(190,110,30,0.30) 0%, transparent 65%)"
                    }}/>
                </div>
                <div style={{maxWidth: 800, margin: "0 auto", position: "relative"}}>
                    <motion.p initial={{opacity: 0, y: 10}} whileInView={{opacity: 1, y: 0}}
                              viewport={{once: true, margin: "-60px"}} transition={{duration: 0.5}} style={{
                        textAlign: "center",
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.16em",
                        fontWeight: 600,
                        color: "rgba(46,31,8,0.45)",
                        marginBottom: 10
                    }}>{t("landing.how_label")}
                    </motion.p>
                    <motion.h2 initial={{opacity: 0, y: 10}} whileInView={{opacity: 1, y: 0}}
                               viewport={{once: true, margin: "-60px"}} transition={{duration: 0.5, delay: 0.08}}
                               style={{
                                   textAlign: "center",
                                   fontFamily: "Georgia, serif",
                                   fontSize: "clamp(1.8rem,3vw,2.6rem)",
                                   fontWeight: 700,
                                   letterSpacing: "-0.03em",
                                   color: "#1a0e04",
                                   marginBottom: 40
                               }}>{t("landing.how_heading")}
                    </motion.h2>
                    <motion.div initial={{opacity: 0, y: 16}} whileInView={{opacity: 1, y: 0}}
                                viewport={{once: true, margin: "-60px"}} transition={{duration: 0.5, delay: 0.18}}>
                        <div style={{
                            display: "flex",
                            justifyContent: "center",
                            gap: 8,
                            marginBottom: 24,
                            flexWrap: "wrap"
                        }}>
                            {lightSteps.map((s, i) => (
                                <button key={s.number} onClick={() => setActiveStep(i)} style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                    borderRadius: "9999px",
                                    padding: "8px 18px",
                                    fontSize: 12,
                                    fontWeight: 500,
                                    cursor: "pointer",
                                    transition: "all 0.15s",
                                    background: i === activeStep ? "rgba(196,124,0,0.20)" : "rgba(255,255,255,0.20)",
                                    border: i === activeStep ? "0.5px solid rgba(196,124,0,0.45)" : "0.5px solid rgba(255,255,255,0.45)",
                                    color: i === activeStep ? "#5c2e08" : "rgba(46,31,8,0.55)"
                                }}>
                                    <span style={{
                                        fontFamily: "monospace",
                                        fontWeight: 700,
                                        fontSize: 11
                                    }}>{s.number}</span>
                                    <span>{s.title}</span>
                                </button>
                            ))}
                        </div>
                        <AnimatePresence mode="wait">
                            <motion.div key={activeStep} initial={{opacity: 0, y: 12}} animate={{opacity: 1, y: 0}}
                                        exit={{opacity: 0, y: -8}} transition={{duration: 0.3}}
                                        style={{
                                            ...warmGlass,
                                            borderRadius: 20,
                                            padding: "28px 32px",
                                            display: "grid",
                                            gridTemplateColumns: "1fr 1fr",
                                            gap: 32,
                                            alignItems: "center"
                                        }}>
                                <div>
                                    <div style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        width: 36,
                                        height: 36,
                                        borderRadius: "50%",
                                        background: "rgba(196,124,0,0.15)",
                                        border: "0.5px solid rgba(196,124,0,0.30)",
                                        color: "#c47c00",
                                        fontFamily: "monospace",
                                        fontSize: 11,
                                        fontWeight: 700,
                                        marginBottom: 16
                                    }}>{lightSteps[activeStep].number}</div>
                                    <h3 style={{
                                        fontSize: 20,
                                        fontWeight: 600,
                                        color: "#1a0e04",
                                        marginBottom: 8
                                    }}>{lightSteps[activeStep].title}</h3>
                                    <p style={{
                                        fontSize: 14,
                                        lineHeight: 1.7,
                                        color: "rgba(46,31,8,0.60)",
                                        marginBottom: 20
                                    }}>{lightSteps[activeStep].body}</p>
                                    <div style={{display: "flex", gap: 6}}>
                                        {lightSteps.map((_, i) => (
                                            <motion.div key={i} onClick={() => setActiveStep(i)} animate={{
                                                width: i === activeStep ? 28 : 8,
                                                opacity: i === activeStep ? 1 : 0.30
                                            }} transition={{duration: 0.3}} style={{
                                                height: 4,
                                                borderRadius: 2,
                                                background: "#c47c00",
                                                cursor: "pointer"
                                            }}/>
                                        ))}
                                    </div>
                                </div>
                                <div style={{
                                    background: "rgba(255,255,255,0.18)",
                                    border: "0.5px solid rgba(255,255,255,0.45)",
                                    borderRadius: 14,
                                    padding: "18px 20px",
                                    minHeight: 120
                                }}>
                                    {activeStep === 0 && <div style={{
                                        background: "rgba(196,124,0,0.10)",
                                        border: "0.5px solid rgba(196,124,0,0.25)",
                                        borderRadius: 10,
                                        padding: "12px 14px"
                                    }}><span
                                        style={{fontSize: 12, fontFamily: "monospace", color: "rgba(46,31,8,0.65)"}}>What are the notice periods under DIFC Employment Law?<span
                                        style={{
                                            display: "inline-block",
                                            width: 2,
                                            height: 13,
                                            background: "#c47c00",
                                            marginLeft: 2,
                                            verticalAlign: "middle",
                                            animation: "blink-cursor 0.7s step-end infinite"
                                        }}/></span></div>}
                                    {activeStep === 1 && <div style={{
                                        display: "flex",
                                        flexDirection: "column",
                                        gap: 10
                                    }}>{["Scanning 47 pages", "Located Article 62", "Ranked 3 passages"].map((label, i) => (
                                        <motion.div key={label} initial={{opacity: 0, x: -10}}
                                                    animate={{opacity: 1, x: 0}}
                                                    transition={{delay: i * 0.25, duration: 0.35}}
                                                    style={{display: "flex", alignItems: "center", gap: 8}}>
                                            <motion.div animate={{scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5]}}
                                                        transition={{duration: 1, repeat: Infinity, delay: i * 0.3}}
                                                        style={{
                                                            width: 8,
                                                            height: 8,
                                                            borderRadius: "50%",
                                                            background: "#c47c00",
                                                            flexShrink: 0
                                                        }}/>
                                            <span style={{
                                                fontSize: 12,
                                                fontFamily: "monospace",
                                                color: "rgba(46,31,8,0.60)"
                                            }}>{label}</span>
                                            <motion.div style={{
                                                flex: 1,
                                                height: 1,
                                                background: "rgba(196,124,0,0.30)",
                                                borderRadius: 1
                                            }} initial={{scaleX: 0, originX: 0}} animate={{scaleX: 1}}
                                                        transition={{delay: i * 0.25 + 0.15, duration: 0.4}}/>
                                        </motion.div>))}</div>}
                                    {activeStep === 2 && <div><p style={{
                                        fontSize: 9,
                                        fontFamily: "monospace",
                                        textTransform: "uppercase",
                                        letterSpacing: "0.12em",
                                        color: "#c47c00",
                                        marginBottom: 8
                                    }}>Article 62 · DIFC Employment Law · Page 18</p>
                                        <motion.div initial={{opacity: 0}} animate={{opacity: 1}}
                                                    transition={{delay: 0.3, duration: 0.4}} style={{
                                            background: "rgba(196,124,0,0.14)",
                                            borderRadius: 8,
                                            padding: "10px 12px"
                                        }}><p style={{
                                            fontSize: 11,
                                            lineHeight: 1.6,
                                            color: "rgba(46,31,8,0.75)",
                                            fontFamily: "Georgia, serif"
                                        }}>"The minimum notice period is <strong>30 days</strong> for employees with
                                            over 1 year of service, rising to <strong>90 days</strong> after 5 years."
                                        </p></motion.div>
                                    </div>}
                                </div>
                            </motion.div>
                        </AnimatePresence>
                    </motion.div>
                </div>
            </section>

            {/* ── BENCHMARK PERFORMANCE (light) ── */}
            <section style={{
                padding: "80px 24px",
                background: "linear-gradient(180deg, #dfc090 0%, #e8d4b8 100%)",
                position: "relative",
                overflow: "hidden"
            }}>
                <div aria-hidden style={{position: "absolute", inset: 0, pointerEvents: "none"}}>
                    <div style={{
                        position: "absolute",
                        width: 500,
                        height: 500,
                        top: -80,
                        right: "10%",
                        background: "radial-gradient(circle, rgba(175,130,20,0.25) 0%, transparent 65%)"
                    }}/>
                </div>
                <div style={{maxWidth: 1000, margin: "0 auto", position: "relative"}}>
                    <motion.p initial={{opacity: 0, y: 10}} whileInView={{opacity: 1, y: 0}}
                              viewport={{once: true, margin: "-60px"}} transition={{duration: 0.5}} style={{
                        textAlign: "center",
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.16em",
                        fontWeight: 600,
                        color: "rgba(46,31,8,0.45)",
                        marginBottom: 10
                    }}>{t("landing.bench_label")}</motion.p>
                    <motion.h2 initial={{opacity: 0, y: 10}} whileInView={{opacity: 1, y: 0}}
                               viewport={{once: true, margin: "-60px"}} transition={{duration: 0.5, delay: 0.08}}
                               style={{
                                   textAlign: "center",
                                   fontFamily: "Georgia, serif",
                                   fontSize: "clamp(1.8rem,3vw,2.6rem)",
                                   fontWeight: 700,
                                   letterSpacing: "-0.03em",
                                   color: "#1a0e04",
                                   marginBottom: 8
                               }}>{t("landing.bench_heading")}</motion.h2>
                    <motion.p initial={{opacity: 0}} whileInView={{opacity: 1}}
                              viewport={{once: true, margin: "-60px"}} transition={{duration: 0.5, delay: 0.14}}
                              style={{
                                  textAlign: "center",
                                  fontSize: 13,
                                  color: "rgba(46,31,8,0.50)",
                                  marginBottom: 40
                              }}>{t("landing.bench_subtitle")}</motion.p>
                    <div style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                        gap: 16
                    }}>
                        {BENCHMARKS.map((b, i) => (
                            <motion.div key={b.name} initial={{opacity: 0, y: 24}} whileInView={{opacity: 1, y: 0}}
                                        viewport={{once: true, margin: "-60px"}}
                                        transition={{duration: 0.5, delay: i * 0.1}}>
                                <LightBenchmarkCard benchmark={b}/>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── CTA ── */}
            <section id="access" style={{
                position: "relative",
                padding: "80px 24px 100px",
                background: "linear-gradient(180deg, #dfc090 0%, #e8d4b8 60%, #dbb870 100%)",
                overflow: "hidden"
            }}>
                <div aria-hidden style={{position: "absolute", inset: 0, pointerEvents: "none"}}>
                    <div style={{
                        position: "absolute",
                        width: 600,
                        height: 600,
                        top: "50%",
                        left: "50%",
                        transform: "translate(-50%,-50%)",
                        background: "radial-gradient(circle, rgba(196,124,0,0.20) 0%, transparent 65%)",
                        filter: "blur(60px)"
                    }}/>
                </div>
                <div style={{maxWidth: 520, margin: "0 auto", position: "relative"}}>
                    <motion.p initial={{opacity: 0, y: 10}} whileInView={{opacity: 1, y: 0}} viewport={{once: true}}
                              transition={{duration: 0.5}} style={{
                        textAlign: "center",
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.20em",
                        fontWeight: 600,
                        color: "rgba(46,31,8,0.45)",
                        marginBottom: 10
                    }}>{t("landing.cta_label")}
                    </motion.p>
                    <motion.h2 initial={{opacity: 0, y: 10}} whileInView={{opacity: 1, y: 0}} viewport={{once: true}}
                               transition={{duration: 0.5, delay: 0.08}} style={{
                        textAlign: "center",
                        fontFamily: "Georgia, serif",
                        fontSize: "clamp(1.8rem,3vw,2.4rem)",
                        fontWeight: 700,
                        letterSpacing: "-0.03em",
                        color: "#1a0e04",
                        marginBottom: 40
                    }}>{t("landing.cta_heading")}
                    </motion.h2>
                    <motion.div initial={{opacity: 0, y: 16}} whileInView={{opacity: 1, y: 0}} viewport={{once: true}}
                                transition={{duration: 0.5, delay: 0.1}} style={{
                        display: "flex",
                        flexWrap: "wrap",
                        justifyContent: "center",
                        gap: 10,
                        marginBottom: 32
                    }}>
                        {LIGHT_TRUST_KEYS.map((keys, i) => {
                            const Icon = LIGHT_TRUST_ICONS[i];
                            const label = t(keys.label);
                            const sub = t(keys.sub);
                            return (
                            <motion.div key={keys.label} initial={{opacity: 0, y: 8}} whileInView={{opacity: 1, y: 0}}
                                        viewport={{once: true}} transition={{duration: 0.4, delay: 0.15 + i * 0.08}}
                                        style={{
                                            display: "flex",
                                            alignItems: "center",
                                            gap: 10, ...warmGlass,
                                            borderRadius: "9999px",
                                            padding: "8px 16px 8px 8px"
                                        }}>
                                <div style={{
                                    width: 24,
                                    height: 24,
                                    borderRadius: 7,
                                    background: "rgba(196,124,0,0.14)",
                                    border: "0.5px solid rgba(196,124,0,0.28)",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center"
                                }}>
                                    <Icon size={13} style={{color: "#c47c00"}}/>
                                </div>
                                <div>
                                    <p style={{
                                        fontSize: 12,
                                        fontWeight: 600,
                                        color: "#1a0e04",
                                        lineHeight: 1,
                                        marginBottom: 2
                                    }}>{label}</p>
                                    <p style={{fontSize: 10, color: "rgba(46,31,8,0.45)", lineHeight: 1}}>{sub}</p>
                                </div>
                            </motion.div>
                        ); })}
                    </motion.div>
                    <motion.div initial={{opacity: 0, y: 24}} whileInView={{opacity: 1, y: 0}} viewport={{once: true}}
                                transition={{duration: 0.6, delay: 0.2}} style={{
                        ...warmGlass,
                        borderRadius: 24,
                        overflow: "clip",
                        textAlign: "center",
                        padding: "36px 24px"
                    }}>
                        <h3 style={{
                            fontFamily: "Georgia, serif",
                            fontSize: "1.15rem",
                            fontWeight: 700,
                            color: "#1a0e04",
                            margin: "0 0 8px"
                        }}>{t("landing.cta_no_cc")}</h3>
                        <p style={{fontSize: 13, color: "rgba(46,31,8,0.50)", margin: "0 0 24px"}}>{t("landing.cta_signup_info")}</p>
                        <div style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 12,
                            maxWidth: 320,
                            margin: "0 auto"
                        }}>
                            <a href="/login" style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: 8,
                                padding: "12px",
                                borderRadius: 12,
                                fontSize: 14,
                                fontWeight: 600,
                                background: "#5c2e08",
                                color: "#fff8ee",
                                textDecoration: "none",
                                boxShadow: "0 2px 12px rgba(92,46,8,0.28)"
                            }}>
                                {t("landing.cta_get_started")} <ArrowRight size={14}/>
                            </a>
                            <a href="/login" style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: 8,
                                padding: "12px",
                                borderRadius: 12,
                                fontSize: 13,
                                fontWeight: 500,
                                background: "rgba(255,255,255,0.30)",
                                border: "0.5px solid rgba(255,255,255,0.55)",
                                color: "#2e1f08",
                                textDecoration: "none"
                            }}>
                                {t("landing.cta_sign_in")}
                            </a>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* ── FOOTER ── */}
            <footer style={{
                padding: "20px 24px",
                background: "rgba(255,248,232,0.55)",
                backdropFilter: "blur(24px)",
                WebkitBackdropFilter: "blur(24px)",
                borderTop: "0.5px solid rgba(255,255,255,0.45)"
            }}>
                <div style={{
                    maxWidth: 1100,
                    margin: "0 auto",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: 12
                }}>
                    <span style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: "rgba(46,31,8,0.55)",
                        fontFamily: "Georgia, serif",
                        letterSpacing: "-0.03em"
                    }}>Vitreon Legal</span>
                    <p style={{fontSize: 11, color: "rgba(46,31,8,0.35)", margin: 0}}>
                        {new Date().getFullYear()} Vitreon Legal
                        <span style={{margin: "0 8px", color: "rgba(46,31,8,0.20)"}}>·</span>
                        <a href="/privacy" style={{color: "rgba(46,31,8,0.40)", textDecoration: "none"}}>{t("landing.privacy")}</a>
                        <span style={{margin: "0 8px", color: "rgba(46,31,8,0.20)"}}>·</span>
                        <a href="/terms" style={{color: "rgba(46,31,8,0.40)", textDecoration: "none"}}>{t("landing.terms")}</a>
                    </p>
                </div>
            </footer>
        </div>
    );
}

function DarkBenchmarkCard({benchmark}: { benchmark: BenchmarkData }) {
    const ourPct = benchmark.ourScore * 100;
    const sotaPct = benchmark.sota * 100;
    return (
        <div style={{
            background: "rgba(255,255,255,0.04)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 16,
            padding: 20,
            display: "flex",
            flexDirection: "column",
            gap: 14
        }}>
            <div>
                <a href={benchmark.url} target="_blank" rel="noopener noreferrer" style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: "rgba(255,255,255,0.90)",
                    textDecoration: "none",
                    borderBottom: "1px solid rgba(201,168,76,0.50)",
                    paddingBottom: 1
                }}>{benchmark.name}</a>
                <p style={{fontSize: 12, color: "rgba(255,255,255,0.38)", margin: "6px 0 0", lineHeight: 1.4}}>
                    {benchmark.description}
                </p>
            </div>
            <div style={{display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap"}}>
                <span style={{
                    fontSize: 30,
                    fontWeight: 800,
                    color: "#C9A84C",
                    letterSpacing: "-0.02em",
                    lineHeight: 1
                }}>{benchmark.ourScore.toFixed(3)}</span>
                <span style={{
                    padding: "3px 10px",
                    borderRadius: "9999px",
                    fontSize: 11,
                    fontWeight: 600,
                    background: "rgba(53,118,174,0.14)",
                    border: "1px solid rgba(53,118,174,0.32)",
                    color: "#7bb8e8"
                }}>{benchmark.improvement}</span>
            </div>
            <div style={{display: "flex", flexDirection: "column", gap: 8}}>
                <div>
                    <div style={{display: "flex", justifyContent: "space-between", marginBottom: 4}}>
                        <span style={{fontSize: 10, color: "rgba(201,168,76,0.70)", fontWeight: 600}}>Vitreon</span>
                        <span style={{
                            fontSize: 10,
                            color: "rgba(255,255,255,0.40)"
                        }}>{benchmark.ourScore.toFixed(3)}</span>
                    </div>
                    <div style={{
                        height: 5,
                        borderRadius: 3,
                        background: "rgba(255,255,255,0.07)",
                        overflow: "hidden"
                    }}>
                        <div style={{
                            height: "100%",
                            width: `${ourPct}%`,
                            background: "linear-gradient(90deg, #C9A84C, #e8cc7a)",
                            borderRadius: 3
                        }}/>
                    </div>
                </div>
                <div>
                    <div style={{display: "flex", justifyContent: "space-between", marginBottom: 4}}>
                        <span style={{fontSize: 10, color: "rgba(255,255,255,0.28)", fontWeight: 600}}>SOTA</span>
                        <span style={{
                            fontSize: 10,
                            color: "rgba(255,255,255,0.28)"
                        }}>{benchmark.sota.toFixed(3)}</span>
                    </div>
                    <div style={{
                        height: 5,
                        borderRadius: 3,
                        background: "rgba(255,255,255,0.07)",
                        overflow: "hidden"
                    }}>
                        <div style={{
                            height: "100%",
                            width: `${sotaPct}%`,
                            background: "rgba(255,255,255,0.18)",
                            borderRadius: 3
                        }}/>
                    </div>
                </div>
            </div>
        </div>
    );
}

function LightBenchmarkCard({benchmark}: { benchmark: BenchmarkData }) {
    const ourPct = benchmark.ourScore * 100;
    const sotaPct = benchmark.sota * 100;
    return (
        <div style={{
            ...warmGlass,
            borderRadius: 16,
            padding: 20,
            display: "flex",
            flexDirection: "column",
            gap: 14
        }}>
            <div>
                <a href={benchmark.url} target="_blank" rel="noopener noreferrer" style={{
                    fontSize: 13,
                    fontWeight: 700,
                    color: "#1a0e04",
                    textDecoration: "none",
                    borderBottom: "1px solid #c47c00",
                    paddingBottom: 1
                }}>{benchmark.name}</a>
                <p style={{fontSize: 11, color: "rgba(46,31,8,0.50)", margin: "5px 0 0", lineHeight: 1.4}}>
                    {benchmark.description}
                </p>
            </div>
            <div style={{display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap"}}>
                <span style={{
                    fontSize: 28,
                    fontWeight: 800,
                    color: "#c47c00",
                    letterSpacing: "-0.02em",
                    lineHeight: 1
                }}>{benchmark.ourScore.toFixed(3)}</span>
                <span style={{
                    padding: "3px 10px",
                    borderRadius: "9999px",
                    fontSize: 11,
                    fontWeight: 600,
                    background: "rgba(53,118,174,0.14)",
                    border: "1px solid rgba(53,118,174,0.32)",
                    color: "#1a3f6e"
                }}>{benchmark.improvement}</span>
            </div>
            <div style={{display: "flex", flexDirection: "column", gap: 6}}>
                <div>
                    <div style={{display: "flex", justifyContent: "space-between", marginBottom: 3}}>
                        <span style={{fontSize: 10, color: "rgba(92,46,8,0.70)", fontWeight: 600}}>Vitreon</span>
                        <span style={{
                            fontSize: 10,
                            color: "rgba(46,31,8,0.50)"
                        }}>{benchmark.ourScore.toFixed(3)}</span>
                    </div>
                    <div style={{
                        height: 5,
                        borderRadius: 3,
                        background: "rgba(0,0,0,0.08)",
                        overflow: "hidden"
                    }}>
                        <div style={{
                            height: "100%",
                            width: `${ourPct}%`,
                            background: "linear-gradient(90deg, #b29254, #c47c00)",
                            borderRadius: 3
                        }}/>
                    </div>
                </div>
                <div>
                    <div style={{display: "flex", justifyContent: "space-between", marginBottom: 3}}>
                        <span style={{fontSize: 10, color: "rgba(46,31,8,0.38)", fontWeight: 600}}>SOTA</span>
                        <span style={{
                            fontSize: 10,
                            color: "rgba(46,31,8,0.38)"
                        }}>{benchmark.sota.toFixed(3)}</span>
                    </div>
                    <div style={{
                        height: 5,
                        borderRadius: 3,
                        background: "rgba(0,0,0,0.08)",
                        overflow: "hidden"
                    }}>
                        <div style={{
                            height: "100%",
                            width: `${sotaPct}%`,
                            background: "rgba(46,31,8,0.22)",
                            borderRadius: 3
                        }}/>
                    </div>
                </div>
            </div>
        </div>
    );
}
