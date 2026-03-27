"use client";

import { useRef } from "react";
import { motion, useInView } from "motion/react";

const steps = [
  {
    number: "01",
    title: "Ask in plain language",
    body: "Type your question the way you'd ask a colleague. No query syntax, no boolean operators.",
    detail: "What are the indemnification obligations under Section 9?",
  },
  {
    number: "02",
    title: "AI reads the full document",
    body: "The system locates the right pages, ranks by relevance, and extracts the exact answer.",
    detail: "Scanning 47 pages · Located Section 9 · Ranked 3 passages",
  },
  {
    number: "03",
    title: "Every answer cites sources",
    body: "Answers include exact page numbers and clause references so you can verify instantly.",
    detail: "Section 9.2 · Indemnification Agreement · Page 18",
  },
];

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section
      ref={ref}
      className="py-24 px-6"
      style={{
        background:
          "linear-gradient(180deg, #0F1623 0%, #0A1120 100%)",
      }}
    >
      <div className="max-w-4xl mx-auto">
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center text-[11px] uppercase tracking-widest font-semibold mb-3"
          style={{ color: "rgba(201,168,76,0.7)" }}
        >
          How it works
        </motion.p>
        <motion.h2
          initial={{ opacity: 0, y: 10 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.08 }}
          className="font-heading text-center text-3xl md:text-4xl font-bold mb-16"
          style={{
            color: "rgba(255,255,255,0.95)",
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
          }}
        >
          Three steps from question to answer
        </motion.h2>

        <div className="flex flex-col gap-0">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, x: -20 }}
              animate={inView ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.55, delay: 0.12 + i * 0.15 }}
              className="relative flex gap-6 pb-10 last:pb-0"
            >
              {/* Vertical line */}
              {i < steps.length - 1 && (
                <div
                  className="absolute left-5 top-10 bottom-0 w-px"
                  style={{
                    background:
                      "linear-gradient(180deg, rgba(201,168,76,0.25) 0%, transparent 100%)",
                  }}
                />
              )}

              {/* Number bubble */}
              <div
                className="flex-shrink-0 flex items-center justify-center size-10 rounded-full font-mono text-[11px] font-bold"
                style={{
                  background: "rgba(201,168,76,0.12)",
                  border: "1px solid rgba(201,168,76,0.3)",
                  color: "#C9A84C",
                }}
              >
                {step.number}
              </div>

              {/* Content */}
              <div className="flex-1 pt-1.5">
                <h3
                  className="font-heading text-lg font-semibold mb-1.5"
                  style={{ color: "rgba(255,255,255,0.92)" }}
                >
                  {step.title}
                </h3>
                <p
                  className="text-sm leading-relaxed mb-3"
                  style={{ color: "rgba(255,255,255,0.5)" }}
                >
                  {step.body}
                </p>
                <div
                  className="inline-flex items-center gap-2 rounded-lg px-3 py-1.5"
                  style={{
                    background: "rgba(27,43,75,0.5)",
                    border: "1px solid rgba(255,255,255,0.08)",
                  }}
                >
                  <div
                    className="size-1 rounded-full"
                    style={{ backgroundColor: "#C9A84C" }}
                  />
                  <span
                    className="text-[11px] font-mono"
                    style={{ color: "rgba(255,255,255,0.55)" }}
                  >
                    {step.detail}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
