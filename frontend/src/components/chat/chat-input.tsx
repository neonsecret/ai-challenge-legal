"use client"

import { useRef, useCallback, useEffect, useState } from "react"
import { ArrowUp, StopCircle } from "lucide-react"

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  onFocusRef?: React.MutableRefObject<(() => void) | null>
}

export function ChatInput({ onSend, disabled, onFocusRef }: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const [hasText, setHasText] = useState(false)

  useEffect(() => {
    if (onFocusRef) {
      onFocusRef.current = () => ref.current?.focus()
    }
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

  return (
    <div
      className="relative rounded-2xl transition-all duration-200"
      style={{
        background: "rgba(255,240,215,0.20)",
        backdropFilter: "blur(24px) saturate(140%)",
        WebkitBackdropFilter: "blur(24px) saturate(140%)",
        border: "1px solid rgba(255,255,255,0.50)",
        boxShadow: "0 8px 32px rgba(100,50,0,0.20), inset 0 1px 0 rgba(255,255,255,0.40)",
      }}
    >
      <textarea
        ref={ref}
        placeholder="Ask a legal question…"
        className="w-full bg-transparent resize-none outline-none text-sm leading-relaxed px-4 pt-4 pb-12 min-h-[56px] max-h-[200px] placeholder:text-[#b29254]"
        style={{
          color: "#2e1f08",
          caretColor: "#c9a230",
        }}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        disabled={disabled}
        rows={1}
        aria-label="Legal question input"
      />
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 pb-3">
        <span
          className="text-[11px] select-none"
          style={{ color: "rgba(92,46,8,0.35)" }}
        >
          ⌘K to focus · Shift+Enter for newline
        </span>
        <button
          onClick={handleSend}
          disabled={disabled || !hasText}
          className="flex items-center justify-center size-8 rounded-xl transition-all disabled:opacity-30"
          style={{
            background: hasText && !disabled ? "#5c2e08" : "rgba(92,46,8,0.12)",
            color: hasText && !disabled ? "#f5e6d0" : "#b29254",
            boxShadow: hasText && !disabled ? "0 2px 12px rgba(92,46,8,0.35)" : "none",
          }}
          aria-label={disabled ? "Waiting for response" : "Send question"}
        >
          {disabled ? (
            <StopCircle className="size-4" />
          ) : (
            <ArrowUp className="size-4" strokeWidth={2.5} />
          )}
        </button>
      </div>
    </div>
  )
}
