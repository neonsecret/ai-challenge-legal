"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { V3_SPRING, V3_FADE_UP } from "@/lib/v3-motion";
import { STRICT_TYPEWRITER, STRICT_HIW } from "@/lib/strict-tokens";

// ─── Data ─────────────────────────────────────────────────────────────────────

const STEPS = [
  {
    num: "01",
    title: "Ask in plain language",
    sub: "No query syntax, no boolean operators. Type your question the way you'd ask a colleague.",
  },
  {
    num: "02",
    title: "AI searches statutes & case law",
    sub: "Searches across legislation and court decisions, ranks passages by relevance, extracts the precise answer.",
  },
  {
    num: "03",
    title: "Every answer cites sources",
    sub: "Exact page numbers, article references, and case citations so you can verify instantly.",
  },
] as const;

const TYPING_QUESTION =
  "What are the indemnification obligations under Section 9?";

const SCAN_ITEMS = [
  "Scanning 4,800+ documents",
  "Located Article 58 §2",
  "Ranked 5 passages",
] as const;

// ─── Visual 1: Typing ─────────────────────────────────────────────────────────

function TypingVisual({ active }: { active: boolean }) {
  const [displayText, setDisplayText] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const indexRef = useRef(0);

  const restart = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setDisplayText("");
    indexRef.current = 0;
    intervalRef.current = setInterval(() => {
      if (indexRef.current >= TYPING_QUESTION.length) {
        clearInterval(intervalRef.current!);
        return;
      }
      setDisplayText(TYPING_QUESTION.slice(0, indexRef.current + 1));
      indexRef.current += 1;
    }, STRICT_TYPEWRITER.hiw);
  }, []);

  useEffect(() => {
    if (active) {
      restart();
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [active, restart]);

  return (
    <div
      style={{
        background: "rgba(0,0,0,0.15)",
        border: "1px solid rgba(201,168,76,0.06)",
        borderRadius: "8px",
        padding: "10px 14px",
        fontFamily: "'SF Mono', Monaco, 'Cascadia Code', monospace",
        fontSize: "11.5px",
        color: "rgba(255,255,255,0.6)",
        minHeight: "40px",
        display: "flex",
        alignItems: "center",
      }}
    >
      <span>{displayText}</span>
      <span
        style={{
          display: "inline-block",
          width: "2px",
          height: "14px",
          background: "var(--strict-gold-text)",
          marginLeft: "1px",
          animation: "hiwCursorBlink 0.7s step-end infinite",
        }}
      />
    </div>
  );
}

// ─── Visual 2: Scanning ───────────────────────────────────────────────────────

interface ScanItemState {
  visible: boolean;
  done: boolean;
}

function ScanningVisual({ active }: { active: boolean }) {
  const [items, setItems] = useState<ScanItemState[]>([
    { visible: false, done: false },
    { visible: false, done: false },
    { visible: false, done: false },
  ]);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const resetAndStart = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    setItems([
      { visible: false, done: false },
      { visible: false, done: false },
      { visible: false, done: false },
    ]);

    SCAN_ITEMS.forEach((_, idx) => {
      // Appear with slide-in
      const appearTimer = setTimeout(
        () => {
          setItems((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], visible: true };
            return next;
          });
        },
        idx * STRICT_HIW.scanStagger
      );
      // Mark done after line fills (1500ms after appearing)
      const doneTimer = setTimeout(
        () => {
          setItems((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], done: true };
            return next;
          });
        },
        idx * STRICT_HIW.scanStagger + 1500
      );
      timersRef.current.push(appearTimer, doneTimer);
    });
  }, []);

  useEffect(() => {
    if (active) {
      resetAndStart();
    } else {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    }
    return () => {
      timersRef.current.forEach(clearTimeout);
    };
  }, [active, resetAndStart]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
      {SCAN_ITEMS.map((label, idx) => {
        const item = items[idx];
        return (
          <div
            key={label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "12px",
              opacity: item.visible ? 1 : 0,
              transform: item.visible ? "translateX(0)" : "translateX(-8px)",
              transition: "opacity 0.4s ease, transform 0.4s ease",
            }}
          >
            {/* Pulsing gold dot */}
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "rgba(201,168,76,0.4)",
                flexShrink: 0,
                animation: "hiwScanPulse 1.2s ease-in-out infinite",
              }}
            />
            {/* Progress line */}
            <div
              style={{
                flex: 1,
                height: "2px",
                background: "rgba(201,168,76,0.08)",
                borderRadius: "1px",
                position: "relative",
                overflow: "hidden",
              }}
            >
              {item.visible && (
                <div
                  key={`fill-${idx}-${active}`}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    height: "100%",
                    background:
                      "linear-gradient(90deg, rgba(201,168,76,0.25), rgba(201,168,76,0.05))",
                    borderRadius: "1px",
                    animation: "hiwScanFill 1.5s ease forwards",
                  }}
                />
              )}
            </div>
            {/* Label */}
            <span
              style={{
                color: "rgba(255,255,255,0.4)",
                fontSize: "10.5px",
                fontFamily: "'SF Mono', Monaco, 'Cascadia Code', monospace",
                minWidth: "120px",
              }}
            >
              {label}
            </span>
            {/* Checkmark */}
            <span
              style={{
                color: "var(--strict-gold-text)",
                fontSize: "11px",
                opacity: item.done ? 1 : 0,
                transition: "opacity 0.3s ease",
              }}
            >
              ✓
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Visual 3: Result ─────────────────────────────────────────────────────────

function ResultVisual({ active }: { active: boolean }) {
  const [highlightVisible, setHighlightVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (active) {
      setHighlightVisible(false);
      timerRef.current = setTimeout(() => {
        setHighlightVisible(true);
      }, STRICT_HIW.resultHighlightDelay);
    } else {
      if (timerRef.current) clearTimeout(timerRef.current);
      setHighlightVisible(false);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [active]);

  return (
    <div
      style={{
        background: "rgba(0,0,0,0.12)",
        border: "1px solid rgba(201,168,76,0.06)",
        borderRadius: "8px",
        padding: "12px 14px",
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          color: "var(--strict-source-label)",
          fontSize: "9px",
          letterSpacing: "0.5px",
          marginBottom: "8px",
        }}
      >
        <span>Article 58 §2 · DIFC Law No. 4 of 2005</span>
        <span>Page 34</span>
      </div>
      {/* Body text */}
      <p
        style={{
          color: "var(--strict-text-body)",
          opacity: 0.5,
          fontSize: "10.5px",
          lineHeight: 1.6,
          fontFamily: "Georgia, serif",
          margin: 0,
        }}
      >
        The minimum notice period varies based on length of continuous service
        with the employer.
      </p>
      {/* Highlighted quote */}
      <div
        style={{
          background: "rgba(201,168,76,0.08)",
          borderLeft: "2px solid rgba(201,168,76,0.2)",
          padding: "8px 10px",
          borderRadius: "0 6px 6px 0",
          marginTop: "8px",
          opacity: highlightVisible ? 1 : 0,
          transform: highlightVisible ? "translateY(0)" : "translateY(6px)",
          transition: "opacity 0.5s ease, transform 0.5s ease",
        }}
      >
        <p
          style={{
            color: "rgba(255,255,255,0.5)",
            fontSize: "10.5px",
            fontFamily: "Georgia, serif",
            lineHeight: 1.6,
            fontStyle: "italic",
            margin: 0,
          }}
        >
          &ldquo;...the employer shall provide not less than thirty days&rsquo;
          written notice to the employee, or payment in lieu thereof, where the
          employee has completed one year of continuous service...&rdquo;
        </p>
      </div>
    </div>
  );
}

// ─── Step item ────────────────────────────────────────────────────────────────

interface StepItemProps {
  num: string;
  title: string;
  sub: string;
  active: boolean;
  index: number;
  onClick: () => void;
}

function StepItem({ num, title, sub, active, index, onClick }: StepItemProps) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...V3_SPRING.gentle, delay: 0.1 + index * 0.08 }}
      style={{
        position: "relative",
        padding: "14px 16px",
        borderRadius: "10px",
        cursor: "pointer",
        border: `1px solid ${active ? "var(--strict-gold-border)" : "transparent"}`,
        background: active ? "var(--strict-glass-bg)" : "transparent",
        display: "flex",
        gap: "12px",
        alignItems: "flex-start",
        textAlign: "left",
        width: "100%",
        transition: "background 0.3s ease, border-color 0.3s ease",
      }}
    >
      {/* Vertical progress bar track */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: "2px",
          borderRadius: "1px",
          background: "rgba(201,168,76,0.06)",
          overflow: "hidden",
        }}
      >
        {/* Fill — re-mounts when step becomes active to restart animation */}
        {active && (
          <div
            key={`progress-${index}-${active}`}
            style={{
              width: "2px",
              borderRadius: "1px",
              background: "rgba(201,168,76,0.3)",
              height: "0%",
              animation: `hiwProgressFill ${STRICT_HIW.stepDuration}ms linear forwards`,
            }}
          />
        )}
      </div>

      {/* Step number */}
      <span
        style={{
          color: active ? "rgba(201,168,76,0.5)" : "rgba(201,168,76,0.25)",
          fontSize: "10px",
          letterSpacing: "0.5px",
          marginTop: "2px",
          minWidth: "16px",
          transition: "color 0.3s ease",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {num}
      </span>

      {/* Step content */}
      <div style={{ flex: 1 }}>
        <div
          style={{
            color: active
              ? "rgba(230,235,245,0.8)"
              : "rgba(230,235,245,0.45)",
            fontSize: "12px",
            fontWeight: 500,
            marginBottom: "3px",
            transition: "color 0.3s ease",
          }}
        >
          {title}
        </div>
        <div
          style={{
            color: active
              ? "rgba(200,210,230,0.35)"
              : "rgba(200,210,230,0.22)",
            fontSize: "9.5px",
            lineHeight: 1.4,
            transition: "color 0.3s ease",
          }}
        >
          {sub}
        </div>
      </div>
    </motion.button>
  );
}

// ─── Right panel visuals ──────────────────────────────────────────────────────

function HiwVisualPanel({ activeStep }: { activeStep: number }) {
  return (
    <div
      style={{
        flex: 1,
        background: "rgba(255,255,255,0.015)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid rgba(201,168,76,0.04)",
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
  const [activeStep, setActiveStep] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userPauseRef = useRef(false);

  // IntersectionObserver: start auto-advance when section is visible
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !isVisible) {
            setIsVisible(true);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.3 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [isVisible]);

  const scheduleAdvance = useCallback(
    (delay: number) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        userPauseRef.current = false;
        setActiveStep((prev) => (prev + 1) % STEPS.length);
      }, delay);
    },
    []
  );

  // Start auto-advance once section is visible
  useEffect(() => {
    if (!isVisible) return;
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
      // Resume auto-advance after user pause
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        userPauseRef.current = false;
        scheduleAdvance(STRICT_HIW.stepDuration);
      }, STRICT_HIW.userPause);
    },
    [scheduleAdvance]
  );

  return (
    <>
      {/* Keyframe injection */}
      <style>{`
        @keyframes hiwProgressFill {
          to { height: 100%; }
        }
        @keyframes hiwCursorBlink {
          50% { opacity: 0; }
        }
        @keyframes hiwScanPulse {
          0%, 100% { transform: scale(1); opacity: 0.6; }
          50% { transform: scale(1.4); opacity: 1; }
        }
        @keyframes hiwScanFill {
          to { width: 100%; }
        }
      `}</style>

      <section
        ref={sectionRef}
        style={{ padding: "56px 32px", maxWidth: "880px", margin: "0 auto" }}
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
          HOW IT WORKS
        </motion.p>

        {/* Title */}
        <motion.h2
          variants={V3_FADE_UP}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          className="font-serif font-normal"
          style={{
            fontSize: "22px",
            color: "var(--strict-text-primary)",
            opacity: 0.75,
            textAlign: "center",
            marginBottom: "32px",
          }}
        >
          See it in action
        </motion.h2>

        {/* Layout: steps + visual panel */}
        <motion.div
          variants={V3_FADE_UP}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          style={{
            display: "flex",
            gap: "24px",
            alignItems: "stretch",
          }}
        >
          {/* Left: step list */}
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
                title={step.title}
                sub={step.sub}
                active={activeStep === idx}
                index={idx}
                onClick={() => handleStepClick(idx)}
              />
            ))}
          </div>

          {/* Right: animated visual panel */}
          <HiwVisualPanel activeStep={activeStep} />
        </motion.div>
      </section>
    </>
  );
}
