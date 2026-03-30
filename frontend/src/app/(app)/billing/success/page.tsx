"use client";

import {Suspense, useState, useEffect, useCallback} from "react";
import {useRouter, useSearchParams} from "next/navigation";
import {useTheme} from "next-themes";
import {CheckCircle} from "lucide-react";

const fontStack =
    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

const REDIRECT_SECONDS = 5;

export default function BillingSuccessPage() {
    return (
        <Suspense>
            <BillingSuccessContent />
        </Suspense>
    );
}

function BillingSuccessContent() {
    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    const [countdown, setCountdown] = useState(REDIRECT_SECONDS);
    const [planName, setPlanName] = useState<string | null>(null);
    const router = useRouter();
    const searchParams = useSearchParams();

    useEffect(() => {
        setMounted(true);
    }, []);

    // Sync subscription from Stripe (fallback if webhook hasn't arrived yet),
    // then fetch billing status to display the correct plan name.
    useEffect(() => {
        const sessionId = searchParams.get("session_id");
        if (!sessionId) return;

        const apiBase = process.env.NEXT_PUBLIC_SSE_URL ?? "";

        // First sync subscription from Stripe, then get billing status
        fetch(`${apiBase}/stripe/sync-subscription`, {
            method: "POST",
            credentials: "include",
            headers: {"X-Requested-With": "XMLHttpRequest"},
        })
            .catch(() => {
                // Sync failed — the webhook may have already handled it
            })
            .finally(() => {
                fetch(`${apiBase}/stripe/billing-status`, {credentials: "include"})
                    .then((r) => r.json())
                    .then((data) => {
                        if (data.plan && data.plan !== "free") {
                            setPlanName(
                                data.plan.charAt(0).toUpperCase() + data.plan.slice(1),
                            );
                        }
                    })
                    .catch(() => {
                        // Ignore — we'll show a generic message
                    });
            });
    }, [searchParams]);

    const isDark = mounted && resolvedTheme === "dark";

    const goToChat = useCallback(() => {
        router.push("/chat");
    }, [router]);

    // Countdown timer with actual decrementing display
    useEffect(() => {
        if (countdown <= 0) {
            goToChat();
            return;
        }
        const timer = setInterval(() => {
            setCountdown((prev) => prev - 1);
        }, 1000);
        return () => clearInterval(timer);
    }, [countdown, goToChat]);

    const glassCard: React.CSSProperties = {
        background: isDark
            ? "rgba(255,255,255,0.06)"
            : "rgba(255,250,235,0.22)",
        backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        border: isDark
            ? "0.5px solid rgba(255,255,255,0.12)"
            : "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: "20px",
        boxShadow: isDark
            ? "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 32px rgba(0,0,0,0.30)"
            : "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    return (
        <div
            style={{
                padding: "24px 16px 120px",
                maxWidth: "640px",
                margin: "0 auto",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: "60vh",
            }}
        >
            <div
                style={{
                    ...glassCard,
                    width: "100%",
                    padding: "48px 32px",
                    textAlign: "center",
                }}
            >
                {/* Success icon */}
                <div
                    style={{
                        display: "flex",
                        justifyContent: "center",
                        marginBottom: "20px",
                    }}
                >
                    <div
                        style={{
                            width: "64px",
                            height: "64px",
                            borderRadius: "50%",
                            background: isDark
                                ? "rgba(74,222,128,0.12)"
                                : "rgba(22,163,74,0.10)",
                            border: isDark
                                ? "0.5px solid rgba(74,222,128,0.25)"
                                : "0.5px solid rgba(22,163,74,0.20)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        <CheckCircle
                            size={32}
                            style={{color: isDark ? "#4ade80" : "#16a34a"}}
                        />
                    </div>
                </div>

                {/* Heading */}
                <h1
                    style={{
                        fontFamily: "var(--font-heading), Georgia, serif",
                        fontSize: "1.5rem",
                        fontWeight: 700,
                        color: isDark ? "rgba(255,255,255,0.90)" : "#1e1208",
                        margin: "0 0 8px 0",
                    }}
                >
                    Payment Successful
                </h1>

                {/* Subtext */}
                <p
                    style={{
                        color: isDark
                            ? "rgba(255,255,255,0.55)"
                            : "rgba(46,31,8,0.65)",
                        fontSize: "14px",
                        fontFamily: fontStack,
                        margin: "0 0 32px 0",
                        lineHeight: 1.5,
                    }}
                >
                    Your Vitreon Legal {planName ?? ""}  subscription is now active.
                </p>

                {/* Go to Chat button */}
                <button
                    onClick={() => router.push("/chat")}
                    style={{
                        background: isDark
                            ? "linear-gradient(135deg, #C9A84C, #e8cc7a)"
                            : "#5c2e08",
                        color: isDark ? "#0F1623" : "#fff8ee",
                        borderRadius: "10px",
                        padding: "10px 28px",
                        fontSize: "13px",
                        fontWeight: 600,
                        fontFamily: fontStack,
                        boxShadow: isDark
                            ? "0 2px 12px rgba(201,168,76,0.30)"
                            : "0 2px 12px rgba(92,46,8,0.30)",
                        border: "none",
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        transition: "opacity 0.15s ease",
                    }}
                >
                    Go to Chat
                </button>

                {/* Auto-redirect notice */}
                <p
                    style={{
                        color: isDark
                            ? "rgba(255,255,255,0.30)"
                            : "rgba(46,31,8,0.40)",
                        fontSize: "11px",
                        fontFamily: fontStack,
                        marginTop: "16px",
                    }}
                >
                    Redirecting to chat in {countdown} second{countdown !== 1 ? "s" : ""}...
                </p>
            </div>
        </div>
    );
}
