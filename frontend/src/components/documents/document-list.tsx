"use client";

import {useState} from "react";
import {FileText, Trash2} from "lucide-react";
import {useColorMode} from "@/lib/color-mode";
import type {Document} from "./use-documents";

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
    });
}

function formatDateFull(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function isTxtFile(doc: Document): boolean {
    return doc.media_type === "text/plain" || Boolean(doc.filename?.toLowerCase().endsWith(".txt"));
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

    const {isDark} = useColorMode();

    const handleDeleteClick = (documentId: string) => setConfirmingId(documentId);

    const handleConfirmDelete = async (documentId: string) => {
        setDeletingId(documentId);
        setConfirmingId(null);
        await onDelete(documentId);
        setDeletingId(null);
    };

    const labelColor = isDark ? "var(--strict-text-dim, rgba(255,255,255,0.40))" : "rgba(46,31,8,0.45)";
    const textPrimary = isDark ? "var(--strict-text-primary, rgba(255,255,255,0.92))" : "#2e1f08";
    const fontFamily = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

    // ── Loading ───────────────────────────────────────────────────────────────
    if (loading) {
        if (isDark) {
            return (
                <div style={{display: "flex", flexDirection: "column", gap: "4px"}}>
                    {[...Array(3)].map((_, i) => (
                        <div key={i} style={{height: "34px", borderRadius: "5px", background: "rgba(201,168,76,0.04)", animation: "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite"}} />
                    ))}
                </div>
            );
        }
        return (
            <div style={{display: "flex", flexDirection: "column", gap: "8px", fontFamily}}>
                {[...Array(3)].map((_, i) => (
                    <div key={i} style={{height: "48px", borderRadius: "8px", background: "rgba(255,255,255,0.20)", animation: "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite"}} />
                ))}
            </div>
        );
    }

    // ── Empty ─────────────────────────────────────────────────────────────────
    if (documents.length === 0) {
        if (isDark) {
            return (
                <div style={{
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    border: "1px dashed rgba(201,168,76,0.12)", borderRadius: "8px", padding: "28px 16px",
                    textAlign: "center",
                }}>
                    <div style={{fontSize: "18px", color: "rgba(201,168,76,0.25)", marginBottom: "8px"}}>⬚</div>
                    <p style={{fontSize: "11px", color: "rgba(200,210,230,0.22)", margin: 0, fontFamily: "system-ui, sans-serif"}}>No documents uploaded yet</p>
                    <p style={{fontSize: "9px", color: "rgba(200,210,230,0.16)", marginTop: "3px", fontFamily: "system-ui, sans-serif"}}>Upload a PDF or TXT above to get started</p>
                </div>
            );
        }
        return (
            <div style={{display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", border: "1.5px dashed rgba(255,255,255,0.35)", borderRadius: "14px", padding: "48px 24px", textAlign: "center", fontFamily}}>
                <FileText size={32} style={{color: "rgba(46,31,8,0.25)", marginBottom: "12px"}} />
                <p style={{fontSize: "13px", color: labelColor, margin: 0}}>No documents uploaded yet</p>
                <p style={{fontSize: "11px", color: "rgba(46,31,8,0.35)", marginTop: "4px"}}>Upload a PDF or TXT above to get started</p>
            </div>
        );
    }

    // ── Dark mode: mockup PDF item list ───────────────────────────────────────
    if (isDark) {
        return (
            <div style={{display: "flex", flexDirection: "column", gap: "2px"}}>
                {documents.map((doc) => (
                    <div
                        key={doc.document_id}
                        onMouseEnter={() => setHoveredRowId(doc.document_id)}
                        onMouseLeave={() => setHoveredRowId(null)}
                        style={{
                            display: "flex", alignItems: "center", gap: "8px",
                            padding: "6px 8px", borderRadius: "5px",
                            border: "1px solid transparent",
                            background: hoveredRowId === doc.document_id ? "rgba(201,168,76,0.03)" : "transparent",
                            borderColor: hoveredRowId === doc.document_id ? "rgba(201,168,76,0.06)" : "transparent",
                            transition: "all 0.12s",
                        }}
                    >
                        {/* File type badge */}
                        <div style={{
                            width: "22px", height: "22px", borderRadius: "4px",
                            background: "rgba(201,168,76,0.05)",
                            border: "1px solid rgba(201,168,76,0.08)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            flexShrink: 0,
                        }}>
                            <span style={{fontSize: "6px", fontFamily: "system-ui, sans-serif", color: "rgba(201,168,76,0.7)", lineHeight: 1}}>
                                {doc.filename.toLowerCase().endsWith(".txt") ? "TXT" : "PDF"}
                            </span>
                        </div>

                        {/* Name + meta */}
                        <div style={{flex: 1, minWidth: 0}}>
                            <div style={{
                                fontSize: "9px", fontFamily: "Georgia, serif",
                                color: "rgba(255,255,255,0.56)",
                                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            }} title={doc.filename}>
                                {doc.filename}
                            </div>
                            <div style={{fontSize: "7px", fontFamily: "system-ui, sans-serif", color: "rgba(200,210,230,0.22)", marginTop: "1px"}}>
                                {formatSize(doc.size_bytes)} · {formatDate(doc.uploaded_at)}
                            </div>
                        </div>

                        {/* Delete */}
                        <div style={{flexShrink: 0}}>
                            {confirmingId === doc.document_id ? (
                                <div style={{display: "flex", gap: "2px", alignItems: "center"}}>
                                    <button
                                        style={{background: "transparent", border: "none", cursor: "pointer", padding: "2px 5px", fontSize: "9px", color: "#ff8c7a", fontFamily: "system-ui, sans-serif"}}
                                        onClick={() => handleConfirmDelete(doc.document_id)}
                                    >
                                        Yes
                                    </button>
                                    <button
                                        style={{background: "transparent", border: "none", cursor: "pointer", padding: "2px 5px", fontSize: "9px", color: "rgba(200,210,230,0.22)", fontFamily: "system-ui, sans-serif"}}
                                        onClick={() => setConfirmingId(null)}
                                    >
                                        No
                                    </button>
                                </div>
                            ) : (
                                <button
                                    disabled={deletingId === doc.document_id}
                                    onClick={() => handleDeleteClick(doc.document_id)}
                                    onMouseEnter={() => setHoveredDeleteId(doc.document_id)}
                                    onMouseLeave={() => setHoveredDeleteId(null)}
                                    style={{
                                        background: "transparent", border: "none",
                                        cursor: deletingId === doc.document_id ? "default" : "pointer",
                                        padding: "4px", display: "flex", alignItems: "center", justifyContent: "center",
                                        color: hoveredDeleteId === doc.document_id ? "#ff8c7a" : "rgba(200,210,230,0.22)",
                                        transition: "color 0.12s",
                                    }}
                                >
                                    {deletingId === doc.document_id ? (
                                        <span style={{display: "inline-block", width: "10px", height: "10px", borderRadius: "50%", border: "1.5px solid currentColor", borderTopColor: "transparent", animation: "spin 0.6s linear infinite"}} />
                                    ) : (
                                        <Trash2 size={11}/>
                                    )}
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    // ── Light mode: original table design unchanged ───────────────────────────
    return (
        <div style={{borderRadius: "14px", border: "0.5px solid rgba(255,255,255,0.35)", overflow: "hidden", fontFamily}}>
            {/* Header row */}
            <div style={{display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: "16px", background: "rgba(255,255,255,0.15)", borderBottom: "0.5px solid rgba(255,255,255,0.30)", padding: "8px 16px", fontSize: "10px", fontWeight: 500, color: labelColor, textTransform: "uppercase", letterSpacing: "0.05em"}}>
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
                        display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: "16px",
                        alignItems: "center", padding: "12px 16px",
                        borderBottom: index < documents.length - 1 ? "0.5px solid rgba(255,255,255,0.20)" : "none",
                        background: hoveredRowId === doc.document_id ? "rgba(255,255,255,0.12)" : "transparent",
                        transition: "background 0.12s",
                    }}
                    onMouseEnter={() => setHoveredRowId(doc.document_id)}
                    onMouseLeave={() => setHoveredRowId(null)}
                >
                    <div style={{display: "flex", alignItems: "center", gap: "8px", minWidth: 0}}>
                        <FileText size={16} style={{flexShrink: 0, color: "#c47c00"}}/>
                        <span style={{overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "13px", fontWeight: 500, color: textPrimary}} title={doc.filename}>{doc.filename}</span>
                    </div>
                    <span className="hidden sm:block" style={{width: "80px", textAlign: "right", fontSize: "12px", color: labelColor, fontVariantNumeric: "tabular-nums"}}>{formatSize(doc.size_bytes)}</span>
                    <span className="hidden sm:block" style={{width: "144px", textAlign: "right", fontSize: "12px", color: labelColor, fontVariantNumeric: "tabular-nums"}}>{formatDateFull(doc.uploaded_at)}</span>
                    <div style={{width: "64px", display: "flex", justifyContent: "flex-end"}}>
                        {confirmingId === doc.document_id ? (
                            <div style={{display: "flex", alignItems: "center", gap: "4px"}}>
                                <button style={{background: "transparent", border: "none", borderRadius: "4px", padding: "2px 6px", fontSize: "11px", color: "#8b3520", cursor: "pointer"}} onClick={() => handleConfirmDelete(doc.document_id)}>Yes</button>
                                <button style={{background: "transparent", border: "none", borderRadius: "4px", padding: "2px 6px", fontSize: "11px", color: labelColor, cursor: "pointer"}} onClick={() => setConfirmingId(null)}>No</button>
                            </div>
                        ) : (
                            <button
                                style={{background: "transparent", border: "none", cursor: "pointer", padding: "4px", borderRadius: "4px", display: "flex", alignItems: "center", justifyContent: "center", color: hoveredDeleteId === doc.document_id ? "#8b3520" : labelColor, transition: "color 0.12s"}}
                                disabled={deletingId === doc.document_id}
                                onClick={() => handleDeleteClick(doc.document_id)}
                                onMouseEnter={() => setHoveredDeleteId(doc.document_id)}
                                onMouseLeave={() => setHoveredDeleteId(null)}
                            >
                                {deletingId === doc.document_id ? (
                                    <span style={{display: "inline-block", width: "12px", height: "12px", borderRadius: "50%", border: "2px solid currentColor", borderTopColor: "transparent", animation: "spin 0.6s linear infinite"}} />
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
