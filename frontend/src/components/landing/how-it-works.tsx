"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";

const AUTO_ADVANCE_MS = 6000;

const steps = [
  {
    number: "01",
    title: "Ask in plain language",
    body: "Type your question the way you'd ask a colleague. No query syntax, no boolean operators.",
  },
  {
    number: "02",
    title: "AI reads the full document",
    body: "The system locates the right pages, ranks by relevance, and extracts the exact answer.",
  },
  {
    number: "03",
    title: "Every answer cites sources",
    body: "Answers include exact page numbers and clause references so you can verify instantly.",
  },
];

/* ------------------------------------------------------------------ */
/*  Step visuals                                                        */
/* ------------------------------------------------------------------ */

function TypingVisual() {
  const fullText = "What are the indemnification obligations under Section 9?";
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    let pos = 0;
    let paused = false;

    const id = setInterval(() => {
      if (paused) return;
      pos++;
      if (pos > fullText.length) {
        paused = true;
        setTimeout(() => {
          pos = 0;
          setDisplayed("");
          paused = false;
        }, 1200);
      } else {
        setDisplayed(fullText.slice(0, pos));
      }
    }, 55);

    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="rounded-xl px-4 py-3 min-h-[52px] flex items-center"
      style={{
        background: "rgba(201,168,76,0.08)",
        border: "1px solid rgba(201,168,76,0.2)",
      }}
    >
      <span
        className="text-[12px] font-mono"
        style={{ color: "rgba(255,255,255,0.75)" }}
      >
        {displayed}
        <span
          className="inline-block w-[2px] h-[13px] ml-0.5 align-middle animate-pulse"
          style={{ backgroundColor: "#C9A84C" }}
        />
      </span>
    </div>
  );
}

function ScanningVisual() {
  const items = ["Scanning 47 pages", "Located Section 9", "Ranked 3 passages"];

  return (
    <div className="flex flex-col gap-3 py-1">
      {items.map((label, i) => (
        <motion.div
          key={label}
          className="flex items-center gap-2.5"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.35, duration: 0.4 }}
        >
          <motion.div
            className="size-2 rounded-full shrink-0"
            style={{ backgroundColor: "#C9A84C" }}
            animate={{ scale: [1, 1.4, 1], opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.3 }}
          />
          <span
            className="text-[12px] font-mono"
            style={{ color: "rgba(255,255,255,0.6)" }}
          >
            {label}
          </span>
          <motion.div
            className="flex-1 h-px rounded"
            style={{ background: "rgba(201,168,76,0.3)" }}
            initial={{ scaleX: 0, originX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: i * 0.35 + 0.2, duration: 0.5 }}
          />
        </motion.div>
      ))}
    </div>
  );
}

function HighlightVisual() {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: "rgba(27,43,75,0.5)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <p
        className="text-[10px] font-mono mb-2 uppercase tracking-wide"
        style={{ color: "rgba(201,168,76,0.7)" }}
      >
        Section 9.2 · Indemnification Agreement · Page 18
      </p>
      <motion.div
        className="rounded-md px-3 py-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3, duration: 0.5 }}
        style={{ backgroundColor: "rgba(201,168,76,0.18)" }}
      >
        <p
          className="text-[11px] leading-relaxed"
          style={{ color: "rgba(255,255,255,0.82)" }}
        >
          &ldquo;...the Indemnifying Party shall defend, indemnify, and hold
          harmless the Indemnitee from and against any and all losses, damages,
          claims, or liabilities arising from a third-party claim...&rdquo;
        </p>
      </motion.div>
    </div>
  );
}

const VISUALS = [TypingVisual, ScanningVisual, HighlightVisual];

/* ------------------------------------------------------------------ */
/*  Main component                                                      */
/* ------------------------------------------------------------------ */

export function HowItWorks() {
  const [activeStep, setActiveStep] = useState(0);
  const [userInteracted, setUserInteracted] = useState(false);

  // Auto-advance only until the user takes control
  useEffect(() => {
    if (userInteracted) return;
    const id = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, AUTO_ADVANCE_MS);
    return () => clearInterval(id);
  }, [userInteracted]);

  const goTo = (i: number) => {
    setActiveStep(i);
    setUserInteracted(true);
  };

  const goPrev = () => goTo((activeStep - 1 + steps.length) % steps.length);
  const goNext = () => goTo((activeStep + 1) % steps.length);

  const Visual = VISUALS[activeStep];

  return (
    <section
      className="py-24 px-6"
      style={{ background: "linear-gradient(180deg, #0F1623 0%, #0A1120 100%)" }}
    >
      <div className="max-w-4xl mx-auto">
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5 }}
          className="text-center text-[11px] uppercase tracking-widest font-semibold mb-3"
          style={{ color: "rgba(201,168,76,0.7)" }}
        >
          How it works
        </motion.p>
        <motion.h2
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: 0.08 }}
          className="font-heading text-center text-3xl md:text-4xl font-bold mb-12"
          style={{
            color: "rgba(255,255,255,0.95)",
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
          }}
        >
          Three steps from question to answer
        </motion.h2>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: 0.18 }}
        >
          {/* Step selector + nav */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {/* Prev arrow */}
            <button
              onClick={goPrev}
              className="shrink-0 flex items-center justify-center size-8 rounded-full transition-colors hover:bg-white/10"
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.10)",
                color: "rgba(255,255,255,0.5)",
              }}
              aria-label="Previous step"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M6.5 2L3.5 5L6.5 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            {/* Step tabs */}
            <div className="flex gap-2">
              {steps.map((s, i) => (
                <button
                  key={s.number}
                  onClick={() => goTo(i)}
                  className="flex items-center gap-2 rounded-full px-4 py-2 transition-all"
                  style={{
                    background:
                      i === activeStep
                        ? "rgba(201,168,76,0.18)"
                        : "rgba(255,255,255,0.04)",
                    border:
                      i === activeStep
                        ? "1px solid rgba(201,168,76,0.4)"
                        : "1px solid rgba(255,255,255,0.08)",
                    color:
                      i === activeStep ? "#C9A84C" : "rgba(255,255,255,0.45)",
                  }}
                >
                  <span className="font-mono text-[11px] font-bold">
                    {s.number}
                  </span>
                  <span className="hidden sm:inline text-[12px] font-medium">
                    {s.title}
                  </span>
                </button>
              ))}
            </div>

            {/* Next arrow */}
            <button
              onClick={goNext}
              className="shrink-0 flex items-center justify-center size-8 rounded-full transition-colors hover:bg-white/10"
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.10)",
                color: "rgba(255,255,255,0.5)",
              }}
              aria-label="Next step"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>

          {/* Step content */}
          <AnimatePresence mode="wait">
            <motion.div
              key={activeStep}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
              className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center rounded-2xl p-5 md:p-8"
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              {/* Left: text */}
              <div>
                <div
                  className="inline-flex items-center justify-center size-10 rounded-full font-mono text-[11px] font-bold mb-4"
                  style={{
                    background: "rgba(201,168,76,0.12)",
                    border: "1px solid rgba(201,168,76,0.3)",
                    color: "#C9A84C",
                  }}
                >
                  {steps[activeStep].number}
                </div>
                <h3
                  className="text-xl font-semibold mb-2"
                  style={{ color: "rgba(255,255,255,0.92)" }}
                >
                  {steps[activeStep].title}
                </h3>
                <p
                  className="text-sm leading-relaxed mb-5"
                  style={{ color: "rgba(255,255,255,0.5)" }}
                >
                  {steps[activeStep].body}
                </p>

                {/* Progress dots */}
                <div className="flex items-center gap-1.5">
                  {steps.map((_, i) => (
                    <motion.div
                      key={i}
                      className="h-1 rounded-full cursor-pointer"
                      style={{ backgroundColor: "#C9A84C" }}
                      animate={{
                        width: i === activeStep ? 28 : 8,
                        opacity: i === activeStep ? 1 : 0.25,
                      }}
                      transition={{ duration: 0.3 }}
                      onClick={() => goTo(i)}
                    />
                  ))}
                  {!userInteracted && (
                    <span
                      className="ml-2 text-[10px] font-mono"
                      style={{ color: "rgba(255,255,255,0.2)" }}
                    >
                      auto
                    </span>
                  )}
                </div>
              </div>

              {/* Right: animated visual */}
              <div>
                <Visual />
              </div>
            </motion.div>
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  );
}
