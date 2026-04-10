"use client";

import {useEffect, useState} from "react";
import {useColorMode} from "@/lib/color-mode";
import {CheckCircle2, AlertCircle, Loader2} from "lucide-react";
import {useI18n} from "@/lib/i18n";

interface IndexStatus {
    status: "ready" | "starting" | "error" | "loading";
    pipeline_ready?: boolean;
}

const API_BASE = `${process.env.NEXT_PUBLIC_API_URL ?? ""}`;

export function IndexInfoPanel() {
    const {isDark} = useColorMode();
    const [indexStatus, setIndexStatus] = useState<IndexStatus>({status: "loading"});
    const {t} = useI18n();

    useEffect(() => {
        let cancelled = false;

        async function fetchStatus() {
            try {
                const res = await fetch(`${API_BASE}/health`, {credentials: "include"});
                if (cancelled) return;
                if (res.ok) {
                    const data = await res.json();
                    setIndexStatus({
                        status: data.pipeline_ready ? "ready" : "starting",
                        pipeline_ready: data.pipeline_ready,
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
        return () => { cancelled = true; };
    }, []);

    // ── Dark mode: single compact status line ─────────────────────────────────
    if (isDark) {
        const statusDot: Record<IndexStatus["status"], {color: string; label: string; animate?: boolean}> = {
            ready:    {color: "#4ade80", label: t("documents.index_status_active")},
            starting: {color: "#C9A84C", label: t("documents.index_status_warming"), animate: true},
            error:    {color: "#f87171", label: t("documents.index_status_unavailable")},
            loading:  {color: "rgba(200,210,230,0.22)", label: t("documents.index_status_checking"), animate: true},
        };
        const s = statusDot[indexStatus.status];

        return (
            <div style={{
                display: "flex", alignItems: "center", gap: "6px",
                padding: "6px 10px", borderRadius: "5px",
                background: "rgba(255,255,255,0.015)",
                border: "1px solid rgba(201,168,76,0.04)",
            }}>
                {/* Status dot */}
                {indexStatus.status === "ready" && (
                    <CheckCircle2 size={11} style={{color: s.color, flexShrink: 0}}/>
                )}
                {indexStatus.status === "error" && (
                    <AlertCircle size={11} style={{color: s.color, flexShrink: 0}}/>
                )}
                {(indexStatus.status === "starting" || indexStatus.status === "loading") && (
                    <Loader2 size={11} style={{color: s.color, flexShrink: 0, animation: "spin 1s linear infinite"}}/>
                )}
                <span style={{
                    fontSize: "9px", fontFamily: "system-ui, sans-serif",
                    color: "rgba(200,210,230,0.42)", flex: 1,
                }}>
                    {s.label}
                </span>
                <span style={{
                    fontSize: "7px", fontFamily: "system-ui, sans-serif",
                    color: "rgba(200,210,230,0.22)",
                    letterSpacing: "0.04em",
                }}>
                    Hybrid BM25 + Vector · Cross-encoder
                </span>
            </div>
        );
    }

    // ── Light mode: original full card design ─────────────────────────────────
    const fontStack = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";
    const labelColor = "rgba(46,31,8,0.45)";
    const valueColor = "#1e1208";

    const glassCard: React.CSSProperties = {
        background: "rgba(255,250,235,0.22)",
        backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        border: "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: "20px",
        boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    const statusConfig = {
        ready: {
            icon: <CheckCircle2 size={14} style={{color: "#16a34a"}}/>,
            label: t("documents.index_status_active"),
            pill: {background: "rgba(74,222,128,0.12)", border: "0.5px solid rgba(74,222,128,0.30)", color: "#16a34a"},
        },
        starting: {
            icon: <Loader2 size={14} style={{color: "#c47c00", animation: "spin 1s linear infinite"}}/>,
            label: t("documents.index_status_warming"),
            pill: {background: "rgba(201,168,76,0.12)", border: "0.5px solid rgba(201,168,76,0.30)", color: "#7a4a00"},
        },
        error: {
            icon: <AlertCircle size={14} style={{color: "#f87171"}}/>,
            label: t("documents.index_status_unavailable"),
            pill: {background: "rgba(248,113,113,0.10)", border: "0.5px solid rgba(248,113,113,0.25)", color: "#f87171"},
        },
        loading: {
            icon: <Loader2 size={14} style={{color: labelColor, animation: "spin 1s linear infinite"}}/>,
            label: t("documents.index_status_checking"),
            pill: {background: "rgba(255,255,255,0.18)", border: "0.5px solid rgba(255,255,255,0.30)", color: labelColor},
        },
    };

    const current = statusConfig[indexStatus.status];

    return (
        <div style={glassCard}>
            <div style={{borderBottom: "0.5px solid rgba(255,255,255,0.30)", padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                <h2 style={{fontSize: "14px", fontWeight: 600, color: valueColor, margin: 0, fontFamily: fontStack}}>
                    {t("documents.index_search_index")}
                </h2>
                <div style={{...current.pill, display: "inline-flex", alignItems: "center", gap: "5px", borderRadius: "9999px", padding: "3px 10px", fontSize: "11px", fontWeight: 600, fontFamily: fontStack}}>
                    {current.icon}{current.label}
                </div>
            </div>
            <div style={{padding: "16px 20px", display: "flex", flexDirection: "column", gap: "16px", fontFamily: fontStack}}>
                <div style={{display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px"}}>
                    {[
                        {label: t("documents.index_engine"), value: "pgvector"},
                        {label: t("documents.index_type"), value: "Hybrid BM25 + Vector"},
                        {label: t("documents.index_reranker"), value: "Cross-encoder"},
                    ].map(({label, value}) => (
                        <div key={label} style={{background: "rgba(255,255,255,0.18)", border: "0.5px solid rgba(255,255,255,0.35)", borderRadius: "12px", padding: "10px 14px"}}>
                            <div style={{fontSize: "10px", fontWeight: 500, textTransform: "uppercase" as const, letterSpacing: "0.05em", color: labelColor, marginBottom: "4px"}}>{label}</div>
                            <div style={{fontSize: "12px", fontWeight: 600, color: valueColor}}>{value}</div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
