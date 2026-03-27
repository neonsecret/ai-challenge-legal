"use client";

import { useMemo, useState } from "react";
import { useTheme } from "next-themes";
import { Folder, FileText, ChevronDown, ChevronRight, Trash2, CheckCircle2 } from "lucide-react";
import type { Document } from "./use-documents";

interface FolderViewProps {
  documents: Document[];
  loading: boolean;
  onDelete: (documentId: string) => Promise<boolean>;
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
    year: "numeric",
  });
}

function getFolderName(filename: string): string {
  // Group by the portion before the first underscore, dash, or space
  // E.g. "civil_code_2024.pdf" → "Civil Code"
  // "commercial-law.pdf"        → "Commercial Law"
  // "document.pdf"              → "Documents"
  const stem = filename.replace(/\.pdf$/i, "");
  const separator = stem.match(/[_\-\s]/)?.[0];
  if (separator) {
    const prefix = stem.split(separator)[0];
    // Capitalize
    return prefix.charAt(0).toUpperCase() + prefix.slice(1).replace(/_/g, " ");
  }
  return "Documents";
}

export function FolderView({ documents, loading, onDelete }: FolderViewProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [hoveredRowId, setHoveredRowId] = useState<string | null>(null);

  const fontStack = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";
  const labelColor = isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)";
  const textColor = isDark ? "rgba(255,255,255,0.82)" : "#1e1208";

  const folders = useMemo<DocumentFolder[]>(() => {
    const map = new Map<string, DocumentFolder>();
    for (const doc of documents) {
      const name = getFolderName(doc.filename);
      if (!map.has(name)) {
        map.set(name, { name, docs: [], totalBytes: 0 });
      }
      const folder = map.get(name)!;
      folder.docs.push(doc);
      folder.totalBytes += doc.size_bytes;
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [documents]);

  const toggleFolder = (name: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const handleDelete = async (documentId: string) => {
    setDeletingId(documentId);
    setConfirmingId(null);
    await onDelete(documentId);
    setDeletingId(null);
  };

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontFamily: fontStack }}>
        {[...Array(2)].map((_, i) => (
          <div
            key={i}
            style={{
              height: "72px",
              borderRadius: "14px",
              background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.18)",
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
          fontFamily: fontStack,
        }}
      >
        <Folder
          size={32}
          style={{
            color: isDark ? "rgba(255,255,255,0.22)" : "rgba(46,31,8,0.22)",
            marginBottom: "12px",
          }}
        />
        <p style={{ fontSize: "13px", color: labelColor, margin: 0 }}>
          No documents yet
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
    <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontFamily: fontStack }}>
      {folders.map((folder) => {
        const isExpanded = expandedFolders.has(folder.name);

        return (
          <div
            key={folder.name}
            style={{
              background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.14)",
              border: isDark
                ? "0.5px solid rgba(255,255,255,0.10)"
                : "0.5px solid rgba(255,255,255,0.35)",
              borderRadius: "14px",
              overflow: "hidden",
            }}
          >
            {/* Folder header row */}
            <button
              onClick={() => toggleFolder(folder.name)}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "14px 16px",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              {/* Folder icon */}
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "10px",
                  background: isDark
                    ? "rgba(201,168,76,0.10)"
                    : "rgba(201,168,76,0.08)",
                  border: isDark
                    ? "0.5px solid rgba(201,168,76,0.22)"
                    : "0.5px solid rgba(201,168,76,0.28)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <Folder size={18} style={{ color: "#C9A84C" }} />
              </div>

              {/* Folder name + meta */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: textColor,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {folder.name}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: labelColor,
                    marginTop: "2px",
                  }}
                >
                  {folder.docs.length} {folder.docs.length === 1 ? "document" : "documents"}
                  {" · "}
                  {formatSize(folder.totalBytes)}
                </div>
              </div>

              {/* Expand chevron */}
              <div style={{ color: labelColor, flexShrink: 0 }}>
                {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </div>
            </button>

            {/* Expanded document list */}
            {isExpanded && (
              <div
                style={{
                  borderTop: isDark
                    ? "0.5px solid rgba(255,255,255,0.08)"
                    : "0.5px solid rgba(255,255,255,0.25)",
                }}
              >
                {folder.docs.map((doc, idx) => (
                  <div
                    key={doc.document_id}
                    onMouseEnter={() => setHoveredRowId(doc.document_id)}
                    onMouseLeave={() => setHoveredRowId(null)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      padding: "11px 16px 11px 24px",
                      borderBottom:
                        idx < folder.docs.length - 1
                          ? isDark
                            ? "0.5px solid rgba(255,255,255,0.06)"
                            : "0.5px solid rgba(255,255,255,0.18)"
                          : "none",
                      background:
                        hoveredRowId === doc.document_id
                          ? isDark
                            ? "rgba(255,255,255,0.04)"
                            : "rgba(255,255,255,0.10)"
                          : "transparent",
                      transition: "background 0.12s",
                    }}
                  >
                    <FileText
                      size={15}
                      style={{ flexShrink: 0, color: "#c47c00" }}
                    />

                    {/* Filename */}
                    <div
                      style={{
                        flex: 1,
                        minWidth: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        fontSize: "13px",
                        fontWeight: 500,
                        color: textColor,
                      }}
                      title={doc.filename}
                    >
                      {doc.filename}
                    </div>

                    {/* Indexed badge */}
                    {doc.indexed && (
                      <span title="Indexed" style={{ display: "inline-flex" }}>
                        <CheckCircle2
                          size={13}
                          style={{
                            flexShrink: 0,
                            color: isDark ? "#4ade80" : "#16a34a",
                          }}
                        />
                      </span>
                    )}

                    {/* Size */}
                    <span
                      className="hidden sm:block"
                      style={{
                        flexShrink: 0,
                        width: "72px",
                        textAlign: "right",
                        fontSize: "11px",
                        color: labelColor,
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {formatSize(doc.size_bytes)}
                    </span>

                    {/* Date */}
                    <span
                      className="hidden sm:block"
                      style={{
                        flexShrink: 0,
                        width: "88px",
                        textAlign: "right",
                        fontSize: "11px",
                        color: labelColor,
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {formatDate(doc.uploaded_at)}
                    </span>

                    {/* Delete */}
                    <div
                      style={{
                        flexShrink: 0,
                        width: "64px",
                        display: "flex",
                        justifyContent: "flex-end",
                      }}
                    >
                      {confirmingId === doc.document_id ? (
                        <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                          <button
                            style={{
                              background: "transparent",
                              border: "none",
                              cursor: "pointer",
                              padding: "2px 6px",
                              fontSize: "11px",
                              color: isDark ? "#ff8c7a" : "#8b3520",
                              fontFamily: fontStack,
                            }}
                            onClick={() => handleDelete(doc.document_id)}
                          >
                            Yes
                          </button>
                          <button
                            style={{
                              background: "transparent",
                              border: "none",
                              cursor: "pointer",
                              padding: "2px 6px",
                              fontSize: "11px",
                              color: labelColor,
                              fontFamily: fontStack,
                            }}
                            onClick={() => setConfirmingId(null)}
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <button
                          disabled={deletingId === doc.document_id}
                          onClick={() => setConfirmingId(doc.document_id)}
                          style={{
                            background: "transparent",
                            border: "none",
                            cursor: deletingId === doc.document_id ? "default" : "pointer",
                            padding: "4px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color:
                              hoveredRowId === doc.document_id
                                ? isDark ? "#ff8c7a" : "#8b3520"
                                : labelColor,
                            transition: "color 0.12s",
                          }}
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
                            <Trash2 size={14} />
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
