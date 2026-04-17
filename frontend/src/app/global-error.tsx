"use client";

// This MUST be a "use client" component (Next.js 16 requirement for global-error).
//
// Root cause of build failures on this page:
//
// 1. NODE_ENV leak — if the build process inherits NODE_ENV=development from the
//    shell, Next.js 16's build worker doesn't fully initialise the React vendor
//    module before prerendering /_global-error. Fix: always run `next build` with
//    NODE_ENV=production (see build script in package.json).
//
// 2. Turbopack module ordering — /_global-error bypasses the root layout, so its
//    SSR bundle is minimal. Turbopack lazily evaluates modules; if the React
//    vendor chunk isn't eagerly evaluated, Next.js's router code throws:
//    "TypeError: Cannot read properties of null (reading 'useContext')".
//    Importing the React default export (`import React`) forces eager evaluation.
//    Named-only imports ({useState, useEffect}) go through indirect re-exports
//    that Turbopack doesn't eagerly evaluate in its multi-worker SSR context.
//
// Note: `export const dynamic = "force-dynamic"` does NOT prevent the prerender
// of /_global-error — Next.js always prerenders it to generate 500.html,
// ignoring route-level dynamic config for this special page.
//
// Theme: ThemeProvider is absent here (no root layout), so we read the theme
// from the DOM class list after mount. See BillingSuccessClient.tsx for the
// same pattern.

import React, {useState, useEffect, startTransition} from "react";

const fontStack =
    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

export default function GlobalError({
    reset,
}: {
    error: Error & {digest?: string};
    reset?: () => void;
}) {
    const [mounted, setMounted] = useState(false);
    const [isDark, setIsDark] = useState(false);

    useEffect(() => {
        startTransition(() => {
            setMounted(true);
            // Read theme from DOM — layout.tsx inline script sets .dark on <html>
            // before hydration, so this is reliable even without ThemeProvider.
            setIsDark(document.documentElement.classList.contains("dark"));
        });
    }, []);

    const dark = mounted && isDark;

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
                    background: dark ? "#0f1623" : "#fffbf4",
                    color: dark ? "rgba(255,255,255,0.85)" : "#1e1208",
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
                            background: dark
                                ? "linear-gradient(135deg,#C9A84C,#e8cc7a)"
                                : "#5c2e08",
                            color: dark ? "#0F1623" : "#fff8ee",
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
                {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- global-error bypasses root layout; full reload is safer for error recovery */}
                <a
                    href="/"
                    style={{
                        opacity: 0.55,
                        fontSize: "12px",
                        fontFamily: fontStack,
                        color: dark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.60)",
                        textDecoration: "underline",
                    }}
                >
                    Go home
                </a>
            </body>
        </html>
    );
}
