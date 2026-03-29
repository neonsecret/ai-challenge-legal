"use client";

import {useState, useEffect} from "react";
import {FileText, Trash2} from "lucide-react";
import {useTheme} from "next-themes";
import type {Document} from "./use-documents";

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

interface DocumentListProps {
    documents: Document[];
    loading: boolean;
    onDelete: (documentId: string) => Promise<boolean>;
}

export function DocumentList({documents, loading, onDelete}: DocumentListProps) {
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [hoveredRowId, setHoveredRowId] = useState<string | null>(null);
    const [hoveredDeleteId, setHoveredDeleteId] = useState<string | null>(null);

    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    const isDark = mounted && resolvedTheme === "dark";

    const handleDeleteClick = (documentId: string) => {
        setConfirmingId(documentId);
    };

    const handleConfirmDelete = async (documentId: string) => {
        setDeletingId(documentId);
        setConfirmingId(null);
        await onDelete(documentId);
        setDeletingId(null);
    };

    const font: React.CSSProperties = {
        fontFamily:
            "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
    };

    if (loading) {
        return (
            <div style={{display: "flex", flexDirection: "column", gap: "8px", ...font}}>
                {[...Array(3)].map((_, i) => (
                    <div
                        key={i}
                        style={{
                            height: "48px",
                            borderRadius: "8px",
                            background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.20)",
                            animation: "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite",
                        }}
                    />
                ))}
            </div>
        );
    }

    if (documents.length === 0) {
        return (
            <div
                style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    border: isDark
                        ? "1.5px dashed rgba(255,255,255,0.14)"
                        : "1.5px dashed rgba(255,255,255,0.35)",
                    borderRadius: "14px",
                    padding: "48px 24px",
                    textAlign: "center",
                    ...font,
                }}
            >
                <FileText
                    size={32}
                    style={{
                        color: isDark ? "rgba(255,255,255,0.25)" : "rgba(46,31,8,0.25)",
                        marginBottom: "12px",
                    }}
                />
                <p
                    style={{
                        fontSize: "13px",
                        color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.45)",
                        margin: 0,
                    }}
                >
                    No documents uploaded yet
                </p>
                <p
                    style={{
                        fontSize: "11px",
                        color: isDark ? "rgba(255,255,255,0.25)" : "rgba(46,31,8,0.35)",
                        marginTop: "4px",
                    }}
                >
                    Upload a PDF above to get started
                </p>
            </div>
        );
    }

    return (
        <div
            style={{
                borderRadius: "14px",
                border: isDark
                    ? "0.5px solid rgba(255,255,255,0.12)"
                    : "0.5px solid rgba(255,255,255,0.35)",
                overflow: "hidden",
                ...font,
            }}
        >
            {/* Header row */}
            <div
                style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(0,1fr) auto",
                    gap: "16px",
                    background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.15)",
                    borderBottom: isDark
                        ? "0.5px solid rgba(255,255,255,0.10)"
                        : "0.5px solid rgba(255,255,255,0.30)",
                    padding: "8px 16px",
                    fontSize: "10px",
                    fontWeight: 500,
                    color: isDark ? "rgba(255,255,255,0.38)" : "rgba(46,31,8,0.45)",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                }}
            >
                <span>Filename</span>
                <span className="hidden sm:block" style={{width: "80px", textAlign: "right"}}>Size</span>
                <span className="hidden sm:block" style={{width: "144px", textAlign: "right"}}>Uploaded</span>
                <span style={{width: "64px", textAlign: "right"}}>Actions</span>
            </div>

            {/* Document rows */}
            {documents.map((doc, index) => (
                <div
                    key={doc.document_id}
                    style={{
                        display: "grid",
                        gridTemplateColumns: "minmax(0,1fr) auto",
                        gap: "16px",
                        alignItems: "center",
                        padding: "12px 16px",
                        borderBottom:
                            index < documents.length - 1
                                ? isDark
                                    ? "0.5px solid rgba(255,255,255,0.08)"
                                    : "0.5px solid rgba(255,255,255,0.20)"
                                : "none",
                        background:
                            hoveredRowId === doc.document_id
                                ? isDark
                                    ? "rgba(255,255,255,0.05)"
                                    : "rgba(255,255,255,0.12)"
                                : "transparent",
                        transition: "background 0.12s",
                    }}
                    onMouseEnter={() => setHoveredRowId(doc.document_id)}
                    onMouseLeave={() => setHoveredRowId(null)}
                >
                    <div
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            minWidth: 0,
                        }}
                    >
                        <FileText
                            size={16}
                            style={{flexShrink: 0, color: "#c47c00"}}
                        />
                        <span
                            style={{
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                fontSize: "13px",
                                fontWeight: 500,
                                color: isDark ? "rgba(255,255,255,0.80)" : "#2e1f08",
                            }}
                            title={doc.filename}
                        >
              {doc.filename}
            </span>
                    </div>

                    <span
                        className="hidden sm:block"
                        style={{
                            width: "80px",
                            textAlign: "right",
                            fontSize: "12px",
                            color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.50)",
                            fontVariantNumeric: "tabular-nums",
                        }}
                    >
            {formatSize(doc.size_bytes)}
          </span>

                    <span
                        className="hidden sm:block"
                        style={{
                            width: "144px",
                            textAlign: "right",
                            fontSize: "12px",
                            color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.50)",
                            fontVariantNumeric: "tabular-nums",
                        }}
                    >
            {formatDate(doc.uploaded_at)}
          </span>

                    <div
                        style={{
                            width: "64px",
                            display: "flex",
                            justifyContent: "flex-end",
                        }}
                    >
                        {confirmingId === doc.document_id ? (
                            <div
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                }}
                            >
                                <button
                                    style={{
                                        background: "transparent",
                                        border: "none",
                                        borderRadius: "4px",
                                        padding: "2px 6px",
                                        fontSize: "11px",
                                        color: isDark ? "#ff8c7a" : "#8b3520",
                                        cursor: "pointer",
                                    }}
                                    onClick={() => handleConfirmDelete(doc.document_id)}
                                >
                                    Yes
                                </button>
                                <button
                                    style={{
                                        background: "transparent",
                                        border: "none",
                                        borderRadius: "4px",
                                        padding: "2px 6px",
                                        fontSize: "11px",
                                        color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.50)",
                                        cursor: "pointer",
                                    }}
                                    onClick={() => setConfirmingId(null)}
                                >
                                    No
                                </button>
                            </div>
                        ) : (
                            <button
                                style={{
                                    background: "transparent",
                                    border: "none",
                                    cursor: "pointer",
                                    padding: "4px",
                                    borderRadius: "4px",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    color:
                                        hoveredDeleteId === doc.document_id
                                            ? isDark
                                                ? "#ff8c7a"
                                                : "#8b3520"
                                            : isDark
                                                ? "rgba(255,255,255,0.35)"
                                                : "rgba(46,31,8,0.40)",
                                    transition: "color 0.12s",
                                }}
                                disabled={deletingId === doc.document_id}
                                onClick={() => handleDeleteClick(doc.document_id)}
                                onMouseEnter={() => setHoveredDeleteId(doc.document_id)}
                                onMouseLeave={() => setHoveredDeleteId(null)}
                            >
                                {deletingId === doc.document_id ? (
                                    <span
                                        style={{
                                            display: "inline-block",
                                            width: "12px",
                                            height: "12px",
                                            borderRadius: "50%",
                                            border: "2px solid currentColor",
                                            borderTopColor: "transparent",
                                            animation: "spin 0.6s linear infinite",
                                        }}
                                    />
                                ) : (
                                    <Trash2 size={14}/>
                                )}
                            </button>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
