"use client"

import { useRef, useCallback, useEffect } from "react"
import { ArrowUp } from "lucide-react"

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  onFocusRef?: React.MutableRefObject<(() => void) | null>
}

export function ChatInput({ onSend, disabled, onFocusRef }: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)

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
    el.style.height = Math.min(el.scrollHeight, 160) + "px"
  }, [])

  return (
    <div
      className="flex items-end gap-3 rounded-2xl px-4 py-3 transition-all"
      style={{
        background: "rgba(255,255,255,0.05)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.10)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.05)",
      }}
    >
      <textarea
        ref={ref}
        placeholder="Ask a legal question…"
        className="flex-1 bg-transparent resize-none outline-none text-sm leading-relaxed min-h-[24px] max-h-[160px]"
        style={{
          color: "rgba(255,255,255,0.88)",
          caretColor: "#C9A84C",
        }}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        disabled={disabled}
        rows={1}
        aria-label="Legal question input"
      />
      <button
        onClick={handleSend}
        disabled={disabled}
        className="shrink-0 flex items-center justify-center size-8 rounded-xl transition-all disabled:opacity-35"
        style={{
          background: "#C9A84C",
          color: "#0F1623",
        }}
        aria-label="Send question"
      >
        <ArrowUp className="size-4" strokeWidth={2.5} />
      </button>
    </div>
  )
}
