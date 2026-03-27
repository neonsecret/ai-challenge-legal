"use client";

import { motion } from "motion/react";

const pillars = [
  {
    title: "Instant Research",
    body: "Find exact clauses in seconds. No more manual page-turning through hundreds of pages.",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="9" cy="9" r="6" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M13.5 13.5L17 17" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M9 6v3l2 1.5" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Source-Grounded",
    body: "Every answer cites the exact page, clause, and document. Verify instantly.",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="3" y="2" width="11" height="16" rx="2" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M6 7h5M6 10h5M6 13h3" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="15" cy="15" r="3.5" fill="#0F1623" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M14.2 15.2l.8.8 1.5-1.5" stroke="#C9A84C" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Multi-Jurisdiction",
    body: "DIFC · EU · UK · US · AU — unified research across every major legal framework.",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="7" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M10 3c-2 2-3.5 4.5-3.5 7S8 16.5 10 17c2-.5 3.5-3 3.5-7S12 5 10 3z" stroke="#C9A84C" strokeWidth="1.5" />
        <path d="M3 10h14" stroke="#C9A84C" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
];

export function ValuePillars() {
  return (
    <section className="py-24 px-6" style={{ background: "#0A1120" }}>
      <div className="max-w-5xl mx-auto">
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
          className="font-heading text-center text-3xl md:text-4xl font-bold mb-14"
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
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.12 }}
              className="rounded-2xl p-6 flex flex-col gap-4"
              style={{
                background: "rgba(255,255,255,0.04)",
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              <div
                className="flex items-center justify-center size-10 rounded-xl"
                style={{
                  background: "rgba(201,168,76,0.10)",
                  border: "1px solid rgba(201,168,76,0.20)",
                }}
              >
                {p.icon}
              </div>
              <div>
                <h3
                  className="text-base font-semibold mb-1.5"
                  style={{ color: "rgba(255,255,255,0.92)" }}
                >
                  {p.title}
                </h3>
                <p
                  className="text-sm leading-relaxed"
                  style={{ color: "rgba(255,255,255,0.5)" }}
                >
                  {p.body}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
