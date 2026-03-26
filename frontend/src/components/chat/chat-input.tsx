"use client"

import { useRef, useCallback } from "react"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Send } from "lucide-react"

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)

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
        placeholder="Ask a legal question… (Shift+Enter for newline)"
        className="resize-none min-h-[44px] max-h-36 flex-1"
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={1}
      />
      <Button
        onClick={handleSend}
        disabled={disabled}
        size="icon"
        className="size-11 shrink-0"
        aria-label="Send"
      >
        <Send className="size-4" />
      </Button>
    </div>
  )
}
