"use client"

import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {FileText} from "lucide-react"
import {useI18n} from "@/lib/i18n"

interface TemplatePickerProps {
    onOpen: () => void
    /** Disabled when 3 documents already exist in this chat */
    disabled: boolean
}

export function TemplatePicker({onOpen, disabled}: TemplatePickerProps) {
    const { t } = useI18n()
    return (
        <button
            onClick={onOpen}
            disabled={disabled}
            title={disabled ? t("template.disabled_tooltip") : t("template.enabled_tooltip")}
            aria-label={t("template.open_picker")}
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
            <span>{t("template.button_label")}</span>
        </button>
    )
}
