"use client"

import { useRef, useCallback, useEffect } from "react"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Send } from "lucide-react"

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  /** When provided, the parent can set this ref to a function that focuses the input (Cmd+K support). */
  onFocusRef?: React.MutableRefObject<(() => void) | null>
}

export function ChatInput({ onSend, disabled, onFocusRef }: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)

  // Expose focus function to parent via ref
  useEffect(() => {
    if (onFocusRef) {
      onFocusRef.current = () => ref.current?.focus()
    }
  }, [onFocusRef])

  const handleSend = useCallback(() => {
    const value = ref.current?.value.trim()
    if (!value || disabled) return
    onSend(value)
    if (ref.current) ref.current.value = ""
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

  return (
    <div className="flex gap-2 items-end">
      <Textarea
        ref={ref}
        placeholder="Ask a legal question…"
        className="resize-none min-h-[44px] max-h-36 flex-1"
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={1}
        aria-label="Legal question input"
      />
      <Button
        onClick={handleSend}
        disabled={disabled}
        size="icon"
        className="size-11 shrink-0"
        aria-label="Send question"
      >
        <Send className="size-4" />
      </Button>
    </div>
  )
}
