"use client"

interface StreamingStatusProps {
  status?: string | null
  isDark?: boolean
}

export function StreamingStatus({ status, isDark = false }: StreamingStatusProps) {
  const label = status ?? "Thinking\u2026"
  return (
    <div
      className="inline-flex items-center gap-2.5 rounded-xl px-3.5 py-2.5"
      style={{
        background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,240,215,0.20)",
        border: isDark ? "1px solid rgba(255,255,255,0.14)" : "1px solid rgba(255,255,255,0.40)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
      }}
    >
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 rounded-full animate-bounce"
            style={{
              background: isDark ? "#C9A84C" : "#c9a230",
              animationDelay: `${i * 0.15}s`,
              animationDuration: "0.8s",
            }}
          />
        ))}
      </div>
      <span className="text-xs" style={{ color: isDark ? "rgba(255,255,255,0.72)" : "#7a5a20" }}>
        {label}
      </span>
    </div>
  )
}
