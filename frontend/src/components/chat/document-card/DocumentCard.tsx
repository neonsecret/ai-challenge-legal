"use client"

import {useColorMode} from "@/lib/color-mode"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {Eye, Download} from "lucide-react"
import type {ChatDocument} from "@/types/documents"

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

interface DocumentCardProps {
    doc: ChatDocument
    chatId: string
    onPreview: (docId: string) => void
}

export function DocumentCard({doc, chatId, onPreview}: DocumentCardProps) {
    const {isDark} = useColorMode()

    const pdfUrl = `${API_BASE}/api/chats/${encodeURIComponent(chatId)}/documents/${encodeURIComponent(doc.doc_id)}/pdf`

    return (
        <div style={{
            display: "flex",
            alignItems: "center",
            gap: SPACE[3],
            padding: `${SPACE[3]}px ${SPACE[4]}px`,
            borderRadius: RADIUS.lg,
            background: isDark ? "rgba(201,168,76,0.04)" : "rgba(196,124,0,0.04)",
            border: isDark
                ? "1px solid rgba(201,168,76,0.12)"
                : "0.5px solid rgba(196,124,0,0.18)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
        }}>
            {/* Doc icon */}
            <div style={{
                width: 32,
                height: 32,
                borderRadius: RADIUS.md,
                background: isDark ? "rgba(201,168,76,0.10)" : "rgba(196,124,0,0.08)",
                border: isDark
                    ? "1px solid rgba(201,168,76,0.18)"
                    : "0.5px solid rgba(196,124,0,0.22)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                color: isDark ? "var(--strict-gold-text)" : "#7a4a00",
            }}>
                <span style={{fontSize: TYPE_SCALE.md}}>⊞</span>
            </div>

            {/* Info */}
            <div style={{flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2}}>
                <span style={{
                    fontFamily: "Georgia, serif",
                    fontSize: TYPE_SCALE.sm,
                    color: isDark ? "var(--strict-text-primary)" : "#1a1006",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                }}>
                    {doc.template_name}
                </span>
                <span style={{
                    fontFamily: FONT.sans,
                    fontSize: TYPE_SCALE.xs,
                    color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a",
                }}>
                    v{doc.version}
                </span>
            </div>

            {/* Actions */}
            <div style={{display: "flex", gap: SPACE[2], flexShrink: 0}}>
                <ActionButton
                    label="Preview"
                    icon={<Eye size={13} strokeWidth={1.8} />}
                    isDark={isDark}
                    onClick={() => onPreview(doc.doc_id)}
                />
                <a
                    href={pdfUrl}
                    download={`${doc.template_name}-v${doc.version}.pdf`}
                    title="Download PDF"
                    style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: SPACE[1],
                        padding: `${SPACE[1]}px ${SPACE[2]}px`,
                        borderRadius: RADIUS.sm,
                        background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.55)",
                        border: isDark
                            ? "1px solid rgba(255,255,255,0.08)"
                            : "0.5px solid rgba(255,255,255,0.60)",
                        color: isDark ? "var(--strict-text-secondary)" : "#5c3d1a",
                        fontFamily: FONT.sans,
                        fontSize: TYPE_SCALE.xs,
                        textDecoration: "none",
                        transition: `all ${TIMING.fast} ${EASE.out}`,
                        cursor: "pointer",
                    }}
                >
                    <Download size={13} strokeWidth={1.8} />
                    PDF
                </a>
            </div>
        </div>
    )
}

function ActionButton({label, icon, isDark, onClick}: {label: string; icon: React.ReactNode; isDark: boolean; onClick: () => void}) {
    return (
        <button
            onClick={onClick}
            title={label}
            aria-label={label}
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: SPACE[1],
                padding: `${SPACE[1]}px ${SPACE[2]}px`,
                borderRadius: RADIUS.sm,
                cursor: "pointer",
                background: isDark ? "rgba(201,168,76,0.06)" : "rgba(196,124,0,0.06)",
                border: isDark
                    ? "1px solid rgba(201,168,76,0.12)"
                    : "0.5px solid rgba(196,124,0,0.18)",
                color: isDark ? "var(--strict-gold-text)" : "#7a4a00",
                fontFamily: FONT.sans,
                fontSize: TYPE_SCALE.xs,
                transition: `all ${TIMING.fast} ${EASE.out}`,
            }}
            onMouseEnter={(e) => {
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
            {icon}
            {label}
        </button>
    )
}
