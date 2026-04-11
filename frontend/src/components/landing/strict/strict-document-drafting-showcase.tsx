"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { V3_FADE_UP } from "@/lib/v3-motion";
import { useIsMobile } from "@/hooks/use-mobile";

// ─── Data ─────────────────────────────────────────────────────────────────────

const SHOWCASE_TEMPLATES = [
    { slug: "zaloba_neplatnost_vypovedi", name: "Žaloba na neplatnost výpovědi", jurisdiction: "CZ", category: "labor" },
    { slug: "navrh_platebni_rozkaz", name: "Návrh na platební rozkaz", jurisdiction: "CZ", category: "civil" },
    { slug: "vlastni_dokument", name: "Vlastní dokument", jurisdiction: "CZ", category: "custom" },
] as const;

const FAKE_FIELDS = [
    { label: "Žalobce", value: "Jan Novák" },
    { label: "Žalovaný", value: "ABC s.r.o." },
    { label: "Datum výpovědi", value: "15. 3. 2025" },
    { label: "Odůvodnění", value: "Porušení pracovní kázně dle § 52 písm. g) ZP..." },
] as const;

const STEPS = [
    {
        num: "01",
        title: "Choose Template",
        sub: "Select from 9 Czech legal templates — employment, civil, commercial.",
    },
    {
        num: "02",
        title: "AI Fills Fields",
        sub: "AI extracts parties, dates, and legal grounds from your case facts.",
    },
    {
        num: "03",
        title: "PDF + Citations",
        sub: "Receive a formatted PDF with statute and case-law citations.",
    },
] as const;

const CATEGORY_LABELS: Record<string, string> = {
    labor: "Pracovní právo",
    civil: "Občanské právo",
    custom: "Vlastní",
};

const STEP_DURATION = 5000;

// ─── Step visuals ─────────────────────────────────────────────────────────────

function ChooseTemplateVisual() {
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {SHOWCASE_TEMPLATES.map((tpl, i) => (
                <motion.div
                    key={tpl.slug}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.15, duration: 0.35 }}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 10,
                        padding: "10px 14px",
                        borderRadius: 10,
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid var(--strict-gold-border)",
                    }}
                >
                    <span style={{
                        fontSize: 11,
                        fontFamily: "Georgia, serif",
                        color: "var(--strict-text-body)",
                        lineHeight: 1.35,
                        flex: 1,
                        minWidth: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>
                        {tpl.name}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                        <span style={{
                            fontSize: 9,
                            fontFamily: "monospace",
                            fontWeight: 700,
                            color: "var(--strict-gold-text)",
                            background: "var(--strict-gold-badge-bg)",
                            border: "1px solid var(--strict-gold-badge-border)",
                            borderRadius: 4,
                            padding: "1px 5px",
                            letterSpacing: "0.05em",
                        }}>
                            {tpl.jurisdiction}
                        </span>
                        <span style={{
                            fontSize: 9,
                            fontFamily: "monospace",
                            color: "var(--strict-text-dim)",
                            background: "rgba(255,255,255,0.03)",
                            border: "1px solid var(--strict-gold-border)",
                            borderRadius: 4,
                            padding: "1px 5px",
                        }}>
                            {CATEGORY_LABELS[tpl.category]}
                        </span>
                    </div>
                </motion.div>
            ))}
        </div>
    );
}

function AiFillsFieldsVisual() {
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {FAKE_FIELDS.map((field, i) => (
                <motion.div
                    key={field.label}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.25, duration: 0.35 }}
                    style={{
                        display: "flex",
                        alignItems: "baseline",
                        gap: 10,
                        padding: "6px 0",
                        borderBottom: "1px solid var(--strict-gold-border)",
                    }}
                >
                    <span style={{
                        fontSize: 9,
                        fontFamily: "monospace",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--strict-text-dim)",
                        flexShrink: 0,
                        width: 96,
                    }}>
                        {field.label}
                    </span>
                    <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.25 + 0.15, duration: 0.3 }}
                        style={{
                            fontSize: 11,
                            color: "var(--strict-text-body)",
                            fontFamily: "Georgia, serif",
                            lineHeight: 1.4,
                        }}
                    >
                        {field.value}
                    </motion.span>
                </motion.div>
            ))}
        </div>
    );
}

function PdfCitationsVisual() {
    return (
        <div style={{
            borderRadius: 12,
            background: "rgba(255,255,255,0.03)",
            border: "1px solid var(--strict-gold-border)",
            padding: "16px 18px",
            fontFamily: "Georgia, serif",
            position: "relative",
        }}>
            {/* Document heading */}
            <div style={{ textAlign: "center", marginBottom: 12 }}>
                <p style={{
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    color: "var(--strict-text-primary)",
                    marginBottom: 6,
                }}>
                    ŽALOBA NA NEPLATNOST VÝPOVĚDI
                </p>
                <div style={{
                    width: 40,
                    height: 1,
                    background: "var(--strict-gold-underbar)",
                    margin: "0 auto",
                }} />
            </div>

            {/* Legal text */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2, duration: 0.4 }}
            >
                <p style={{ fontSize: 10, lineHeight: 1.6, color: "var(--strict-text-body)", marginBottom: 4 }}>
                    Žalobce <strong>Jan Novák</strong> se domáhá určení, že výpověď ze dne 15. 3. 2025
                    je neplatná dle <strong>§ 52 písm. g) zákoníku práce</strong>.
                </p>
                <p style={{ fontSize: 10, lineHeight: 1.6, color: "var(--strict-text-body)", marginBottom: 4 }}>
                    Zaměstnavatel neprokázal porušení pracovní kázně zvlášť hrubým způsobem dle
                    ustálené judikatury Nejvyššího soudu.
                </p>
                <p style={{ fontSize: 10, lineHeight: 1.6, color: "var(--strict-text-secondary)" }}>
                    Žalobce navrhuje, aby soud výpověď prohlásil za neplatnou a uložil žalovanému
                    zaplatit náhradu mzdy za dobu výpovědní lhůty.
                </p>
            </motion.div>

            {/* Citation badge */}
            <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6, duration: 0.3 }}
                style={{
                    marginTop: 12,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    background: "var(--strict-gold-badge-bg)",
                    border: "1px solid var(--strict-gold-badge-border)",
                    borderRadius: 6,
                    padding: "4px 10px",
                }}
            >
                <div style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "var(--strict-gold-base)",
                    opacity: 0.7,
                    flexShrink: 0,
                }} />
                <span style={{
                    fontSize: 9,
                    fontFamily: "monospace",
                    color: "var(--strict-gold-badge-text)",
                    letterSpacing: "0.04em",
                }}>
                    § 52 písm. g) ZP · Zákoník práce · str. 18
                </span>
                {/* Download icon (decorative) */}
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="10"
                    height="10"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="var(--strict-gold-text)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ marginLeft: "auto", flexShrink: 0, opacity: 0.6 }}
                >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
            </motion.div>
        </div>
    );
}

// ─── Visual panel ─────────────────────────────────────────────────────────────

function DraftingVisualPanel({ activeStep }: { activeStep: number }) {
    return (
        <div
            style={{
                flex: 1,
                background: "var(--strict-hiw-bg)",
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
                border: "1px solid var(--strict-hiw-border)",
                borderRadius: "14px",
                padding: "24px",
                minHeight: "220px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                position: "relative",
                overflow: "hidden",
            }}
        >
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeStep}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.4, ease: "easeInOut" }}
                >
                    {activeStep === 0 && <ChooseTemplateVisual />}
                    {activeStep === 1 && <AiFillsFieldsVisual />}
                    {activeStep === 2 && <PdfCitationsVisual />}
                </motion.div>
            </AnimatePresence>
        </div>
    );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function StrictDocumentDraftingShowcase() {
    const isMobile = useIsMobile();
    const [activeStep, setActiveStep] = useState(0);
    const [userInteracted, setUserInteracted] = useState(false);

    useEffect(() => {
        if (userInteracted) return;
        const id = setInterval(() => {
            setActiveStep((prev) => (prev + 1) % STEPS.length);
        }, STEP_DURATION);
        return () => clearInterval(id);
    }, [userInteracted]);

    const goTo = (i: number) => {
        setActiveStep(i);
        setUserInteracted(true);
    };

    return (
        <section
            style={{
                padding: isMobile ? "40px 16px" : "56px 32px",
                maxWidth: "880px",
                margin: "0 auto",
            }}
        >
            {/* Label */}
            <motion.p
                variants={V3_FADE_UP}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, amount: 0.3 }}
                className="uppercase tracking-[1.5px]"
                style={{
                    fontSize: "10px",
                    color: "var(--strict-gold-text)",
                    opacity: 0.4,
                    textAlign: "center",
                    marginBottom: "8px",
                }}
            >
                DOCUMENT DRAFTING
            </motion.p>

            {/* Heading */}
            <motion.h2
                variants={V3_FADE_UP}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, amount: 0.3 }}
                className="font-serif font-normal"
                style={{
                    fontSize: isMobile ? "18px" : "22px",
                    color: "var(--strict-text-primary)",
                    opacity: 0.75,
                    textAlign: "center",
                    marginBottom: "8px",
                }}
            >
                Draft legal filings — cited, not guessed
            </motion.h2>

            {/* Subtext */}
            <motion.p
                variants={V3_FADE_UP}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, amount: 0.3 }}
                style={{
                    fontSize: "12px",
                    color: "var(--strict-text-secondary)",
                    textAlign: "center",
                    marginBottom: "32px",
                }}
            >
                9 Czech legal templates. Every claim grounded in statute or court ruling.
            </motion.p>

            {/* Layout: mobile = visual on top + tabs below; desktop = steps left + visual right */}
            <motion.div
                variants={V3_FADE_UP}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, amount: 0.2 }}
                style={{
                    display: "flex",
                    flexDirection: isMobile ? "column" : "row",
                    gap: isMobile ? "20px" : "24px",
                    alignItems: "stretch",
                }}
            >
                {/* Visual panel — top on mobile */}
                {isMobile && <DraftingVisualPanel activeStep={activeStep} />}

                {/* Step list */}
                {isMobile ? (
                    <div style={{ display: "flex", gap: "8px" }}>
                        {STEPS.map((step, idx) => (
                            <button
                                key={step.num}
                                type="button"
                                onClick={() => goTo(idx)}
                                style={{
                                    flex: 1,
                                    padding: "10px 8px",
                                    borderRadius: "10px",
                                    cursor: "pointer",
                                    border: `1px solid ${activeStep === idx ? "var(--strict-gold-border)" : "transparent"}`,
                                    background: activeStep === idx ? "var(--strict-glass-bg)" : "transparent",
                                    textAlign: "center",
                                    transition: "background 0.3s ease, border-color 0.3s ease",
                                    minHeight: "44px",
                                    position: "relative",
                                    overflow: "hidden",
                                }}
                            >
                                {/* Progress bar */}
                                {activeStep === idx && (
                                    <div
                                        style={{
                                            position: "absolute",
                                            bottom: 0,
                                            left: 0,
                                            right: 0,
                                            height: "2px",
                                            background: "var(--strict-hiw-progress-track)",
                                            overflow: "hidden",
                                        }}
                                    >
                                        <div
                                            key={`progress-mob-${idx}-${activeStep}`}
                                            style={{
                                                height: "2px",
                                                width: "100%",
                                                background: "var(--strict-hiw-progress-fill)",
                                                transformOrigin: "left",
                                                willChange: "transform",
                                                animation: `hiwScanFill ${STEP_DURATION}ms linear forwards`,
                                            }}
                                        />
                                    </div>
                                )}
                                <div style={{
                                    color: activeStep === idx ? "var(--strict-step-num-active)" : "var(--strict-step-num-inactive)",
                                    fontSize: "9px",
                                    letterSpacing: "0.5px",
                                    marginBottom: "3px",
                                }}>
                                    {step.num}
                                </div>
                                <div style={{
                                    color: activeStep === idx ? "var(--strict-step-title-active)" : "var(--strict-step-title-inactive)",
                                    fontSize: "10px",
                                    fontWeight: 500,
                                    lineHeight: 1.3,
                                    transition: "color 0.3s ease",
                                }}>
                                    {step.title}
                                </div>
                            </button>
                        ))}
                    </div>
                ) : (
                    <div
                        style={{
                            width: "280px",
                            flexShrink: 0,
                            display: "flex",
                            flexDirection: "column",
                            gap: "8px",
                        }}
                    >
                        {STEPS.map((step, idx) => (
                            <button
                                key={step.num}
                                type="button"
                                onClick={() => goTo(idx)}
                                style={{
                                    position: "relative",
                                    padding: "14px 16px",
                                    borderRadius: "10px",
                                    cursor: "pointer",
                                    border: `1px solid ${activeStep === idx ? "var(--strict-gold-border)" : "transparent"}`,
                                    background: activeStep === idx ? "var(--strict-glass-bg)" : "transparent",
                                    display: "flex",
                                    gap: "12px",
                                    alignItems: "flex-start",
                                    textAlign: "left",
                                    width: "100%",
                                    transition: "background 0.3s ease, border-color 0.3s ease",
                                }}
                            >
                                {/* Vertical progress bar track */}
                                <div
                                    style={{
                                        position: "absolute",
                                        left: 0,
                                        top: 0,
                                        bottom: 0,
                                        width: "2px",
                                        borderRadius: "1px",
                                        background: "var(--strict-hiw-progress-track)",
                                        overflow: "hidden",
                                    }}
                                >
                                    {activeStep === idx && (
                                        <div
                                            key={`progress-${idx}-${activeStep}`}
                                            style={{
                                                width: "2px",
                                                height: "100%",
                                                borderRadius: "1px",
                                                background: "var(--strict-hiw-progress-fill)",
                                                transformOrigin: "top",
                                                willChange: "transform",
                                                animation: `hiwProgressFill ${STEP_DURATION}ms linear forwards`,
                                            }}
                                        />
                                    )}
                                </div>

                                {/* Step number */}
                                <span
                                    style={{
                                        color: activeStep === idx ? "var(--strict-step-num-active)" : "var(--strict-step-num-inactive)",
                                        fontSize: "10px",
                                        letterSpacing: "0.5px",
                                        marginTop: "2px",
                                        minWidth: "16px",
                                        transition: "color 0.3s ease",
                                        fontVariantNumeric: "tabular-nums",
                                    }}
                                >
                                    {step.num}
                                </span>

                                {/* Step content */}
                                <div style={{ flex: 1 }}>
                                    <div
                                        style={{
                                            color: activeStep === idx ? "var(--strict-step-title-active)" : "var(--strict-step-title-inactive)",
                                            fontSize: "12px",
                                            fontWeight: 500,
                                            marginBottom: "3px",
                                            transition: "color 0.3s ease",
                                        }}
                                    >
                                        {step.title}
                                    </div>
                                    <div
                                        style={{
                                            color: activeStep === idx ? "var(--strict-step-sub-active)" : "var(--strict-step-sub-inactive)",
                                            fontSize: "9.5px",
                                            lineHeight: 1.4,
                                            transition: "color 0.3s ease",
                                        }}
                                    >
                                        {step.sub}
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )}

                {/* Visual panel — right on desktop */}
                {!isMobile && <DraftingVisualPanel activeStep={activeStep} />}
            </motion.div>
        </section>
    );
}
