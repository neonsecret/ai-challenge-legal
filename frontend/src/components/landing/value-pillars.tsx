"use client";

import {motion} from "motion/react";
import {useI18n} from "@/lib/i18n";

const ICONS = [
    (
        <svg key="search" width="22" height="22" viewBox="0 0 22 22" fill="none">
            <circle cx="10" cy="10" r="7" stroke="var(--dt-accent-color)" strokeWidth="1.5"/>
            <path d="M15.5 15.5L19 19" stroke="var(--dt-accent-color)" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M10 7v3l2.5 1.5" stroke="var(--dt-accent-color)" strokeWidth="1.5" strokeLinecap="round"
                  strokeLinejoin="round"/>
        </svg>
    ),
    (
        <svg key="cite" width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect x="3" y="2" width="12" height="17" rx="2" stroke="var(--dt-accent-color)" strokeWidth="1.5"/>
            <path d="M6 8h6M6 11h6M6 14h4" stroke="var(--dt-accent-color)" strokeWidth="1.5" strokeLinecap="round"/>
            <circle cx="16" cy="16" r="4" fill="var(--dt-landing-bg-secondary)" stroke="var(--dt-accent-color)" strokeWidth="1.5"/>
            <path d="M15 16.2l.8.8 1.7-1.7" stroke="var(--dt-accent-color)" strokeWidth="1.2" strokeLinecap="round"
                  strokeLinejoin="round"/>
        </svg>
    ),
    (
        <svg key="shield" width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M11 2L3 6v5c0 5.5 3.4 10.7 8 12 4.6-1.3 8-6.5 8-12V6l-8-4z" stroke="var(--dt-accent-color)" strokeWidth="1.5"
                  strokeLinejoin="round"/>
            <path d="M8 11.5l2 2 4-4" stroke="var(--dt-accent-color)" strokeWidth="1.5" strokeLinecap="round"
                  strokeLinejoin="round"/>
        </svg>
    ),
];

export function ValuePillars() {
    const {t} = useI18n();
    return (
        <section
            className="py-16 sm:py-28 px-6 relative overflow-hidden"
            style={{background: "var(--dt-landing-bg-secondary)"}}
        >
            {/* Subtle radial glow behind cards */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-0"
                style={{
                    background:
                        "radial-gradient(ellipse 70% 50% at 50% 60%, var(--dt-landing-accent-glow-subtle) 0%, transparent 70%)",
                }}
            />

            <div className="max-w-5xl mx-auto relative">
                <motion.p
                    initial={{opacity: 0, y: 12}}
                    whileInView={{opacity: 1, y: 0}}
                    viewport={{once: true, margin: "-80px"}}
                    transition={{duration: 0.5}}
                    className="text-center text-[11px] uppercase tracking-widest font-semibold mb-3"
                    style={{color: "var(--dt-landing-label-color)"}}
                >
                    {t("landing.why_label")}
                </motion.p>
                <motion.h2
                    initial={{opacity: 0, y: 12}}
                    whileInView={{opacity: 1, y: 0}}
                    viewport={{once: true, margin: "-80px"}}
                    transition={{duration: 0.5, delay: 0.08}}
                    className="font-heading text-center text-3xl md:text-4xl font-bold mb-16"
                    style={{
                        color: "var(--dt-text-primary)",
                        letterSpacing: "-0.02em",
                        lineHeight: 1.15,
                    }}
                >
                    {t("landing.why_heading")}
                </motion.h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                    {[1, 2, 3].map((n, i) => {
                        const p = {
                            stat: t(`landing.pillar${n}_stat`),
                            statLabel: t(`landing.pillar${n}_stat_label`),
                            title: t(`landing.pillar${n}_title`),
                            body: t(`landing.pillar${n}_body`),
                            icon: ICONS[i],
                        };
                        return (
                        <motion.div
                            key={p.title}
                            initial={{opacity: 0, y: 28}}
                            whileInView={{opacity: 1, y: 0}}
                            viewport={{once: true, margin: "-80px"}}
                            transition={{duration: 0.55, delay: i * 0.12}}
                            whileHover={{y: -4, transition: {duration: 0.2}}}
                            className="group relative rounded-2xl p-6 flex flex-col gap-0 cursor-default"
                            style={{
                                background:
                                    "linear-gradient(145deg, var(--dt-landing-glass-bg-strong) 0%, var(--dt-landing-glass-bg) 100%)",
                                backdropFilter: "blur(48px) saturate(160%)",
                                WebkitBackdropFilter: "blur(48px) saturate(160%)",
                                border: "1px solid var(--dt-glass-border)",
                                borderTop: "2px solid var(--dt-accent-highlight)",
                                boxShadow:
                                    "var(--dt-landing-card-shadow), var(--dt-landing-card-glow)",
                            }}
                        >
                            {/* Hover glow */}
                            <div
                                className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                                style={{
                                    boxShadow: "0 0 60px var(--dt-landing-accent-bg), inset 0 0 20px var(--dt-landing-accent-glow-subtle)",
                                }}
                            />

                            {/* Shimmer overlay */}
                            <div
                                className="pointer-events-none absolute inset-0 rounded-2xl"
                                style={{
                                    background: "linear-gradient(135deg, var(--dt-glass-bg-subtle) 0%, transparent 50%, rgba(255,255,255,0.02) 100%)",
                                }}
                            />

                            {/* Stat */}
                            <div className="mb-5">
                                <p
                                    className="font-heading text-4xl font-bold leading-none mb-1"
                                    style={{
                                        background:
                                            "linear-gradient(135deg, var(--dt-color-gold-light) 0%, var(--dt-color-gold-base) 100%)",
                                        WebkitBackgroundClip: "text",
                                        backgroundClip: "text",
                                        WebkitTextFillColor: "transparent",
                                    }}
                                >
                                    {p.stat}
                                </p>
                                <p
                                    className="text-[11px] uppercase tracking-wide font-medium"
                                    style={{color: "var(--dt-landing-stat-label)"}}
                                >
                                    {p.statLabel}
                                </p>
                            </div>

                            {/* Divider */}
                            <div
                                className="mb-5 h-px w-full"
                                style={{
                                    background:
                                        "linear-gradient(90deg, var(--dt-landing-accent-border-light) 0%, transparent 100%)",
                                }}
                            />

                            {/* Icon + title */}
                            <div className="flex items-center gap-3 mb-3">
                                <div
                                    className="flex items-center justify-center size-9 rounded-xl shrink-0"
                                    style={{
                                        background: "var(--dt-accent-tint-faint)",
                                        border: "1px solid var(--dt-landing-accent-border-light)",
                                    }}
                                >
                                    {p.icon}
                                </div>
                                <h3
                                    className="text-base font-semibold"
                                    style={{color: "var(--dt-text-primary)"}}
                                >
                                    {p.title}
                                </h3>
                            </div>

                            <p
                                className="text-sm leading-relaxed"
                                style={{color: "var(--dt-text-tertiary)"}}
                            >
                                {p.body}
                            </p>
                        </motion.div>
                    ); })}
                </div>
            </div>
        </section>
    );
}
