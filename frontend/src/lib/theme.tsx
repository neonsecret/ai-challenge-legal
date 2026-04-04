"use client";

// Custom theme implementation — replaces next-themes.
//
// next-themes caused a Turbopack SSR module-init bug (module 13902: React null
// during first SSR bundle load) that crashed prerendering for /_global-error
// and other pages. This module provides the same API surface (theme,
// resolvedTheme, setTheme) without the problematic initialization chain.
//
// Flash prevention: layout.tsx includes an inline <script> that reads
// localStorage and sets document.documentElement.classList before hydration,
// mirroring what next-themes' inline script did.

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
    /** Stored preference — may be "system" */
    theme: Theme;
    /** Effective theme after resolving "system" — undefined before client mount */
    resolvedTheme: ResolvedTheme | undefined;
    setTheme: (theme: Theme) => void;
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

const STORAGE_KEY = "theme";

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function getSystemTheme(): ResolvedTheme {
    if (typeof window === "undefined") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveTheme(theme: Theme): ResolvedTheme {
    return theme === "system" ? getSystemTheme() : theme;
}

function applyTheme(resolved: ResolvedTheme) {
    document.documentElement.classList.toggle("dark", resolved === "dark");
}

function readStorage(): Theme {
    try {
        return (localStorage.getItem(STORAGE_KEY) as Theme) || "system";
    } catch {
        return "system";
    }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ThemeProvider({children}: {children: ReactNode}) {
    const [theme, setThemeState] = useState<Theme>("system");
    const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme | undefined>(undefined);

    useEffect(() => {
        const stored = readStorage();
        const resolved = resolveTheme(stored);
        setThemeState(stored);
        setResolvedTheme(resolved);
        applyTheme(resolved);

        // Re-resolve when OS preference changes and user has "system" set
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const handleChange = () => {
            setThemeState((current) => {
                if (current === "system") {
                    const newResolved = mq.matches ? "dark" : "light";
                    setResolvedTheme(newResolved);
                    applyTheme(newResolved);
                }
                return current;
            });
        };
        mq.addEventListener("change", handleChange);
        return () => mq.removeEventListener("change", handleChange);
    }, []);

    const setTheme = useCallback((newTheme: Theme) => {
        try {
            localStorage.setItem(STORAGE_KEY, newTheme);
        } catch {}
        const resolved = resolveTheme(newTheme);
        setThemeState(newTheme);
        setResolvedTheme(resolved);
        applyTheme(resolved);
    }, []);

    return (
        <ThemeContext.Provider value={{theme, resolvedTheme, setTheme}}>
            {children}
        </ThemeContext.Provider>
    );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useTheme(): ThemeContextValue {
    const ctx = useContext(ThemeContext);
    // Safe fallback when used outside provider (e.g. error boundaries)
    return ctx ?? {theme: "system", resolvedTheme: undefined, setTheme: () => {}};
}
