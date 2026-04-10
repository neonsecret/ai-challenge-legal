"use client"

import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {FileText} from "lucide-react"

interface TemplatePickerProps {
    onOpen: () => void
    /** Disabled when 3 documents already exist in this chat */
    disabled: boolean
}

export function TemplatePicker({onOpen, disabled}: TemplatePickerProps) {
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
                background: "var(--doc-gold-action-bg)",
                border: "1px solid var(--doc-gold-action-border)",
                color: "var(--doc-gold-action-color)",
                fontFamily: FONT.sans,
                fontSize: TYPE_SCALE.xs,
                transition: `all ${TIMING.fast} ${EASE.out}`,
                flexShrink: 0,
            }}
            onMouseEnter={(e) => {
                if (disabled) return
                e.currentTarget.style.background = "var(--doc-gold-action-hover-bg)"
                e.currentTarget.style.borderColor = "var(--doc-gold-action-hover-border)"
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--doc-gold-action-bg)"
                e.currentTarget.style.borderColor = "var(--doc-gold-action-border)"
            }}
        >
            <FileText size={12} strokeWidth={1.8} />
            <span>Draft</span>
        </button>
    )
}
