"use client";

import { useState, type ReactNode } from "react";
import { useColorMode } from "@/lib/color-mode";

interface CollapsibleTurnProps {
    question: string;
    sourceCount: number;
    isLatest: boolean;
    children: ReactNode;
}

export function CollapsibleTurn({ question, sourceCount, isLatest, children }: CollapsibleTurnProps) {
    const { isDark } = useColorMode();
    const [expanded, setExpanded] = useState(false);

    // Light mode or latest turn: always show full content
    if (!isDark || isLatest) {
        return <>{children}</>;
    }

    return (
        <div>
            {/* Collapsed row */}
            {!expanded && (
                <button
                    onClick={() => setExpanded(true)}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        width: "100%",
                        padding: "6px 10px",
                        borderRadius: 6,
                        background: "rgba(201,168,76, 0.02)",
                        border: "1px solid rgba(201,168,76, 0.05)",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "background 0.15s, border-color 0.15s",
                    }}
                    onMouseEnter={e => {
                        e.currentTarget.style.background = "rgba(201,168,76, 0.04)";
                        e.currentTarget.style.borderColor = "rgba(201,168,76, 0.08)";
                    }}
                    onMouseLeave={e => {
                        e.currentTarget.style.background = "rgba(201,168,76, 0.02)";
                        e.currentTarget.style.borderColor = "rgba(201,168,76, 0.05)";
                    }}
                >
                    <span style={{ color: "var(--strict-text-dim)", fontSize: 11, flexShrink: 0 }}>›</span>
                    <span style={{
                        flex: 1,
                        fontSize: 11,
                        fontFamily: "Georgia, serif",
                        fontStyle: "italic",
                        color: "var(--strict-text-secondary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>
                        {question}
                    </span>
                    {sourceCount > 0 && (
                        <span style={{ fontSize: 10, color: "var(--strict-text-dim)", flexShrink: 0, fontFamily: "system-ui" }}>
                            {sourceCount} {sourceCount === 1 ? "source" : "sources"}
                        </span>
                    )}
                </button>
            )}

            {/* Expanded content — CSS grid for smooth animation */}
            <div style={{
                display: "grid",
                gridTemplateRows: expanded ? "1fr" : "0fr",
                transition: "grid-template-rows 0.3s ease",
                overflow: "hidden",
            }}>
                <div style={{ minHeight: 0 }}>
                    {expanded && (
                        <button
                            onClick={() => setExpanded(false)}
                            style={{
                                display: "flex", alignItems: "center", gap: 6,
                                padding: "4px 10px 8px", width: "100%",
                                background: "none", border: "none", cursor: "pointer",
                                color: "var(--strict-text-dim)", fontSize: 10, fontFamily: "system-ui",
                            }}
                        >
                            ‹ Collapse
                        </button>
                    )}
                    {children}
                </div>
            </div>
        </div>
    );
}
