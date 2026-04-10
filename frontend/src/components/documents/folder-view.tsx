"use client";

import {useMemo, useState, useCallback} from "react";
import {useColorMode} from "@/lib/color-mode";
import {Folder, ChevronDown, ChevronRight, Trash2, CheckCircle2, Pencil, Check, X} from "lucide-react";
import type {Document} from "./use-documents";
import {useI18n} from "@/lib/i18n";

const API_BASE = `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/v1`;

interface FolderViewProps {
    documents: Document[];
    loading: boolean;
    onDelete: (documentId: string) => Promise<boolean>;
    onRefresh?: () => void;
}

interface DocumentFolder {
    name: string;
    docs: Document[];
    totalBytes: number;
}

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

export function FolderView({documents, loading, onDelete, onRefresh}: FolderViewProps) {
    const {isDark} = useColorMode();
    const {t} = useI18n();

    const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [hoveredRowId, setHoveredRowId] = useState<string | null>(null);
    const [renamingFolder, setRenamingFolder] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState("");

    const fontStack = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";
    const labelColor = isDark ? "var(--strict-text-dim, rgba(255,255,255,0.40))" : "rgba(46,31,8,0.45)";
    const textColor = isDark ? "var(--strict-text-primary, rgba(255,255,255,0.92))" : "#1e1208";

    const folders = useMemo<DocumentFolder[]>(() => {
        const map = new Map<string, DocumentFolder>();
        for (const doc of documents) {
            const name = doc.collection ?? "My Documents";
            if (!map.has(name)) map.set(name, {name, docs: [], totalBytes: 0});
            const folder = map.get(name)!;
            folder.docs.push(doc);
            folder.totalBytes += doc.size_bytes;
        }
        return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
    }, [documents]);

    const handleRename = useCallback(async (oldName: string, newName: string) => {
        if (!newName.trim() || newName === oldName) {
            setRenamingFolder(null);
            return;
        }
        try {
            const res = await fetch(`${API_BASE}/documents/collections/rename`, {
                method: "PATCH",
                credentials: "include",
                headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                body: JSON.stringify({old_name: oldName, new_name: newName.trim()}),
            });
            if (res.ok) {
                setRenamingFolder(null);
                onRefresh?.();
            }
        } catch {
            // ignore
        }
    }, [onRefresh]);

    const toggleFolder = (name: string) => {
        setExpandedFolders((prev) => {
            const next = new Set(prev);
            if (next.has(name)) next.delete(name);
            else next.add(name);
            return next;
        });
    };

    const handleDelete = async (documentId: string) => {
        setDeletingId(documentId);
        setConfirmingId(null);
        await onDelete(documentId);
        setDeletingId(null);
    };

    // ── Loading skeleton ──────────────────────────────────────────────────────
    if (loading) {
        if (isDark) {
            return (
                <div style={{display: "flex", flexDirection: "column", gap: "6px"}}>
                    {[...Array(2)].map((_, i) => (
                        <div key={i} style={{height: "34px", borderRadius: "5px", background: "rgba(201,168,76,0.04)", animation: "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite"}} />
                    ))}
                </div>
            );
        }
        return (
            <div style={{display: "flex", flexDirection: "column", gap: "10px", fontFamily: fontStack}}>
                {[...Array(2)].map((_, i) => (
                    <div key={i} style={{height: "72px", borderRadius: "14px", background: "rgba(255,255,255,0.18)", animation: "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite"}} />
                ))}
            </div>
        );
    }

    // ── Empty state ───────────────────────────────────────────────────────────
    if (documents.length === 0) {
        if (isDark) {
            return (
                <div style={{
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    border: "1px dashed rgba(201,168,76,0.15)", borderRadius: "12px", padding: "36px 20px",
                    textAlign: "center",
                }}>
                    <div style={{fontSize: "18px", color: "rgba(201,168,76,0.25)", marginBottom: "10px"}}>⬚</div>
                    <p style={{fontSize: "13px", fontFamily: "Georgia, serif", color: "rgba(255,255,255,0.56)", margin: 0}}>
                        {t("documents.no_documents")}
                    </p>
                    <p style={{fontSize: "10px", color: "rgba(200,210,230,0.30)", marginTop: "4px", fontFamily: "system-ui, sans-serif"}}>
                        {t("documents.upload_to_start")}
                    </p>
                </div>
            );
        }
        return (
            <div style={{display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", border: "1.5px dashed rgba(255,255,255,0.35)", borderRadius: "14px", padding: "48px 24px", textAlign: "center", fontFamily: fontStack}}>
                <Folder size={32} style={{color: "rgba(46,31,8,0.22)", marginBottom: "12px"}} />
                <p style={{fontSize: "13px", color: labelColor, margin: 0}}>{t("documents.no_documents")}</p>
                <p style={{fontSize: "11px", color: "rgba(46,31,8,0.35)", marginTop: "4px"}}>{t("documents.upload_to_start")}</p>
            </div>
        );
    }

    // ── Dark mode: mockup-matched folder rows ─────────────────────────────────
    if (isDark) {
        return (
            <div style={{display: "flex", flexDirection: "column", gap: "0"}}>
                {folders.map((folder, fi) => {
                    const isExpanded = expandedFolders.has(folder.name);
                    return (
                        <div key={folder.name}>
                            {/* Gold gradient separator between folders */}
                            {fi > 0 && (
                                <div style={{
                                    height: "1px",
                                    background: "linear-gradient(90deg, rgba(201,168,76,0.12), rgba(201,168,76,0.02))",
                                    margin: "4px 8px 4px",
                                }} />
                            )}

                            {/* Folder header row */}
                            <div
                                style={{
                                    display: "flex", alignItems: "center", gap: "6px",
                                    padding: "5px 8px", borderRadius: "5px",
                                    background: "rgba(201,168,76,0.025)",
                                    border: "1px solid rgba(201,168,76,0.06)",
                                    cursor: "pointer", marginBottom: isExpanded ? "3px" : "0",
                                    transition: "background 0.15s, border-color 0.15s, box-shadow 0.15s",
                                }}
                                onClick={() => toggleFolder(folder.name)}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = "rgba(201,168,76,0.04)";
                                    e.currentTarget.style.borderColor = "rgba(201,168,76,0.12)";
                                    e.currentTarget.style.boxShadow = "0 2px 8px rgba(201,168,76,0.04)";
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = "rgba(201,168,76,0.025)";
                                    e.currentTarget.style.borderColor = "rgba(201,168,76,0.06)";
                                    e.currentTarget.style.boxShadow = "none";
                                }}
                            >
                                {/* Folder SVG icon */}
                                <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="rgba(201,168,76,0.7)" strokeWidth="1.4" style={{flexShrink: 0}}>
                                    <path d="M2 4.5V13a1 1 0 001 1h10a1 1 0 001-1V6a1 1 0 00-1-1H8L6.5 3H3a1 1 0 00-1 1.5z"/>
                                </svg>

                                {/* Folder name */}
                                {renamingFolder === folder.name ? (
                                    <div style={{flex: 1, display: "flex", alignItems: "center", gap: "4px"}} onClick={(e) => e.stopPropagation()}>
                                        <input
                                            autoFocus
                                            value={renameValue}
                                            onChange={(e) => setRenameValue(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter") handleRename(folder.name, renameValue);
                                                if (e.key === "Escape") setRenamingFolder(null);
                                            }}
                                            style={{
                                                flex: 1, fontSize: "9px", color: "rgba(230,235,245,0.88)",
                                                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(201,168,76,0.30)",
                                                borderRadius: "4px", padding: "2px 6px", outline: "none",
                                                fontFamily: "system-ui, sans-serif",
                                            }}
                                        />
                                        <button onClick={(e) => { e.stopPropagation(); handleRename(folder.name, renameValue); }}
                                            style={{background: "none", border: "none", cursor: "pointer", padding: "2px"}}>
                                            <Check size={11} style={{color: "#4ade80"}}/>
                                        </button>
                                        <button onClick={(e) => { e.stopPropagation(); setRenamingFolder(null); }}
                                            style={{background: "none", border: "none", cursor: "pointer", padding: "2px"}}>
                                            <X size={11} style={{color: "rgba(255,255,255,0.4)"}}/>
                                        </button>
                                    </div>
                                ) : (
                                    <span style={{flex: 1, fontSize: "13px", lineHeight: 1.3, fontFamily: "Georgia, serif", color: "rgba(230,235,245,0.66)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"}}>
                                        {folder.name}
                                    </span>
                                )}

                                {/* Doc count */}
                                <span style={{fontSize: "9px", lineHeight: 1, fontFamily: "system-ui, sans-serif", color: "rgba(200,210,230,0.22)", flexShrink: 0}}>
                                    {folder.docs.length} {folder.docs.length === 1 ? t("documents.document") : t("documents.documents")}
                                </span>

                                {/* Rename button */}
                                {renamingFolder !== folder.name && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setRenamingFolder(folder.name); setRenameValue(folder.name); }}
                                        title="Rename collection"
                                        style={{background: "none", border: "none", cursor: "pointer", padding: "2px", color: "rgba(200,210,230,0.22)", flexShrink: 0, display: "flex", alignItems: "center"}}
                                        onMouseEnter={(e) => { e.currentTarget.style.color = "rgba(201,168,76,0.7)"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(200,210,230,0.22)"; }}
                                    >
                                        <Pencil size={9}/>
                                    </button>
                                )}

                                {/* Chevron */}
                                <div style={{color: "rgba(201,168,76,0.5)", flexShrink: 0, display: "flex", alignItems: "center"}}>
                                    {isExpanded ? <ChevronDown size={10}/> : <ChevronRight size={10}/>}
                                </div>
                            </div>

                            {/* Expanded PDF items */}
                            {isExpanded && (
                                <div style={{paddingLeft: "18px", marginBottom: "2px"}}>
                                    {folder.docs.map((doc) => (
                                        <div
                                            key={doc.document_id}
                                            onMouseEnter={() => setHoveredRowId(doc.document_id)}
                                            onMouseLeave={() => setHoveredRowId(null)}
                                            style={{
                                                display: "flex", alignItems: "center", gap: "10px",
                                                padding: "8px 0",
                                                borderBottom: "1px solid rgba(201,168,76,0.04)",
                                                background: hoveredRowId === doc.document_id ? "rgba(201,168,76,0.015)" : "transparent",
                                                transition: "background 0.12s",
                                            }}
                                        >
                                            {/* PDF badge */}
                                            <div style={{
                                                width: "28px", height: "28px", borderRadius: "6px",
                                                background: "rgba(201,168,76,0.04)",
                                                border: "1px solid rgba(201,168,76,0.06)",
                                                display: "flex", alignItems: "center", justifyContent: "center",
                                                flexShrink: 0,
                                            }}>
                                                <span style={{fontSize: "10px", lineHeight: 1, fontFamily: "system-ui, sans-serif", color: "rgba(201,168,76,0.4)"}}>PDF</span>
                                            </div>

                                            {/* Name + meta */}
                                            <div style={{flex: 1, minWidth: 0}}>
                                                <div style={{
                                                    fontSize: "12px", lineHeight: 1.3, fontFamily: "Georgia, serif",
                                                    color: "rgba(230,235,245,0.66)",
                                                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                                }} title={doc.filename}>
                                                    {doc.filename}
                                                </div>
                                                <div style={{fontSize: "9px", lineHeight: 1.2, fontFamily: "system-ui, sans-serif", color: "rgba(200,210,230,0.3)", marginTop: "2px"}}>
                                                    {formatSize(doc.size_bytes)} · {formatDate(doc.uploaded_at)}
                                                    {doc.indexed && <span style={{marginLeft: "4px", color: "rgba(74,222,128,0.6)"}}>✓</span>}
                                                </div>
                                            </div>

                                            {/* Delete */}
                                            <div style={{flexShrink: 0}}>
                                                {confirmingId === doc.document_id ? (
                                                    <div style={{display: "flex", gap: "2px", alignItems: "center"}}>
                                                        <button
                                                            style={{background: "transparent", border: "none", cursor: "pointer", padding: "2px 5px", fontSize: "9px", color: "#ff8c7a", fontFamily: "system-ui, sans-serif"}}
                                                            onClick={() => handleDelete(doc.document_id)}
                                                        >
                                                            {t("documents.confirm_yes")}
                                                        </button>
                                                        <button
                                                            style={{background: "transparent", border: "none", cursor: "pointer", padding: "2px 5px", fontSize: "9px", color: "rgba(200,210,230,0.22)", fontFamily: "system-ui, sans-serif"}}
                                                            onClick={() => setConfirmingId(null)}
                                                        >
                                                            {t("documents.confirm_no")}
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        disabled={deletingId === doc.document_id}
                                                        onClick={() => setConfirmingId(doc.document_id)}
                                                        style={{
                                                            background: "transparent", border: "none",
                                                            cursor: deletingId === doc.document_id ? "default" : "pointer",
                                                            padding: "4px", display: "flex", alignItems: "center", justifyContent: "center",
                                                            color: hoveredRowId === doc.document_id ? "#f87171" : "rgba(200,210,230,0.22)",
                                                            transition: "color 0.12s",
                                                        }}
                                                    >
                                                        {deletingId === doc.document_id ? (
                                                            <span style={{display: "inline-block", width: "10px", height: "10px", borderRadius: "50%", border: "1.5px solid currentColor", borderTopColor: "transparent", animation: "spin 0.6s linear infinite"}} />
                                                        ) : (
                                                            <Trash2 size={11} strokeWidth={1.8} />
                                                        )}
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        );
    }

    // ── Light mode: original design unchanged ─────────────────────────────────
    return (
        <div style={{display: "flex", flexDirection: "column", gap: "8px", fontFamily: fontStack}}>
            {folders.map((folder) => {
                const isExpanded = expandedFolders.has(folder.name);
                return (
                    <div
                        key={folder.name}
                        style={{
                            background: "rgba(255,255,255,0.14)",
                            border: "0.5px solid rgba(255,255,255,0.35)",
                            borderRadius: "14px",
                            overflow: "hidden",
                        }}
                    >
                        <button
                            onClick={() => toggleFolder(folder.name)}
                            style={{width: "100%", display: "flex", alignItems: "center", gap: "12px", padding: "14px 16px", background: "transparent", border: "none", cursor: "pointer", textAlign: "left"}}
                        >
                            <div style={{width: "36px", height: "36px", borderRadius: "10px", background: "rgba(201,168,76,0.08)", border: "0.5px solid rgba(201,168,76,0.28)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0}}>
                                <Folder size={18} style={{color: "#C9A84C"}}/>
                            </div>
                            <div style={{flex: 1, minWidth: 0}}>
                                {renamingFolder === folder.name ? (
                                    <div style={{display: "flex", alignItems: "center", gap: "6px"}} onClick={(e) => e.stopPropagation()}>
                                        <input autoFocus value={renameValue} onChange={(e) => setRenameValue(e.target.value)}
                                            onKeyDown={(e) => { if (e.key === "Enter") handleRename(folder.name, renameValue); if (e.key === "Escape") setRenamingFolder(null); }}
                                            style={{fontSize: "13px", fontWeight: 600, color: textColor, background: "rgba(0,0,0,0.04)", border: "1px solid rgba(201,168,76,0.4)", borderRadius: "6px", padding: "2px 8px", width: "160px", outline: "none", fontFamily: fontStack}} />
                                        <button onClick={(e) => { e.stopPropagation(); handleRename(folder.name, renameValue); }} style={{background: "none", border: "none", cursor: "pointer", padding: "2px"}}><Check size={14} style={{color: "#4ade80"}}/></button>
                                        <button onClick={(e) => { e.stopPropagation(); setRenamingFolder(null); }} style={{background: "none", border: "none", cursor: "pointer", padding: "2px"}}><X size={14} style={{color: "rgba(0,0,0,0.3)"}}/></button>
                                    </div>
                                ) : (
                                    <div style={{fontSize: "13px", fontWeight: 600, color: textColor, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"}}>{folder.name}</div>
                                )}
                                <div style={{fontSize: "11px", color: labelColor, marginTop: "2px"}}>
                                    {folder.docs.length} {folder.docs.length === 1 ? t("documents.document") : t("documents.documents")} · {formatSize(folder.totalBytes)}
                                </div>
                            </div>
                            {renamingFolder !== folder.name && (
                                <button onClick={(e) => { e.stopPropagation(); setRenamingFolder(folder.name); setRenameValue(folder.name); }} title="Rename collection"
                                    style={{background: "none", border: "none", cursor: "pointer", color: labelColor, padding: "4px", flexShrink: 0, opacity: 0.6, transition: "opacity 0.15s"}}
                                    onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                                    onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.6")}>
                                    <Pencil size={14}/>
                                </button>
                            )}
                            <div style={{color: labelColor, flexShrink: 0}}>
                                {isExpanded ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}
                            </div>
                        </button>
                        {isExpanded && (
                            <div style={{borderTop: "0.5px solid rgba(255,255,255,0.25)"}}>
                                {folder.docs.map((doc, idx) => (
                                    <div
                                        key={doc.document_id}
                                        onMouseEnter={() => setHoveredRowId(doc.document_id)}
                                        onMouseLeave={() => setHoveredRowId(null)}
                                        style={{
                                            display: "flex", alignItems: "center", gap: "12px",
                                            padding: "11px 16px 11px 24px",
                                            borderBottom: idx < folder.docs.length - 1 ? "0.5px solid rgba(255,255,255,0.18)" : "none",
                                            background: hoveredRowId === doc.document_id ? "rgba(255,255,255,0.10)" : "transparent",
                                            transition: "background 0.12s",
                                        }}
                                    >
                                        <CheckCircle2 size={15} style={{flexShrink: 0, color: doc.indexed ? "#16a34a" : "rgba(46,31,8,0.22)"}}/>
                                        <div style={{flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "13px", fontWeight: 500, color: textColor}} title={doc.filename}>{doc.filename}</div>
                                        <span className="hidden sm:block" style={{flexShrink: 0, width: "72px", textAlign: "right", fontSize: "11px", color: labelColor}}>{formatSize(doc.size_bytes)}</span>
                                        <span className="hidden sm:block" style={{flexShrink: 0, width: "88px", textAlign: "right", fontSize: "11px", color: labelColor}}>{formatDate(doc.uploaded_at)}</span>
                                        <div style={{flexShrink: 0, width: "64px", display: "flex", justifyContent: "flex-end"}}>
                                            {confirmingId === doc.document_id ? (
                                                <div style={{display: "flex", gap: "4px", alignItems: "center"}}>
                                                    <button style={{background: "transparent", border: "none", cursor: "pointer", padding: "2px 6px", fontSize: "11px", color: "#8b3520", fontFamily: fontStack}} onClick={() => handleDelete(doc.document_id)}>{t("documents.confirm_yes")}</button>
                                                    <button style={{background: "transparent", border: "none", cursor: "pointer", padding: "2px 6px", fontSize: "11px", color: labelColor, fontFamily: fontStack}} onClick={() => setConfirmingId(null)}>{t("documents.confirm_no")}</button>
                                                </div>
                                            ) : (
                                                <button disabled={deletingId === doc.document_id} onClick={() => setConfirmingId(doc.document_id)}
                                                    style={{background: "transparent", border: "none", cursor: deletingId === doc.document_id ? "default" : "pointer", padding: "4px", display: "flex", alignItems: "center", justifyContent: "center", color: hoveredRowId === doc.document_id ? "#8b3520" : labelColor, transition: "color 0.12s"}}>
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
                        )}
                    </div>
                );
            })}
        </div>
    );
}
