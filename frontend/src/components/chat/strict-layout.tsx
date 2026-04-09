"use client"

import { useState, type ReactNode } from "react"
import { useIsMobile } from "@/hooks/use-mobile"
import {
    StrictSourceMargin,
    type StrictSourceMarginSource,
} from "./strict-source-margin"
import { StrictSidebarRail } from "./strict-sidebar-rail"

interface StrictLayoutProps {
    children: ReactNode
    sources: StrictSourceMarginSource[]
    onSourceClick?: (id: string) => void
    sourcesVisible?: boolean
}

/**
 * Full Glass Scholar layout wrapper.
 *
 * Desktop:
 *   [Sidebar Rail 44px] | [Reading Area flex-1] | [Source Margin 160px]
 *
 * Mobile:
 *   [Reading Area full-width]
 *   [Collapsible Sources panel at bottom]
 *
 * This is a pure layout wrapper — no chat logic lives here.
 */
export function StrictLayout({
    children,
    sources,
    onSourceClick,
    sourcesVisible = false,
}: StrictLayoutProps) {
    const isMobile = useIsMobile()
    const [sourcesExpanded, setSourcesExpanded] = useState(false)

    return (
        <div
            style={{
                display: "flex",
                flex: 1,
                minHeight: 0,
                minWidth: 0,
                overflow: "hidden",
                background: "var(--strict-glass-bg)",
                backdropFilter: "var(--strict-glass-blur)",
                WebkitBackdropFilter: "var(--strict-glass-blur)",
                border: "1px solid var(--strict-glass-border)",
                borderRadius: isMobile ? 12 : 16,
                boxShadow: "var(--strict-glass-shadow)",
                flexDirection: isMobile ? "column" : "row",
            }}
        >
            {/* Sidebar rail — desktop only */}
            {!isMobile && <StrictSidebarRail />}

            {/* Reading area */}
            <div
                style={{
                    flex: 1,
                    minWidth: 0,
                    minHeight: 0,
                    display: "flex",
                    flexDirection: "column",
                    overflow: "hidden",
                }}
            >
                {children}
            </div>

            {/* Source margin — desktop: right column; mobile: collapsible bottom panel */}
            {isMobile ? (
                sources.length > 0 && sourcesVisible ? (
                    <div
                        style={{
                            borderTop: "1px solid var(--strict-gold-border)",
                            flexShrink: 0,
                        }}
                    >
                        {/* Toggle header */}
                        <button
                            type="button"
                            onClick={() => setSourcesExpanded((v) => !v)}
                            style={{
                                width: "100%",
                                padding: "10px 14px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                background: "var(--strict-glass-recessed)",
                                border: "none",
                                cursor: "pointer",
                                minHeight: "44px",
                            }}
                        >
                            <span
                                style={{
                                    color: "var(--strict-source-label)",
                                    fontSize: 8,
                                    letterSpacing: "0.5px",
                                    textTransform: "uppercase",
                                }}
                            >
                                SOURCES ({sources.length})
                            </span>
                            <span
                                style={{
                                    color: "var(--strict-gold-text)",
                                    fontSize: 10,
                                    opacity: 0.5,
                                    transition: "transform 0.2s ease",
                                    transform: sourcesExpanded
                                        ? "rotate(180deg)"
                                        : "rotate(0deg)",
                                }}
                            >
                                ▾
                            </span>
                        </button>

                        {/* Expandable content — CSS grid for GPU-composited animation */}
                        <div
                            style={{
                                background: "var(--strict-glass-recessed)",
                                display: "grid",
                                gridTemplateRows: sourcesExpanded ? "1fr" : "0fr",
                                transition: "grid-template-rows 0.35s ease",
                                overflow: "hidden",
                            }}
                        >
                            <div style={{ overflow: "hidden" }}>
                                <StrictSourceMargin
                                    sources={sources}
                                    onSourceClick={onSourceClick}
                                    visible={sourcesVisible && sourcesExpanded}
                                    mobile
                                />
                            </div>
                        </div>
                    </div>
                ) : null
            ) : (
                <StrictSourceMargin
                    sources={sources}
                    onSourceClick={onSourceClick}
                    visible={sourcesVisible}
                />
            )}
        </div>
    )
}
