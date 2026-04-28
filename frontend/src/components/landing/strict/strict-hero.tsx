"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { V3_SPRING } from "@/lib/v3-motion";
import {
  STRICT_COUNTER,
  STRICT_HERO_STAGGER,
  STRICT_BADGE_PULSE,
  STRICT_GLOW_PULSE,
} from "@/lib/strict-tokens";
import { useIsMobile } from "@/hooks/use-mobile";
import { useI18n } from "@/lib/i18n";

// ─── Data ─────────────────────────────────────────────────────────────────────

const STATS = [
  { value: "0.824", label: "GaRAGe RAF", badge: "+36% above SOTA", detail: "Retrieval-augmented factuality · ACL 2025" },
  { value: "0.860", label: "Legal RAG Bench retrieval", badge: null, detail: "Full 100-question evaluation" },
  { value: "0.691", label: "LEXam Open EN", badge: "+21% above SOTA", detail: "Published SOTA: 0.572 (Claude 3.7-S)" },
] as const;

const JURISDICTIONS = ["Czech", "DIFC", "UK", "Australia"] as const;

// ─── Shared styles ────────────────────────────────────────────────────────────

const goldGradientText: React.CSSProperties = {
  background: "linear-gradient(135deg, var(--strict-gold-gradient-start), var(--strict-gold-gradient-end))",
  WebkitBackgroundClip: "text",
  WebkitTextFillColor: "transparent",
  backgroundClip: "text",
};

// ─── Jurisdiction pills ───────────────────────────────────────────────────────

function JurisdictionPills() {
  const [hovered, setHovered] = useState<string | null>(null);
  return (
    <div className="flex items-center flex-wrap gap-[8px] mb-5">
      {JURISDICTIONS.map((jur, i) => (
        <span key={jur} className="flex items-center gap-[8px]">
          <span
            onMouseEnter={() => setHovered(jur)}
            onMouseLeave={() => setHovered(null)}
            className="text-[10px] tracking-[0.5px] cursor-default transition-all duration-200"
            style={
              hovered === jur
                ? {
                    color: "var(--strict-gold-text)",
                    background: "var(--strict-gold-badge-bg)",
                    border: "1px solid var(--strict-gold-border)",
                    borderRadius: "5px",
                    padding: "1px 6px",
                    opacity: 1,
                  }
                : { color: "var(--strict-gold-text)", opacity: 0.7 }
            }
          >
            {jur}
          </span>
          {i < JURISDICTIONS.length - 1 && (
            <span
              className="text-[10px] select-none"
              style={{ color: "var(--strict-gold-text)", opacity: 0.15 }}
            >
              ·
            </span>
          )}
        </span>
      ))}
    </div>
  );
}

// ─── CTA button ───────────────────────────────────────────────────────────────

function CtaButton() {
  const [hovered, setHovered] = useState(false);
  const { t } = useI18n();
  return (
    <a
      href="/login"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="inline-block text-[12px] tracking-[0.3px] no-underline"
      style={{
        background: "var(--strict-glass-bg)",
        backdropFilter: "blur(12px)",
        border: "1px solid var(--strict-glass-border)",
        borderBottom: `1px solid ${hovered ? "var(--strict-gold-underbar-hover)" : "var(--strict-gold-underbar)"}`,
        borderRadius: "8px",
        padding: "10px 24px",
        color: "var(--strict-text-primary)",
        opacity: hovered ? 1 : 0.8,
        transform: hovered ? "translateY(-1px)" : "translateY(0)",
        boxShadow: hovered ? "0 2px 8px var(--strict-hiw-progress-track)" : "none",
        transition:
          "transform 0.2s ease, border-bottom-color 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease",
        minHeight: "44px",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {t("landing.get_started")}
    </a>
  );
}

// ─── Stat separator ───────────────────────────────────────────────────────────

const StatSep = () => (
  <div style={{ height: "1px", background: "var(--strict-gold-sep)" }} />
);

// ─── Stat badge ───────────────────────────────────────────────────────────────

const StatBadge = ({ text }: { text: string }) => (
  <span
    className="inline-block text-[8px] ml-1.5"
    style={{
      background: "var(--strict-gold-badge-bg)",
      border: "1px solid var(--strict-gold-badge-border)",
      color: "var(--strict-badge-text)",
      borderRadius: "4px",
      padding: "1px 6px",
      animation: `strictBadgePulse ${STRICT_BADGE_PULSE}s ease-in-out infinite`,
    }}
  >
    {text}
  </span>
);

// ─── Normal stat row ──────────────────────────────────────────────────────────

function StatRow({
  value,
  label,
  badge,
  detail,
  index,
}: {
  value: string;
  label: string;
  badge: string | null;
  detail: string;
  index: number;
}) {
  return (
    <motion.div
      initial={{ y: 12 }}
      animate={{ y: 0 }}
      transition={{
        ...V3_SPRING.gentle,
        delay: 0.3 + index * (STRICT_HERO_STAGGER / 1000),
      }}
    >
      <div className="flex items-baseline gap-2 flex-wrap">
        <span
          className="font-serif leading-none"
          style={{
            fontSize: "24px",
            color: "var(--strict-text-primary)",
            opacity: 0.82,
          }}
        >
          {value}
        </span>
        <span
          className="text-[10px] leading-snug"
          style={{ color: "var(--strict-text-secondary)", opacity: 0.35 }}
        >
          {label}
        </span>
        {badge && <StatBadge text={badge} />}
      </div>
      <p className="text-[9px] mt-0.5" style={{ color: "var(--strict-text-dim)" }}>
        {detail}
      </p>
    </motion.div>
  );
}

// ─── 100% citation accuracy stat (animated counter + gold glow) ───────────────

function CitationStat() {
  const { t } = useI18n();
  const [count, setCount] = useState(0);
  const [glowVisible, setGlowVisible] = useState(false);
  const [pulsing, setPulsing] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const startTimeout = setTimeout(() => {
      setGlowVisible(true);
      intervalRef.current = setInterval(() => {
        setCount((prev) => {
          const next = prev + STRICT_COUNTER.step;
          if (next >= 100) {
            clearInterval(intervalRef.current!);
            setPulsing(true);
            return 100;
          }
          return next;
        });
      }, STRICT_COUNTER.interval);
    }, STRICT_COUNTER.delay);

    return () => {
      clearTimeout(startTimeout);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return (
    <motion.div
      className="relative"
      initial={{ y: 12 }}
      animate={{ y: 0 }}
      transition={{
        ...V3_SPRING.gentle,
        delay: 0.3 + 3 * (STRICT_HERO_STAGGER / 1000),
      }}
    >
      {/* Gold radial glow */}
      <div
        className="absolute pointer-events-none"
        style={{
          top: "-4px",
          left: "-8px",
          width: "60px",
          height: "36px",
          background: "var(--strict-glow-radial)",
          borderRadius: "50%",
          opacity: glowVisible ? 1 : 0,
          transition: "opacity 1s ease",
        }}
      />
      <div className="flex items-baseline gap-2 flex-wrap">
        <span
          className="font-serif leading-none"
          style={{
            fontSize: "28px",
            ...goldGradientText,
            animation: pulsing
              ? `strictGlowPulse ${STRICT_GLOW_PULSE}s ease-in-out infinite`
              : undefined,
          }}
        >
          {count}%
        </span>
        <span
          className="text-[10px] leading-snug"
          style={{ color: "var(--strict-text-secondary)", opacity: 0.35 }}
        >
          {t("landing.light_pillar2_stat_label")}
        </span>
      </div>
      <p className="text-[9px] mt-0.5" style={{ color: "var(--strict-text-dim)" }}>
        {t("strict.citation_detail")}
      </p>
    </motion.div>
  );
}

// ─── Stats block (shared between desktop right column and mobile bottom) ──────

function StatsBlock() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-4">
      <motion.p
        initial={{ y: 8 }}
        animate={{ y: 0 }}
        transition={{ ...V3_SPRING.gentle, delay: 0.2 }}
        className="uppercase tracking-[1px]"
        style={{
          fontSize: "8px",
          color: "var(--strict-source-label)",
          marginBottom: "4px",
        }}
      >
        {t("landing.bench_heading")}
      </motion.p>

      {STATS.map((stat, i) => (
        <div key={stat.value} className="flex flex-col gap-4">
          <StatRow
            value={stat.value}
            label={stat.label}
            badge={stat.badge ?? null}
            detail={stat.detail}
            index={i}
          />
          <StatSep />
        </div>
      ))}

      <CitationStat />
    </div>
  );
}

// ─── Hero slab (main export) ──────────────────────────────────────────────────

export function StrictHero() {
  const isMobile = useIsMobile();
  const { t } = useI18n();

  return (
    <section
      className="mx-auto"
      style={{ maxWidth: "880px", padding: isMobile ? "24px 16px 32px" : "40px 32px 48px" }}
    >
      {/* Living Glass Slab - no animation wrapper to ensure LCP fires immediately */}
      <div
        className="strict-hero-container"
        style={{
          background: "var(--strict-glass-bg)",
          backdropFilter: "var(--strict-glass-blur)",
          border: "1px solid var(--strict-glass-border)",
          borderRadius: isMobile ? "12px" : "18px",
          padding: isMobile ? "20px 16px" : "32px",
          boxShadow: "var(--strict-glass-shadow)",
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          gap: isMobile ? "0" : "28px",
          alignItems: "flex-start",
        }}
      >
        {/* Hero text - plain elements for immediate LCP */}
        <div className="flex flex-col" style={{ flex: 1 }}>
          <h1
            className="font-serif font-normal leading-[1.2] mb-2.5"
            style={{
              fontSize: isMobile ? "24px" : "32px",
              color: "var(--strict-text-primary)",
            }}
          >
            {t("landing.hero_title_prefix")}
            <br />
            <span style={goldGradientText}>{t("landing.hero_title_highlight")}</span>
          </h1>

          <p
            className="text-[13px] leading-[1.6] mb-[18px]"
            style={{ color: "var(--strict-text-secondary)", whiteSpace: "pre-line" }}
          >
            {t("landing.hero_subtitle")}
          </p>

          <div>
            <JurisdictionPills />
          </div>

          <div>
            <CtaButton />
          </div>
        </div>

        {/* Divider — horizontal on mobile, vertical on desktop */}
        <div
          style={
            isMobile
              ? {
                  height: "1px",
                  background: "var(--strict-gold-sep)",
                  margin: "20px 0",
                  width: "100%",
                }
              : {
                  width: "1px",
                  background: "var(--strict-gold-border)",
                  alignSelf: "stretch",
                }
          }
        />

        {/* Stats */}
        <div
          style={
            isMobile
              ? { width: "100%" }
              : { width: "260px", flexShrink: 0 }
          }
        >
          <StatsBlock />
        </div>
        </div>
    </section>
  );
}
