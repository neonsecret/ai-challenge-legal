"use client";

import { useEffect, useRef, useState } from "react";
import { STRICT_HIW } from "@/lib/strict-tokens";

export function ResultVisual({ active }: { active: boolean }) {
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
        background: "var(--strict-hiw-bg)",
        border: "1px solid var(--strict-hiw-border)",
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
          background: "var(--strict-hiw-progress-track)",
          borderLeft: "2px solid var(--strict-hiw-progress-fill)",
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
