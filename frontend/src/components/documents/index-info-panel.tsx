"use client";

import {useEffect, useState} from "react";
import {useColorMode} from "@/lib/color-mode";
import {Database, Activity, CheckCircle2, AlertCircle, Loader2} from "lucide-react";
import {useI18n} from "@/lib/i18n";

interface IndexStatus {
    status: "ready" | "starting" | "error" | "loading";
    pipeline_ready?: boolean;
}

const API_BASE = `${process.env.NEXT_PUBLIC_API_URL ?? ""}`;


export function IndexInfoPanel() {
    const {isDark} = useColorMode();
    const [indexStatus, setIndexStatus] = useState<IndexStatus>({status: "loading"});

    useEffect(() => {
        let cancelled = false;

        async function fetchStatus() {
            try {
                const res = await fetch(`${API_BASE}/health`, {
                    credentials: "include",
                });
                if (cancelled) return;
                if (res.ok) {
                    const data = await res.json();
                    setIndexStatus({
                        status: data.pipeline_ready ? "ready" : "starting",
                        pipeline_ready: data.pipeline_ready
                    });
                } else if (res.status === 503) {
                    const data = await res.json();
                    setIndexStatus({status: data.status === "starting" ? "starting" : "error"});
                } else {
                    setIndexStatus({status: "error"});
                }
            } catch {
                if (!cancelled) setIndexStatus({status: "error"});
            }
        }

        fetchStatus();
        return () => {
            cancelled = true;
        };
    }, []);

    const {t} = useI18n();

    const glassCard: React.CSSProperties = {
        background: isDark ? "rgba(255,255,255,0.02)" : "rgba(255,250,235,0.22)",
        backdropFilter: isDark ? "blur(24px)" : "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: isDark ? "blur(24px)" : "blur(32px) saturate(180%) brightness(106%)",
        border: isDark
            ? "0.5px solid rgba(201,168,76,0.06)"
            : "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: isDark ? "14px" : "20px",
        boxShadow: isDark
            ? "0 2px 16px rgba(0,0,0,0.45), inset 0 1px 0 rgba(201,168,76,0.04)"
            : "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    const cardHeaderSep: React.CSSProperties = {
        borderBottom: isDark
            ? "0.5px solid rgba(201,168,76,0.06)"
            : "0.5px solid rgba(255,255,255,0.30)",
    };

    const labelColor = isDark ? "var(--strict-text-dim, rgba(255,255,255,0.40))" : "rgba(46,31,8,0.45)";
    const valueColor = isDark ? "var(--strict-text-primary, rgba(255,255,255,0.92))" : "#1e1208";
    const fontStack = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

    const statusConfig = {
        ready: {
            icon: <CheckCircle2 size={14} style={{color: "#4ade80"}}/>,
            label: t("documents.index_status_active"),
            pill: {
                background: "rgba(74,222,128,0.12)",
                border: "0.5px solid rgba(74,222,128,0.30)",
                color: isDark ? "#4ade80" : "#16a34a",
            },
        },
        starting: {
            icon: <Loader2 size={14} style={{color: "#C9A84C", animation: "spin 1s linear infinite"}}/>,
            label: t("documents.index_status_warming"),
            pill: {
                background: "rgba(201,168,76,0.12)",
                border: "0.5px solid rgba(201,168,76,0.30)",
                color: isDark ? "#C9A84C" : "#7a4a00",
            },
        },
        error: {
            icon: <AlertCircle size={14} style={{color: "#f87171"}}/>,
            label: t("documents.index_status_unavailable"),
            pill: {
                background: "rgba(248,113,113,0.10)",
                border: "0.5px solid rgba(248,113,113,0.25)",
                color: "#f87171",
            },
        },
        loading: {
            icon: <Loader2 size={14} style={{color: labelColor, animation: "spin 1s linear infinite"}}/>,
            label: t("documents.index_status_checking"),
            pill: {
                background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.18)",
                border: `0.5px solid ${isDark ? "rgba(201,168,76,0.06)" : "rgba(255,255,255,0.30)"}`,
                color: labelColor,
            },
        },
    };

    const current = statusConfig[indexStatus.status];

    // Available indexes (future-ready: today just one)
    const availableIndexes = [
        {id: "default", label: "Default (FAISS)", active: true},
    ];

    return (
        <div style={glassCard}>
            {/* Header */}
            <div
                style={{
                    ...cardHeaderSep,
                    padding: "16px 20px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                }}
            >
                <div style={{display: "flex", alignItems: "center", gap: "8px"}}>
                    <Database
                        size={16}
                        style={{color: isDark ? "#C9A84C" : "rgba(46,31,8,0.45)"}}
                    />
                    <h2
                        style={{
                            fontSize: "14px",
                            fontWeight: 600,
                            color: valueColor,
                            margin: 0,
                            fontFamily: fontStack,
                        }}
                    >
                        {t("documents.index_search_index")}
                    </h2>
                </div>

                {/* Pipeline status pill */}
                <div
                    style={{
                        ...current.pill,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "5px",
                        borderRadius: "9999px",
                        padding: "3px 10px",
                        fontSize: "11px",
                        fontWeight: 600,
                        fontFamily: fontStack,
                    }}
                >
                    {current.icon}
                    {current.label}
                </div>
            </div>

            {/* Body */}
            <div
                style={{
                    padding: "16px 20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                    fontFamily: fontStack,
                }}
            >
                {/* Stats row */}
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr 1fr",
                        gap: "12px",
                    }}
                >
                    {[
                        {label: t("documents.index_engine"), value: "FAISS"},
                        {label: t("documents.index_type"), value: "Hybrid BM25 + Vector"},
                        {label: t("documents.index_reranker"), value: "Cross-encoder"},
                    ].map(({label, value}) => (
                        <div
                            key={label}
                            style={{
                                background: isDark ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.18)",
                                border: isDark
                                    ? "0.5px solid rgba(201,168,76,0.06)"
                                    : "0.5px solid rgba(255,255,255,0.35)",
                                borderRadius: isDark ? "10px" : "12px",
                                padding: "10px 14px",
                            }}
                        >
                            <div
                                style={{
                                    fontSize: "10px",
                                    fontWeight: 500,
                                    textTransform: "uppercase" as const,
                                    letterSpacing: "0.05em",
                                    color: labelColor,
                                    marginBottom: "4px",
                                }}
                            >
                                {label}
                            </div>
                            <div
                                style={{
                                    fontSize: "12px",
                                    fontWeight: 600,
                                    color: valueColor,
                                }}
                            >
                                {value}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Index selector (future-ready) */}
                <div>
                    <div
                        style={{
                            fontSize: "11px",
                            fontWeight: 500,
                            textTransform: "uppercase" as const,
                            letterSpacing: "0.05em",
                            color: labelColor,
                            marginBottom: "8px",
                        }}
                    >
                        {t("documents.index_available")}
                    </div>
                    <div style={{display: "flex", flexDirection: "column", gap: "6px"}}>
                        {availableIndexes.map((idx) => (
                            <div
                                key={idx.id}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    background: idx.active
                                        ? isDark
                                            ? "rgba(201,168,76,0.06)"
                                            : "rgba(201,168,76,0.06)"
                                        : isDark
                                            ? "rgba(255,255,255,0.02)"
                                            : "rgba(255,255,255,0.12)",
                                    border: idx.active
                                        ? isDark
                                            ? "0.5px solid rgba(201,168,76,0.18)"
                                            : "0.5px solid rgba(201,168,76,0.30)"
                                        : isDark
                                            ? "0.5px solid rgba(201,168,76,0.06)"
                                            : "0.5px solid rgba(255,255,255,0.25)",
                                    borderRadius: isDark ? "10px" : "10px",
                                    padding: "10px 14px",
                                }}
                            >
                                <div style={{display: "flex", alignItems: "center", gap: "10px"}}>
                                    <Activity
                                        size={14}
                                        style={{
                                            color: idx.active
                                                ? "#C9A84C"
                                                : isDark
                                                    ? "rgba(255,255,255,0.30)"
                                                    : "rgba(46,31,8,0.35)",
                                        }}
                                    />
                                    <span
                                        style={{
                                            fontSize: "13px",
                                            fontWeight: idx.active ? 500 : 400,
                                            color: idx.active ? (isDark ? "#C9A84C" : "#7a4a00") : labelColor,
                                        }}
                                    >
                    {idx.label}
                  </span>
                                </div>
                                {idx.active && (
                                    <span
                                        style={{
                                            fontSize: "10px",
                                            fontWeight: 600,
                                            textTransform: "uppercase" as const,
                                            letterSpacing: "0.06em",
                                            color: isDark ? "rgba(201,168,76,0.70)" : "#c47c00",
                                        }}
                                    >
                                        {t("documents.index_active")}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                    <p
                        style={{
                            fontSize: "11px",
                            color: labelColor,
                            marginTop: "8px",
                            lineHeight: 1.5,
                        }}
                    >
                        {t("documents.index_switching_future")}
                    </p>
                </div>
            </div>
        </div>
    );
}
