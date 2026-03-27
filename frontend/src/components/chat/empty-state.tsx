"use client"

import { GlassCard } from "@/components/ui/glass-card"

const DEMO_QUESTIONS = [
  "What is the limitation period under DIFC Law No. 5 of 2005?",
  "What are the grounds for terminating an employment contract under DIFC Employment Law?",
  "What fiduciary duties does a company director owe under DIFC Companies Law?",
  "How is arbitration initiated under the DIFC Arbitration Law?",
]

interface EmptyStateProps {
  onSelectQuestion: (q: string) => void
}

export function EmptyState({ onSelectQuestion }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[65vh] text-center px-2">

      {/* Shield logo glow — 80x80px */}
      <div
        className="flex items-center justify-center size-20 rounded-3xl mb-6"
        style={{
          background: "rgba(201,162,48,0.12)",
          backdropFilter: "blur(24px)",
          WebkitBackdropFilter: "blur(24px)",
          border: "1px solid rgba(201,162,48,0.28)",
          boxShadow:
            "0 0 60px rgba(201,162,48,0.18), 0 0 120px rgba(201,162,48,0.08), inset 0 1px 0 rgba(255,255,255,0.30)",
        }}
      >
        <svg width="34" height="34" viewBox="0 0 14 14" fill="none">
          <path
            d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
            stroke="#c9a230"
            strokeWidth="1.2"
            strokeLinejoin="round"
            fill="rgba(201,162,48,0.22)"
          />
        </svg>
      </div>

      <h2
        className="font-heading text-3xl font-bold mb-3"
        style={{ color: "#1e1208", letterSpacing: "-0.03em" }}
      >
        What can I help you research?
      </h2>
      <p className="text-sm mb-12 max-w-sm" style={{ color: "#7a5a20" }}>
        Precise answers from your legal documents. Every response cites the exact page and clause.
      </p>

      {/* Suggestion grid — GlassCard with CSS-only hover */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {DEMO_QUESTIONS.map((q, i) => (
          <button
            key={q}
            onClick={() => onSelectQuestion(q)}
            className="text-left transition-all group"
            style={{ background: "none", border: "none", padding: 0 }}
          >
            <GlassCard
              variant="subtle"
              className="rounded-2xl px-5 py-4 text-sm cursor-pointer
                         hover:border-[rgba(201,162,48,0.40)]
                         hover:[background:rgba(255,240,215,0.25)]
                         transition-all duration-150"
            >
              <div className="flex items-start gap-3">
                <span
                  className="shrink-0 mt-0.5 text-[10px] font-bold font-mono rounded-md px-1.5 py-0.5"
                  style={{
                    background: "rgba(201,162,48,0.14)",
                    border: "1px solid rgba(201,162,48,0.28)",
                    color: "#7a5a20",
                  }}
                >
                  0{i + 1}
                </span>
                <span
                  className="line-clamp-2 leading-relaxed group-hover:text-[#2e1f08] transition-colors"
                  style={{ color: "#7a5a20" }}
                >
                  {q}
                </span>
              </div>
            </GlassCard>
          </button>
        ))}
      </div>
    </div>
  )
}
