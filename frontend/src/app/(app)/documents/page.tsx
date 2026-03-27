"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { UploadZone } from "@/components/documents/upload-zone";
import { FolderView } from "@/components/documents/folder-view";
import { ReindexButton } from "@/components/documents/reindex-button";
import { IndexInfoPanel } from "@/components/documents/index-info-panel";
import { useDocuments } from "@/components/documents/use-documents";

export default function DocumentsPage() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted && resolvedTheme === "dark";

  const {
    documents,
    loading,
    error,
    uploadProgress,
    reindexJob,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    triggerReindex,
  } = useDocuments();

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const glassCard: React.CSSProperties = {
    background: isDark
      ? "rgba(255,255,255,0.06)"
      : "rgba(255,250,235,0.22)",
    backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    border: isDark
      ? "0.5px solid rgba(255,255,255,0.12)"
      : "0.5px solid rgba(255,255,255,0.38)",
    borderRadius: "20px",
    boxShadow: isDark
      ? "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 32px rgba(0,0,0,0.30)"
      : "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
    overflow: "clip",
  };

  const cardHeaderSep: React.CSSProperties = {
    borderBottom: isDark
      ? "0.5px solid rgba(255,255,255,0.12)"
      : "0.5px solid rgba(255,255,255,0.30)",
  };

  const fontStack =
    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

  return (
    <div
      style={{
        padding: "24px 16px 120px",
        maxWidth: "800px",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
        fontFamily: fontStack,
      }}
    >
      {/* Page header */}
      <div>
        <h1
          style={{
            fontFamily: "var(--font-heading), Georgia, serif",
            fontSize: "1.5rem",
            fontWeight: 700,
            color: isDark ? "rgba(255,255,255,0.90)" : "#1e1208",
            margin: 0,
          }}
        >
          Documents
        </h1>
        <p
          style={{
            fontSize: "13px",
            color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.55)",
            marginTop: "4px",
          }}
        >
          Manage the PDF documents used for legal research
        </p>
      </div>

      {/* Global error banner */}
      {error && (
        <div
          style={{
            background: "rgba(139,53,32,0.10)",
            border: "0.5px solid rgba(139,53,32,0.25)",
            color: "#8b3520",
            borderRadius: "12px",
            padding: "10px 16px",
            fontSize: "13px",
          }}
        >
          {error}
        </div>
      )}

      {/* Index info panel */}
      <IndexInfoPanel />

      {/* Upload section */}
      <div style={glassCard}>
        <div style={{ ...cardHeaderSep, padding: "16px 20px" }}>
          <h2
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
              margin: 0,
              fontFamily: fontStack,
            }}
          >
            Upload Document
          </h2>
        </div>
        <div style={{ padding: "16px 20px" }}>
          <UploadZone onUpload={uploadDocument} uploadProgress={uploadProgress} />
        </div>
      </div>

      {/* Collections / folder view */}
      <div style={glassCard}>
        <div
          style={{
            ...cardHeaderSep,
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h2
              style={{
                fontSize: "14px",
                fontWeight: 600,
                color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
                margin: 0,
                fontFamily: fontStack,
              }}
            >
              Collections
              {documents.length > 0 && (
                <span
                  style={{
                    marginLeft: "8px",
                    fontSize: "13px",
                    fontWeight: 400,
                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
                  }}
                >
                  ({documents.length} {documents.length === 1 ? "document" : "documents"})
                </span>
              )}
            </h2>
            <p
              style={{
                fontSize: "11px",
                color: isDark ? "rgba(255,255,255,0.35)" : "rgba(46,31,8,0.45)",
                margin: "3px 0 0",
                fontFamily: fontStack,
              }}
            >
              Documents grouped by name prefix
            </p>
          </div>
          <ReindexButton onReindex={triggerReindex} job={reindexJob} />
        </div>
        <div style={{ padding: "16px 20px" }}>
          <FolderView
            documents={documents}
            loading={loading}
            onDelete={deleteDocument}
          />
        </div>
      </div>
    </div>
  );
}
