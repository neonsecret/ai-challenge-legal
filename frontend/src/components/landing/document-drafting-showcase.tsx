"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";

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
    { number: "01", title: "Choose Template" },
    { number: "02", title: "AI Fills Fields" },
    { number: "03", title: "PDF + Citations" },
] as const;

const CATEGORY_LABELS: Record<string, string> = {
    labor: "Pracovní právo",
    civil: "Občanské právo",
    custom: "Vlastní",
};

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
                        borderRadius: 12,
                        background: "var(--wl-card-bg)",
                        border: "0.5px solid var(--wl-glass-border)",
                    }}
                >
                    <span style={{
                        fontSize: 12,
                        fontFamily: "Georgia, serif",
                        color: "var(--wl-heading-color)",
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
                            color: "var(--wl-accent)",
                            background: "var(--wl-accent-bg-faint)",
                            border: "0.5px solid var(--wl-accent-border-subtle)",
                            borderRadius: 4,
                            padding: "1px 5px",
                            letterSpacing: "0.05em",
                        }}>
                            {tpl.jurisdiction}
                        </span>
                        <span style={{
                            fontSize: 9,
                            fontFamily: "monospace",
                            color: "var(--wl-subtext-color)",
                            background: "var(--wl-category-bg)",
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
                        gap: 8,
                        padding: "6px 0",
                        borderBottom: "0.5px solid var(--wl-accent-border-faint)",
                    }}
                >
                    <span style={{
                        fontSize: 10,
                        fontFamily: "monospace",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--wl-label-color)",
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
                            fontSize: 12,
                            color: "var(--wl-heading-color)",
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
            borderRadius: 14,
            background: "var(--wl-pdf-bg)",
            border: "0.5px solid var(--wl-pdf-border)",
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
                    color: "var(--wl-pdf-heading)",
                    marginBottom: 6,
                }}>
                    ŽALOBA NA NEPLATNOST VÝPOVĚDI
                </p>
                <div style={{ width: 40, height: 1, background: "var(--wl-pdf-divider)", margin: "0 auto" }} />
            </div>

            {/* Legal text */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2, duration: 0.4 }}
            >
                <p style={{ fontSize: 10, lineHeight: 1.6, color: "var(--wl-pdf-text)", marginBottom: 4 }}>
                    Žalobce <strong>Jan Novák</strong> se domáhá určení, že výpověď ze dne 15. 3. 2025
                    je neplatná dle <strong>§ 52 písm. g) zákoníku práce</strong>.
                </p>
                <p style={{ fontSize: 10, lineHeight: 1.6, color: "var(--wl-pdf-text)", marginBottom: 4 }}>
                    Zaměstnavatel neprokázal porušení pracovní kázně zvlášť hrubým způsobem dle
                    ustálené judikatury Nejvyššího soudu.
                </p>
                <p style={{ fontSize: 10, lineHeight: 1.6, color: "var(--wl-pdf-text-secondary)" }}>
                    Žalobce proto navrhuje, aby soud výpověď prohlásil za neplatnou a uložil žalovanému
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
                    background: "var(--wl-accent-badge-bg)",
                    borderRadius: 6,
                    padding: "4px 10px",
                }}
            >
                <div style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "var(--wl-accent-dot)",
                    flexShrink: 0,
                }} />
                <span style={{
                    fontSize: 9,
                    fontFamily: "monospace",
                    color: "var(--wl-text-on-accent)",
                    letterSpacing: "0.04em",
                }}>
                    § 52 písm. g) ZP · Zákoník práce · str. 18
                </span>
                {/* Download icon (decorative) */}
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="var(--wl-download-icon)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ marginLeft: "auto", flexShrink: 0 }}
                >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
            </motion.div>
        </div>
    );
}

const STEP_VISUALS = [ChooseTemplateVisual, AiFillsFieldsVisual, PdfCitationsVisual];
const STEP_DESCRIPTIONS = [
    "Select from 9 Czech legal templates — employment, civil, commercial.",
    "AI extracts parties, dates, and legal grounds from your case facts.",
    "Receive a fully formatted PDF with statute and case-law citations.",
];

// ─── Main component ───────────────────────────────────────────────────────────

export function DocumentDraftingShowcase() {
    const [activeStep, setActiveStep] = useState(0);
    const [userInteracted, setUserInteracted] = useState(false);

    useEffect(() => {
        if (userInteracted) return;
        const id = setInterval(() => {
            setActiveStep((prev) => (prev + 1) % STEPS.length);
        }, 5000);
        return () => clearInterval(id);
    }, [userInteracted]);

    const goTo = (i: number) => {
        setActiveStep(i);
        setUserInteracted(true);
    };

    const Visual = STEP_VISUALS[activeStep];

    return (
        <section style={{
            padding: "80px 24px",
            background: "var(--wl-bg-section)",
            position: "relative",
            overflow: "hidden",
        }}>
            {/* Ambient glow */}
            <div aria-hidden style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
                <div style={{
                    position: "absolute",
                    width: 480,
                    height: 480,
                    top: -60,
                    left: "20%",
                    background: `radial-gradient(circle, var(--wl-glow-ambient) 0%, transparent 65%)`,
                }} />
            </div>

            <div style={{ maxWidth: 800, margin: "0 auto", position: "relative" }}>
                {/* Label */}
                <motion.p
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-60px" }}
                    transition={{ duration: 0.5 }}
                    style={{
                        textAlign: "center",
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.16em",
                        fontWeight: 600,
                        color: "var(--wl-label-color)",
                        marginBottom: 10,
                    }}
                >
                    DOCUMENT DRAFTING
                </motion.p>

                {/* Heading */}
                <motion.h2
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-60px" }}
                    transition={{ duration: 0.5, delay: 0.08 }}
                    style={{
                        textAlign: "center",
                        fontFamily: "Georgia, serif",
                        fontSize: "clamp(1.8rem,3vw,2.6rem)",
                        fontWeight: 700,
                        letterSpacing: "-0.03em",
                        color: "var(--wl-heading-color)",
                        marginBottom: 8,
                    }}
                >
                    Draft legal filings — cited, not guessed
                </motion.h2>

                {/* Subtext */}
                <motion.p
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true, margin: "-60px" }}
                    transition={{ duration: 0.5, delay: 0.14 }}
                    style={{
                        textAlign: "center",
                        fontSize: 13,
                        color: "var(--wl-subtext-color)",
                        marginBottom: 40,
                    }}
                >
                    9 Czech legal templates. Every claim grounded in statute or court ruling.
                </motion.p>

                {/* Step tabs */}
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-60px" }}
                    transition={{ duration: 0.5, delay: 0.18 }}
                >
                    <div style={{
                        display: "flex",
                        justifyContent: "center",
                        gap: 8,
                        marginBottom: 24,
                        flexWrap: "wrap",
                    }}>
                        {STEPS.map((s, i) => (
                            <button
                                key={s.number}
                                onClick={() => goTo(i)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                    borderRadius: "9999px",
                                    padding: "8px 18px",
                                    fontSize: 12,
                                    fontWeight: 500,
                                    cursor: "pointer",
                                    transition: "all 0.15s",
                                    background: i === activeStep ? "var(--wl-accent-bg)" : "var(--wl-card-bg)",
                                    border: i === activeStep ? "0.5px solid var(--wl-accent-border)" : "0.5px solid var(--wl-glass-border)",
                                    color: i === activeStep ? "var(--wl-active-text)" : "var(--wl-body-text-muted)",
                                }}
                            >
                                <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 11 }}>
                                    {s.number}
                                </span>
                                <span>{s.title}</span>
                            </button>
                        ))}
                    </div>

                    {/* Step content panel */}
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={activeStep}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            transition={{ duration: 0.3 }}
                            className="grid grid-cols-1 sm:grid-cols-2 gap-5 sm:gap-8 p-5 sm:py-7 sm:px-8"
                            style={{
                                background: "var(--wl-glass-bg)",
                                backdropFilter: "var(--wl-glass-backdrop)",
                                WebkitBackdropFilter: "var(--wl-glass-backdrop)",
                                border: "0.5px solid var(--wl-glass-border)",
                                boxShadow: "var(--wl-glass-shadow)",
                                borderRadius: 20,
                                alignItems: "center",
                            }}
                        >
                            {/* Left: text */}
                            <div>
                                <div style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: 36,
                                    height: 36,
                                    borderRadius: "50%",
                                    background: "var(--wl-accent-bg-subtle)",
                                    border: "0.5px solid var(--wl-accent-border-mid)",
                                    color: "var(--wl-accent)",
                                    fontFamily: "monospace",
                                    fontSize: 11,
                                    fontWeight: 700,
                                    marginBottom: 16,
                                }}>
                                    {STEPS[activeStep].number}
                                </div>
                                <h3 style={{
                                    fontSize: 20,
                                    fontWeight: 600,
                                    color: "var(--wl-heading-color)",
                                    marginBottom: 8,
                                }}>
                                    {STEPS[activeStep].title}
                                </h3>
                                <p style={{
                                    fontSize: 14,
                                    lineHeight: 1.7,
                                    color: "var(--wl-body-text)",
                                    marginBottom: 20,
                                }}>
                                    {STEP_DESCRIPTIONS[activeStep]}
                                </p>

                                {/* Progress dots */}
                                <div style={{ display: "flex", gap: 6 }}>
                                    {STEPS.map((_, i) => (
                                        <motion.div
                                            key={i}
                                            onClick={() => goTo(i)}
                                            animate={{
                                                width: i === activeStep ? 28 : 8,
                                                opacity: i === activeStep ? 1 : 0.30,
                                            }}
                                            transition={{ duration: 0.3 }}
                                            style={{
                                                height: 4,
                                                borderRadius: 2,
                                                background: "var(--wl-accent)",
                                                cursor: "pointer",
                                            }}
                                        />
                                    ))}
                                </div>
                            </div>

                            {/* Right: visual */}
                            <div>
                                <Visual />
                            </div>
                        </motion.div>
                    </AnimatePresence>
                </motion.div>
            </div>
        </section>
    );
}
