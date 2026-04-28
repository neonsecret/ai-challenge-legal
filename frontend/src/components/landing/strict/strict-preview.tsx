"use client";

import { startTransition, useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { STRICT_SOURCES, STRICT_PREVIEW } from "@/lib/strict-tokens";
import { V3_SPRING, V3_FADE_UP } from "@/lib/v3-motion";
import { useIsMobile } from "@/hooks/use-mobile";
import { useI18n } from "@/lib/i18n";
import { useStrictTypewriter } from "@/lib/useStrictTypewriter";
import { StrictSidebarRail } from "@/components/chat/strict-sidebar-rail";
import { StrictSourceMargin } from "@/components/chat/strict-source-margin";
import type { StrictSourceMarginSource } from "@/components/chat/strict-source-margin";

// ─── Static content constants ─────────────────────────────────────────────────

const ANSWER_HTML =
  "Czech courts apply a strict test for force majeure under § 2913(2) of the Civil Code<sup>1</sup>. The debtor must prove the obstacle was objective, unforeseeable, and insurmountable by any reasonable precaution<sup>2</sup>.<br><br>The Supreme Court (NS) has consistently held that economic crises, price fluctuations, or market shifts do not ordinarily constitute force majeure absent extraordinary, state-level disruption<sup>3</sup>.";

const SOURCES_DATA: StrictSourceMarginSource[] = [
  { id: "0", label: "NS 23 Cdo 1561/2022 — Force Majeure Conditions", detail: "" },
  { id: "1", label: "Civil Code § 2913(2) — Exemption from Liability", detail: "" },
  { id: "2", label: "NS 23 Cdo 3141/2020 — Commercial Contracts", detail: "" },
];

// ─── Component ────────────────────────────────────────────────────────────────

export function StrictPreview() {
  const { t } = useI18n();
  const isMobile = useIsMobile();

  // Intersection visibility — trigger once, then unobserve
  const sectionRef = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(false);

  // Animation phase tracking
  const [questionVisible, setQuestionVisible] = useState(false);
  const [typewriterActive, setTypewriterActive] = useState(false);
  const [sourcesVisible, setSourcesVisible] = useState(false);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  // rAF typewriter hook — answerRef is mutated directly, no tick re-renders
  const { answerRef, typingDone } = useStrictTypewriter(ANSWER_HTML, typewriterActive);

  // ── IntersectionObserver: fire once ────────────────────────────────────────
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.3 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // ── Choreography: kick off sub-animations once in view ──────────────────────
  useEffect(() => {
    if (!inView) return;
    const t1 = setTimeout(() => setQuestionVisible(true), STRICT_PREVIEW.questionDelay);
    const t2 = setTimeout(() => setTypewriterActive(true), STRICT_PREVIEW.typewriterDelay);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [inView]);

  // ── Sources reveal after typing completes ───────────────────────────────────
  useEffect(() => {
    if (typingDone) {
      startTransition(() => {
        setSourcesVisible(true);
        if (isMobile) setSourcesExpanded(true);
      });
    }
  }, [typingDone, isMobile]);

  // ── Citation click handler (event delegation on answerRef) ────────────────
  useEffect(() => {
    if (!typingDone || !answerRef.current) return;
    const container = answerRef.current;

    const handleCitationClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName !== "SUP") return;
      target.classList.remove("citation-pulse");
      void target.offsetWidth; // force reflow to restart animation
      target.classList.add("citation-pulse");
      const timer = setTimeout(() => target.classList.remove("citation-pulse"), 600);
      return () => clearTimeout(timer);
    };

    container.addEventListener("click", handleCitationClick);
    return () => container.removeEventListener("click", handleCitationClick);
  }, [typingDone, answerRef]);

  return (
    <section
      id="features"
      ref={sectionRef}
      className="mx-auto"
      style={{
        padding: isMobile ? "40px 16px" : "56px 32px",
        maxWidth: "880px",
      }}
    >
      {/* Section header */}
      <p
        className="text-center mb-2"
        style={{
          color: "var(--strict-source-label)",
          fontSize: 10,
          letterSpacing: "1.5px",
          textTransform: "uppercase",
        }}
      >
        {t("strict.preview_label")}
      </p>
      <h2
        className="text-center mb-8"
        style={{
          fontFamily: "Georgia, serif",
          fontSize: isMobile ? 18 : 22,
          fontWeight: "normal",
          color: "var(--strict-text-primary)",
          opacity: 0.75,
        }}
      >
        {t("strict.preview_heading")}
      </h2>

      {/* Step 1 — glass pane fades up on inView */}
      <motion.div
        variants={V3_FADE_UP}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        style={{
          background: "var(--strict-glass-bg)",
          backdropFilter: "var(--strict-glass-blur)",
          border: "1px solid var(--strict-glass-border)",
          borderRadius: isMobile ? 12 : 16,
          boxShadow: "var(--strict-glass-shadow)",
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          overflow: "hidden",
          minHeight: isMobile ? "auto" : 320,
        }}
      >
        {/* Sidebar rail — desktop only */}
        {!isMobile && <StrictSidebarRail />}

        {/* Reading area — flex-1 */}
        <div
          style={{
            flex: 1,
            padding: isMobile ? "16px 14px" : "18px 22px",
            display: "flex",
            flexDirection: "column",
            minWidth: 0,
          }}
        >
          {/* Step 2 — question fades in */}
          <p
            style={{
              fontFamily: "Georgia, serif",
              fontSize: isMobile ? 11 : 12,
              fontStyle: "italic",
              color: "var(--strict-text-question)",
              marginBottom: 14,
              paddingBottom: 10,
              borderBottom: "1px solid var(--strict-gold-border)",
              opacity: questionVisible ? 1 : 0,
              transform: questionVisible ? "translateY(0)" : "translateY(8px)",
              transition: "opacity 0.5s ease, transform 0.5s ease",
            }}
          >
            {t("strict.preview_question")}
          </p>

          {/* Step 3 — typewriter answer (innerHTML set imperatively via answerRef) */}
          <style>{`
            .strict-answer-body sup {
              cursor: pointer;
              color: var(--strict-citation);
              font-size: 0.72em;
              vertical-align: super;
              padding: 0 2px;
              border-radius: 3px;
              transition: background 0.12s ease;
            }
            .strict-answer-body sup:hover {
              background: rgba(180,150,60,0.12);
            }
            @keyframes citationPulse {
              0%   { background: transparent; box-shadow: 0 0 0 0 rgba(180,150,60,0.5); }
              40%  { background: rgba(180,150,60,0.18); box-shadow: 0 0 0 6px rgba(180,150,60,0); }
              100% { background: transparent; box-shadow: 0 0 0 0 rgba(180,150,60,0); }
            }
            .strict-answer-body sup.citation-pulse {
              animation: citationPulse 0.55s ease-out forwards;
            }
          `}</style>
          <div
            ref={answerRef}
            className="strict-answer-body"
            style={{
              fontFamily: "Georgia, serif",
              fontSize: isMobile ? 12 : 12.5,
              color: "var(--strict-text-body)",
              lineHeight: 1.8,
              letterSpacing: "0.01em",
              flex: 1,
            }}
          />

          {/* Input bar */}
          <div
            style={{
              marginTop: "auto",
              paddingTop: 14,
              borderTop: "1px solid var(--strict-gold-border)",
              display: "flex",
              alignItems: "center",
            }}
          >
            <span
              style={{
                fontFamily: "Georgia, serif",
                fontSize: 11,
                color: "var(--strict-text-ghost)",
                flex: 1,
              }}
            >
              {t("strict.preview_input")}
            </span>
            <span
              style={{
                fontSize: 10,
                color: "var(--strict-gold-text)",
                opacity: 0.4,
              }}
            >
              ↵
            </span>
          </div>
        </div>

        {/* Source margin — desktop: right column; mobile: collapsible section below */}
        {isMobile ? (
          <div style={{ borderTop: "1px solid var(--strict-gold-border)" }}>
            {/* Collapsible toggle */}
            <button
              type="button"
              onClick={() => setSourcesExpanded((v) => !v)}
              style={{
                width: "100%",
                padding: "10px 14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "var(--strict-glass-recessed)",
                border: "none",
                cursor: "pointer",
                minHeight: "44px",
              }}
            >
              <span
                style={{
                  color: "var(--strict-gold-text)",
                  fontSize: 8,
                  letterSpacing: "0.5px",
                  textTransform: "uppercase",
                  opacity: 0.6,
                }}
              >
                SOURCES ({SOURCES_DATA.length})
              </span>
              <span
                style={{
                  color: "var(--strict-gold-text)",
                  fontSize: 10,
                  opacity: 0.5,
                  transition: "transform 0.2s ease",
                  transform: sourcesExpanded ? "rotate(180deg)" : "rotate(0deg)",
                }}
              >
                ▾
              </span>
            </button>

            {/* Expandable source list — CSS grid for GPU-composited animation */}
            <div
              style={{
                background: "var(--strict-glass-recessed)",
                display: "grid",
                gridTemplateRows: sourcesExpanded ? "1fr" : "0fr",
                transition: "grid-template-rows 0.35s ease",
                overflow: "hidden",
              }}
            >
              <div style={{ overflow: "hidden" }}>
                <StrictSourceMargin
                  sources={SOURCES_DATA}
                  visible={sourcesVisible && sourcesExpanded}
                  mobile
                />
              </div>
            </div>
          </div>
        ) : (
          <StrictSourceMargin
            sources={SOURCES_DATA}
            visible={sourcesVisible}
          />
        )}
      </motion.div>
    </section>
  );
}
