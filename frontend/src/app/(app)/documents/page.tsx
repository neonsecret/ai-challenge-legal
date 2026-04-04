"use client";

import {useEffect, useState, useCallback} from "react";
import {useTheme} from "@/lib/theme";
import Link from "next/link";
import {UploadZone} from "@/components/documents/upload-zone";
import {FolderView} from "@/components/documents/folder-view";
import {ReindexButton} from "@/components/documents/reindex-button";
import {IndexInfoPanel} from "@/components/documents/index-info-panel";
import {LegalIndexLibrary} from "@/components/documents/legal-index-library";
import {useDocuments} from "@/components/documents/use-documents";
import {useAuth} from "@/lib/use-auth";
import {useI18n} from "@/lib/i18n";

export default function DocumentsPage() {
    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    const {t} = useI18n();
    const {user} = useAuth();

    useEffect(() => {
        setMounted(true);
    }, []);

    const isDark = mounted && resolvedTheme === "dark";
    const isFreeTier = !user || user.subscription_status === "free" || user.max_corpora === 0;

    const {
        documents,
        loading,
        error,
        uploadProgress,
        reindexJob,
        fetchDocuments,
        uploadFile,
        deleteDocument,
        triggerReindex,
    } = useDocuments();

    const [zipResult, setZipResult] = useState<import("@/components/documents/use-documents").ZipUploadResult | null>(null);

    const handleUpload = useCallback(async (file: File, collection?: string) => {
        const result = await uploadFile(file, collection);
        // If this was a ZIP upload, show the result banner
        if (result && "uploaded_count" in result) {
            setZipResult(result);
        }
        return result;
    }, [uploadFile]);

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
                    {t("documents.title")}
                </h1>
                <p
                    style={{
                        fontSize: "13px",
                        color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.55)",
                        marginTop: "4px",
                    }}
                >
                    {t("documents.subtitle")}
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
            <IndexInfoPanel/>

            {/* Section divider: Your Documents */}
            <div>
                <h2
                    style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.08em",
                        color: isDark ? "rgba(255,255,255,0.38)" : "rgba(46,31,8,0.40)",
                        margin: "0 0 12px",
                        fontFamily: fontStack,
                    }}
                >
                    {t("documents.your_documents")}
                </h2>

                {/* Upload section — gated by plan */}
                {isFreeTier ? (
                    <div style={{...glassCard, marginBottom: "16px"}}>
                        <div style={{padding: "24px 20px", textAlign: "center"}}>
                            <div
                                style={{
                                    width: "40px",
                                    height: "40px",
                                    margin: "0 auto 12px",
                                    borderRadius: "12px",
                                    background: isDark
                                        ? "rgba(255,255,255,0.06)"
                                        : "rgba(46,31,8,0.06)",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                }}
                            >
                                <svg
                                    width="20"
                                    height="20"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke={isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.50)"}
                                    strokeWidth="1.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                >
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="17 8 12 3 7 8"/>
                                    <line x1="12" y1="3" x2="12" y2="15"/>
                                </svg>
                            </div>
                            <h3
                                style={{
                                    fontSize: "15px",
                                    fontWeight: 600,
                                    color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
                                    margin: "0 0 6px",
                                    fontFamily: fontStack,
                                }}
                            >
                                {t("documents.upgrade_required")}
                            </h3>
                            <p
                                style={{
                                    fontSize: "13px",
                                    lineHeight: 1.5,
                                    color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.55)",
                                    margin: "0 0 16px",
                                    maxWidth: "420px",
                                    marginLeft: "auto",
                                    marginRight: "auto",
                                }}
                            >
                                {t("documents.upgrade_description")}
                            </p>
                            <Link
                                href="/billing"
                                style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "6px",
                                    padding: "8px 20px",
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    fontFamily: fontStack,
                                    color: isDark ? "#fff" : "#fff",
                                    background: isDark
                                        ? "rgba(255,255,255,0.12)"
                                        : "rgba(46,31,8,0.80)",
                                    border: isDark
                                        ? "0.5px solid rgba(255,255,255,0.18)"
                                        : "0.5px solid rgba(46,31,8,0.15)",
                                    borderRadius: "10px",
                                    textDecoration: "none",
                                    cursor: "pointer",
                                    transition: "opacity 0.15s",
                                }}
                            >
                                {t("documents.upgrade_button")}
                                <svg
                                    width="14"
                                    height="14"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                >
                                    <line x1="5" y1="12" x2="19" y2="12"/>
                                    <polyline points="12 5 19 12 12 19"/>
                                </svg>
                            </Link>
                        </div>
                    </div>
                ) : (
                    <div style={{...glassCard, marginBottom: "16px"}}>
                        <div style={{...cardHeaderSep, padding: "16px 20px"}}>
                            <h3
                                style={{
                                    fontSize: "14px",
                                    fontWeight: 600,
                                    color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
                                    margin: 0,
                                    fontFamily: fontStack,
                                }}
                            >
                                {t("documents.upload_document")}
                            </h3>
                        </div>
                        <div style={{padding: "16px 20px"}}>
                            <UploadZone onUpload={handleUpload} uploadProgress={uploadProgress} zipResult={zipResult}/>
                        </div>
                    </div>
                )}

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
                            <h3
                                style={{
                                    fontSize: "14px",
                                    fontWeight: 600,
                                    color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
                                    margin: 0,
                                    fontFamily: fontStack,
                                }}
                            >
                                {t("documents.collections")}
                                {documents.length > 0 && (
                                    <span
                                        style={{
                                            marginLeft: "8px",
                                            fontSize: "13px",
                                            fontWeight: 400,
                                            color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
                                        }}
                                    >
                    ({documents.length} {documents.length === 1 ? t("documents.document") : t("documents.documents")})
                  </span>
                                )}
                            </h3>
                            <p
                                style={{
                                    fontSize: "11px",
                                    color: isDark ? "rgba(255,255,255,0.35)" : "rgba(46,31,8,0.45)",
                                    margin: "3px 0 0",
                                    fontFamily: fontStack,
                                }}
                            >
                                {t("documents.collections_subtitle")}
                            </p>
                        </div>
                        {/* Reindex button removed — indexing happens automatically after upload */}
                    </div>
                    <div style={{padding: "16px 20px"}}>
                        <FolderView
                            documents={documents}
                            loading={loading}
                            onDelete={deleteDocument}
                            onRefresh={fetchDocuments}
                        />
                    </div>
                </div>
            </div>

            {/* Section divider: Legal Index Library */}
            <div>
                <h2
                    style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "uppercase" as const,
                        letterSpacing: "0.08em",
                        color: isDark ? "rgba(255,255,255,0.38)" : "rgba(46,31,8,0.40)",
                        margin: "0 0 12px",
                        fontFamily: fontStack,
                    }}
                >
                    {t("documents.legal_index_library")}
                </h2>
                <LegalIndexLibrary isDark={isDark}/>
            </div>
        </div>
    );
}
