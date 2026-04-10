"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { STRICT_TYPEWRITER } from "@/lib/strict-tokens";
import { useI18n } from "@/lib/i18n";

const TYPING_QUESTIONS: Record<string, string> = {
  en: "What are the indemnification obligations under Section 9?",
  cs: "Může zaměstnavatel dát výpověď z důvodu nadbytečnosti?",
};

export function TypingVisual({ active }: { active: boolean }) {
  const { locale } = useI18n();
  const question = TYPING_QUESTIONS[locale] ?? TYPING_QUESTIONS.en;
  const [displayText, setDisplayText] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const indexRef = useRef(0);

  const restart = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setDisplayText("");
    indexRef.current = 0;
    intervalRef.current = setInterval(() => {
      if (indexRef.current >= question.length) {
        clearInterval(intervalRef.current!);
        return;
      }
      setDisplayText(question.slice(0, indexRef.current + 1));
      indexRef.current += 1;
    }, STRICT_TYPEWRITER.hiw);
  }, [question]);

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
        background: "var(--strict-hiw-bg)",
        border: "1px solid var(--strict-hiw-border)",
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
