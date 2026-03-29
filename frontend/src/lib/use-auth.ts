"use client";

import {useState, useEffect, useCallback} from "react";

const API = process.env.NEXT_PUBLIC_SSE_URL ?? "";

export interface User {
    id: string;
    email: string;
    name: string | null;
    avatar_url: string | null;
    subscription_status: string;
    monthly_queries_used: number;
    max_corpora: number;
}

interface AuthState {
    user: User | null;
    loading: boolean;
    error: string | null;
}

async function parseError(res: Response): Promise<string> {
    try {
        const body = await res.json();
        if (typeof body.detail === "string") return body.detail;
        if (typeof body.message === "string") return body.message;
        if (typeof body.error === "string") return body.error;
    } catch {
        // response wasn't JSON — fall through
    }
    return `Request failed (${res.status})`;
}

export function useAuth(): {
    user: User | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    loginWithGoogle: () => void;
    register: (email: string, password: string, name?: string) => Promise<void>;
    logout: () => Promise<void>;
    error: string | null;
    clearError: () => void;
} {
    const [state, setState] = useState<AuthState>({
        user: null,
        loading: true,
        error: null,
    });

    // Check for existing session on mount
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(`${API}/auth/me`, {
                    credentials: "include",
                });
                if (!cancelled && res.ok) {
                    const user: User = await res.json();
                    localStorage.setItem("neolex_uid", user.id);
                    setState({user, loading: false, error: null});
                } else if (!cancelled) {
                    setState({user: null, loading: false, error: null});
                }
            } catch {
                if (!cancelled) {
                    setState({user: null, loading: false, error: null});
                }
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    const login = useCallback(async (email: string, password: string) => {
        setState((prev) => ({...prev, error: null}));
        try {
            const res = await fetch(`${API}/auth/login`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "include",
                body: JSON.stringify({email, password}),
            });
            if (!res.ok) {
                const msg = await parseError(res);
                setState((prev) => ({...prev, error: msg}));
                return;
            }
            // Login returns {message: "..."}, not the user — fetch profile separately
            const meRes = await fetch(`${API}/auth/me`, {credentials: "include"});
            if (meRes.ok) {
                const user: User = await meRes.json();
                localStorage.setItem("neolex_uid", user.id);
                setState({user, loading: false, error: null});
            } else {
                setState((prev) => ({...prev, error: "Login succeeded but failed to load profile."}));
            }
        } catch {
            setState((prev) => ({
                ...prev,
                error: "Cannot reach the server. Please try again.",
            }));
        }
    }, []);

    const loginWithGoogle = useCallback(() => {
        window.location.href = `${API}/auth/google`;
    }, []);

    const register = useCallback(
        async (email: string, password: string, name?: string) => {
            setState((prev) => ({...prev, error: null}));
            try {
                const res = await fetch(`${API}/auth/register`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    credentials: "include",
                    body: JSON.stringify({email, password, name}),
                });
                if (!res.ok) {
                    const msg = await parseError(res);
                    setState((prev) => ({...prev, error: msg}));
                    return;
                }
                // Registration returns {message: "..."} — user must verify email first
                // Don't set user state; the login page will show a success message
                setState({user: null, loading: false, error: null});
            } catch {
                setState((prev) => ({
                    ...prev,
                    error: "Cannot reach the server. Please try again.",
                }));
            }
        },
        []
    );

    const logout = useCallback(async () => {
        try {
            await fetch(`${API}/auth/logout`, {method: "POST", credentials: "include"});
        } catch {
            // swallow — we clear local state regardless
        }
        localStorage.removeItem("neolex_uid");
        setState({user: null, loading: false, error: null});
    }, []);

    const clearError = useCallback(() => {
        setState((prev) => ({...prev, error: null}));
    }, []);

    return {
        user: state.user,
        loading: state.loading,
        login,
        loginWithGoogle,
        register,
        logout,
        error: state.error,
        clearError,
    };
}
