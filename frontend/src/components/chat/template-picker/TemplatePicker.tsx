"use client"

import {useColorMode} from "@/lib/color-mode"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {FileText} from "lucide-react"

interface TemplatePickerProps {
    onOpen: () => void
    /** Disabled when 3 documents already exist in this chat */
    disabled: boolean
}

export function TemplatePicker({onOpen, disabled}: TemplatePickerProps) {
    const {isDark} = useColorMode()

    return (
        <button
            onClick={onOpen}
            disabled={disabled}
            title={disabled ? "Maximum 3 documents per chat reached" : "Generate a legal document from a template"}
            aria-label="Open template picker"
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: SPACE[1],
                padding: `${SPACE[1]}px ${SPACE[2]}px`,
                borderRadius: RADIUS.md,
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.38 : 1,
                background: isDark ? "rgba(201,168,76,0.06)" : "rgba(196,124,0,0.06)",
                border: isDark
                    ? "1px solid rgba(201,168,76,0.12)"
                    : "0.5px solid rgba(196,124,0,0.18)",
                color: isDark ? "var(--strict-gold-text)" : "#7a4a00",
                fontFamily: FONT.sans,
                fontSize: TYPE_SCALE.xs,
                transition: `all ${TIMING.fast} ${EASE.out}`,
                flexShrink: 0,
            }}
            onMouseEnter={(e) => {
                if (disabled) return
                e.currentTarget.style.background = isDark
                    ? "rgba(201,168,76,0.12)"
                    : "rgba(196,124,0,0.10)"
                e.currentTarget.style.borderColor = isDark
                    ? "rgba(201,168,76,0.22)"
                    : "rgba(196,124,0,0.28)"
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.background = isDark
                    ? "rgba(201,168,76,0.06)"
                    : "rgba(196,124,0,0.06)"
                e.currentTarget.style.borderColor = isDark
                    ? "rgba(201,168,76,0.12)"
                    : "rgba(196,124,0,0.18)"
            }}
        >
            <FileText size={12} strokeWidth={1.8} />
            <span>Draft</span>
        </button>
    )
}
