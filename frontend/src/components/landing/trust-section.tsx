"use client";

import {ArrowRight, ShieldCheck, Globe, Lock} from "lucide-react";
import {motion} from "motion/react";
import {useI18n} from "@/lib/i18n";

const TRUST_ICONS = [Globe, ShieldCheck, Lock] as const;
const TRUST_KEYS = [
    {label: "landing.trust_jurisdictions", sub: "landing.trust_jurisdictions_sub"},
    {label: "landing.trust_soc2", sub: "landing.trust_soc2_sub"},
    {label: "landing.trust_privacy", sub: "landing.trust_privacy_sub"},
] as const;

interface TrustSectionProps {
    demoMode?: boolean;
    initialApiKey?: string;
}

export function TrustSection({
                                 demoMode: _demoMode = false,
                                 initialApiKey: _initialApiKey = "",
                             }: TrustSectionProps) {
    const {t} = useI18n();
    return (
        <section
            id="access"
            className="relative py-16 sm:py-32 px-6 overflow-hidden"
            style={{background: "var(--dt-landing-bg-deep)"}}
        >
            {/* Aurora orbs */}
            <div aria-hidden className="pointer-events-none absolute inset-0">
                <div
                    className="absolute rounded-full"
                    style={{
                        width: "700px",
                        height: "700px",
                        top: "50%",
                        left: "50%",
                        transform: "translate(-50%, -50%)",
                        background:
                            "radial-gradient(circle, var(--dt-landing-accent-bg) 0%, var(--dt-landing-glass-bg) 40%, transparent 70%)",
                        filter: "blur(60px)",
                    }}
                />
                <div
                    className="absolute rounded-full"
                    style={{
                        width: "500px",
                        height: "500px",
                        top: "-100px",
                        right: "-100px",
                        background:
                            "radial-gradient(circle, var(--dt-landing-glass-card) 0%, transparent 70%)",
                        filter: "blur(80px)",
                    }}
                />
            </div>

            <div className="max-w-lg mx-auto relative">
                <motion.p
                    initial={{opacity: 0, y: 10}}
                    whileInView={{opacity: 1, y: 0}}
                    viewport={{once: true}}
                    transition={{duration: 0.5}}
                    className="text-center text-[11px] uppercase tracking-[0.2em] font-semibold mb-3"
                    style={{color: "var(--dt-landing-label-color)"}}
                >
                    {t("landing.cta_label")}
                </motion.p>

                <motion.h2
                    initial={{opacity: 0, y: 10}}
                    whileInView={{opacity: 1, y: 0}}
                    viewport={{once: true}}
                    transition={{duration: 0.5, delay: 0.08}}
                    className="font-heading text-center text-3xl md:text-4xl font-bold mb-16"
                    style={{
                        color: "var(--dt-text-primary)",
                        letterSpacing: "-0.02em",
                        lineHeight: 1.15,
                    }}
                >
                    {t("landing.cta_heading")}
                </motion.h2>

                {/* Trust badges */}
                <motion.div
                    initial={{opacity: 0, y: 16}}
                    whileInView={{opacity: 1, y: 0}}
                    viewport={{once: true}}
                    transition={{duration: 0.5, delay: 0.1}}
                    className="flex flex-wrap justify-center gap-3 mb-12"
                >
                    {TRUST_KEYS.map((keys, i) => {
                        const Icon = TRUST_ICONS[i];
                        return (
                        <motion.div
                            key={keys.label}
                            initial={{opacity: 0, y: 8}}
                            whileInView={{opacity: 1, y: 0}}
                            viewport={{once: true}}
                            transition={{duration: 0.4, delay: 0.15 + i * 0.08}}
                            className="flex items-center gap-2.5 rounded-full px-4 py-2.5"
                            style={{
                                background: "var(--dt-glass-border-subtle)",
                                backdropFilter: "blur(32px) saturate(150%)",
                                WebkitBackdropFilter: "blur(32px) saturate(150%)",
                                border: "1px solid var(--dt-landing-glass-border)",
                                boxShadow: "inset 0 1px 0 var(--dt-landing-glass-glow)",
                            }}
                        >
                            <div
                                className="flex items-center justify-center size-5 rounded-md shrink-0"
                                style={{
                                    background: "var(--dt-landing-accent-bg-subtle)",
                                    border: "1px solid var(--dt-landing-accent-border-light)",
                                }}
                            >
                                <Icon className="size-3" style={{color: "var(--dt-accent-color)"}}/>
                            </div>
                            <div>
                                <p
                                    className="text-[12px] font-semibold leading-none mb-0.5"
                                    style={{color: "var(--dt-confidence-text)"}}
                                >
                                    {t(keys.label)}
                                </p>
                                <p
                                    className="text-[10px] leading-none"
                                    style={{color: "var(--dt-landing-text-faint)"}}
                                >
                                    {t(keys.sub)}
                                </p>
                            </div>
                        </motion.div>
                        );
                    })}
                </motion.div>

                {/* CTA card */}
                <motion.div
                    initial={{opacity: 0, y: 24}}
                    whileInView={{opacity: 1, y: 0}}
                    viewport={{once: true}}
                    transition={{duration: 0.6, delay: 0.2}}
                    className="rounded-3xl p-8 text-center"
                    style={{
                        background: "var(--dt-landing-glass-bg-strong)",
                        backdropFilter: "blur(48px) saturate(160%)",
                        WebkitBackdropFilter: "blur(48px) saturate(160%)",
                        border: "1px solid var(--dt-panel-border-color)",
                        boxShadow:
                            "0 32px 80px rgba(0,0,0,0.5), 0 0 0 1px var(--dt-accent-tint-faint), inset 0 1px 0 var(--dt-landing-glass-bg-strong)",
                    }}
                >
                    <h3
                        className="font-heading text-xl font-bold mb-2"
                        style={{color: "var(--dt-text-primary)"}}
                    >
                        {t("landing.cta_no_cc")}
                    </h3>
                    <p
                        className="text-sm mb-8"
                        style={{color: "var(--dt-landing-text-faint)"}}
                    >
                        {t("landing.cta_signup_info")}
                    </p>

                    <div className="flex flex-col gap-3 max-w-xs mx-auto">
                        <a
                            href="/login"
                            className="flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold transition-all"
                            style={{
                                background: "var(--dt-landing-cta-gradient)",
                                backgroundSize: "200% auto",
                                color: "var(--dt-landing-cta-text)",
                                boxShadow: "var(--dt-landing-cta-shadow)",
                                textDecoration: "none",
                            }}
                        >
                            {t("landing.cta_get_started")}
                            <ArrowRight className="size-4"/>
                        </a>
                        <a
                            href="/login"
                            className="flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium transition-all"
                            style={{
                                background: "var(--dt-landing-glass-bg)",
                                border: "1px solid var(--dt-glass-border)",
                                color: "var(--dt-code-copy-color)",
                                textDecoration: "none",
                            }}
                        >
                            {t("landing.cta_sign_in")}
                        </a>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
