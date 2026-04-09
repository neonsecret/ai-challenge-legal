"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { STRICT_HIW } from "@/lib/strict-tokens";

const SCAN_ITEMS = [
  "Scanning 4,800+ documents",
  "Located Article 58 §2",
  "Ranked 5 passages",
] as const;

interface ScanItemState {
  visible: boolean;
  done: boolean;
}

export function ScanningVisual({ active }: { active: boolean }) {
  const [items, setItems] = useState<ScanItemState[]>([
    { visible: false, done: false },
    { visible: false, done: false },
    { visible: false, done: false },
  ]);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const resetAndStart = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    setItems([
      { visible: false, done: false },
      { visible: false, done: false },
      { visible: false, done: false },
    ]);

    SCAN_ITEMS.forEach((_, idx) => {
      const appearTimer = setTimeout(
        () => {
          setItems((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], visible: true };
            return next;
          });
        },
        idx * STRICT_HIW.scanStagger
      );
      const doneTimer = setTimeout(
        () => {
          setItems((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], done: true };
            return next;
          });
        },
        idx * STRICT_HIW.scanStagger + STRICT_HIW.scanFillDuration
      );
      timersRef.current.push(appearTimer, doneTimer);
    });
  }, []);

  useEffect(() => {
    if (active) {
      resetAndStart();
    } else {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    }
    return () => {
      timersRef.current.forEach(clearTimeout);
    };
  }, [active, resetAndStart]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
      {SCAN_ITEMS.map((label, idx) => {
        const item = items[idx];
        return (
          <div
            key={label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "12px",
              opacity: item.visible ? 1 : 0,
              transform: item.visible ? "translateX(0)" : "translateX(-8px)",
              transition: "opacity 0.4s ease, transform 0.4s ease",
            }}
          >
            {/* Pulsing gold dot */}
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "var(--strict-hiw-dot)",
                flexShrink: 0,
                animation: "hiwScanPulse 1.2s ease-in-out infinite",
              }}
            />
            {/* Progress line */}
            <div
              style={{
                flex: 1,
                height: "2px",
                background: "var(--strict-hiw-progress-track)",
                borderRadius: "1px",
                position: "relative",
                overflow: "hidden",
              }}
            >
              {item.visible && (
                <div
                  key={`fill-${idx}-${active}`}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    height: "100%",
                    width: "100%",
                    background: "var(--strict-hiw-scan-fill)",
                    borderRadius: "1px",
                    transformOrigin: "left",
                    willChange: "transform",
                    animation: `hiwScanFill ${STRICT_HIW.scanFillDuration}ms ease forwards`,
                  }}
                />
              )}
            </div>
            {/* Label */}
            <span
              style={{
                color: "rgba(255,255,255,0.4)",
                fontSize: "10.5px",
                fontFamily: "'SF Mono', Monaco, 'Cascadia Code', monospace",
                minWidth: "120px",
              }}
            >
              {label}
            </span>
            {/* Checkmark */}
            <span
              style={{
                color: "var(--strict-gold-text)",
                fontSize: "11px",
                opacity: item.done ? 1 : 0,
                transition: "opacity 0.3s ease",
              }}
            >
              ✓
            </span>
          </div>
        );
      })}
    </div>
  );
}
