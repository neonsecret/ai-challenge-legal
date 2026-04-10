"use client"

import {useRef, useCallback, useEffect, useState} from "react"
import {useColorMode} from "@/lib/color-mode"
import {ArrowUp, StopCircle, X} from "lucide-react"
import {useI18n} from "@/lib/i18n"
import {TemplatePicker} from "@/components/chat/template-picker/TemplatePicker"
import {TemplatePanel} from "@/components/chat/template-picker/TemplatePanel"

interface ChatInputProps {
    onSend: (message: string) => void
    disabled?: boolean
    onFocusRef?: React.MutableRefObject<(() => void) | null>
    /** Present when a chat session is active; gates template picker visibility. */
    chatId?: string
    /** Called when user picks a template from the panel. */
    onTemplateSelect?: (slug: string) => void
    /** Disables picker when chat already has 3 documents. */
    documentCount?: number
    /** Slug of the template queued for the next send. Shown as a pill below input. */
    pendingTemplateSlug?: string | null
    /** Called when user dismisses the pending template pill. */
    onClearTemplate?: () => void
}

function formatTemplateName(slug: string): string {
    if (slug === "__custom__") return "Custom document"
    return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export function ChatInput({onSend, disabled, onFocusRef, chatId, onTemplateSelect, documentCount = 0, pendingTemplateSlug, onClearTemplate}: ChatInputProps) {
    const ref = useRef<HTMLTextAreaElement>(null)
    const [hasText, setHasText] = useState(false)
    const [focused, setFocused] = useState(false)
    const [panelOpen, setPanelOpen] = useState(false)
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

    const handleTemplateSelect = useCallback((slug: string) => {
        setPanelOpen(false)
        onTemplateSelect?.(slug)
    }, [onTemplateSelect])

    const sendBg = hasText && !disabled
        ? isGlassmorphic
            ? "linear-gradient(135deg, rgba(201,168,76,0.22), rgba(201,168,76,0.12))"
            : isDark ? "linear-gradient(135deg, #C9A84C, #e8cc7a)" : "#5c2e08"
        : isGlassmorphic
            ? "rgba(50,50,50,0.40)"
            : isDark ? "rgba(255,255,255,0.08)" : "rgba(92,46,8,0.12)"

    const sendColor = hasText && !disabled
        ? isGlassmorphic ? "var(--strict-gold-base)" : isDark ? "#0F1623" : "#f5e6d0"
        : isGlassmorphic ? "rgba(255,255,255,0.25)" : isDark ? "rgba(255,255,255,0.30)" : "#b29254"

    const borderColor = focused
        ? isGlassmorphic ? "rgba(201,168,76, 0.2)" : isDark ? "rgba(201,168,76,0.40)" : "rgba(196,124,0,0.35)"
        : isGlassmorphic ? "var(--strict-input-border)" : isDark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.55)"

    const glowShadow = focused
        ? isGlassmorphic
            ? "0 0 0 2px rgba(201,168,76, 0.08)"
            : isDark
                ? "inset 0 1px 0 rgba(255,255,255,0.10), 0 0 0 3px rgba(201,168,76,0.08), 0 2px 16px rgba(201,168,76,0.10)"
                : "inset 0 1px 0 rgba(255,255,255,0.80), 0 0 0 3px rgba(196,124,0,0.06), 0 2px 16px rgba(196,124,0,0.08)"
        : isGlassmorphic
            ? "inset 0 1px 0 rgba(255,255,255,0.05), 0 4px 16px rgba(0,0,0,0.25)"
            : isDark
                ? "inset 0 1px 0 rgba(255,255,255,0.08)"
                : "inset 0 1px 0 rgba(255,255,255,0.70)"

    return (
        <>
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
                    placeholder={isGlassmorphic ? "Continue your research\u2026" : t("chat.placeholder")}
                    className="w-full bg-transparent resize-none outline-none leading-relaxed px-4 pt-3.5 pb-11 min-h-[52px] max-h-[200px]"
                    style={isGlassmorphic ? {
                        color: "var(--strict-text-body)",
                        caretColor: "var(--strict-gold-base)",
                        font: "14px/1.5 Georgia, serif",
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
                    <div style={{display: "flex", alignItems: "center", gap: 6}}>
                        <span style={{
                            fontSize: "11px",
                            color: isGlassmorphic ? "rgba(255,255,255,0.22)" : isDark ? "rgba(255,255,255,0.20)" : "rgba(46,31,8,0.25)",
                            fontFamily: "system-ui, sans-serif",
                            userSelect: "none",
                            transition: "opacity 0.2s",
                            opacity: focused && !hasText ? 1 : 0,
                        }}>
                            ↵ Enter
                        </span>
                        {chatId && onTemplateSelect && (
                            <TemplatePicker
                                onOpen={() => setPanelOpen(true)}
                                disabled={documentCount >= 3}
                            />
                        )}
                    </div>
                    <button
                        onClick={handleSend}
                        disabled={disabled || !hasText}
                        className="flex items-center justify-center disabled:opacity-30"
                        style={{
                            width: 32,
                            height: 32,
                            borderRadius: isGlassmorphic ? 7 : 12,
                            background: sendBg,
                            color: sendColor,
                            border: isGlassmorphic
                                ? `1px solid ${hasText && !disabled ? "rgba(201,168,76, 0.25)" : "rgba(201,168,76, 0.08)"}`
                                : "none",
                            boxShadow: hasText && !disabled
                                ? isGlassmorphic ? "0 2px 12px rgba(201,168,76,0.20)" : "0 2px 12px rgba(201,168,76,0.25)"
                                : "none",
                            transition: "all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
                            transform: "scale(1)",
                        }}
                        onMouseEnter={e => {
                            if (hasText && !disabled) e.currentTarget.style.transform = "scale(1.06)"
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
                        aria-label={disabled ? "Stop generating" : "Send message"}
                    >
                        {disabled ? <StopCircle className="size-4"/> : <ArrowUp className="size-4" strokeWidth={2.5}/>}
                    </button>
                </div>
            </div>

            {/* Pending template pill — shown below the input when a template is queued */}
            {pendingTemplateSlug && (
                <div
                    role="status"
                    aria-live="polite"
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        marginTop: 6,
                        padding: "4px 10px 4px 8px",
                        borderRadius: 20,
                        background: "var(--doc-pill-active-bg)",
                        border: "1px solid var(--doc-pill-active-border)",
                        width: "fit-content",
                        maxWidth: "100%",
                    }}
                >
                    <span style={{fontSize: 12, lineHeight: 1}}>📄</span>
                    <span style={{
                        fontFamily: "system-ui, sans-serif",
                        fontSize: 11,
                        color: "var(--doc-pill-active-color)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>
                        {formatTemplateName(pendingTemplateSlug)} — press Enter to draft
                    </span>
                    {onClearTemplate && (
                        <button
                            onClick={onClearTemplate}
                            aria-label="Clear selected template"
                            style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                width: 14,
                                height: 14,
                                borderRadius: "50%",
                                background: "var(--doc-close-btn-bg)",
                                border: "none",
                                cursor: "pointer",
                                color: "var(--doc-pill-active-color)",
                                flexShrink: 0,
                                padding: 0,
                            }}
                        >
                            <X size={9} strokeWidth={2.5} />
                        </button>
                    )}
                </div>
            )}

            {/* Template panel — portal-like, rendered outside the input box */}
            {chatId && onTemplateSelect && (
                <TemplatePanel
                    open={panelOpen}
                    onClose={() => setPanelOpen(false)}
                    onSelect={handleTemplateSelect}
                />
            )}
        </>
    )
}
