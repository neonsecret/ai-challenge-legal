"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Scale, ArrowRight, Loader2 } from "lucide-react";

export default function LandingPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);

  // On mount: check for existing key or demo mode
  useEffect(() => {
    const existing = localStorage.getItem("neolex_api_key");
    if (existing) {
      router.replace("/chat");
      return;
    }

    // Check backend for demo mode config
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
        // Backend not reachable — show normal landing
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
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-16">
      {/* Logo mark */}
      <div className="flex items-center justify-center size-16 rounded-2xl bg-[#d4af37]/15 mb-6 ring-1 ring-[#d4af37]/30">
        <Scale className="size-8 text-[#d4af37]" />
      </div>

      {/* Heading */}
      <h1 className="text-3xl font-bold tracking-tight text-foreground mb-1">
        NeoLex
      </h1>
      <p className="text-muted-foreground text-base mb-2">
        Your AI Legal Counsel
      </p>

      {demoMode && (
        <Badge className="mb-8 bg-[#d4af37]/20 text-[#d4af37] border-[#d4af37]/30 hover:bg-[#d4af37]/20">
          Demo Mode
        </Badge>
      )}

      {/* Login card */}
      <div className="w-full max-w-sm bg-card rounded-2xl border border-border p-8 shadow-lg mt-4">
        {demoMode ? (
          <div className="mb-4 rounded-lg bg-[#d4af37]/10 border border-[#d4af37]/20 px-4 py-3 text-sm text-[#d4af37]">
            Demo key pre-filled. Click "Get Started" to continue.
          </div>
        ) : (
          <p className="text-sm text-muted-foreground mb-4">
            Enter your NeoLex API key to get started.
          </p>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
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
            className="w-full gap-2 mt-1"
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
  );
}
