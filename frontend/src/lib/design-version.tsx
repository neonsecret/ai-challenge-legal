"use client";

// Design version hook — toggles .design-neon or .design-strict class on <html>.
// Modeled on frontend/src/lib/theme.tsx.
//
// V1 (Classic) has been removed. Neon (formerly V2/Modern) and Strict (formerly V3/Luminous) are active.
//
// No inline <script> needed — a brief flash on first load is acceptable
// (design version is not SSR-critical).

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

export type DesignVersion = "neon" | "strict";

interface DesignVersionContextValue {
    version: DesignVersion;
    setVersion: (v: DesignVersion) => void;
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

const STORAGE_KEY = "vitreon-design-version";
const DEFAULT_VERSION: DesignVersion = "neon";

const DesignVersionContext = createContext<DesignVersionContextValue | undefined>(undefined);

function readStorage(): DesignVersion {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored === "neon" || stored === "strict") return stored;
        return DEFAULT_VERSION;
    } catch {
        return DEFAULT_VERSION;
    }
}

function applyVersion(version: DesignVersion) {
    document.documentElement.classList.toggle("design-neon", version === "neon");
    document.documentElement.classList.toggle("design-strict", version === "strict");
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function DesignVersionProvider({ children }: { children: ReactNode }) {
    const [version, setVersionState] = useState<DesignVersion>(DEFAULT_VERSION);

    useEffect(() => {
        const stored = readStorage();
        setVersionState(stored);
        applyVersion(stored);
    }, []);

    const setVersion = useCallback((v: DesignVersion) => {
        try {
            localStorage.setItem(STORAGE_KEY, v);
        } catch {}
        setVersionState(v);
        applyVersion(v);
    }, []);

    return (
        <DesignVersionContext.Provider value={{ version, setVersion }}>
            {children}
        </DesignVersionContext.Provider>
    );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useDesignVersion(): DesignVersionContextValue {
    const ctx = useContext(DesignVersionContext);
    return ctx ?? { version: DEFAULT_VERSION, setVersion: () => {} };
}
