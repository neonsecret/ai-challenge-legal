"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { Input } from "@/components/ui/input";

const trustItems = [
  { label: "5 Jurisdictions", sub: "DIFC · EU · UK · US · AU" },
  { label: "SOC 2 Ready", sub: "Enterprise security posture" },
  { label: "Zero Model Training", sub: "Your documents stay private" },
];

interface TrustSectionProps {
  demoMode?: boolean;
  initialApiKey?: string;
}

export function TrustSection({
  demoMode = false,
  initialApiKey = "",
}: TrustSectionProps) {
  const router = useRouter();
  const [apiKey, setApiKey] = useState(initialApiKey);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <section
      id="access"
      className="py-24 px-6"
      style={{ background: "#FAFAF9" }}
    >
      <div className="max-w-3xl mx-auto">
        {/* Trust badges */}
        <div className="flex flex-wrap justify-center gap-6 mb-16">
          {trustItems.map((item, i) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="flex flex-col items-center gap-1 text-center"
            >
              <div className="size-1.5 rounded-full bg-[#C9A84C] mx-auto mb-1" />
              <span className="text-sm font-semibold text-[#1B2B4B]">
                {item.label}
              </span>
              <span className="text-xs text-[#6B7280]">{item.sub}</span>
            </motion.div>
          ))}
        </div>

        {/* API Key form */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="max-w-sm mx-auto"
        >
          <h2
            className="font-heading text-2xl font-bold text-center mb-2"
            style={{ color: "#1B2B4B" }}
          >
            Already have access?
          </h2>
          <p className="text-sm text-center text-[#6B7280] mb-6">
            {demoMode
              ? "Demo key pre-filled — click Continue to explore."
              : "Enter your NeoLex API key to continue."}
          </p>

          {demoMode && (
            <div className="mb-4 rounded-lg bg-[#C9A84C]/10 border border-[#C9A84C]/20 px-4 py-3 text-sm text-[#C9A84C] text-left">
              Demo mode active — key pre-filled below.
            </div>
          )}

          <div
            className="rounded-2xl border p-8 shadow-sm"
            style={{
              background: "#FFFFFF",
              borderColor: "#E5E2DD",
            }}
          >
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="api-key-input"
                  className="text-xs font-medium text-[#6B7280] uppercase tracking-wide"
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
                  className="font-mono text-sm bg-white text-[#111827] border-[#E5E2DD]"
                  autoComplete="off"
                  autoFocus={!demoMode}
                />
                {error && (
                  <p className="text-xs text-red-500 mt-0.5">{error}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full mt-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium transition-colors"
                style={{
                  background: submitting ? "#b8973b" : "#C9A84C",
                  color: "#FFFFFF",
                }}
              >
                {submitting ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <>
                    Continue
                    <ArrowRight className="size-4" />
                  </>
                )}
              </button>
            </form>

            <p className="text-xs text-[#6B7280] text-center mt-4">
              Need a key? Contact your NeoLex administrator.
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
