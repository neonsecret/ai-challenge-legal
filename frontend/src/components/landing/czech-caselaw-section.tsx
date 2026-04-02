"use client"

import { motion } from "motion/react"
import { Scale, BookOpen, RefreshCw } from "lucide-react"
import { COLOR, TEXT_DARK, GLASS, TYPE_SCALE, SPACE } from "@/lib/design-tokens"

/* ------------------------------------------------------------------ */
/*  Czech Case Law Feature Section (dark theme only -- landing hero)  */
/* ------------------------------------------------------------------ */

const FEATURES = [
    {
        icon: BookOpen,
        title: "Z\u00e1kony \u010cR",
        description:
            "V\u0161echny kl\u00ed\u010dov\u00e9 \u010desk\u00e9 z\u00e1kony \u2014 Ob\u010dansk\u00fd z\u00e1kon\u00edk, Z\u00e1kon\u00edk pr\u00e1ce, Trestn\u00ed z\u00e1kon\u00edk a dal\u0161\u00ed.",
        stat: "11",
        statLabel: "z\u00e1kon\u016f",
    },
    {
        icon: Scale,
        title: "Judikatura NS",
        description:
            "V\u00edce ne\u017e 33\u00a0000 rozhodnut\u00ed Nejvy\u0161\u0161\u00edho soudu s pln\u00fdm textem a pr\u00e1vn\u00edmi v\u011btami.",
        stat: "33 000+",
        statLabel: "rozhodnut\u00ed",
    },
    {
        icon: RefreshCw,
        title: "AI anal\u00fdza",
        description:
            "AI propojuje z\u00e1konn\u00e1 ustanoven\u00ed s v\u00fdkladem soud\u016f \u2014 p\u0159esn\u00fd kontext v jednom dotazu.",
        stat: "Denn\u011b",
        statLabel: "aktualizace",
    },
] as const

export function CzechCaselawSection() {
    return (
        <section
            style={{
                padding: `${SPACE["12"]}px ${SPACE["6"]}px`,
                background: "#0A1120",
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
                            "radial-gradient(circle, rgba(201,168,76,0.05) 0%, transparent 70%)",
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
                        fontSize: TYPE_SCALE.xs,
                        color: "rgba(201,168,76,0.60)",
                        marginBottom: SPACE["2"],
                    }}
                >
                    {/* "Z\u00e1kony + Judikatura" */}
                    Z\u00e1kony + Judikatura
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
                        color: TEXT_DARK.primary,
                        marginBottom: SPACE["3"],
                    }}
                >
                    \u010cesk\u00fd pr\u00e1vn\u00ed v\u00fdzkum na jednom m\u00edst\u011b
                </motion.h2>

                {/* subtitle */}
                <motion.p
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.5, delay: 0.14 }}
                    className="text-center"
                    style={{
                        fontSize: TYPE_SCALE.sm,
                        color: TEXT_DARK.tertiary,
                        marginBottom: SPACE["10"],
                        maxWidth: 560,
                        marginLeft: "auto",
                        marginRight: "auto",
                        lineHeight: 1.6,
                    }}
                >
                    AI propojuje z\u00e1kony s rozsudky Nejvy\u0161\u0161\u00edho soudu &mdash;
                    nemus\u00edte hledat ve v\u00edce syst\u00e9mech.
                </motion.p>

                {/* 3-card grid */}
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns:
                            "repeat(auto-fit, minmax(260px, 1fr))",
                        gap: SPACE["4"],
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
                                        background: GLASS.dark.bg,
                                        backdropFilter: GLASS.dark.blurLight,
                                        WebkitBackdropFilter:
                                            GLASS.dark.blurLight,
                                        border: `1px solid ${GLASS.dark.borderSubtle}`,
                                        borderRadius: 16,
                                        padding: SPACE["5"],
                                        display: "flex",
                                        flexDirection: "column",
                                        gap: SPACE["3"],
                                    }}
                                >
                                    {/* icon */}
                                    <div
                                        style={{
                                            width: 36,
                                            height: 36,
                                            borderRadius: 10,
                                            background: COLOR.gold.tint,
                                            border: `1px solid ${COLOR.gold.border}`,
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                        }}
                                    >
                                        <Icon
                                            size={16}
                                            style={{
                                                color: COLOR.gold.base,
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
                                                color: COLOR.gold.base,
                                                letterSpacing: "-0.02em",
                                                lineHeight: 1,
                                            }}
                                        >
                                            {f.stat}
                                        </span>
                                        <span
                                            style={{
                                                fontSize: TYPE_SCALE.xs,
                                                color: TEXT_DARK.tertiary,
                                                marginLeft: SPACE["2"],
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
                                            fontSize: TYPE_SCALE.md,
                                            fontWeight: 600,
                                            color: TEXT_DARK.primary,
                                        }}
                                    >
                                        {f.title}
                                    </h3>
                                    <p
                                        style={{
                                            fontSize: TYPE_SCALE.sm,
                                            lineHeight: 1.65,
                                            color: TEXT_DARK.secondary,
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
                        marginTop: SPACE["8"],
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: SPACE["4"],
                        flexWrap: "wrap",
                    }}
                >
                    {/* statute card */}
                    <div
                        style={{
                            background: GLASS.dark.bg,
                            border: `1px solid ${COLOR.gold.border}`,
                            borderRadius: 12,
                            padding: `${SPACE["3"]}px ${SPACE["4"]}px`,
                            maxWidth: 220,
                        }}
                    >
                        <p
                            style={{
                                fontSize: 9,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: COLOR.gold.base,
                                marginBottom: SPACE["1"],
                                fontWeight: 600,
                            }}
                        >
                            Z\u00e1kon
                        </p>
                        <p
                            style={{
                                fontSize: TYPE_SCALE.xs,
                                color: TEXT_DARK.primary,
                                fontWeight: 600,
                                marginBottom: SPACE["1"],
                            }}
                        >
                            {"\u00a7 52 p\u00edsm. c) Z\u00e1kon\u00edk pr\u00e1ce"}
                        </p>
                        <p
                            style={{
                                fontSize: 10,
                                color: TEXT_DARK.tertiary,
                                lineHeight: 1.5,
                            }}
                        >
                            {"V\u00fdpov\u011b\u010f z d\u016fvodu nadbyte\u010dnosti"}
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
                            stroke={COLOR.gold.base}
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            opacity={0.6}
                        />
                    </svg>

                    {/* court decision card */}
                    <div
                        style={{
                            background: GLASS.dark.bg,
                            border: `1px solid ${COLOR.teal.border}`,
                            borderRadius: 12,
                            padding: `${SPACE["3"]}px ${SPACE["4"]}px`,
                            maxWidth: 240,
                        }}
                    >
                        <p
                            style={{
                                fontSize: 9,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: COLOR.teal.base,
                                marginBottom: SPACE["1"],
                                fontWeight: 600,
                            }}
                        >
                            Judikatura NS
                        </p>
                        <p
                            style={{
                                fontSize: TYPE_SCALE.xs,
                                color: TEXT_DARK.primary,
                                fontWeight: 600,
                                marginBottom: SPACE["1"],
                            }}
                        >
                            21 Cdo 262/2006
                        </p>
                        <p
                            style={{
                                fontSize: 10,
                                color: TEXT_DARK.tertiary,
                                lineHeight: 1.5,
                            }}
                        >
                            {"Organiza\u010dn\u00ed zm\u011bna a nadbyte\u010dnost"}
                        </p>
                    </div>
                </motion.div>
            </div>
        </section>
    )
}
