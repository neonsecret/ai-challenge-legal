"use client";

// This MUST be a "use client" component (Next.js 16 requirement for global-error).
//
// IMPORTANT: The `useTheme` import below is NOT optional — it is a deliberate
// workaround for a Turbopack SSR module-initialization ordering bug.
//
// Background: the `/_global-error` page bypasses the root layout (by design).
// As a result, its SSR bundle is minimal and does not include `theme.tsx`.
// Next.js's own router-context code (in node_modules_next_dist_0h9llsw chunk)
// calls `(0, React.useContext)(AppRouterContext)` during prerender. Due to how
// Turbopack lazily evaluates modules, `React` (module 72131) can be null at
// that point — causing `TypeError: Cannot read properties of null (reading
// 'useContext')` and a build failure.
//
// Pages that render through the root layout work because `theme.tsx` imports
// React via `a.i(72131)` at module scope (`createContext`), which forces the
// React vendor module to be fully initialized. By importing `useTheme` here,
// `theme.tsx` is pulled into the `_global-error` SSR bundle, replicating that
// initialization for this page too.
//
// Related: BillingSuccessClient.tsx uses the same DOM-based pattern to avoid
// calling useTheme() where ThemeProvider may be absent.

import {useTheme} from "@/lib/theme";
import {useState, useEffect} from "react";

const fontStack =
    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

export default function GlobalError({
    reset,
}: {
    error: Error & {digest?: string};
    reset?: () => void;
}) {
    const [mounted, setMounted] = useState(false);

    // useTheme forces theme.tsx into the _global-error SSR bundle.
    // It returns a safe fallback ({resolvedTheme: undefined}) when
    // ThemeProvider is absent (which it always is here), so this is safe.
    const {resolvedTheme} = useTheme();
    const isDark = mounted && resolvedTheme === "dark";

    useEffect(() => setMounted(true), []);

    return (
        <html lang="en">
            <body
                style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    minHeight: "100vh",
                    fontFamily: fontStack,
                    background: isDark ? "#0f1623" : "#fffbf4",
                    color: isDark ? "rgba(255,255,255,0.85)" : "#1e1208",
                    margin: 0,
                }}
            >
                <h1
                    style={{
                        fontSize: "1.5rem",
                        fontWeight: 700,
                        marginBottom: "8px",
                        fontFamily: "Georgia, serif",
                    }}
                >
                    Something went wrong
                </h1>
                <p
                    style={{
                        opacity: 0.55,
                        fontSize: "14px",
                        marginBottom: "24px",
                        textAlign: "center",
                    }}
                >
                    An unexpected error occurred. Please reload the page.
                </p>
                {reset && (
                    <button
                        onClick={reset}
                        style={{
                            marginBottom: "12px",
                            padding: "9px 28px",
                            borderRadius: "10px",
                            background: isDark
                                ? "linear-gradient(135deg,#C9A84C,#e8cc7a)"
                                : "#5c2e08",
                            color: isDark ? "#0F1623" : "#fff8ee",
                            border: "none",
                            cursor: "pointer",
                            fontWeight: 600,
                            fontSize: "13px",
                            fontFamily: fontStack,
                        }}
                    >
                        Try again
                    </button>
                )}
                <a
                    href="/"
                    style={{
                        opacity: 0.55,
                        fontSize: "12px",
                        fontFamily: fontStack,
                        color: isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.60)",
                        textDecoration: "underline",
                    }}
                >
                    Go home
                </a>
            </body>
        </html>
    );
}
