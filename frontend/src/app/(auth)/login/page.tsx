"use client";

import {useState, useEffect} from "react";
import {useRouter} from "next/navigation";
import {useTheme} from "@/lib/theme";
import {motion, AnimatePresence} from "motion/react";
import {useAuth} from "@/lib/use-auth";

const fontStack =
    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

/* ── Google "G" SVG ── */
function GoogleIcon({size = 18}: { size?: number }) {
    return (
        <svg width={size} height={size} viewBox="0 0 48 48">
            <path
                fill="#EA4335"
                d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
            />
            <path
                fill="#4285F4"
                d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
            />
            <path
                fill="#FBBC05"
                d="M10.53 28.59a14.5 14.5 0 0 1 0-9.18l-7.98-6.19a24.09 24.09 0 0 0 0 21.56l7.98-6.19z"
            />
            <path
                fill="#34A853"
                d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
            />
        </svg>
    );
}

type Mode = "login" | "register";

export default function LoginPage() {
    const router = useRouter();
    const {resolvedTheme} = useTheme();
    const {user, login, loginWithGoogle, register, error, clearError} =
        useAuth();

    const [mounted, setMounted] = useState(false);
    const [mode, setMode] = useState<Mode>("login");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [name, setName] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [registerSuccess, setRegisterSuccess] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    // Redirect when user is already logged in
    useEffect(() => {
        if (user) {
            router.push("/chat");
        }
    }, [user, router]);

    const isDark = mounted && resolvedTheme === "dark";

    /* ── Shared glass styles (matching settings page exactly) ── */
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

    const inputStyle: React.CSSProperties = {
        background: isDark
            ? "rgba(255,255,255,0.08)"
            : "rgba(255,255,255,0.35)",
        border: isDark
            ? "0.5px solid rgba(255,255,255,0.14)"
            : "0.5px solid rgba(255,255,255,0.50)",
        borderRadius: "10px",
        padding: "11px 14px",
        fontSize: "14px",
        color: isDark ? "rgba(255,255,255,0.88)" : "#2e1f08",
        caretColor: isDark ? "#C9A84C" : undefined,
        fontFamily: fontStack,
        width: "100%",
        outline: "none",
        boxSizing: "border-box" as const,
        transition: "border-color 0.15s ease, box-shadow 0.15s ease",
    };

    const labelStyle: React.CSSProperties = {
        fontSize: "12px",
        fontWeight: 500,
        color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
        fontFamily: fontStack,
        marginBottom: "6px",
        display: "block",
    };

    const handleInputFocus = (e: React.FocusEvent<HTMLInputElement>) => {
        e.currentTarget.style.borderColor = isDark
            ? "rgba(201,168,76,0.55)"
            : "rgba(196,124,0,0.55)";
        if (isDark) {
            e.currentTarget.style.boxShadow = "0 0 0 3px rgba(201,168,76,0.10)";
        }
    };

    const handleInputBlur = (e: React.FocusEvent<HTMLInputElement>) => {
        e.currentTarget.style.borderColor = isDark
            ? "rgba(255,255,255,0.14)"
            : "rgba(255,255,255,0.50)";
        e.currentTarget.style.boxShadow = "none";
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (submitting) return;
        setSubmitting(true);
        setRegisterSuccess(false);
        clearError();

        if (mode === "login") {
            await login(email, password);
        } else {
            await register(email, password, name || undefined);
            // If no error after register, show success
            // (we check error in the next render)
            setRegisterSuccess(true);
        }
        setSubmitting(false);
    };

    // Reset register success if there's an error
    useEffect(() => {
        if (error) setRegisterSuccess(false);
    }, [error]);

    const switchMode = (newMode: Mode) => {
        setMode(newMode);
        clearError();
        setRegisterSuccess(false);
    };

    const accentColor = isDark ? "#C9A84C" : "#5c2e08";
    const mutedText = isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)";

    return (
        <div
            style={{
                minHeight: "100vh",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "24px 16px",
                fontFamily: fontStack,
                /* Background gradient matching the landing page */
                background: isDark
                    ? "linear-gradient(145deg, #0d1520 0%, #0f1b2e 50%, #0a1120 100%)"
                    : "linear-gradient(145deg, #c8b080 0%, #d4be92 45%, #bca070 100%)",
                position: "relative",
                overflow: "hidden",
            }}
        >
            {/* Aurora blobs */}
            <div
                aria-hidden
                style={{
                    position: "fixed",
                    inset: 0,
                    zIndex: 0,
                    pointerEvents: "none",
                }}
            >
                {isDark ? (
                    <>
                        <div
                            style={{
                                position: "absolute",
                                width: 580,
                                height: 580,
                                top: -80,
                                left: "8%",
                                background:
                                    "radial-gradient(circle, rgba(27,43,75,0.45) 0%, rgba(27,43,75,0.12) 45%, transparent 70%)",
                            }}
                        />
                        <div
                            style={{
                                position: "absolute",
                                width: 460,
                                height: 460,
                                top: 180,
                                right: "4%",
                                background:
                                    "radial-gradient(circle, rgba(15,60,150,0.32) 0%, rgba(15,60,150,0.08) 45%, transparent 70%)",
                            }}
                        />
                        <div
                            style={{
                                position: "absolute",
                                width: 380,
                                height: 380,
                                bottom: 30,
                                left: "28%",
                                background:
                                    "radial-gradient(circle, rgba(40,30,100,0.28) 0%, rgba(40,30,100,0.07) 45%, transparent 70%)",
                            }}
                        />
                    </>
                ) : (
                    <>
                        <div
                            style={{
                                position: "absolute",
                                width: 580,
                                height: 580,
                                top: -80,
                                left: "8%",
                                background:
                                    "radial-gradient(circle, rgba(190,110,30,0.38) 0%, rgba(190,110,30,0.12) 45%, transparent 70%)",
                            }}
                        />
                        <div
                            style={{
                                position: "absolute",
                                width: 460,
                                height: 460,
                                top: 180,
                                right: "4%",
                                background:
                                    "radial-gradient(circle, rgba(200,80,20,0.30) 0%, rgba(200,80,20,0.08) 45%, transparent 70%)",
                            }}
                        />
                        <div
                            style={{
                                position: "absolute",
                                width: 380,
                                height: 380,
                                bottom: 30,
                                left: "28%",
                                background:
                                    "radial-gradient(circle, rgba(175,130,20,0.26) 0%, rgba(175,130,20,0.07) 45%, transparent 70%)",
                            }}
                        />
                    </>
                )}
            </div>

            {/* Card with entrance animation */}
            <div
                style={{
                    ...glassCard,
                    width: "100%",
                    maxWidth: 420,
                    position: "relative",
                    zIndex: 1,
                    animation: "loginFadeIn 0.5s ease-out both",
                }}
            >
                <style>{`
          @keyframes loginFadeIn {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        `}</style>

                {/* Logo + Brand */}
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        padding: "32px 32px 0",
                    }}
                >
                    <div
                        style={{
                            width: 44,
                            height: 44,
                            borderRadius: 13,
                            background: isDark
                                ? "rgba(201,168,76,0.12)"
                                : "rgba(196,124,0,0.18)",
                            border: isDark
                                ? "1px solid rgba(201,168,76,0.25)"
                                : "0.5px solid rgba(196,124,0,0.38)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            boxShadow: isDark
                                ? undefined
                                : "inset 0 1px 0 rgba(255,255,255,0.65)",
                            marginBottom: 12,
                        }}
                    >
                        <svg width="20" height="20" viewBox="0 0 14 14" fill="none">
                            <path
                                d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
                                stroke={isDark ? "#C9A84C" : "#7a4a00"}
                                strokeWidth="1.2"
                                strokeLinejoin="round"
                                fill={
                                    isDark ? "rgba(201,168,76,0.15)" : "rgba(196,124,0,0.10)"
                                }
                            />
                        </svg>
                    </div>
                    <span
                        style={{
                            fontFamily: "var(--font-heading), Georgia, serif",
                            fontSize: "18px",
                            fontWeight: 700,
                            color: isDark ? "rgba(255,255,255,0.95)" : "#1a0e04",
                            letterSpacing: "-0.03em",
                        }}
                    >
            Vitreon Legal
          </span>
                    <AnimatePresence mode="wait">
                        <motion.span
                            key={mode + "-subtitle"}
                            initial={{opacity: 0, y: 4}}
                            animate={{opacity: 1, y: 0}}
                            exit={{opacity: 0, y: -4}}
                            transition={{duration: 0.12, ease: "easeInOut"}}
                            style={{
                                fontSize: "13px",
                                color: mutedText,
                                marginTop: 4,
                                display: "block",
                            }}
                        >
                            {mode === "login"
                                ? "Sign in to your account"
                                : "Create your account"}
                        </motion.span>
                    </AnimatePresence>
                </div>

                {/* Tab switch */}
                <div
                    style={{
                        display: "flex",
                        position: "relative",
                        margin: "20px 32px 0",
                        background: isDark
                            ? "rgba(255,255,255,0.05)"
                            : "rgba(255,255,255,0.20)",
                        borderRadius: "10px",
                        padding: 3,
                        border: isDark
                            ? "0.5px solid rgba(255,255,255,0.08)"
                            : "0.5px solid rgba(255,255,255,0.30)",
                    }}
                >
                    {/* Sliding indicator pill */}
                    <motion.div
                        layoutId="auth-tab-indicator"
                        style={{
                            position: "absolute",
                            top: 3,
                            bottom: 3,
                            width: "calc(50% - 3px)",
                            borderRadius: "8px",
                            background: isDark
                                ? "rgba(201,168,76,0.18)"
                                : "rgba(255,255,255,0.55)",
                            boxShadow: isDark
                                ? "0 1px 4px rgba(0,0,0,0.20)"
                                : "0 1px 4px rgba(100,50,0,0.10)",
                        }}
                        animate={{
                            left: mode === "login" ? 3 : "calc(50% + 0px)",
                        }}
                        transition={{
                            type: "spring",
                            stiffness: 500,
                            damping: 35,
                            mass: 0.8,
                        }}
                    />
                    {(["login", "register"] as Mode[]).map((m) => (
                        <button
                            key={m}
                            onClick={() => switchMode(m)}
                            style={{
                                flex: 1,
                                padding: "8px 0",
                                fontSize: "13px",
                                fontWeight: 600,
                                fontFamily: fontStack,
                                borderRadius: "8px",
                                border: "none",
                                cursor: "pointer",
                                position: "relative",
                                zIndex: 1,
                                background: "transparent",
                                transition: "color 0.15s ease",
                                color:
                                    mode === m
                                        ? accentColor
                                        : isDark
                                            ? "rgba(255,255,255,0.40)"
                                            : "rgba(46,31,8,0.45)",
                            }}
                        >
                            {m === "login" ? "Sign In" : "Sign Up"}
                        </button>
                    ))}
                </div>

                {/* Form body */}
                <div style={{padding: "20px 32px 32px"}}>
                    {/* Google button */}
                    <button
                        type="button"
                        onClick={loginWithGoogle}
                        style={{
                            width: "100%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 10,
                            padding: "11px 0",
                            borderRadius: "10px",
                            fontSize: "14px",
                            fontWeight: 500,
                            fontFamily: fontStack,
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                            background: isDark
                                ? "rgba(255,255,255,0.08)"
                                : "rgba(255,255,255,0.45)",
                            border: isDark
                                ? "0.5px solid rgba(255,255,255,0.14)"
                                : "0.5px solid rgba(255,255,255,0.55)",
                            color: isDark ? "rgba(255,255,255,0.85)" : "#2e1f08",
                        }}
                    >
                        <GoogleIcon size={18}/>
                        Continue with Google
                    </button>

                    {/* Divider */}
                    <div
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 12,
                            margin: "20px 0",
                        }}
                    >
                        <div
                            style={{
                                flex: 1,
                                height: "0.5px",
                                background: isDark
                                    ? "rgba(255,255,255,0.10)"
                                    : "rgba(46,31,8,0.10)",
                            }}
                        />
                        <span
                            style={{
                                fontSize: "11px",
                                fontWeight: 500,
                                color: mutedText,
                                textTransform: "uppercase",
                                letterSpacing: "0.08em",
                            }}
                        >
              or
            </span>
                        <div
                            style={{
                                flex: 1,
                                height: "0.5px",
                                background: isDark
                                    ? "rgba(255,255,255,0.10)"
                                    : "rgba(46,31,8,0.10)",
                            }}
                        />
                    </div>

                    {/* Error message */}
                    {error && (
                        <div
                            style={{
                                background: isDark
                                    ? "rgba(239,68,68,0.12)"
                                    : "rgba(220,38,38,0.08)",
                                border: isDark
                                    ? "0.5px solid rgba(239,68,68,0.30)"
                                    : "0.5px solid rgba(220,38,38,0.25)",
                                borderRadius: "10px",
                                padding: "10px 14px",
                                marginBottom: 16,
                                fontSize: "13px",
                                color: isDark ? "#fca5a5" : "#b91c1c",
                                fontFamily: fontStack,
                            }}
                        >
                            {error}
                        </div>
                    )}

                    {/* Register success */}
                    {registerSuccess && !error && mode === "register" && (
                        <div
                            style={{
                                background: isDark
                                    ? "rgba(34,197,94,0.12)"
                                    : "rgba(22,163,74,0.08)",
                                border: isDark
                                    ? "0.5px solid rgba(34,197,94,0.30)"
                                    : "0.5px solid rgba(22,163,74,0.25)",
                                borderRadius: "10px",
                                padding: "10px 14px",
                                marginBottom: 16,
                                fontSize: "13px",
                                color: isDark ? "#86efac" : "#15803d",
                                fontFamily: fontStack,
                            }}
                        >
                            Check your email to verify your account.
                        </div>
                    )}

                    <AnimatePresence mode="wait">
                        <motion.div
                            key={mode}
                            initial={{opacity: 0, y: 6}}
                            animate={{opacity: 1, y: 0}}
                            exit={{opacity: 0, y: -6}}
                            transition={{duration: 0.15, ease: "easeInOut"}}
                        >
                    <form onSubmit={handleSubmit}>
                        <div
                            style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 14,
                            }}
                        >
                            {/* Name (register only) */}
                            {mode === "register" && (
                                <div>
                                    <label htmlFor="auth-name" style={labelStyle}>
                                        Name
                                    </label>
                                    <input
                                        id="auth-name"
                                        type="text"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="Your name (optional)"
                                        autoComplete="name"
                                        style={inputStyle}
                                        onFocus={handleInputFocus}
                                        onBlur={handleInputBlur}
                                    />
                                </div>
                            )}

                            {/* Email */}
                            <div>
                                <label htmlFor="auth-email" style={labelStyle}>
                                    Email
                                </label>
                                <input
                                    id="auth-email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@company.com"
                                    autoComplete="email"
                                    required
                                    style={inputStyle}
                                    onFocus={handleInputFocus}
                                    onBlur={handleInputBlur}
                                />
                            </div>

                            {/* Password */}
                            <div>
                                <label htmlFor="auth-password" style={labelStyle}>
                                    Password
                                </label>
                                <input
                                    id="auth-password"
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder={
                                        mode === "register"
                                            ? "Create a password"
                                            : "Enter your password"
                                    }
                                    autoComplete={
                                        mode === "register" ? "new-password" : "current-password"
                                    }
                                    required
                                    style={inputStyle}
                                    onFocus={handleInputFocus}
                                    onBlur={handleInputBlur}
                                />
                            </div>
                        </div>

                        {/* Forgot password (login only) */}
                        {mode === "login" && (
                            <div style={{marginTop: 10, textAlign: "right"}}>
                                <a
                                    href="/forgot-password"
                                    style={{
                                        fontSize: "12px",
                                        fontWeight: 500,
                                        color: accentColor,
                                        fontFamily: fontStack,
                                        textDecoration: "none",
                                        transition: "opacity 0.15s ease",
                                    }}
                                >
                                    Forgot password?
                                </a>
                            </div>
                        )}

                        {/* Submit button */}
                        <button
                            type="submit"
                            disabled={submitting}
                            style={{
                                width: "100%",
                                marginTop: 20,
                                padding: "12px 0",
                                borderRadius: "10px",
                                fontSize: "14px",
                                fontWeight: 600,
                                fontFamily: fontStack,
                                cursor: submitting ? "default" : "pointer",
                                border: "none",
                                transition: "all 0.15s ease",
                                background: isDark
                                    ? "linear-gradient(135deg, #C9A84C, #e8cc7a)"
                                    : "#5c2e08",
                                color: isDark ? "#0F1623" : "#fff8ee",
                                boxShadow: isDark
                                    ? "0 2px 12px rgba(201,168,76,0.30)"
                                    : "0 2px 12px rgba(92,46,8,0.30)",
                                opacity: submitting ? 0.7 : 1,
                            }}
                        >
                            {submitting
                                ? "Please wait..."
                                : mode === "login"
                                    ? "Sign In"
                                    : "Create Account"}
                        </button>

                        {/* Terms & Privacy (register only) */}
                        {mode === "register" && (
                            <p
                                style={{
                                    textAlign: "center",
                                    marginTop: 12,
                                    fontSize: "11px",
                                    lineHeight: "1.5",
                                    color: mutedText,
                                    fontFamily: fontStack,
                                }}
                            >
                                By creating an account, you agree to our{" "}
                                <a
                                    href="/terms"
                                    style={{
                                        color: accentColor,
                                        textDecoration: "none",
                                        fontWeight: 500,
                                    }}
                                >
                                    Terms of Service
                                </a>{" "}
                                and{" "}
                                <a
                                    href="/privacy"
                                    style={{
                                        color: accentColor,
                                        textDecoration: "none",
                                        fontWeight: 500,
                                    }}
                                >
                                    Privacy Policy
                                </a>
                                .
                            </p>
                        )}
                    </form>

                    {/* Bottom link */}
                    <p
                        style={{
                            textAlign: "center",
                            marginTop: 20,
                            fontSize: "13px",
                            color: mutedText,
                            fontFamily: fontStack,
                        }}
                    >
                        {mode === "login" ? (
                            <>
                                Don&apos;t have an account?{" "}
                                <button
                                    type="button"
                                    onClick={() => switchMode("register")}
                                    style={{
                                        background: "none",
                                        border: "none",
                                        cursor: "pointer",
                                        fontWeight: 600,
                                        color: accentColor,
                                        fontFamily: fontStack,
                                        fontSize: "13px",
                                        padding: 0,
                                    }}
                                >
                                    Sign up
                                </button>
                            </>
                        ) : (
                            <>
                                Already have an account?{" "}
                                <button
                                    type="button"
                                    onClick={() => switchMode("login")}
                                    style={{
                                        background: "none",
                                        border: "none",
                                        cursor: "pointer",
                                        fontWeight: 600,
                                        color: accentColor,
                                        fontFamily: fontStack,
                                        fontSize: "13px",
                                        padding: 0,
                                    }}
                                >
                                    Sign in
                                </button>
                            </>
                        )}
                    </p>
                        </motion.div>
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
}
