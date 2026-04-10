"use client"

import {useRef, useCallback, useEffect, useState} from "react"
import {useColorMode} from "@/lib/color-mode"
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
    const {isDark} = useColorMode()
    const isGlassmorphic = isDark
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
        ? isGlassmorphic
            ? "linear-gradient(135deg, rgba(201,168,76,0.25), rgba(201,168,76,0.15))"
            : isDark ? "linear-gradient(135deg, #C9A84C, #e8cc7a)" : "#5c2e08"
        : isGlassmorphic
            ? "rgba(50,50,50,0.40)"
            : isDark ? "rgba(255,255,255,0.08)" : "rgba(92,46,8,0.12)"

    const sendColor = hasText && !disabled
        ? isGlassmorphic ? "var(--strict-gold-base)" : isDark ? "#0F1623" : "#f5e6d0"
        : isGlassmorphic ? "rgba(255,255,255,0.25)" : isDark ? "rgba(255,255,255,0.30)" : "#b29254"

    const borderColor = focused
        ? isGlassmorphic ? "var(--strict-gold-underbar)" : isDark ? "rgba(201,168,76,0.40)" : "rgba(196,124,0,0.35)"
        : isGlassmorphic ? "var(--strict-input-border)" : isDark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.55)"

    const glowShadow = focused
        ? isGlassmorphic
            ? "var(--strict-input-glow)"
            : isDark
                ? "inset 0 1px 0 rgba(255,255,255,0.10), 0 0 0 3px rgba(201,168,76,0.08), 0 2px 16px rgba(201,168,76,0.10)"
                : "inset 0 1px 0 rgba(255,255,255,0.80), 0 0 0 3px rgba(196,124,0,0.06), 0 2px 16px rgba(196,124,0,0.08)"
        : isGlassmorphic
            ? "inset 0 1px 0 rgba(255,255,255,0.05), 0 4px 16px rgba(0,0,0,0.25)"
            : isDark
                ? "inset 0 1px 0 rgba(255,255,255,0.08)"
                : "inset 0 1px 0 rgba(255,255,255,0.70)"

    return (
        <div
            className="relative"
            style={{
                borderRadius: isGlassmorphic ? 8 : 16,
                background: isGlassmorphic
                    ? focused ? "var(--strict-input-bg-focused)" : "var(--strict-input-bg)"
                    : isDark
                        ? focused ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.06)"
                        : focused ? "rgba(255,255,255,0.30)" : "rgba(255,255,255,0.22)",
                backdropFilter: isGlassmorphic ? "blur(15px)" : "var(--dt-glass-blur)",
                WebkitBackdropFilter: isGlassmorphic ? "blur(15px)" : "var(--dt-glass-blur)",
                border: `${isGlassmorphic ? "1px" : "0.5px"} solid ${borderColor}`,
                boxShadow: glowShadow,
                transition: "border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease",
            }}
        >
      <textarea
          ref={ref}
          suppressHydrationWarning
          placeholder={isGlassmorphic ? "Continue your research..." : t("chat.placeholder")}
          className="w-full bg-transparent resize-none outline-none leading-relaxed px-4 pt-3.5 pb-11 min-h-[52px] max-h-[200px]"
          style={isGlassmorphic ? {
              color: "var(--strict-text-body)",
              caretColor: "var(--strict-gold-base)",
              font: "11px/1 Georgia, serif",
              letterSpacing: "0.01em",
          } : {
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
                    color: isGlassmorphic ? "var(--gm-text-quaternary, rgba(255,255,255,0.22))" : isDark ? "rgba(255,255,255,0.20)" : "rgba(46,31,8,0.25)",
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
                        borderRadius: 7,
                        background: sendBg,
                        color: sendColor,
                        border: isGlassmorphic ? "1px solid rgba(201,168,76, 0.25)" : "none",
                        boxShadow: hasText && !disabled
                            ? isGlassmorphic ? "0 2px 12px rgba(201,168,76,0.20)" : "0 2px 12px rgba(201,168,76,0.25)"
                            : "none",
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
        {isGlassmorphic && (
            <p style={{
                font: "8.5px/1.3 system-ui, sans-serif",
                color: "var(--strict-text-ghost)",
                textAlign: "center",
                margin: "6px 0 0",
                userSelect: "none",
            }}>
                AI-generated legal research. Verify all citations independently.
            </p>
        )}
    )
}
