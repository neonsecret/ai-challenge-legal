"use client"

interface StreamingStatusProps {
  status?: string | null
}

export function StreamingStatus({ status }: StreamingStatusProps) {
  const label = status ?? "Thinking\u2026"
  return (
    <div
      className="inline-flex items-center gap-2.5 rounded-xl px-3.5 py-2.5"
      style={{
        background: "rgba(255,240,215,0.20)",
        border: "1px solid rgba(255,255,255,0.40)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
      }}
    >
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 rounded-full bg-[#c9a230] animate-bounce"
            style={{ animationDelay: `${i * 0.15}s`, animationDuration: "0.8s" }}
          />
        ))}
      </div>
      <span className="text-xs" style={{ color: "#7a5a20" }}>
        {label}
      </span>
    </div>
  )
}
