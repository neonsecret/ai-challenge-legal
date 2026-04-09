"use client"

import { motion } from "motion/react"
import { Scale, BookOpen, RefreshCw } from "lucide-react"

/* ------------------------------------------------------------------ */
/*  Czech Case Law Feature Section (dark theme — landing hero)         */
/*  Uses CSS variables so V3 iris palette is applied automatically.    */
/* ------------------------------------------------------------------ */

const FEATURES = [
    {
        icon: BookOpen,
        title: "Zákony ČR",
        description:
            "Všechny klíčové české zákony — Občanský zákoník, Zákoník práce, Trestní zákoník a další.",
        stat: "11",
        statLabel: "zákonů",
    },
    {
        icon: Scale,
        title: "Judikatura NS",
        description:
            "Více než 33\u00a0000 rozhodnutí Nejvyššího soudu s plným textem a právními větami.",
        stat: "33 000+",
        statLabel: "rozhodnutí",
    },
    {
        icon: RefreshCw,
        title: "AI analýza",
        description:
            "AI propojuje zákonná ustanovení s výkladem soudů — přesný kontext v jednom dotazu.",
        stat: "Denně",
        statLabel: "aktualizace",
    },
] as const

export function CzechCaselawSection() {
    return (
        <section
            style={{
                padding: "48px 24px",
                background: "var(--dt-landing-bg-secondary)",
                position: "relative",
                overflow: "hidden",
            }}
        >
            {/* ambient glow */}
            <div
                aria-hidden
                style={{
                    position: "absolute",
                    inset: 0,
                    pointerEvents: "none",
                }}
            >
                <div
                    style={{
                        position: "absolute",
                        width: 600,
                        height: 600,
                        top: "50%",
                        left: "50%",
                        transform: "translate(-50%,-50%)",
                        background:
                            "radial-gradient(circle, var(--dt-landing-accent-glow-subtle) 0%, transparent 70%)",
                        filter: "blur(60px)",
                    }}
                />
            </div>

            <div
                className="max-w-5xl mx-auto"
                style={{ position: "relative" }}
            >
                {/* section label */}
                <motion.p
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.5 }}
                    className="text-center uppercase tracking-[0.16em] font-semibold"
                    style={{
                        fontSize: 11,
                        color: "var(--dt-landing-label-muted)",
                        marginBottom: 8,
                    }}
                >
                    Zákony + Judikatura
                </motion.p>

                {/* heading */}
                <motion.h2
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.5, delay: 0.08 }}
                    className="font-heading text-center font-bold"
                    style={{
                        fontSize: "clamp(1.8rem,3vw,2.4rem)",
                        letterSpacing: "-0.03em",
                        color: "var(--dt-text-primary)",
                        marginBottom: 12,
                    }}
                >
                    Český právní výzkum na jednom místě
                </motion.h2>

                {/* subtitle */}
                <motion.p
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.5, delay: 0.14 }}
                    className="text-center"
                    style={{
                        fontSize: 13,
                        color: "var(--dt-text-tertiary)",
                        marginBottom: 40,
                        maxWidth: 560,
                        marginLeft: "auto",
                        marginRight: "auto",
                        lineHeight: 1.6,
                    }}
                >
                    AI propojuje zákony s rozsudky Nejvyššího soudu &mdash;
                    nemusíte hledat ve více systémech.
                </motion.p>

                {/* 3-card grid */}
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns:
                            "repeat(auto-fit, minmax(260px, 1fr))",
                        gap: 16,
                    }}
                >
                    {FEATURES.map((f, i) => {
                        const Icon = f.icon
                        return (
                            <motion.div
                                key={f.title}
                                initial={{ opacity: 0, y: 24 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-60px" }}
                                transition={{
                                    duration: 0.5,
                                    delay: i * 0.1,
                                }}
                            >
                                <div
                                    style={{
                                        background: "var(--dt-glass-bg)",
                                        backdropFilter: "var(--dt-glass-blur-light)",
                                        WebkitBackdropFilter: "var(--dt-glass-blur-light)",
                                        border: "1px solid var(--dt-glass-border-subtle)",
                                        borderRadius: 16,
                                        padding: 20,
                                        display: "flex",
                                        flexDirection: "column",
                                        gap: 12,
                                    }}
                                >
                                    {/* icon */}
                                    <div
                                        style={{
                                            width: 36,
                                            height: 36,
                                            borderRadius: 10,
                                            background: "var(--dt-color-gold-tint)",
                                            border: "1px solid var(--dt-color-gold-border)",
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                        }}
                                    >
                                        <Icon
                                            size={16}
                                            style={{
                                                color: "var(--dt-color-gold-base)",
                                            }}
                                            strokeWidth={1.7}
                                        />
                                    </div>

                                    {/* stat */}
                                    <div>
                                        <span
                                            style={{
                                                fontSize: 28,
                                                fontWeight: 800,
                                                color: "var(--dt-color-gold-base)",
                                                letterSpacing: "-0.02em",
                                                lineHeight: 1,
                                            }}
                                        >
                                            {f.stat}
                                        </span>
                                        <span
                                            style={{
                                                fontSize: 11,
                                                color: "var(--dt-text-tertiary)",
                                                marginLeft: 8,
                                                fontWeight: 600,
                                                textTransform: "uppercase",
                                                letterSpacing: "0.08em",
                                            }}
                                        >
                                            {f.statLabel}
                                        </span>
                                    </div>

                                    {/* title & body */}
                                    <h3
                                        style={{
                                            fontSize: 15,
                                            fontWeight: 600,
                                            color: "var(--dt-text-primary)",
                                        }}
                                    >
                                        {f.title}
                                    </h3>
                                    <p
                                        style={{
                                            fontSize: 13,
                                            lineHeight: 1.65,
                                            color: "var(--dt-text-secondary)",
                                        }}
                                    >
                                        {f.description}
                                    </p>
                                </div>
                            </motion.div>
                        )
                    })}
                </div>

                {/* visual: statute -> court decision connector */}
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-60px" }}
                    transition={{ duration: 0.6, delay: 0.3 }}
                    style={{
                        marginTop: 32,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 16,
                        flexWrap: "wrap",
                    }}
                >
                    {/* statute card */}
                    <div
                        style={{
                            background: "var(--dt-glass-bg)",
                            border: "1px solid var(--dt-color-gold-border)",
                            borderRadius: 12,
                            padding: "12px 16px",
                            maxWidth: 220,
                        }}
                    >
                        <p
                            style={{
                                fontSize: 9,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: "var(--dt-color-gold-base)",
                                marginBottom: 4,
                                fontWeight: 600,
                            }}
                        >
                            Zákon
                        </p>
                        <p
                            style={{
                                fontSize: 11,
                                color: "var(--dt-text-primary)",
                                fontWeight: 600,
                                marginBottom: 4,
                            }}
                        >
                            § 52 písm. c) Zákoník práce
                        </p>
                        <p
                            style={{
                                fontSize: 10,
                                color: "var(--dt-text-tertiary)",
                                lineHeight: 1.5,
                            }}
                        >
                            Výpověď z důvodu nadbytečnosti
                        </p>
                    </div>

                    {/* arrow */}
                    <svg
                        width="40"
                        height="20"
                        viewBox="0 0 40 20"
                        fill="none"
                        style={{ flexShrink: 0 }}
                    >
                        <path
                            d="M2 10h32M28 4l6 6-6 6"
                            stroke="var(--dt-color-gold-base)"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            opacity={0.6}
                        />
                    </svg>

                    {/* court decision card */}
                    <div
                        style={{
                            background: "var(--dt-glass-bg)",
                            border: "1px solid var(--dt-color-teal-border)",
                            borderRadius: 12,
                            padding: "12px 16px",
                            maxWidth: 240,
                        }}
                    >
                        <p
                            style={{
                                fontSize: 9,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: "var(--dt-color-teal-base)",
                                marginBottom: 4,
                                fontWeight: 600,
                            }}
                        >
                            Judikatura NS
                        </p>
                        <p
                            style={{
                                fontSize: 11,
                                color: "var(--dt-text-primary)",
                                fontWeight: 600,
                                marginBottom: 4,
                            }}
                        >
                            21 Cdo 262/2006
                        </p>
                        <p
                            style={{
                                fontSize: 10,
                                color: "var(--dt-text-tertiary)",
                                lineHeight: 1.5,
                            }}
                        >
                            Organizační změna a nadbytečnost
                        </p>
                    </div>
                </motion.div>
            </div>
        </section>
    )
}
