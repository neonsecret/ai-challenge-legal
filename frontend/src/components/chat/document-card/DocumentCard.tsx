"use client"

import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {Eye, Download, FileCode} from "lucide-react"
import type {ChatDocument} from "@/types/documents"

const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

interface DocumentCardProps {
    doc: ChatDocument
    chatId: string
    onPreview: (docId: string) => void
}

export function DocumentCard({doc, chatId, onPreview}: DocumentCardProps) {
    const pdfUrl = `${API_BASE}/api/v1/conversations/${encodeURIComponent(chatId)}/documents/${encodeURIComponent(doc.doc_id)}/pdf`
    const texUrl = `${API_BASE}/api/v1/conversations/${encodeURIComponent(chatId)}/documents/${encodeURIComponent(doc.doc_id)}/tex`
    const isReady = doc.fields !== undefined && Object.keys(doc.fields).length > 0

    return (
        <div style={{
            display: "flex",
            alignItems: "center",
            gap: SPACE[3],
            padding: `${SPACE[3]}px ${SPACE[4]}px`,
            borderRadius: RADIUS.lg,
            background: "var(--doc-gold-card-bg)",
            border: "1px solid var(--doc-gold-card-border)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
        }}>
            {/* Doc icon */}
            <div style={{
                width: 32,
                height: 32,
                borderRadius: RADIUS.md,
                background: "var(--doc-gold-icon-bg)",
                border: "1px solid var(--doc-gold-icon-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                color: "var(--doc-text-label)",
            }}>
                <span style={{fontSize: TYPE_SCALE.md}}>⊞</span>
            </div>

            {/* Info */}
            <div style={{flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2}}>
                <span style={{
                    fontFamily: "Georgia, serif",
                    fontSize: TYPE_SCALE.sm,
                    color: "var(--doc-text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                }}>
                    {doc.template_name}
                </span>
                <span style={{
                    fontFamily: FONT.sans,
                    fontSize: TYPE_SCALE.xs,
                    color: "var(--doc-text-secondary)",
                }}>
                    v{doc.version} · Generated at {new Date(doc.generated_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}
                </span>
            </div>

            {/* Actions — hidden until fields are populated */}
            {isReady ? (
                <div style={{display: "flex", gap: SPACE[2], flexShrink: 0}}>
                    <ActionButton
                        label="Preview"
                        icon={<Eye size={13} strokeWidth={1.8} />}
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
                            background: "var(--doc-btn-glass-bg)",
                            border: "1px solid var(--doc-btn-glass-border)",
                            color: "var(--doc-text-secondary)",
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
                    <a
                        href={texUrl}
                        download={`${doc.template_name}-v${doc.version}.tex`}
                        title="Download LaTeX source"
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: SPACE[1],
                            padding: `${SPACE[1]}px ${SPACE[2]}px`,
                            borderRadius: RADIUS.sm,
                            background: "var(--doc-btn-glass-bg)",
                            border: "1px solid var(--doc-btn-glass-border)",
                            color: "var(--doc-text-secondary)",
                            fontFamily: FONT.sans,
                            fontSize: TYPE_SCALE.xs,
                            textDecoration: "none",
                            transition: `all ${TIMING.fast} ${EASE.out}`,
                            cursor: "pointer",
                        }}
                    >
                        <FileCode size={13} strokeWidth={1.8} />
                        .tex
                    </a>
                </div>
            ) : (
                <div style={{flexShrink: 0}}>
                    <style>{`
                        @keyframes doc-field-pulse {
                            0%, 100% { opacity: 0.45; }
                            50% { opacity: 1; }
                        }
                    `}</style>
                    <span style={{
                        fontFamily: FONT.sans,
                        fontSize: TYPE_SCALE.xs,
                        color: "var(--doc-text-secondary)",
                        animation: "doc-field-pulse 1.6s ease-in-out infinite",
                        display: "inline-block",
                    }}>
                        AI is filling fields…
                    </span>
                </div>
            )}
        </div>
    )
}

function ActionButton({label, icon, onClick}: {label: string; icon: React.ReactNode; onClick: () => void}) {
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
                background: "var(--doc-gold-action-bg)",
                border: "1px solid var(--doc-gold-action-border)",
                color: "var(--doc-gold-action-color)",
                fontFamily: FONT.sans,
                fontSize: TYPE_SCALE.xs,
                transition: `all ${TIMING.fast} ${EASE.out}`,
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--doc-gold-action-hover-bg)"
                e.currentTarget.style.borderColor = "var(--doc-gold-action-hover-border)"
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--doc-gold-action-bg)"
                e.currentTarget.style.borderColor = "var(--doc-gold-action-border)"
            }}
        >
            {icon}
            {label}
        </button>
    )
}
