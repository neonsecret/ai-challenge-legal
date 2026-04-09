"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { STRICT_TYPEWRITER, STRICT_SOURCES } from "@/lib/strict-tokens";
import { V3_SPRING, V3_FADE_UP } from "@/lib/v3-motion";
import { useIsMobile } from "@/hooks/use-mobile";

// ─── Static content constants ─────────────────────────────────────────────────

const QUESTION =
  "What is the notice period for termination of employment under DIFC law?";

/**
 * Answer HTML source. Citations are wrapped as <sup>N</sup> so the typewriter
 * appends entire tags at once (per the task spec).
 */
const ANSWER_HTML =
  "The notice period under DIFC Employment Law No. 4 of 2005 varies based on the length of continuous service<sup>1</sup>. For employees with less than one year of service, the minimum notice period is seven days. For those with one to five years, the period extends to thirty days<sup>2</sup>.<br><br>In cases where the employment contract specifies a longer notice period, the contractual term prevails<sup>3</sup>.";

const SOURCES = [
  "DIFC Law No. 4 of 2005, Art. 58 — Notice Requirements",
  "DIFC Employment Regulations 2019, Schedule 2",
  "DIFC Court of First Instance, Case 024/2021",
] as const;

// ─── Typewriter helpers ───────────────────────────────────────────────────────

/**
 * Build the next "chunk" to append from position `pos` in `src`.
 * - If the char at `pos` is `<`, scan ahead to the closing `>` and return the
 *   full tag (plus one trailing char after `</...>` if present).
 * - `\n` becomes `<br>`.
 * - Otherwise returns the single character.
 *
 * Returns `{ chunk, next }` where `next` is the new cursor position.
 */
function nextChunk(src: string, pos: number): { chunk: string; next: number } {
  if (pos >= src.length) return { chunk: "", next: pos };

  const ch = src[pos];

  if (ch === "<") {
    // Scan to closing >
    const closeIdx = src.indexOf(">", pos);
    if (closeIdx === -1) {
      // Malformed — emit char by char
      return { chunk: ch, next: pos + 1 };
    }
    const tag = src.slice(pos, closeIdx + 1);
    let next = closeIdx + 1;

    // After a closing tag, also grab the very next char so the cursor advances
    // past it without extra flicker.
    if (tag.startsWith("</") && next < src.length && src[next] !== "<") {
      const extra = src[next] === "\n" ? "<br>" : src[next];
      return { chunk: tag + extra, next: next + 1 };
    }
    return { chunk: tag, next };
  }

  if (ch === "\n") return { chunk: "<br>", next: pos + 1 };

  return { chunk: ch, next: pos + 1 };
}

// ─── Component ────────────────────────────────────────────────────────────────

export function StrictPreview() {
  const isMobile = useIsMobile();

  // Intersection visibility
  const sectionRef = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(false);

  // Animation phase tracking
  const [questionVisible, setQuestionVisible] = useState(false);
  const [typingDone, setTypingDone] = useState(false);
  const [sourcesVisible, setSourcesVisible] = useState(false);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  // Typewriter state
  const bufferRef = useRef("");
  const posRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [, setTick] = useState(0); // forces re-render on each char

  // ── IntersectionObserver: trigger at 30% threshold ──────────────────────────
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !inView) {
          setInView(true);
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [inView]);

  // ── Choreography: kick off sub-animations once in view ──────────────────────
  useEffect(() => {
    if (!inView) return;

    // Step 2 — question fades in at 300 ms
    const t1 = setTimeout(() => setQuestionVisible(true), 300);

    // Step 3 — typewriter starts at 900 ms
    const t2 = setTimeout(() => {
      bufferRef.current = "";
      posRef.current = 0;

      const tick = () => {
        if (posRef.current >= ANSWER_HTML.length) {
          setTypingDone(true);
          return;
        }
        const { chunk, next } = nextChunk(ANSWER_HTML, posRef.current);
        bufferRef.current += chunk;
        posRef.current = next;
        setTick((n) => n + 1);
        timerRef.current = setTimeout(tick, STRICT_TYPEWRITER.preview);
      };

      timerRef.current = setTimeout(tick, STRICT_TYPEWRITER.preview);
    }, 900);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [inView]);

  // ── Sources reveal after typing completes ───────────────────────────────────
  useEffect(() => {
    if (typingDone) {
      setSourcesVisible(true);
      // Auto-expand sources on mobile when they appear
      if (isMobile) setSourcesExpanded(true);
    }
  }, [typingDone, isMobile]);

  return (
    <section
      ref={sectionRef}
      className="mx-auto"
      style={{
        padding: isMobile ? "40px 16px" : "56px 32px",
        maxWidth: "880px",
      }}
    >
      {/* Section header */}
      <p
        className="text-center mb-2"
        style={{
          color: "var(--strict-source-label)",
          fontSize: 10,
          letterSpacing: "1.5px",
          textTransform: "uppercase",
        }}
      >
        PREVIEW
      </p>
      <h2
        className="text-center mb-8"
        style={{
          fontFamily: "Georgia, serif",
          fontSize: isMobile ? 18 : 22,
          fontWeight: "normal",
          color: "var(--strict-text-primary)",
          opacity: 0.75,
        }}
      >
        The research experience
      </h2>

      {/* Step 1 — glass pane fades up on inView */}
      <motion.div
        variants={V3_FADE_UP}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        style={{
          background: "var(--strict-glass-bg)",
          backdropFilter: "var(--strict-glass-blur)",
          border: "1px solid var(--strict-glass-border)",
          borderRadius: isMobile ? 12 : 16,
          boxShadow: "var(--strict-glass-shadow)",
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          overflow: "hidden",
          minHeight: isMobile ? "auto" : 320,
        }}
      >
        {/* Sidebar rail — desktop only */}
        {!isMobile && (
          <div
            style={{
              width: 44,
              background: "var(--strict-glass-recessed)",
              borderRight: "1px solid var(--strict-gold-border)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              paddingTop: 14,
              gap: 10,
              flexShrink: 0,
            }}
          >
            {/* Logo circle */}
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                border: "1px solid var(--strict-gold-border-active)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 8,
                color: "var(--strict-gold-text)",
              }}
            >
              V
            </div>
            {/* Icon placeholders */}
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: 4,
                  background: "var(--strict-glass-bg)",
                }}
              />
            ))}
          </div>
        )}

        {/* Reading area — flex-1 */}
        <div
          style={{
            flex: 1,
            padding: isMobile ? "16px 14px" : "18px 22px",
            display: "flex",
            flexDirection: "column",
            minWidth: 0,
          }}
        >
          {/* Step 2 — question fades in */}
          <p
            style={{
              fontFamily: "Georgia, serif",
              fontSize: isMobile ? 11 : 12,
              fontStyle: "italic",
              color: "var(--strict-text-question)",
              marginBottom: 14,
              paddingBottom: 10,
              borderBottom: "1px solid var(--strict-gold-border)",
              opacity: questionVisible ? 1 : 0,
              transform: questionVisible ? "translateY(0)" : "translateY(8px)",
              transition: "opacity 0.5s ease, transform 0.5s ease",
            }}
          >
            {QUESTION}
          </p>

          {/* Step 3 — typewriter answer */}
          <div
            dangerouslySetInnerHTML={{ __html: bufferRef.current }}
            style={{
              fontFamily: "Georgia, serif",
              fontSize: isMobile ? 12 : 12.5,
              color: "var(--strict-text-body)",
              lineHeight: 1.8,
              letterSpacing: "0.01em",
              flex: 1,
            }}
          />

          {/* Input bar */}
          <div
            style={{
              marginTop: "auto",
              paddingTop: 14,
              borderTop: "1px solid var(--strict-gold-border)",
              display: "flex",
              alignItems: "center",
            }}
          >
            <span
              style={{
                fontFamily: "Georgia, serif",
                fontSize: 11,
                color: "var(--strict-text-ghost)",
                flex: 1,
              }}
            >
              Continue your research...
            </span>
            <span
              style={{
                fontSize: 10,
                color: "var(--strict-gold-text)",
                opacity: 0.4,
              }}
            >
              ↵
            </span>
          </div>
        </div>

        {/* Source margin — desktop: right column; mobile: collapsible section below */}
        {isMobile ? (
          <div
            style={{
              borderTop: "1px solid var(--strict-gold-border)",
            }}
          >
            {/* Collapsible toggle */}
            <button
              type="button"
              onClick={() => setSourcesExpanded((v) => !v)}
              style={{
                width: "100%",
                padding: "10px 14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "var(--strict-glass-recessed)",
                border: "none",
                cursor: "pointer",
                minHeight: "44px",
              }}
            >
              <span
                style={{
                  color: "var(--strict-gold-text)",
                  fontSize: 8,
                  letterSpacing: "0.5px",
                  textTransform: "uppercase",
                  opacity: 0.6,
                }}
              >
                SOURCES ({SOURCES.length})
              </span>
              <span
                style={{
                  color: "var(--strict-gold-text)",
                  fontSize: 10,
                  opacity: 0.5,
                  transition: "transform 0.2s ease",
                  transform: sourcesExpanded ? "rotate(180deg)" : "rotate(0deg)",
                }}
              >
                ▾
              </span>
            </button>

            {/* Expandable source list */}
            <div
              style={{
                background: "var(--strict-glass-recessed)",
                overflow: "hidden",
                maxHeight: sourcesExpanded ? "400px" : "0",
                transition: "max-height 0.35s ease",
                padding: sourcesExpanded ? "12px 14px 14px" : "0 14px",
              }}
            >
              {SOURCES.map((src, idx) => (
                <div key={idx}>
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: 8 }}
                    animate={
                      sourcesVisible && sourcesExpanded
                        ? { opacity: 1, scale: 1, y: 0 }
                        : { opacity: 0, scale: 0.95, y: 8 }
                    }
                    transition={{
                      ...V3_SPRING.standard,
                      delay:
                        sourcesVisible && sourcesExpanded
                          ? idx * (STRICT_SOURCES.stagger / 1000)
                          : 0,
                    }}
                  >
                    <p
                      style={{
                        color: "var(--strict-gold-text)",
                        fontSize: 9,
                        marginBottom: 2,
                        opacity: 0.6,
                      }}
                    >
                      {idx + 1}
                    </p>
                    <p
                      style={{
                        color: "var(--strict-source-text)",
                        fontSize: 10,
                        lineHeight: 1.5,
                      }}
                    >
                      {src}
                    </p>
                  </motion.div>
                  {idx < SOURCES.length - 1 && (
                    <div
                      style={{
                        height: 1,
                        background: "var(--strict-gold-sep)",
                        margin: "10px 0",
                      }}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* Desktop source margin */
          <div
            style={{
              width: 160,
              background: "var(--strict-glass-recessed)",
              borderLeft: "1px solid var(--strict-gold-border)",
              padding: "18px 12px",
              flexShrink: 0,
            }}
          >
            <p
              style={{
                color: "var(--strict-gold-text)",
                fontSize: 8,
                letterSpacing: "0.5px",
                textTransform: "uppercase",
                marginBottom: 12,
                opacity: 0.6,
              }}
            >
              SOURCES
            </p>

            {/* Step 4 — sources reveal as staggered glass tiles */}
            {SOURCES.map((src, idx) => (
              <div key={idx}>
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, x: 12 }}
                  animate={
                    sourcesVisible
                      ? { opacity: 1, scale: 1, x: 0 }
                      : { opacity: 0, scale: 0.95, x: 12 }
                  }
                  transition={{
                    ...V3_SPRING.standard,
                    delay: sourcesVisible
                      ? idx * (STRICT_SOURCES.stagger / 1000)
                      : 0,
                  }}
                >
                  <p
                    style={{
                      color: "var(--strict-gold-text)",
                      fontSize: 9,
                      marginBottom: 2,
                      opacity: 0.6,
                    }}
                  >
                    {idx + 1}
                  </p>
                  <p
                    style={{
                      color: "var(--strict-source-text)",
                      fontSize: 9,
                      lineHeight: 1.4,
                    }}
                  >
                    {src}
                  </p>
                </motion.div>

                {/* Gold gradient fade separator (not after last item) */}
                {idx < SOURCES.length - 1 && (
                  <div
                    style={{
                      height: 1,
                      background: "var(--strict-gold-sep)",
                      margin: "10px 0",
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </section>
  );
}
