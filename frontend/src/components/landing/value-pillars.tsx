"use client";

import { motion } from "motion/react";

const pillars = [
  {
    stat: "< 2s",
    statLabel: "average response",
    title: "Instant Research",
    body: "Find exact clauses in seconds. No more manual page-turning through hundreds of pages.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <circle cx="10" cy="10" r="7" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M15.5 15.5L19 19" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M10 7v3l2.5 1.5" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    stat: "100%",
    statLabel: "source-grounded",
    title: "Verified Citations",
    body: "Every answer cites the exact page, clause, and document. Verify any claim instantly.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <rect x="3" y="2" width="12" height="17" rx="2" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M6 8h6M6 11h6M6 14h4" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="16" cy="16" r="4" fill="#0A1120" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M15 16.2l.8.8 1.7-1.7" stroke="#C9A84C" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    stat: "5+",
    statLabel: "major jurisdictions",
    title: "Multi-Jurisdiction",
    body: "DIFC · EU · UK · US · AU — unified research across every major legal framework.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <circle cx="11" cy="11" r="8" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M11 3c-2.2 2.2-3.5 5-3.5 8s1.3 5.8 3.5 8c2.2-2.2 3.5-5 3.5-8S13.2 5.2 11 3z" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M3 11h16" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
];

export function ValuePillars() {
  return (
    <section
      className="py-28 px-6 relative overflow-hidden"
      style={{ background: "#0A1120" }}
    >
      {/* Subtle radial glow behind cards */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 50% 60%, rgba(201,168,76,0.05) 0%, transparent 70%)",
        }}
      />

      <div className="max-w-5xl mx-auto relative">
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="text-center text-[11px] uppercase tracking-widest font-semibold mb-3"
          style={{ color: "rgba(201,168,76,0.7)" }}
        >
          Why NeoLex
        </motion.p>
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5, delay: 0.08 }}
          className="font-heading text-center text-3xl md:text-4xl font-bold mb-16"
          style={{
            color: "rgba(255,255,255,0.95)",
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
          }}
        >
          Built for legal professionals
        </motion.h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {pillars.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.55, delay: i * 0.12 }}
              whileHover={{ y: -4, transition: { duration: 0.2 } }}
              className="group relative rounded-2xl p-6 flex flex-col gap-0 cursor-default"
              style={{
                background:
                  "linear-gradient(145deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.03) 100%)",
                backdropFilter: "blur(24px)",
                WebkitBackdropFilter: "blur(24px)",
                border: "1px solid rgba(255,255,255,0.09)",
                borderTop: "2px solid rgba(201,168,76,0.45)",
                boxShadow:
                  "0 8px 32px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.06)",
              }}
            >
              {/* Hover glow */}
              <div
                className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{
                  boxShadow: "0 0 40px rgba(201,168,76,0.12)",
                }}
              />

              {/* Stat */}
              <div className="mb-5">
                <p
                  className="font-heading text-4xl font-bold leading-none mb-1"
                  style={{
                    background:
                      "linear-gradient(135deg, #e8cc7a 0%, #C9A84C 100%)",
                    WebkitBackgroundClip: "text",
                    backgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  {p.stat}
                </p>
                <p
                  className="text-[11px] uppercase tracking-wide font-medium"
                  style={{ color: "rgba(201,168,76,0.55)" }}
                >
                  {p.statLabel}
                </p>
              </div>

              {/* Divider */}
              <div
                className="mb-5 h-px w-full"
                style={{
                  background:
                    "linear-gradient(90deg, rgba(201,168,76,0.2) 0%, transparent 100%)",
                }}
              />

              {/* Icon + title */}
              <div className="flex items-center gap-3 mb-3">
                <div
                  className="flex items-center justify-center size-9 rounded-xl shrink-0"
                  style={{
                    background: "rgba(201,168,76,0.10)",
                    border: "1px solid rgba(201,168,76,0.20)",
                  }}
                >
                  {p.icon}
                </div>
                <h3
                  className="text-base font-semibold"
                  style={{ color: "rgba(255,255,255,0.92)" }}
                >
                  {p.title}
                </h3>
              </div>

              <p
                className="text-sm leading-relaxed"
                style={{ color: "rgba(255,255,255,0.45)" }}
              >
                {p.body}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
