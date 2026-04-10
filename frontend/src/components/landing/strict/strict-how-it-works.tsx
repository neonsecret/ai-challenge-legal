"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { V3_FADE_UP } from "@/lib/v3-motion";
import { STRICT_HIW } from "@/lib/strict-tokens";
import { useIsMobile } from "@/hooks/use-mobile";
import { useI18n } from "@/lib/i18n";
import { TypingVisual } from "./strict-hiw-typing-visual";
import { ScanningVisual } from "./strict-hiw-scanning-visual";
import { ResultVisual } from "./strict-hiw-result-visual";
import { StepItem } from "./strict-hiw-step-item";

// ─── Data ─────────────────────────────────────────────────────────────────────

const STEPS = [
  { num: "01", titleKey: "landing.step1_title", subKey: "landing.step1_body" },
  { num: "02", titleKey: "landing.step2_title", subKey: "landing.step2_body" },
  { num: "03", titleKey: "landing.step3_title", subKey: "landing.step3_body" },
] as const;

// ─── Right panel visuals ──────────────────────────────────────────────────────

function HiwVisualPanel({ activeStep }: { activeStep: number }) {
  return (
    <div
      style={{
        flex: 1,
        background: "var(--strict-hiw-bg)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid var(--strict-hiw-border)",
        borderRadius: "14px",
        padding: "24px",
        minHeight: "220px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.02)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={activeStep}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
        >
          {activeStep === 0 && <TypingVisual active={true} />}
          {activeStep === 1 && <ScanningVisual active={true} />}
          {activeStep === 2 && <ResultVisual active={true} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function StrictHowItWorks() {
  const { t } = useI18n();
  const isMobile = useIsMobile();
  const [activeStep, setActiveStep] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userPauseRef = useRef(false);

  // IntersectionObserver: trigger once, then unobserve
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const scheduleAdvance = useCallback((delay: number) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      userPauseRef.current = false;
      setActiveStep((prev) => (prev + 1) % STEPS.length);
    }, delay);
  }, []);

  // Auto-advance: skip if user just clicked
  useEffect(() => {
    if (!isVisible) return;
    if (userPauseRef.current) return;
    scheduleAdvance(STRICT_HIW.stepDuration);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isVisible, activeStep, scheduleAdvance]);

  const handleStepClick = useCallback(
    (index: number) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      userPauseRef.current = true;
      setActiveStep(index);
      timerRef.current = setTimeout(() => {
        userPauseRef.current = false;
        scheduleAdvance(STRICT_HIW.stepDuration);
      }, STRICT_HIW.userPause);
    },
    [scheduleAdvance]
  );

  return (
    <section
      ref={sectionRef}
      style={{
        padding: isMobile ? "40px 16px" : "56px 32px",
        maxWidth: "880px",
        margin: "0 auto",
      }}
    >
      {/* Label */}
      <motion.p
        variants={V3_FADE_UP}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.3 }}
        className="uppercase tracking-[1.5px]"
        style={{
          fontSize: "10px",
          color: "var(--strict-gold-text)",
          opacity: 0.4,
          textAlign: "center",
          marginBottom: "8px",
        }}
      >
        {t("landing.how_label")}
      </motion.p>

      {/* Title */}
      <motion.h2
        variants={V3_FADE_UP}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.3 }}
        className="font-serif font-normal"
        style={{
          fontSize: isMobile ? "18px" : "22px",
          color: "var(--strict-text-primary)",
          opacity: 0.75,
          textAlign: "center",
          marginBottom: "32px",
        }}
      >
        {t("landing.how_heading")}
      </motion.h2>

      {/* Layout: mobile = visual on top + step tabs below; desktop = steps left + visual right */}
      <motion.div
        variants={V3_FADE_UP}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.2 }}
        style={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          gap: isMobile ? "20px" : "24px",
          alignItems: "stretch",
        }}
      >
        {/* Visual panel — top on mobile, right on desktop */}
        {isMobile && <HiwVisualPanel activeStep={activeStep} />}

        {/* Step list */}
        {isMobile ? (
          <div style={{ display: "flex", gap: "8px" }}>
            {STEPS.map((step, idx) => (
              <button
                key={step.num}
                type="button"
                onClick={() => handleStepClick(idx)}
                style={{
                  flex: 1,
                  padding: "10px 8px",
                  borderRadius: "10px",
                  cursor: "pointer",
                  border: `1px solid ${activeStep === idx ? "var(--strict-gold-border)" : "transparent"}`,
                  background: activeStep === idx ? "var(--strict-glass-bg)" : "transparent",
                  textAlign: "center",
                  transition: "background 0.3s ease, border-color 0.3s ease",
                  minHeight: "44px",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                {/* Progress bar at bottom of tab */}
                {activeStep === idx && (
                  <div
                    style={{
                      position: "absolute",
                      bottom: 0,
                      left: 0,
                      right: 0,
                      height: "2px",
                      background: "var(--strict-hiw-progress-track)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      key={`progress-mob-${idx}-${activeStep}`}
                      style={{
                        height: "2px",
                        width: "100%",
                        background: "var(--strict-hiw-progress-fill)",
                        transformOrigin: "left",
                        willChange: "transform",
                        animation: `hiwScanFill ${STRICT_HIW.stepDuration}ms linear forwards`,
                      }}
                    />
                  </div>
                )}
                <div
                  style={{
                    color: activeStep === idx
                      ? "var(--strict-step-num-active)"
                      : "var(--strict-step-num-inactive)",
                    fontSize: "9px",
                    letterSpacing: "0.5px",
                    marginBottom: "3px",
                  }}
                >
                  {step.num}
                </div>
                <div
                  style={{
                    color: activeStep === idx
                      ? "var(--strict-step-title-active)"
                      : "var(--strict-step-title-inactive)",
                    fontSize: "10px",
                    fontWeight: 500,
                    lineHeight: 1.3,
                    transition: "color 0.3s ease",
                  }}
                >
                  {t(step.titleKey)}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div
            style={{
              width: "280px",
              flexShrink: 0,
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}
          >
            {STEPS.map((step, idx) => (
              <StepItem
                key={step.num}
                num={step.num}
                title={t(step.titleKey)}
                sub={t(step.subKey)}
                active={activeStep === idx}
                index={idx}
                onClick={() => handleStepClick(idx)}
              />
            ))}
          </div>
        )}

        {/* Visual panel — right on desktop */}
        {!isMobile && <HiwVisualPanel activeStep={activeStep} />}
      </motion.div>
    </section>
  );
}
