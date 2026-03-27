"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { Loader2 } from "lucide-react";
import { DemoPanel } from "@/components/landing/demo-panel";
import { ValuePillars } from "@/components/landing/value-pillars";
import { HowItWorks } from "@/components/landing/how-it-works";
import { TrustSection } from "@/components/landing/trust-section";

export default function LandingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoMode] = useState(false);
  const [demoKey, setDemoKey] = useState("");

  useEffect(() => {
    const existing = localStorage.getItem("neolex_api_key");
    if (existing) {
      router.replace("/chat");
      return;
    }

    const apiUrl =
      localStorage.getItem("neolex_backend_url") ?? "http://localhost:8000";
    fetch(`${apiUrl}/api/v1/demo/config`)
      .then((r) => r.json())
      .then((data) => {
        if (data.demo_mode && data.api_key) {
          setDemoMode(true);
          setDemoKey(data.api_key);
        }
        setLoading(false);
        window.scrollTo(0, 0);
      })
      .catch(() => {
        setLoading(false);
        window.scrollTo(0, 0);
      });
  }, [router]);

  if (loading) {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        style={{ background: "#0F1623" }}
      >
        <Loader2 className="size-6 animate-spin" style={{ color: "#C9A84C" }} />
      </div>
    );
  }

  return (
    // Force dark mode context for the entire landing page
    <div className="dark">
      {/* ================================================================
          SECTION 1: HERO
      ================================================================ */}
      <section
        className="hero-aurora relative min-h-screen flex flex-col overflow-hidden"
        style={{ color: "rgba(255,255,255,0.9)" }}
      >
        {/* Nav */}
        <nav
          className="sticky top-0 z-50 w-full"
          style={{
            background: "rgba(15,22,35,0.85)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-2.5">
              <div
                className="flex items-center justify-center size-7 rounded-lg"
                style={{
                  background: "rgba(201,168,76,0.12)",
                  border: "1px solid rgba(201,168,76,0.25)",
                }}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                >
                  <path
                    d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
                    stroke="#C9A84C"
                    strokeWidth="1.2"
                    strokeLinejoin="round"
                    fill="rgba(201,168,76,0.15)"
                  />
                </svg>
              </div>
              <span
                className="font-heading text-lg font-bold tracking-tight"
                style={{ color: "rgba(255,255,255,0.95)" }}
              >
                NeoLex
              </span>
            </div>

            {/* Right nav */}
            <a
              href="#access"
              className="inline-flex items-center gap-1.5 text-sm font-medium px-4 py-1.5 rounded-full transition-all"
              style={{
                background: "rgba(201,168,76,0.12)",
                border: "1px solid rgba(201,168,76,0.3)",
                color: "#C9A84C",
              }}
            >
              Request Access
            </a>
          </div>
        </nav>

        {/* Hero content */}
        <div className="flex-1 flex flex-col items-center justify-center px-6 pt-12 pb-8">
          {/* Micro-text */}
          <motion.p
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-5"
            style={{ color: "rgba(201,168,76,0.75)" }}
          >
            AI Legal Counsel
          </motion.p>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.18 }}
            className="font-heading text-center font-bold mb-5 max-w-3xl"
            style={{
              fontSize: "clamp(2.2rem, 5vw, 4.5rem)",
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
              color: "rgba(255,255,255,0.95)",
            }}
          >
            Legal Research at the{" "}
            <span
              style={{
                background:
                  "linear-gradient(90deg, #C9A84C 0%, #e8cc7a 50%, #C9A84C 100%)",
                backgroundSize: "200% auto",
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                WebkitTextFillColor: "transparent",
                animation: "shimmer 3s linear infinite",
              }}
            >
              Speed of Thought
            </span>
          </motion.h1>

          {/* Sub-headline */}
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.28 }}
            className="text-base text-center mb-10 max-w-xl"
            style={{ color: "rgba(255,255,255,0.48)", lineHeight: 1.6 }}
          >
            Precise, source-grounded answers from your legal documents.
            <br className="hidden sm:block" />
            Every answer cites the exact page and clause.
          </motion.p>

          {/* Demo panel */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.38 }}
            className="w-full max-w-5xl"
          >
            <DemoPanel />
          </motion.div>
        </div>

        {/* Scroll hint */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2, duration: 0.8 }}
          className="flex justify-center pb-8"
        >
          <a
            href="#why"
            className="flex flex-col items-center gap-1.5 text-[10px] uppercase tracking-widest"
            style={{ color: "rgba(255,255,255,0.25)" }}
          >
            scroll to explore
            <svg
              width="10"
              height="14"
              viewBox="0 0 10 14"
              fill="none"
              style={{ animation: "fade-in-up 1.2s ease-out infinite alternate" }}
            >
              <path
                d="M5 1v12M1 9l4 4 4-4"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>
        </motion.div>

        {/* Aurora orbs for depth */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden"
          style={{ zIndex: 0 }}
        >
          <div
            className="absolute rounded-full"
            style={{
              width: "600px",
              height: "600px",
              top: "-200px",
              left: "50%",
              transform: "translateX(-50%)",
              background:
                "radial-gradient(circle, rgba(201,168,76,0.06) 0%, transparent 70%)",
              filter: "blur(40px)",
            }}
          />
          <div
            className="absolute rounded-full"
            style={{
              width: "400px",
              height: "400px",
              bottom: "-100px",
              right: "10%",
              background:
                "radial-gradient(circle, rgba(27,43,75,0.8) 0%, transparent 70%)",
              filter: "blur(60px)",
            }}
          />
        </div>
      </section>

      {/* ================================================================
          SECTION 2: VALUE PILLARS
      ================================================================ */}
      <div id="why">
        <ValuePillars />
      </div>

      {/* ================================================================
          SECTION 3: HOW IT WORKS
      ================================================================ */}
      <HowItWorks />

      {/* ================================================================
          SECTION 4: TRUST + API KEY
      ================================================================ */}
      <TrustSection demoMode={demoMode} initialApiKey={demoKey} />

      {/* ================================================================
          SECTION 5: FOOTER
      ================================================================ */}
      <footer
        className="py-8 px-6"
        style={{
          background: "#0A1120",
          borderTop: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div
              className="flex items-center justify-center size-5 rounded"
              style={{ background: "rgba(201,168,76,0.12)" }}
            >
              <svg width="10" height="10" viewBox="0 0 14 14" fill="none">
                <path
                  d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
                  stroke="#C9A84C"
                  strokeWidth="1.2"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <span
              className="font-heading text-sm font-semibold"
              style={{ color: "rgba(255,255,255,0.6)" }}
            >
              NeoLex
            </span>
          </div>
          <p
            className="text-[11px]"
            style={{ color: "rgba(255,255,255,0.28)" }}
          >
            2026 NeoLex
            <span className="mx-2" style={{ color: "rgba(255,255,255,0.15)" }}>
              ·
            </span>
            <a href="#" className="hover:text-white/50 transition-colors">
              Privacy
            </a>
            <span className="mx-2" style={{ color: "rgba(255,255,255,0.15)" }}>
              ·
            </span>
            <a href="#" className="hover:text-white/50 transition-colors">
              Terms
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
