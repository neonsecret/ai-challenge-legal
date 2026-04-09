"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { STRICT_SOURCES, STRICT_PREVIEW } from "@/lib/strict-tokens";
import { V3_SPRING, V3_FADE_UP } from "@/lib/v3-motion";
import { useIsMobile } from "@/hooks/use-mobile";
import { useStrictTypewriter } from "@/lib/useStrictTypewriter";
import { StrictSidebarRail } from "@/components/chat/strict-sidebar-rail";
import { StrictSourceMargin } from "@/components/chat/strict-source-margin";
import type { StrictSourceMarginSource } from "@/components/chat/strict-source-margin";

// ─── Static content constants ─────────────────────────────────────────────────

const QUESTION =
  "What is the notice period for termination of employment under DIFC law?";

const ANSWER_HTML =
  "The notice period under DIFC Employment Law No. 4 of 2005 varies based on the length of continuous service<sup>1</sup>. For employees with less than one year of service, the minimum notice period is seven days. For those with one to five years, the period extends to thirty days<sup>2</sup>.<br><br>In cases where the employment contract specifies a longer notice period, the contractual term prevails<sup>3</sup>.";

const SOURCES_DATA: StrictSourceMarginSource[] = [
  { id: "0", label: "DIFC Law No. 4 of 2005, Art. 58 — Notice Requirements", detail: "" },
  { id: "1", label: "DIFC Employment Regulations 2019, Schedule 2", detail: "" },
  { id: "2", label: "DIFC Court of First Instance, Case 024/2021", detail: "" },
];

// ─── Component ────────────────────────────────────────────────────────────────

export function StrictPreview() {
  const isMobile = useIsMobile();

  // Intersection visibility — trigger once, then unobserve
  const sectionRef = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(false);

  // Animation phase tracking
  const [questionVisible, setQuestionVisible] = useState(false);
  const [typewriterActive, setTypewriterActive] = useState(false);
  const [sourcesVisible, setSourcesVisible] = useState(false);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  // rAF typewriter hook
  const { bufferRef, typingDone } = useStrictTypewriter(ANSWER_HTML, typewriterActive);

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
      setSourcesVisible(true);
      if (isMobile) setSourcesExpanded(true);
    }
  }, [typingDone, isMobile]);

  return (
    <section
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
        PREVIEW
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
        The research experience
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
            {QUESTION}
          </p>

          {/* Step 3 — typewriter answer */}
          <div
            dangerouslySetInnerHTML={{ __html: bufferRef.current }}
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
              Continue your research...
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
