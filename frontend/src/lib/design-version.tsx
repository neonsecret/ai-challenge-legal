"use client";

// Design version hook — toggles .design-v2 class on <html>.
// Modeled on frontend/src/lib/theme.tsx.
//
// V1 (Classic) has been removed. V2 (Modern) is the only active design.
// This provider is kept extensible for future V3 addition.
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

export type DesignVersion = "v2";

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
        // Migrate any stored V1 preference to V2
        return stored === "v2" ? "v2" : DEFAULT_VERSION;
    } catch {
        return DEFAULT_VERSION;
    }
}

function applyVersion(version: DesignVersion) {
    document.documentElement.classList.toggle("design-v2", version === "v2");
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
