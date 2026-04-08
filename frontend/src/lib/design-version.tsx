"use client";

// Design version hook — toggles .design-v2 or .design-v3 class on <html>.
// Modeled on frontend/src/lib/theme.tsx.
//
// V1 (Classic) has been removed. V2 (Modern) and V3 (Luminous) are active.
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

export type DesignVersion = "v2" | "v3";

interface DesignVersionContextValue {
    version: DesignVersion;
    setVersion: (v: DesignVersion) => void;
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

const STORAGE_KEY = "vitreon-design-version";
const DEFAULT_VERSION: DesignVersion = "v2";

const DesignVersionContext = createContext<DesignVersionContextValue | undefined>(undefined);

function readStorage(): DesignVersion {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored === "v2" || stored === "v3") return stored;
        return DEFAULT_VERSION;
    } catch {
        return DEFAULT_VERSION;
    }
}

function applyVersion(version: DesignVersion) {
    document.documentElement.classList.toggle("design-v2", version === "v2");
    document.documentElement.classList.toggle("design-v3", version === "v3");
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
