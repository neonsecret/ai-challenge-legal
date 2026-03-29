"use client";

import {createContext, useContext, useState, useCallback, useRef} from "react";
import {X, CheckCircle, AlertCircle, Info} from "lucide-react";
import {cn} from "@/lib/utils";

export type ToastVariant = "default" | "success" | "error";

export interface Toast {
    id: string;
    message: string;
    variant: ToastVariant;
}

interface ToastContextValue {
    toasts: Toast[];
    addToast: (message: string, variant?: ToastVariant) => void;
    removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({children}: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const timerRefs = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

    const removeToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        clearTimeout(timerRefs.current[id]);
        delete timerRefs.current[id];
    }, []);

    const addToast = useCallback(
        (message: string, variant: ToastVariant = "default") => {
            const id = `toast-${Date.now()}-${Math.random()}`;
            setToasts((prev) => [...prev.slice(-4), {id, message, variant}]);
            timerRefs.current[id] = setTimeout(() => removeToast(id), 4000);
        },
        [removeToast]
    );

    return (
        <ToastContext.Provider value={{toasts, addToast, removeToast}}>
            {children}
            <ToastContainer toasts={toasts} onDismiss={removeToast}/>
        </ToastContext.Provider>
    );
}

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error("useToast must be used within ToastProvider");
    return ctx;
}

const ICON: Record<ToastVariant, React.ReactNode> = {
    default: <Info className="size-4 shrink-0"/>,
    success: <CheckCircle className="size-4 shrink-0 text-green-400"/>,
    error: <AlertCircle className="size-4 shrink-0 text-destructive"/>,
};

function ToastContainer({
                            toasts,
                            onDismiss,
                        }: {
    toasts: Toast[];
    onDismiss: (id: string) => void;
}) {
    if (toasts.length === 0) return null;

    return (
        <div
            className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
            aria-live="polite"
            aria-label="Notifications"
        >
            {toasts.map((t) => (
                <div
                    key={t.id}
                    className={cn(
                        "pointer-events-auto flex items-start gap-3 rounded-xl border bg-card px-4 py-3 text-sm shadow-lg",
                        "animate-in slide-in-from-bottom-4 fade-in duration-200",
                        t.variant === "error" && "border-destructive/40 bg-destructive/10",
                        t.variant === "success" && "border-green-500/30 bg-green-500/10",
                        t.variant === "default" && "border-border"
                    )}
                    role="alert"
                >
                    {ICON[t.variant]}
                    <span className="flex-1 text-foreground leading-snug">{t.message}</span>
                    <button
                        onClick={() => onDismiss(t.id)}
                        className="ml-2 shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                        aria-label="Dismiss notification"
                    >
                        <X className="size-3.5"/>
                    </button>
                </div>
            ))}
        </div>
    );
}
