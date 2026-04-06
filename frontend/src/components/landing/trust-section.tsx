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
            style={{background: "#080E1A"}}
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
                            "radial-gradient(circle, rgba(201,168,76,0.18) 0%, rgba(201,168,76,0.06) 40%, transparent 70%)",
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
                            "radial-gradient(circle, rgba(27,43,75,0.9) 0%, transparent 70%)",
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
                    style={{color: "rgba(201,168,76,0.7)"}}
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
                        color: "rgba(255,255,255,0.95)",
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
                                background: "rgba(255,255,255,0.08)",
                                backdropFilter: "blur(32px) saturate(150%)",
                                WebkitBackdropFilter: "blur(32px) saturate(150%)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.07)",
                            }}
                        >
                            <div
                                className="flex items-center justify-center size-5 rounded-md shrink-0"
                                style={{
                                    background: "rgba(201,168,76,0.12)",
                                    border: "1px solid rgba(201,168,76,0.2)",
                                }}
                            >
                                <Icon className="size-3" style={{color: "#C9A84C"}}/>
                            </div>
                            <div>
                                <p
                                    className="text-[12px] font-semibold leading-none mb-0.5"
                                    style={{color: "rgba(255,255,255,0.88)"}}
                                >
                                    {t(keys.label)}
                                </p>
                                <p
                                    className="text-[10px] leading-none"
                                    style={{color: "rgba(255,255,255,0.38)"}}
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
                        background: "rgba(255,255,255,0.10)",
                        backdropFilter: "blur(48px) saturate(160%)",
                        WebkitBackdropFilter: "blur(48px) saturate(160%)",
                        border: "1px solid rgba(255,255,255,0.18)",
                        boxShadow:
                            "0 32px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(201,168,76,0.08), inset 0 1px 0 rgba(255,255,255,0.10)",
                    }}
                >
                    <h3
                        className="font-heading text-xl font-bold mb-2"
                        style={{color: "rgba(255,255,255,0.95)"}}
                    >
                        {t("landing.cta_no_cc")}
                    </h3>
                    <p
                        className="text-sm mb-8"
                        style={{color: "rgba(255,255,255,0.38)"}}
                    >
                        {t("landing.cta_signup_info")}
                    </p>

                    <div className="flex flex-col gap-3 max-w-xs mx-auto">
                        <a
                            href="/login"
                            className="flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold transition-all"
                            style={{
                                background:
                                    "linear-gradient(135deg, #C9A84C 0%, #e8cc7a 50%, #C9A84C 100%)",
                                backgroundSize: "200% auto",
                                color: "#0F1623",
                                boxShadow: "0 4px 20px rgba(201,168,76,0.3)",
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
                                background: "rgba(255,255,255,0.06)",
                                border: "1px solid rgba(255,255,255,0.14)",
                                color: "rgba(255,255,255,0.55)",
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
