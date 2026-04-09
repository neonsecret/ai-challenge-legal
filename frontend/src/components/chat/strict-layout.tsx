"use client"

import { type ReactNode } from "react"
import {
    StrictSourceMargin,
    type StrictSourceMarginSource,
} from "./strict-source-margin"

interface StrictLayoutProps {
    children: ReactNode
    sources: StrictSourceMarginSource[]
    onSourceClick?: (id: string) => void
    sourcesVisible?: boolean
}

/**
 * Full Glass Scholar layout wrapper.
 *
 * One glass pane containing:
 *   [Sidebar Rail 44px] | [Reading Area flex-1] | [Source Margin 160px]
 *
 * This is a pure layout wrapper — no chat logic lives here.
 */
export function StrictLayout({
    children,
    sources,
    onSourceClick,
    sourcesVisible = false,
}: StrictLayoutProps) {
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
                borderRadius: 16,
                boxShadow: "var(--strict-glass-shadow)",
            }}
        >
            {/* Sidebar rail — 44px */}
            <div
                style={{
                    width: 44,
                    flexShrink: 0,
                    background: "var(--strict-glass-recessed)",
                    borderRight: "1px solid var(--strict-gold-border)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    paddingTop: 14,
                    gap: 10,
                }}
            >
                {/* Logo circle */}
                <div
                    style={{
                        width: 22,
                        height: 22,
                        borderRadius: "50%",
                        border: "1px solid var(--strict-gold-border-active)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 8,
                        color: "var(--strict-source-label)",
                        flexShrink: 0,
                    }}
                >
                    V
                </div>

                {/* Icon placeholders */}
                {[0, 1, 2].map((i) => (
                    <div
                        key={i}
                        style={{
                            width: 16,
                            height: 16,
                            borderRadius: 4,
                            background: "rgba(255,255,255,0.04)",
                            flexShrink: 0,
                        }}
                    />
                ))}
            </div>

            {/* Reading area — flex-1 */}
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

            {/* Source margin */}
            <StrictSourceMargin
                sources={sources}
                onSourceClick={onSourceClick}
                visible={sourcesVisible}
            />
        </div>
    )
}
