"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Database, Activity, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

interface IndexStatus {
  status: "ready" | "starting" | "error" | "loading";
  pipeline_ready?: boolean;
}

const API_BASE = `${process.env.NEXT_PUBLIC_API_URL ?? ""}`;

function getApiKey(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("neolex_api_key") ?? "";
  }
  return "";
}

export function IndexInfoPanel() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [indexStatus, setIndexStatus] = useState<IndexStatus>({ status: "loading" });

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function fetchStatus() {
      try {
        const res = await fetch(`${API_BASE}/health`, {
          headers: { Authorization: `Bearer ${getApiKey()}` },
        });
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          setIndexStatus({ status: data.pipeline_ready ? "ready" : "starting", pipeline_ready: data.pipeline_ready });
        } else if (res.status === 503) {
          const data = await res.json();
          setIndexStatus({ status: data.status === "starting" ? "starting" : "error" });
        } else {
          setIndexStatus({ status: "error" });
        }
      } catch {
        if (!cancelled) setIndexStatus({ status: "error" });
      }
    }
    fetchStatus();
    return () => { cancelled = true; };
  }, []);

  const isDark = mounted && resolvedTheme === "dark";

  const glassCard: React.CSSProperties = {
    background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,250,235,0.22)",
    backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    border: isDark
      ? "0.5px solid rgba(255,255,255,0.12)"
      : "0.5px solid rgba(255,255,255,0.38)",
    borderRadius: "20px",
    boxShadow: isDark
      ? "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 32px rgba(0,0,0,0.30)"
      : "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
    overflow: "clip",
  };

  const cardHeaderSep: React.CSSProperties = {
    borderBottom: isDark
      ? "0.5px solid rgba(255,255,255,0.12)"
      : "0.5px solid rgba(255,255,255,0.30)",
  };

  const labelColor = isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)";
  const valueColor = isDark ? "rgba(255,255,255,0.82)" : "#1e1208";
  const fontStack = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

  const statusConfig = {
    ready: {
      icon: <CheckCircle2 size={14} style={{ color: "#4ade80" }} />,
      label: "Active",
      pill: {
        background: "rgba(74,222,128,0.12)",
        border: "0.5px solid rgba(74,222,128,0.30)",
        color: isDark ? "#4ade80" : "#16a34a",
      },
    },
    starting: {
      icon: <Loader2 size={14} style={{ color: "#C9A84C", animation: "spin 1s linear infinite" }} />,
      label: "Warming up",
      pill: {
        background: "rgba(201,168,76,0.12)",
        border: "0.5px solid rgba(201,168,76,0.30)",
        color: isDark ? "#C9A84C" : "#7a4a00",
      },
    },
    error: {
      icon: <AlertCircle size={14} style={{ color: "#f87171" }} />,
      label: "Unavailable",
      pill: {
        background: "rgba(248,113,113,0.10)",
        border: "0.5px solid rgba(248,113,113,0.25)",
        color: "#f87171",
      },
    },
    loading: {
      icon: <Loader2 size={14} style={{ color: labelColor, animation: "spin 1s linear infinite" }} />,
      label: "Checking...",
      pill: {
        background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.18)",
        border: `0.5px solid ${isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.30)"}`,
        color: labelColor,
      },
    },
  };

  const current = statusConfig[indexStatus.status];

  // Available indexes (future-ready: today just one)
  const availableIndexes = [
    { id: "default", label: "Default (FAISS)", active: true },
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
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Database
            size={16}
            style={{ color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.45)" }}
          />
          <h2
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
              margin: 0,
              fontFamily: fontStack,
            }}
          >
            Search Index
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
            { label: "Engine", value: "FAISS" },
            { label: "Type", value: "Hybrid BM25 + Vector" },
            { label: "Reranker", value: "Cross-encoder" },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                background: isDark ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.18)",
                border: isDark
                  ? "0.5px solid rgba(255,255,255,0.08)"
                  : "0.5px solid rgba(255,255,255,0.35)",
                borderRadius: "12px",
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
            Available Indexes
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {availableIndexes.map((idx) => (
              <div
                key={idx.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: idx.active
                    ? isDark
                      ? "rgba(201,168,76,0.08)"
                      : "rgba(201,168,76,0.06)"
                    : isDark
                      ? "rgba(255,255,255,0.04)"
                      : "rgba(255,255,255,0.12)",
                  border: idx.active
                    ? isDark
                      ? "0.5px solid rgba(201,168,76,0.25)"
                      : "0.5px solid rgba(201,168,76,0.30)"
                    : isDark
                      ? "0.5px solid rgba(255,255,255,0.08)"
                      : "0.5px solid rgba(255,255,255,0.25)",
                  borderRadius: "10px",
                  padding: "10px 14px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
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
                    Active
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
            Index switching will be available in a future release.
          </p>
        </div>
      </div>
    </div>
  );
}
