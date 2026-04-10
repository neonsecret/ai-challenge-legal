"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { V3_SPRING, V3_FADE_UP } from "@/lib/v3-motion";
import { useIsMobile } from "@/hooks/use-mobile";
import { useI18n } from "@/lib/i18n";

// ─── Data ─────────────────────────────────────────────────────────────────────

const PLAN_DEFS = [
  {
    name: "FREE",
    price: "$0",
    priceSuffix: undefined,
    subKey: "strict.plan_free_sub",
    featureKeys: ["strict.feature_all_jurisdictions", "strict.feature_source_citations", "strict.feature_basic_export"],
    ctaKey: "landing.get_started",
    featured: false,
  },
  {
    name: "STARTER",
    price: "$29",
    priceSuffix: "/mo",
    subKey: "strict.plan_starter_sub",
    featureKeys: ["strict.feature_everything_free", "strict.feature_doc_upload", "strict.feature_priority_support"],
    ctaKey: "strict.subscribe",
    featured: true,
  },
  {
    name: "PRO",
    price: "$179",
    priceSuffix: "/mo",
    subKey: "strict.plan_pro_sub",
    featureKeys: ["strict.feature_everything_starter", "billing.feature_pro_5", "strict.feature_team_workspace"],
    ctaKey: "strict.subscribe",
    featured: false,
  },
  {
    name: "ENTERPRISE",
    price: "$499",
    priceSuffix: "/mo",
    subKey: "strict.plan_enterprise_sub",
    featureKeys: [
      "strict.feature_everything_pro",
      "billing.feature_enterprise_3",
      "billing.feature_enterprise_4",
    ],
    ctaKey: "strict.subscribe",
    featured: false,
  },
] as const;

// ─── Card component ───────────────────────────────────────────────────────────

type ResolvedPlan = {
  name: string;
  price: string;
  priceSuffix?: string;
  sub: string;
  features: string[];
  cta: string;
  featured: boolean;
};

function PricingCard({
  plan,
  index,
}: {
  plan: ResolvedPlan;
  index: number;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [ctaHovered, setCtaHovered] = useState(false);

  return (
    <motion.div
      variants={V3_FADE_UP}
      custom={index}
      whileHover={{ y: -3, transition: V3_SPRING.micro }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        flex: 1,
        background: "var(--strict-glass-bg)",
        backdropFilter: "var(--strict-glass-blur)",
        border: `1px solid ${
          plan.featured
            ? isHovered
              ? "var(--strict-gold-border)"
              : "var(--strict-gold-border-active)"
            : isHovered
              ? "var(--strict-gold-border)"
              : "rgba(255,255,255,0.04)"
        }`,
        borderRadius: "14px",
        padding: "20px",
        boxShadow: plan.featured
          ? isHovered
            ? "0 0 20px rgba(201,168,76,0.08)"
            : "0 0 20px rgba(201,168,76,0.03)"
          : isHovered
            ? "0 8px 24px rgba(0,0,0,0.2)"
            : "none",
        transition: "border-color 0.2s ease, box-shadow 0.2s ease",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      {/* Plan name */}
      <p
        className="uppercase tracking-[0.5px]"
        style={{
          fontSize: "11px",
          color: "var(--strict-text-primary)",
          opacity: 0.6,
        }}
      >
        {plan.name}
      </p>

      {/* Price */}
      <div className="flex items-baseline gap-0.5">
        <span
          className="font-serif"
          style={{
            fontSize: "20px",
            color: "var(--strict-text-primary)",
            opacity: 0.8,
          }}
        >
          {plan.price}
        </span>
        {plan.priceSuffix && (
          <span
            style={{
              fontSize: "12px",
              color: "var(--strict-text-secondary)",
              opacity: 0.5,
            }}
          >
            {plan.priceSuffix}
          </span>
        )}
      </div>

      {/* Sub-label */}
      <p
        style={{
          fontSize: "9px",
          color: "var(--strict-text-dim)",
        }}
      >
        {plan.sub}
      </p>

      {/* Feature list */}
      <ul className="flex flex-col" style={{ gap: "0", listStyle: "none", padding: 0, margin: 0 }}>
        {plan.features.map((feature) => (
          <li
            key={feature}
            className="flex items-start gap-1"
            style={{
              fontSize: "9.5px",
              color: "var(--strict-text-secondary)",
              opacity: 0.35,
              lineHeight: 1.8,
            }}
          >
            <span
              style={{
                color: "var(--strict-gold-text)",
                opacity: 1,
                flexShrink: 0,
              }}
            >
              ·
            </span>
            {feature}
          </li>
        ))}
      </ul>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* CTA button */}
      <a
        href="/login"
        onMouseEnter={() => setCtaHovered(true)}
        onMouseLeave={() => setCtaHovered(false)}
        className="no-underline transition-all duration-200"
        style={{
          fontSize: "10px",
          background: "rgba(255,255,255,0.025)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,0.04)",
          borderBottom: `1px solid ${ctaHovered || plan.featured ? "var(--strict-gold-underbar-hover)" : "var(--strict-gold-underbar)"}`,
          borderRadius: "8px",
          padding: "8px 16px",
          color: "var(--strict-text-primary)",
          opacity: plan.featured ? (ctaHovered ? 1 : 0.8) : ctaHovered ? 0.8 : 0.7,
          transform: ctaHovered ? "translateY(-1px)" : "translateY(0)",
          boxShadow: ctaHovered ? "0 2px 8px rgba(201,168,76,0.08)" : "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "44px",
        }}
      >
        {plan.cta}
      </a>
    </motion.div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function StrictPricing() {
  const { t } = useI18n();
  const isMobile = useIsMobile();

  const plans: ResolvedPlan[] = PLAN_DEFS.map((def) => ({
    name: def.name,
    price: def.price,
    priceSuffix: def.priceSuffix,
    sub: t(def.subKey),
    features: def.featureKeys.map((k) => t(k)),
    cta: t(def.ctaKey),
    featured: def.featured,
  }));

  return (
    <section
        id="pricing"
        className="mx-auto"
        style={{
          maxWidth: "880px",
          padding: isMobile ? "32px 0 40px" : "40px 32px 48px",
        }}
      >
        {/* Section header */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.15 }}
          variants={V3_FADE_UP}
          className="text-center mb-8"
          style={{ padding: isMobile ? "0 16px" : undefined }}
        >
          <p
            className="uppercase tracking-[1.5px] mb-3"
            style={{
              fontSize: "9px",
              color: "var(--strict-gold-text)",
            }}
          >
            {t("strict.pricing_label")}
          </p>
          <h2
            className="font-serif font-normal"
            style={{
              fontSize: isMobile ? "18px" : "22px",
              color: "var(--strict-text-primary)",
            }}
          >
            {t("billing.choose_plan")}
          </h2>
        </motion.div>

        {isMobile ? (
          /* Mobile: horizontal scroll carousel with snap */
          <>
            <motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.1 }}
              variants={{
                hidden: { opacity: 0 },
                visible: {
                  opacity: 1,
                  transition: { staggerChildren: 0.08, delayChildren: 0.05 },
                },
              }}
              style={{
                display: "flex",
                gap: "12px",
                overflowX: "auto",
                scrollSnapType: "x mandatory",
                WebkitOverflowScrolling: "touch",
                paddingLeft: "16px",
                paddingRight: "16px",
                paddingBottom: "8px",
                /* Hide scrollbar but keep scrolling */
                scrollbarWidth: "none",
                msOverflowStyle: "none",
              }}
            >
              {plans.map((plan, index) => (
                <div
                  key={plan.name}
                  style={{
                    scrollSnapAlign: "center",
                    flexShrink: 0,
                    /* Show ~10px of next card to hint scrollability */
                    width: "calc(75vw - 16px)",
                    maxWidth: "240px",
                    minWidth: "200px",
                  }}
                >
                  <PricingCard plan={plan} index={index} />
                </div>
              ))}
            </motion.div>

            {/* Scroll indicator dots */}
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                gap: "6px",
                marginTop: "16px",
              }}
            >
              {plans.map((plan) => (
                <div
                  key={plan.name}
                  style={{
                    width: plan.featured ? "16px" : "6px",
                    height: "6px",
                    borderRadius: "3px",
                    background: plan.featured
                      ? "rgba(201,168,76,0.5)"
                      : "rgba(201,168,76,0.2)",
                    transition: "width 0.2s ease",
                  }}
                />
              ))}
            </div>

            {/* Edge-fade hint shadows */}
            <style>{`
              .strict-pricing-scroll::-webkit-scrollbar { display: none; }
            `}</style>
          </>
        ) : (
          /* Desktop: flex row */
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.1 }}
            variants={{
              hidden: { opacity: 0 },
              visible: {
                opacity: 1,
                transition: { staggerChildren: 0.08, delayChildren: 0.05 },
              },
            }}
            className="flex"
            style={{ gap: "14px" }}
          >
            {plans.map((plan, index) => (
              <PricingCard key={plan.name} plan={plan} index={index} />
            ))}
          </motion.div>
        )}
      </section>
  );
}
