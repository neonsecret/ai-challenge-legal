"use client"

import {useRef, useCallback, useEffect, useState} from "react"
import {useTheme} from "next-themes"
import {ArrowUp, StopCircle} from "lucide-react"
import {useI18n} from "@/lib/i18n"

interface ChatInputProps {
    onSend: (message: string) => void
    disabled?: boolean
    onFocusRef?: React.MutableRefObject<(() => void) | null>
}

export function ChatInput({onSend, disabled, onFocusRef}: ChatInputProps) {
    const ref = useRef<HTMLTextAreaElement>(null)
    const [hasText, setHasText] = useState(false)
    const [focused, setFocused] = useState(false)
    const [mounted, setMounted] = useState(false)
    const {resolvedTheme} = useTheme()
    useEffect(() => setMounted(true), [])
    const isDark = mounted && resolvedTheme === "dark"
    const {t} = useI18n()

    useEffect(() => {
        if (onFocusRef) onFocusRef.current = () => ref.current?.focus()
    }, [onFocusRef])

    const handleSend = useCallback(() => {
        const value = ref.current?.value.trim()
        if (!value || disabled) return
        onSend(value)
        if (ref.current) {
            ref.current.value = ""
            ref.current.style.height = "auto"
            setHasText(false)
        }
    }, [onSend, disabled])

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                handleSend()
            }
        },
        [handleSend]
    )

    const handleInput = useCallback(() => {
        const el = ref.current
        if (!el) return
        el.style.height = "auto"
        el.style.height = Math.min(el.scrollHeight, 200) + "px"
        setHasText(el.value.trim().length > 0)
    }, [])

    const sendBg = hasText && !disabled
        ? isDark ? "linear-gradient(135deg, #C9A84C, #e8cc7a)" : "#5c2e08"
        : isDark ? "rgba(255,255,255,0.08)" : "rgba(92,46,8,0.12)"

    const sendColor = hasText && !disabled
        ? isDark ? "#0F1623" : "#f5e6d0"
        : isDark ? "rgba(255,255,255,0.30)" : "#b29254"

    const borderColor = focused
        ? isDark ? "rgba(201,168,76,0.40)" : "rgba(196,124,0,0.35)"
        : isDark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.55)"

    const glowShadow = focused
        ? isDark
            ? "inset 0 1px 0 rgba(255,255,255,0.10), 0 0 0 3px rgba(201,168,76,0.08), 0 2px 16px rgba(201,168,76,0.10)"
            : "inset 0 1px 0 rgba(255,255,255,0.80), 0 0 0 3px rgba(196,124,0,0.06), 0 2px 16px rgba(196,124,0,0.08)"
        : isDark
            ? "inset 0 1px 0 rgba(255,255,255,0.08)"
            : "inset 0 1px 0 rgba(255,255,255,0.70)"

    return (
        <div
            className="relative rounded-2xl"
            style={{
                background: isDark
                    ? focused ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.06)"
                    : focused ? "rgba(255,255,255,0.30)" : "rgba(255,255,255,0.22)",
                backdropFilter: "blur(32px) saturate(160%)",
                WebkitBackdropFilter: "blur(32px) saturate(160%)",
                border: `0.5px solid ${borderColor}`,
                boxShadow: glowShadow,
                transition: "border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease",
            }}
        >
      <textarea
          ref={ref}
          suppressHydrationWarning
          placeholder={t("chat.placeholder")}
          className="w-full bg-transparent resize-none outline-none leading-relaxed px-4 pt-3.5 pb-11 min-h-[52px] max-h-[200px]"
          style={{
              color: isDark ? "rgba(255,255,255,0.92)" : "#2e1f08",
              caretColor: isDark ? "#C9A84C" : "#c9a230",
              fontSize: "14px",
              fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
              letterSpacing: "-0.006em",
          }}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={disabled}
          rows={1}
          aria-label="Message input"
      />
            <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 pb-2.5">
                <span style={{
                    fontSize: "11px",
                    color: isDark ? "rgba(255,255,255,0.20)" : "rgba(46,31,8,0.25)",
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    userSelect: "none",
                    transition: "opacity 0.2s",
                    opacity: focused && !hasText ? 1 : 0,
                }}>
                    ↵ Enter
                </span>
                <button
                    onClick={handleSend}
                    disabled={disabled || !hasText}
                    className="flex items-center justify-center rounded-xl disabled:opacity-30"
                    style={{
                        width: 32,
                        height: 32,
                        background: sendBg,
                        color: sendColor,
                        boxShadow: hasText && !disabled ? "0 2px 12px rgba(201,168,76,0.25)" : "none",
                        transition: "all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
                        transform: "scale(1)",
                    }}
                    onMouseEnter={e => {
                        if (hasText && !disabled) e.currentTarget.style.transform = "scale(1.08)"
                    }}
                    onMouseLeave={e => {
                        e.currentTarget.style.transform = "scale(1)"
                    }}
                    onMouseDown={e => {
                        e.currentTarget.style.transform = "scale(0.92)"
                    }}
                    onMouseUp={e => {
                        e.currentTarget.style.transform = "scale(1)"
                    }}
                    aria-label={disabled ? "Waiting for response" : "Send message"}
                >
                    {disabled ? <StopCircle className="size-4"/> : <ArrowUp className="size-4" strokeWidth={2.5}/>}
                </button>
            </div>
        </div>
    )
}
