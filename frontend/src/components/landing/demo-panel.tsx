"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { useTypewriter } from "./typewriter";
import { FakePdf } from "./fake-pdf";

const DEMO = {
  question:
    "What are the penalty clauses under Article 14.3 of the Supply Agreement?",
  thinkingDelay: 800,
  answer:
    "Under Article 14.3 of the Supply Agreement, the penalty clauses stipulate that:\n\n1. Late delivery incurs a penalty of 0.5% of the contract value per day of delay, capped at 10% of the total contract price.\n\n2. Material breach requires written notice and a 30-day cure period before penalties apply.\n\n3. Force majeure events as defined in Article 18 suspend penalty accrual for the duration of the qualifying event.",
  typingSpeed: 38,
  streamingSpeed: 14,
  highlightDelay: 500,
};

type Phase =
  | "idle"
  | "typing-question"
  | "thinking"
  | "streaming-answer"
  | "done";

export function DemoPanel() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [showHighlights, setShowHighlights] = useState(false);
  const answerIndexRef = useRef(0);
  const streamIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const startStreaming = useCallback(() => {
    setPhase("streaming-answer");
    answerIndexRef.current = 0;
    setStreamedAnswer("");

    // Trigger highlights after highlightDelay into streaming
    const highlightTimer = setTimeout(
      () => setShowHighlights(true),
      DEMO.highlightDelay
    );

    streamIntervalRef.current = setInterval(() => {
      const next = answerIndexRef.current + 1;
      setStreamedAnswer(DEMO.answer.slice(0, next));
      answerIndexRef.current = next;
      if (next >= DEMO.answer.length) {
        if (streamIntervalRef.current) {
          clearInterval(streamIntervalRef.current);
        }
        setPhase("done");
        // Restart cycle after 6 seconds
        restartTimerRef.current = setTimeout(() => {
          restart();
        }, 6000);
      }
    }, DEMO.streamingSpeed);

    return () => clearTimeout(highlightTimer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const restart = useCallback(() => {
    setPhase("idle");
    setStreamedAnswer("");
    setShowHighlights(false);
    answerIndexRef.current = 0;
    setTimeout(() => setPhase("typing-question"), 300);
  }, []);

  useEffect(() => {
    // Kick off after a short initial delay
    const init = setTimeout(() => setPhase("typing-question"), 600);
    return () => {
      clearTimeout(init);
      if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
      if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    };
  }, []);

  // Scroll chat to bottom as answer streams
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [streamedAnswer]);

  const { displayed: typedQuestion, done: questionDone } = useTypewriter({
    text: DEMO.question,
    speed: DEMO.typingSpeed,
    startDelay: 0,
    onComplete: () => {
      setTimeout(() => setPhase("thinking"), 100);
    },
  });

  // Only run typewriter when in typing-question phase
  const questionText = phase === "typing-question" ? typedQuestion : "";
  const showQuestionFull =
    phase === "thinking" ||
    phase === "streaming-answer" ||
    phase === "done";

  // After thinking delay, start streaming
  useEffect(() => {
    if (phase === "thinking") {
      const t = setTimeout(startStreaming, DEMO.thinkingDelay);
      return () => clearTimeout(t);
    }
  }, [phase, startStreaming]);

  const answerLines = streamedAnswer.split("\n");

  return (
    <div
      className="w-full max-w-5xl mx-auto rounded-2xl overflow-hidden"
      style={{
        background: "rgba(255,255,255,0.05)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        border: "1px solid rgba(255,255,255,0.10)",
        boxShadow:
          "0 32px 64px rgba(0,0,0,0.4), 0 0 0 1px rgba(201,168,76,0.08)",
      }}
    >
      {/* Window chrome */}
      <div
        className="flex items-center gap-2 px-4 py-3"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
      >
        <div className="flex gap-1.5">
          <div className="size-3 rounded-full bg-red-500/60" />
          <div className="size-3 rounded-full bg-yellow-500/60" />
          <div className="size-3 rounded-full bg-green-500/60" />
        </div>
        <div
          className="flex-1 text-center text-[11px] font-mono"
          style={{ color: "rgba(255,255,255,0.25)" }}
        >
          neolex.ai — Research Assistant
        </div>
      </div>

      {/* Split pane */}
      <div className="grid grid-cols-1 md:grid-cols-2 min-h-[420px]">
        {/* LEFT: Chat */}
        <div
          className="flex flex-col p-5 gap-4 overflow-hidden"
          style={{ borderRight: "1px solid rgba(255,255,255,0.08)" }}
        >
          <p
            className="text-[10px] uppercase tracking-widest font-semibold"
            style={{ color: "rgba(201,168,76,0.7)" }}
          >
            Research Query
          </p>

          {/* User bubble */}
          <AnimatePresence>
            {(phase !== "idle") && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex justify-end"
              >
                <div
                  className="max-w-[85%] rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-[12px] leading-relaxed"
                  style={{
                    background: "rgba(201,168,76,0.15)",
                    border: "1px solid rgba(201,168,76,0.25)",
                    color: "rgba(255,255,255,0.9)",
                  }}
                >
                  {showQuestionFull ? DEMO.question : questionText}
                  {phase === "typing-question" && !questionDone && (
                    <span
                      className="inline-block w-[2px] h-[13px] ml-0.5 align-middle animate-pulse"
                      style={{ backgroundColor: "#C9A84C" }}
                    />
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Thinking dots */}
          <AnimatePresence>
            {phase === "thinking" && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1.5 px-1"
              >
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: "#C9A84C" }}
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{
                      duration: 0.8,
                      repeat: Infinity,
                      delay: i * 0.18,
                    }}
                  />
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Streaming answer */}
          <AnimatePresence>
            {(phase === "streaming-answer" || phase === "done") &&
              streamedAnswer && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex-1 overflow-y-auto"
                >
                  <div
                    className="rounded-2xl rounded-tl-sm px-3.5 py-3 text-[11.5px] leading-[1.65]"
                    style={{
                      background: "rgba(27,43,75,0.5)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      color: "rgba(255,255,255,0.82)",
                    }}
                  >
                    {answerLines.map((line, i) => (
                      <span key={i}>
                        {line}
                        {i < answerLines.length - 1 && <br />}
                      </span>
                    ))}
                    {phase === "streaming-answer" && (
                      <span
                        className="inline-block w-[2px] h-[13px] ml-0.5 align-middle"
                        style={{
                          backgroundColor: "#C9A84C",
                          animation: "blink-cursor 0.7s step-end infinite",
                        }}
                      />
                    )}
                  </div>

                  {/* Source badge */}
                  <AnimatePresence>
                    {phase === "done" && (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="mt-2 inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5"
                        style={{
                          background: "rgba(201,168,76,0.12)",
                          border: "1px solid rgba(201,168,76,0.3)",
                        }}
                      >
                        <div className="size-1.5 rounded-full bg-[#C9A84C]" />
                        <span
                          className="text-[10px] font-mono"
                          style={{ color: "#C9A84C" }}
                        >
                          Article 14.3 · Page 7
                        </span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}
          </AnimatePresence>

          <div ref={chatBottomRef} />
        </div>

        {/* RIGHT: Fake PDF */}
        <div className="p-5">
          <p
            className="text-[10px] uppercase tracking-widest font-semibold mb-3"
            style={{ color: "rgba(201,168,76,0.7)" }}
          >
            Source Document
          </p>
          <div className="h-[360px]">
            <FakePdf showHighlights={showHighlights} />
          </div>
        </div>
      </div>
    </div>
  );
}
