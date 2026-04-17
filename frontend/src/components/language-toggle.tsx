"use client"

import { useState, useRef, useEffect, startTransition } from "react"
import {useTheme} from "@/lib/theme"
import { useI18n, LOCALES, type Locale } from "@/lib/i18n"
import { useIsMobile } from "@/hooks/use-mobile"

export function LanguageToggle() {
    const { locale, setLocale } = useI18n()
    const { resolvedTheme } = useTheme()
    const [open, setOpen] = useState(false)
    const [mounted, setMounted] = useState(false)
    const [openUp, setOpenUp] = useState(false)
    const ref = useRef<HTMLDivElement>(null)
    const buttonRef = useRef<HTMLButtonElement>(null)
    const isMobile = useIsMobile()

    useEffect(() => startTransition(() => setMounted(true)), [])

    // Close on outside click
    useEffect(() => {
        if (!open) return
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener("mousedown", handler)
        return () => document.removeEventListener("mousedown", handler)
    }, [open])

    const isDark = mounted && resolvedTheme === "dark"
    const current = LOCALES.find((l) => l.code === locale) ?? LOCALES[0]

    const inactiveColor = isDark ? "rgba(255,255,255,0.42)" : "rgba(46,31,8,0.48)"
    const activeColor = isDark ? "#C9A84C" : "#5c2e08"

    return (
        <div ref={ref} style={{ position: "relative" }}>
            {/* Trigger button */}
            <button
                ref={buttonRef}
                suppressHydrationWarning
                onClick={() => {
                    setOpen((v) => {
                        if (!v && buttonRef.current) {
                            const rect = buttonRef.current.getBoundingClientRect()
                            setOpenUp(rect.bottom + 250 > window.innerHeight)
                        }
                        return !v
                    })
                }}
                style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: isMobile ? "6px 10px" : "7px 12px",
                    borderRadius: "10px",
                    background: open
                        ? isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)"
                        : "transparent",
                    border: "0.5px solid transparent",
                    cursor: "pointer",
                    transition: "all 0.14s ease",
                    color: open ? activeColor : inactiveColor,
                }}
                onMouseEnter={(e) => {
                    if (!open) e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)"
                }}
                onMouseLeave={(e) => {
                    if (!open) e.currentTarget.style.background = "transparent"
                }}
            >
                <span
                    suppressHydrationWarning
                    style={{
                        fontSize: isMobile ? "11px" : "12px",
                        fontWeight: 600,
                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        letterSpacing: "0.06em",
                        lineHeight: 1,
                    }}
                >
                    {current.code.toUpperCase()}
                </span>
            </button>

            {/* Dropdown */}
            {open && (
                <div
                    style={{
                        position: "absolute",
                        ...(openUp
                            ? { bottom: "calc(100% + 8px)" }
                            : { top: "calc(100% + 8px)" }),
                        left: "50%",
                        transform: "translateX(-50%)",
                        minWidth: "80px",
                        padding: "4px",
                        borderRadius: "14px",
                        background: isDark
                            ? "rgba(15,22,35,0.92)"
                            : "rgba(255,250,235,0.85)",
                        backdropFilter: "blur(32px) saturate(180%)",
                        WebkitBackdropFilter: "blur(32px) saturate(180%)",
                        border: isDark
                            ? "0.5px solid rgba(255,255,255,0.12)"
                            : "0.5px solid rgba(255,255,255,0.42)",
                        boxShadow: isDark
                            ? "0 8px 32px rgba(0,0,0,0.50)"
                            : "0 8px 32px rgba(100,50,0,0.15)",
                        zIndex: 100,
                    }}
                >
                    {LOCALES.map((l) => {
                        const isActive = l.code === locale
                        return (
                            <button
                                key={l.code}
                                onClick={() => {
                                    setLocale(l.code as Locale)
                                    setOpen(false)
                                }}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: "100%",
                                    padding: "8px 12px",
                                    borderRadius: "10px",
                                    border: "none",
                                    cursor: "pointer",
                                    transition: "all 0.12s ease",
                                    background: isActive
                                        ? isDark ? "rgba(201,168,76,0.16)" : "rgba(255,255,255,0.35)"
                                        : "transparent",
                                    color: isActive ? activeColor : (isDark ? "rgba(255,255,255,0.70)" : "rgba(46,31,8,0.70)"),
                                    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                                    fontSize: "12px",
                                    fontWeight: isActive ? 700 : 500,
                                    letterSpacing: "0.06em",
                                    textAlign: "center",
                                }}
                                onMouseEnter={(e) => {
                                    if (!isActive) e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.20)"
                                }}
                                onMouseLeave={(e) => {
                                    if (!isActive) e.currentTarget.style.background = "transparent"
                                }}
                            >
                                {l.code.toUpperCase()}
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
