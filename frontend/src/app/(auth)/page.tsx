"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Scale,
  ArrowRight,
  Loader2,
  Globe,
  BookOpen,
  ShieldCheck,
} from "lucide-react";

export default function LandingPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);

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
          setApiKey(data.api_key);
        }
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [router]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = apiKey.trim();
    if (!trimmed) {
      setError("Please enter your API key.");
      return;
    }
    setSubmitting(true);
    localStorage.setItem("neolex_api_key", trimmed);
    router.push("/chat");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* ── Navigation ── */}
      <nav className="w-full border-b border-border bg-background/95 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center size-8 rounded-lg bg-[#C9A84C]/15 ring-1 ring-[#C9A84C]/30">
              <Scale className="size-4 text-[#C9A84C]" />
            </div>
            <span className="font-heading text-xl font-bold text-primary tracking-tight">
              NeoLex
            </span>
          </div>
          <div className="flex items-center gap-6">
            <a
              href="#features"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors hidden sm:block"
            >
              Features
            </a>
            <a
              href="#access"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors hidden sm:block"
            >
              Security
            </a>
            <a
              href="#access"
              className="inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Request Demo
            </a>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 pt-24 pb-16">
        <div className="max-w-3xl mx-auto text-center animate-fade-in-up">
          {/* Logo mark */}
          <div className="flex items-center justify-center size-20 rounded-3xl bg-[#C9A84C]/10 ring-1 ring-[#C9A84C]/25 mx-auto mb-8">
            <Scale className="size-10 text-[#C9A84C]" />
          </div>

          <h1 className="font-heading text-5xl sm:text-6xl font-bold text-primary leading-tight tracking-tight mb-5">
            Legal Research at the{" "}
            <span className="shimmer-text">Speed of Thought</span>
          </h1>

          <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-8 leading-relaxed">
            Precise, source-grounded answers from your legal documents across
            DIFC, EU, UK, and US law. Trusted by legal professionals who demand
            accuracy.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <a
              href="#access"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#C9A84C] text-white font-medium text-base hover:bg-[#b8973b] transition-colors shadow-lg shadow-[#C9A84C]/20"
            >
              Get Started
              <ArrowRight className="size-4" />
            </a>
            <a
              href="#features"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-foreground font-medium text-base hover:text-[#C9A84C] transition-colors"
            >
              Learn More
            </a>
          </div>
        </div>

        {/* ── Trust bar ── */}
        <div className="mt-16 flex flex-wrap items-center justify-center gap-8 text-sm text-muted-foreground">
          {["5 jurisdictions", "SOC 2 ready", "Source-grounded answers", "Zero data retention"].map(
            (item) => (
              <span key={item} className="flex items-center gap-2">
                <span className="size-1.5 rounded-full bg-[#C9A84C] inline-block" />
                {item}
              </span>
            )
          )}
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="bg-secondary/40 border-t border-border py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-heading text-3xl font-bold text-primary text-center mb-3">
            Built for Legal Professionals
          </h2>
          <p className="text-muted-foreground text-center mb-12 max-w-xl mx-auto">
            Every feature is designed around the precision and reliability that
            law firms require.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              {
                icon: Globe,
                title: "Multi-Jurisdiction Coverage",
                desc: "Unified research across DIFC, EU Regulation, UK Statute, and US Federal law from a single interface.",
              },
              {
                icon: BookOpen,
                title: "Source-Grounded Answers",
                desc: "Every answer cites the exact page and document. Verify instantly — no hallucinations, no guesswork.",
              },
              {
                icon: ShieldCheck,
                title: "Enterprise Security",
                desc: "SOC 2-ready architecture, data isolation by default, and full audit logging for compliance teams.",
              },
            ].map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="bg-card rounded-2xl border border-border p-6 hover:border-[#C9A84C]/40 hover:shadow-md transition-all"
              >
                <div className="flex items-center justify-center size-11 rounded-xl bg-[#C9A84C]/10 ring-1 ring-[#C9A84C]/20 mb-4">
                  <Icon className="size-5 text-[#C9A84C]" />
                </div>
                <h3 className="font-heading text-base font-semibold text-primary mb-2">
                  {title}
                </h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── API Key Section ── */}
      <section id="access" className="py-20 px-6">
        <div className="max-w-sm mx-auto text-center">
          <h2 className="font-heading text-2xl font-bold text-primary mb-2">
            Already Have Access?
          </h2>
          <p className="text-sm text-muted-foreground mb-8">
            {demoMode
              ? "Demo key pre-filled. Click \"Get Started\" to continue."
              : "Enter your NeoLex API key to continue."}
          </p>

          {demoMode && (
            <div className="mb-4 rounded-lg bg-[#C9A84C]/10 border border-[#C9A84C]/20 px-4 py-3 text-sm text-[#C9A84C] text-left">
              Demo mode active — key pre-filled below.
            </div>
          )}

          <div className="bg-card rounded-2xl border border-border p-8 shadow-sm text-left">
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="api-key-input"
                  className="text-xs font-medium text-muted-foreground uppercase tracking-wide"
                >
                  API Key
                </label>
                <Input
                  id="api-key-input"
                  type="password"
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setError(null);
                  }}
                  placeholder="nxk_..."
                  className="font-mono text-sm"
                  autoComplete="off"
                  autoFocus={!demoMode}
                />
                {error && (
                  <p className="text-xs text-destructive mt-0.5">{error}</p>
                )}
              </div>

              <Button
                type="submit"
                disabled={submitting}
                className="w-full gap-2 mt-1 bg-[#C9A84C] hover:bg-[#b8973b] text-white border-0"
              >
                {submitting ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <>
                    Get Started
                    <ArrowRight className="size-4" />
                  </>
                )}
              </Button>
            </form>

            <p className="text-xs text-muted-foreground text-center mt-4">
              Need a key? Contact your NeoLex administrator.
            </p>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-border bg-secondary/30 py-6 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Scale className="size-3.5 text-[#C9A84C]" />
            <span className="font-heading font-semibold text-foreground">NeoLex</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="#" className="hover:text-foreground transition-colors">
              Privacy Policy
            </a>
            <a href="#" className="hover:text-foreground transition-colors">
              Terms of Service
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
