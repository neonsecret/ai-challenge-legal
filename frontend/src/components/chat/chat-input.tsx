"use client"

import { useRef, useCallback, useEffect, useState } from "react"
import { useTheme } from "next-themes"
import { ArrowUp, StopCircle } from "lucide-react"

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  onFocusRef?: React.MutableRefObject<(() => void) | null>
}

export function ChatInput({ onSend, disabled, onFocusRef }: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const [hasText, setHasText] = useState(false)
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

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

  return (
    <div
      className="relative rounded-2xl"
      style={{
        background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.22)",
        backdropFilter: "blur(32px) saturate(160%)",
        WebkitBackdropFilter: "blur(32px) saturate(160%)",
        border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.55)",
        boxShadow: isDark
          ? "inset 0 1px 0 rgba(255,255,255,0.08)"
          : "inset 0 1px 0 rgba(255,255,255,0.70)",
        transition: "border-color 0.2s ease, background 0.2s ease",
      }}
    >
      <textarea
        ref={ref}
        placeholder="Ask a legal question…"
        className="w-full bg-transparent resize-none outline-none leading-relaxed px-4 pt-4 pb-12 min-h-[56px] max-h-[200px]"
        style={{
          color: isDark ? "rgba(255,255,255,0.85)" : "#2e1f08",
          caretColor: isDark ? "#C9A84C" : "#c9a230",
          fontSize: "13.5px",
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        }}
        placeholder-style={{ color: isDark ? "rgba(255,255,255,0.28)" : "#b29254" } as React.CSSProperties}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        disabled={disabled}
        rows={1}
        aria-label="Legal question input"
      />
      <style>{`
        textarea::placeholder { color: ${isDark ? "rgba(255,255,255,0.30)" : "#b29254"}; }
      `}</style>
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-end px-3 pb-3">
        <button
          onClick={handleSend}
          disabled={disabled || !hasText}
          className="flex items-center justify-center size-8 rounded-xl disabled:opacity-30"
          style={{
            background: sendBg,
            color: sendColor,
            boxShadow: hasText && !disabled ? "0 2px 12px rgba(201,168,76,0.25)" : "none",
            transition: "all 0.18s ease",
            transform: "scale(1)",
          }}
          onMouseEnter={e => { if (hasText && !disabled) (e.currentTarget as HTMLElement).style.transform = "scale(1.08)" }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = "scale(1)" }}
          onMouseDown={e => { (e.currentTarget as HTMLElement).style.transform = "scale(0.94)" }}
          onMouseUp={e => { (e.currentTarget as HTMLElement).style.transform = "scale(1)" }}
          aria-label={disabled ? "Waiting for response" : "Send question"}
        >
          {disabled ? <StopCircle className="size-4" /> : <ArrowUp className="size-4" strokeWidth={2.5} />}
        </button>
      </div>
    </div>
  )
}
