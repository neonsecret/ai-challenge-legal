"use client";

import { motion } from "motion/react";
import { V3_SPRING } from "@/lib/v3-motion";
import { STRICT_HIW } from "@/lib/strict-tokens";

export interface StepItemProps {
  num: string;
  title: string;
  sub: string;
  active: boolean;
  index: number;
  onClick: () => void;
}

export function StepItem({ num, title, sub, active, index, onClick }: StepItemProps) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        ...V3_SPRING.gentle,
        delay: STRICT_HIW.stepBaseDelay + index * STRICT_HIW.stepStagger,
      }}
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
          background: "var(--strict-hiw-progress-track)",
          overflow: "hidden",
        }}
      >
        {/* Fill — re-mounts when step becomes active to restart animation */}
        {active && (
          <div
            key={`progress-${index}-${active}`}
            style={{
              width: "2px",
              height: "100%",
              borderRadius: "1px",
              background: "var(--strict-hiw-progress-fill)",
              transformOrigin: "top",
              willChange: "transform",
              animation: `hiwProgressFill ${STRICT_HIW.stepDuration}ms linear forwards`,
            }}
          />
        )}
      </div>

      {/* Step number */}
      <span
        style={{
          color: active ? "var(--strict-step-num-active)" : "var(--strict-step-num-inactive)",
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
            color: active ? "var(--strict-step-title-active)" : "var(--strict-step-title-inactive)",
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
            color: active ? "var(--strict-step-sub-active)" : "var(--strict-step-sub-inactive)",
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
