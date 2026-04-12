"use client";

// ColorModeContext — single dark/light toggle replacing DesignVersionContext.
// Light mode = Neon (unchanged). Dark mode = Strict (gold glassmorphism).
// An inline <script> in layout.tsx applies .dark or .light before paint to prevent FOUC.

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

export type ColorMode = "light" | "dark" | "system";

interface ColorModeContextValue {
    mode: ColorMode;
    resolvedMode: "light" | "dark";
    setMode: (m: ColorMode) => void;
    isDark: boolean;
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

const STORAGE_KEY = "vitreon-color-mode";
const OLD_DESIGN_KEY = "vitreon-design-version";
const OLD_THEME_KEY = "theme";

const ColorModeContext = createContext<ColorModeContextValue | undefined>(undefined);

function getSystemPreference(): "light" | "dark" {
    if (typeof window === "undefined") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readStoredMode(): ColorMode {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored === "light" || stored === "dark" || stored === "system") return stored;

        // Migration from old design-version key
        const oldDesign = localStorage.getItem(OLD_DESIGN_KEY);
        if (oldDesign === "strict") return "dark";
        if (oldDesign === "neon") return "light";

        // Migration from next-themes key
        const oldTheme = localStorage.getItem(OLD_THEME_KEY);
        if (oldTheme === "dark") return "dark";
        if (oldTheme === "light") return "light";
    } catch {
        // localStorage unavailable
    }
    // Default to dark for new users with no stored preference
    return "dark";
}

function applyMode(resolved: "light" | "dark") {
    document.documentElement.classList.toggle("dark", resolved === "dark");
    document.documentElement.classList.toggle("light", resolved === "light");
}

function migrateOldKeys() {
    try {
        localStorage.removeItem(OLD_DESIGN_KEY);
    } catch {
        // ignore
    }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

function getInitialResolved(): "light" | "dark" {
    if (typeof document !== "undefined") {
        return document.documentElement.classList.contains("dark") ? "dark" : "light";
    }
    return "light";
}

export function ColorModeProvider({ children }: { children: ReactNode }) {
    const [mode, setModeState] = useState<ColorMode>(() =>
        typeof window !== "undefined" ? readStoredMode() : "system"
    );
    const [resolvedMode, setResolvedMode] = useState<"light" | "dark">(getInitialResolved);

    useEffect(() => {
        const stored = readStoredMode();
        const resolved = stored === "system" ? getSystemPreference() : stored;
        setModeState(stored);
        setResolvedMode(resolved);
        applyMode(resolved);
        migrateOldKeys();

        if (stored !== "system") return;

        const mql = window.matchMedia("(prefers-color-scheme: dark)");
        const handler = (e: MediaQueryListEvent) => {
            const r = e.matches ? "dark" : "light";
            setResolvedMode(r);
            applyMode(r);
        };
        mql.addEventListener("change", handler);
        return () => mql.removeEventListener("change", handler);
    }, []);

    const setMode = useCallback((m: ColorMode) => {
        const resolved = m === "system" ? getSystemPreference() : m;
        try {
            localStorage.setItem(STORAGE_KEY, m);
        } catch { /* ignore */ }
        setModeState(m);
        setResolvedMode(resolved);
        applyMode(resolved);
    }, []);

    return (
        <ColorModeContext.Provider value={{ mode, resolvedMode, setMode, isDark: resolvedMode === "dark" }}>
            {children}
        </ColorModeContext.Provider>
    );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useColorMode(): ColorModeContextValue {
    const ctx = useContext(ColorModeContext);
    return ctx ?? { mode: "light", resolvedMode: "light", setMode: () => {}, isDark: false };
}
