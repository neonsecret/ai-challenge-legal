"use client";

import {useState, useEffect} from "react";
import {useTheme} from "@/lib/theme";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_SSE_URL ?? "";

const FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

export default function ForgotPasswordPage() {
    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    const [email, setEmail] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setMounted(true);
    }, []);

    const isDark = !mounted || resolvedTheme === "dark";

    const glassCard: React.CSSProperties = {
        background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,250,235,0.22)",
        backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: "20px",
        boxShadow: isDark
            ? "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 32px rgba(0,0,0,0.30)"
            : "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    const accentColor = isDark ? "#C9A84C" : "#5c2e08";
    const textPrimary = isDark ? "rgba(255,255,255,0.92)" : "rgba(60,30,0,0.9)";
    const textSecondary = isDark ? "rgba(255,255,255,0.48)" : "rgba(80,40,0,0.55)";
    const bgPage = isDark
        ? "#0F1623"
        : "linear-gradient(145deg, #dfc090 0%, #e8d4b8 45%, #dbb870 100%)";

    const inputStyle: React.CSSProperties = {
        width: "100%",
        padding: "12px 16px",
        borderRadius: "12px",
        border: isDark ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(140,80,0,0.15)",
        background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.35)",
        color: textPrimary,
        fontSize: "15px",
        fontFamily: FONT,
        outline: "none",
        transition: "border-color 0.2s",
    };

    const buttonStyle: React.CSSProperties = {
        width: "100%",
        padding: "12px 0",
        borderRadius: "12px",
        border: "none",
        background: isDark
            ? "linear-gradient(135deg, rgba(201,168,76,0.25), rgba(201,168,76,0.15))"
            : "linear-gradient(135deg, rgba(92,46,8,0.18), rgba(92,46,8,0.10))",
        color: accentColor,
        fontSize: "15px",
        fontWeight: 600,
        fontFamily: FONT,
        cursor: submitting ? "wait" : "pointer",
        opacity: submitting ? 0.6 : 1,
        transition: "opacity 0.2s, transform 0.15s",
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const trimmed = email.trim();
        if (!trimmed) {
            setError("Please enter your email address.");
            return;
        }

        setSubmitting(true);
        setError(null);
        setSuccess(false);

        try {
            const res = await fetch(`${API}/auth/forgot-password`, {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                body: JSON.stringify({email: trimmed}),
            });

            if (res.ok) {
                setSuccess(true);
            } else {
                const data = await res.json().catch(() => null);
                setError(data?.detail ?? data?.message ?? "Something went wrong. Please try again.");
            }
        } catch {
            setError("Cannot reach the server. Please try again.");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div
            style={{
                minHeight: "100vh",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "24px",
                fontFamily: FONT,
                background: bgPage,
            }}
        >
            {/* Logo */}
            <div style={{display: "flex", alignItems: "center", gap: "10px", marginBottom: "32px"}}>
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "32px",
                        height: "32px",
                        borderRadius: "10px",
                        background: isDark ? "rgba(201,168,76,0.12)" : "rgba(92,46,8,0.08)",
                        border: isDark ? "1px solid rgba(201,168,76,0.25)" : "1px solid rgba(92,46,8,0.12)",
                    }}
                >
                    <svg width="16" height="16" viewBox="0 0 14 14" fill="none">
                        <path
                            d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
                            stroke={accentColor}
                            strokeWidth="1.2"
                            strokeLinejoin="round"
                            fill={isDark ? "rgba(201,168,76,0.15)" : "rgba(92,46,8,0.08)"}
                        />
                    </svg>
                </div>
                <span style={{fontSize: "20px", fontWeight: 700, letterSpacing: "-0.02em", color: textPrimary}}>
          Vitreon Legal
        </span>
            </div>

            {/* Glass Card */}
            <div style={{...glassCard, width: "100%", maxWidth: "420px", padding: "36px 32px"}}>
                <h1 style={{
                    fontSize: "22px",
                    fontWeight: 700,
                    color: textPrimary,
                    marginBottom: "8px",
                    textAlign: "center"
                }}>
                    Forgot Password
                </h1>
                <p style={{
                    fontSize: "14px",
                    color: textSecondary,
                    textAlign: "center",
                    marginBottom: "28px",
                    lineHeight: 1.5
                }}>
                    Enter your email and we&apos;ll send you a reset link.
                </p>

                {/* Success Message */}
                {success && (
                    <div
                        style={{
                            padding: "12px 16px",
                            borderRadius: "12px",
                            background: isDark ? "rgba(34,197,94,0.12)" : "rgba(34,160,74,0.10)",
                            border: isDark ? "1px solid rgba(34,197,94,0.25)" : "1px solid rgba(34,160,74,0.2)",
                            color: isDark ? "#4ade80" : "#15803d",
                            fontSize: "14px",
                            textAlign: "center",
                            marginBottom: "20px",
                            lineHeight: 1.5,
                        }}
                    >
                        Check your email for a reset link.
                    </div>
                )}

                {/* Error Message */}
                {error && (
                    <div
                        style={{
                            padding: "12px 16px",
                            borderRadius: "12px",
                            background: isDark ? "rgba(239,68,68,0.10)" : "rgba(220,38,38,0.08)",
                            border: isDark ? "1px solid rgba(239,68,68,0.2)" : "1px solid rgba(220,38,38,0.15)",
                            color: isDark ? "#f87171" : "#b91c1c",
                            fontSize: "14px",
                            textAlign: "center",
                            marginBottom: "20px",
                            lineHeight: 1.5,
                        }}
                    >
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} style={{display: "flex", flexDirection: "column", gap: "16px"}}>
                    <div>
                        <label style={{
                            display: "block",
                            fontSize: "13px",
                            fontWeight: 500,
                            color: textSecondary,
                            marginBottom: "6px"
                        }}>
                            Email Address
                        </label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="you@example.com"
                            autoComplete="email"
                            style={inputStyle}
                            onFocus={(e) => {
                                e.currentTarget.style.borderColor = accentColor;
                            }}
                            onBlur={(e) => {
                                e.currentTarget.style.borderColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(140,80,0,0.15)";
                            }}
                        />
                    </div>

                    <button type="submit" disabled={submitting} style={buttonStyle}>
                        {submitting ? (
                            <span style={{display: "inline-flex", alignItems: "center", gap: "8px"}}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                     style={{animation: "spin 1s linear infinite"}}>
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" strokeDasharray="50 14"
                          strokeLinecap="round"/>
                </svg>
                Sending...
              </span>
                        ) : (
                            "Send Reset Link"
                        )}
                    </button>
                </form>

                <div style={{textAlign: "center", marginTop: "24px"}}>
                    <Link
                        href="/login"
                        style={{
                            fontSize: "14px",
                            color: accentColor,
                            textDecoration: "none",
                            fontWeight: 500,
                            transition: "opacity 0.2s",
                        }}
                        onMouseEnter={(e) => {
                            (e.target as HTMLElement).style.opacity = "0.7";
                        }}
                        onMouseLeave={(e) => {
                            (e.target as HTMLElement).style.opacity = "1";
                        }}
                    >
                        Back to login
                    </Link>
                </div>
            </div>

            {/* Spinner keyframe */}
            <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
        </div>
    );
}
