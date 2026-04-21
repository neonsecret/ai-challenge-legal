"use client";

import {useState, useEffect, Suspense} from "react";
import {useRouter, useSearchParams} from "next/navigation";
import {useTheme} from "@/lib/theme";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_SSE_URL ?? "";

const FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

function ResetPasswordForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const token = searchParams.get("token") ?? "";
    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [validationError, setValidationError] = useState<string | null>(null);

    useEffect(() => {
        setMounted(true);
    }, []);

    // Redirect after success
    useEffect(() => {
        if (!success) return;
        const timer = setTimeout(() => router.push("/login"), 2000);
        return () => clearTimeout(timer);
    }, [success, router]);

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
        fontSize: "16px",
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
        setError(null);
        setValidationError(null);

        // Client-side validation
        if (password.length < 8) {
            setValidationError("Password must be at least 8 characters.");
            return;
        }
        if (password !== confirm) {
            setValidationError("Passwords do not match.");
            return;
        }
        if (!token) {
            setError("Missing reset token. Please use the link from your email.");
            return;
        }

        setSubmitting(true);

        try {
            const res = await fetch(`${API}/auth/reset-password`, {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                body: JSON.stringify({token, new_password: password}),
            });

            if (res.ok) {
                setSuccess(true);
            } else {
                const data = await res.json().catch(() => null);
                setError(data?.detail ?? data?.message ?? "Invalid or expired reset token. Please request a new link.");
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
                    Reset Password
                </h1>
                <p style={{
                    fontSize: "14px",
                    color: textSecondary,
                    textAlign: "center",
                    marginBottom: "28px",
                    lineHeight: 1.5
                }}>
                    Enter your new password below.
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
                        Password reset! Redirecting to login...
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

                {/* Validation Error */}
                {validationError && (
                    <div
                        style={{
                            padding: "12px 16px",
                            borderRadius: "12px",
                            background: isDark ? "rgba(251,191,36,0.10)" : "rgba(217,119,6,0.08)",
                            border: isDark ? "1px solid rgba(251,191,36,0.2)" : "1px solid rgba(217,119,6,0.15)",
                            color: isDark ? "#fbbf24" : "#92400e",
                            fontSize: "14px",
                            textAlign: "center",
                            marginBottom: "20px",
                            lineHeight: 1.5,
                        }}
                    >
                        {validationError}
                    </div>
                )}

                {!success && (
                    <form onSubmit={handleSubmit} style={{display: "flex", flexDirection: "column", gap: "16px"}}>
                        <div>
                            <label style={{
                                display: "block",
                                fontSize: "13px",
                                fontWeight: 500,
                                color: textSecondary,
                                marginBottom: "6px"
                            }}>
                                New Password
                            </label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => {
                                    setPassword(e.target.value);
                                    setValidationError(null);
                                }}
                                placeholder="Min. 8 characters"
                                autoComplete="new-password"
                                style={inputStyle}
                                onFocus={(e) => {
                                    e.currentTarget.style.borderColor = accentColor;
                                }}
                                onBlur={(e) => {
                                    e.currentTarget.style.borderColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(140,80,0,0.15)";
                                }}
                            />
                        </div>

                        <div>
                            <label style={{
                                display: "block",
                                fontSize: "13px",
                                fontWeight: 500,
                                color: textSecondary,
                                marginBottom: "6px"
                            }}>
                                Confirm Password
                            </label>
                            <input
                                type="password"
                                value={confirm}
                                onChange={(e) => {
                                    setConfirm(e.target.value);
                                    setValidationError(null);
                                }}
                                placeholder="Re-enter your password"
                                autoComplete="new-password"
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
                  Resetting...
                </span>
                            ) : (
                                "Reset Password"
                            )}
                        </button>
                    </form>
                )}

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

export default function ResetPasswordPage() {
    return (
        <Suspense
            fallback={
                <div
                    style={{
                        minHeight: "100vh",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: "#0F1623",
                        fontFamily: FONT,
                    }}
                >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                         style={{animation: "spin 1s linear infinite"}}>
                        <circle cx="12" cy="12" r="10" stroke="#C9A84C" strokeWidth="2.5" strokeDasharray="50 14"
                                strokeLinecap="round"/>
                    </svg>
                    <style>{`
            @keyframes spin {
              from { transform: rotate(0deg); }
              to { transform: rotate(360deg); }
            }
          `}</style>
                </div>
            }
        >
            <ResetPasswordForm/>
        </Suspense>
    );
}
