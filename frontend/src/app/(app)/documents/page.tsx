"use client";

import {useEffect, useState, useCallback} from "react";
import {useColorMode} from "@/lib/color-mode";
import {motion} from "motion/react";
import {V3_LIST_VARIANT, V3_ITEM_VARIANT} from "@/lib/v3-motion";
import Link from "next/link";
import {UploadZone} from "@/components/documents/upload-zone";
import {FolderView} from "@/components/documents/folder-view";
import {IndexInfoPanel} from "@/components/documents/index-info-panel";
import {LegalIndexLibrary} from "@/components/documents/legal-index-library";
import {useDocuments} from "@/components/documents/use-documents";
import {useAuth} from "@/lib/use-auth";
import {useI18n} from "@/lib/i18n";

export default function DocumentsPage() {
    const {isDark} = useColorMode();
    const {t} = useI18n();
    const {user} = useAuth();

    const isFreeTier = !user || user.subscription_status === "free" || user.max_corpora === 0;

    const {
        documents,
        loading,
        error,
        uploadProgress,
        fetchDocuments,
        uploadFile,
        deleteDocument,
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

    const glassCard: React.CSSProperties = isDark ? {
        background: "rgba(255,255,255, 0.02)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        border: "1px solid rgba(201,168,76, 0.06)",
        borderRadius: "14px",
        boxShadow: "0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025)",
        overflow: "clip",
    } : {
        background: "rgba(255,250,235,0.22)",
        backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        border: "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: "20px",
        boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    const glassCardClass = "";

    const cardHeaderSep: React.CSSProperties = {
        borderBottom: isDark
            ? "1px solid rgba(201,168,76, 0.06)"
            : "0.5px solid rgba(255,255,255,0.30)",
    };

    const fontStack =
        "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

    return (
        <div
            style={{
                ...(isDark ? {
                    display: "flex",
                    flexDirection: "column" as const,
                    height: "100%",
                    overflow: "hidden",
                } : {
                    padding: "24px 16px 120px",
                    maxWidth: "800px",
                    margin: "0 auto",
                    display: "flex",
                    flexDirection: "column" as const,
                    gap: "24px",
                    fontFamily: fontStack,
                }),
            }}
        >
            {/* Page header */}
            {isDark ? (
                <div style={{
                    height: 44,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    padding: "0 20px",
                    borderBottom: "1px solid rgba(201,168,76, 0.06)",
                    background: "linear-gradient(180deg, rgba(255,255,255,0.015) 0%, transparent 100%)",
                }}>
                    <h1 style={{
                        fontFamily: "Georgia, serif",
                        fontSize: 14,
                        fontWeight: "normal",
                        color: "var(--strict-text-primary)",
                        margin: 0,
                    }}>
                        {t("documents.title")}
                    </h1>
                </div>
            ) : (
            <div>
                <h1
                    style={{
                        fontFamily: "var(--font-heading), Georgia, serif",
                        fontSize: "1.5rem",
                        fontWeight: 700,
                        color: "#1e1208",
                        margin: 0,
                    }}
                >
                    {t("documents.title")}
                </h1>
                <p
                    style={{
                        fontSize: "13px",
                        color: "rgba(46,31,8,0.55)",
                        marginTop: "4px",
                    }}
                >
                    {t("documents.subtitle")}
                </p>
            </div>
            )}

            {/* Content area — scrollable in dark mode */}
            <div style={{
                ...(isDark ? {
                    flex: 1,
                    overflowY: "auto" as const,
                    padding: "20px 24px",
                    display: "flex",
                    flexDirection: "column" as const,
                    gap: 20,
                    maxWidth: 800,
                    width: "100%",
                    marginLeft: "auto",
                    marginRight: "auto",
                } : {}),
            }}>

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

            {isDark ? (
                /* ── Dark mode: continuous flow, no glass card wrappers ── */
                <motion.div
                    variants={V3_LIST_VARIANT}
                    initial="hidden"
                    animate="visible"
                    style={{display: "flex", flexDirection: "column", gap: "20px"}}
                >
                    {/* Upload section — gated by plan */}
                    {isFreeTier ? (
                        <motion.div variants={V3_ITEM_VARIANT}>
                            <div style={{padding: "16px", textAlign: "center", border: "1px dashed rgba(201,168,76,0.12)", borderRadius: "8px"}}>
                                <div style={{fontSize: "18px", color: "rgba(201,168,76,0.25)", marginBottom: "8px"}}>↑</div>
                                <p style={{fontSize: "11px", fontFamily: "Georgia, serif", color: "rgba(255,255,255,0.56)", margin: "0 0 6px"}}>
                                    {t("documents.upgrade_required")}
                                </p>
                                <p style={{fontSize: "9px", fontFamily: "system-ui, sans-serif", color: "rgba(200,210,230,0.22)", margin: "0 0 10px", lineHeight: 1.5}}>
                                    {t("documents.upgrade_description")}
                                </p>
                                <Link
                                    href="/billing"
                                    style={{
                                        display: "inline-flex", alignItems: "center", gap: "4px",
                                        padding: "4px 12px", fontSize: "9px", fontFamily: "system-ui, sans-serif",
                                        color: "rgba(201,168,76,0.7)",
                                        background: "rgba(201,168,76,0.06)",
                                        border: "1px solid rgba(201,168,76,0.12)",
                                        borderRadius: "5px", textDecoration: "none", cursor: "pointer",
                                    }}
                                >
                                    {t("documents.upgrade_button")}
                                </Link>
                            </div>
                        </motion.div>
                    ) : (
                        <motion.div variants={V3_ITEM_VARIANT}>
                            <UploadZone onUpload={handleUpload} uploadProgress={uploadProgress} zipResult={zipResult}/>
                        </motion.div>
                    )}

                    {/* COLLECTIONS label + folder view */}
                    <motion.div variants={V3_ITEM_VARIANT} style={{display: "flex", flexDirection: "column", gap: "0"}}>
                        <div style={{
                            fontSize: "8px", fontFamily: "system-ui, sans-serif",
                            letterSpacing: "1.5px", textTransform: "uppercase" as const,
                            color: "var(--strict-text-dim)", marginBottom: "12px",
                        }}>
                            {t("documents.collections")}
                        </div>
                        <FolderView
                            documents={documents}
                            loading={loading}
                            onDelete={deleteDocument}
                            onRefresh={fetchDocuments}
                        />
                    </motion.div>

                    {/* Legal index library — compact list (section label is inside LegalIndexLibrary) */}
                    <motion.div variants={V3_ITEM_VARIANT}>
                        <LegalIndexLibrary />
                    </motion.div>
                </motion.div>
            ) : (
                /* ── Light mode: original glass card sections ── */
                <motion.div
                    variants={V3_LIST_VARIANT}
                    initial="hidden"
                    animate="visible"
                >
                    <h2
                        style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            textTransform: "uppercase" as const,
                            letterSpacing: "0.08em",
                            color: "rgba(46,31,8,0.40)",
                            margin: "0 0 12px",
                            fontFamily: fontStack,
                        }}
                    >
                        {t("documents.your_documents")}
                    </h2>

                    {/* Upload section — gated by plan */}
                    {isFreeTier ? (
                        <motion.div
                            variants={V3_ITEM_VARIANT}
                            className={glassCardClass}
                            style={{...glassCard, marginBottom: "16px"}}
                        >
                            <div style={{padding: "24px 20px", textAlign: "center"}}>
                                <div
                                    style={{
                                        width: "40px", height: "40px",
                                        margin: "0 auto 12px", borderRadius: "12px",
                                        background: "rgba(46,31,8,0.06)",
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                    }}
                                >
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                                        stroke="rgba(46,31,8,0.50)" strokeWidth="1.5"
                                        strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                        <polyline points="17 8 12 3 7 8"/>
                                        <line x1="12" y1="3" x2="12" y2="15"/>
                                    </svg>
                                </div>
                                <h3 style={{fontSize: "15px", fontWeight: 600, color: "#1e1208", margin: "0 0 6px", fontFamily: fontStack}}>
                                    {t("documents.upgrade_required")}
                                </h3>
                                <p style={{fontSize: "13px", lineHeight: 1.5, color: "rgba(46,31,8,0.55)", margin: "0 0 16px", maxWidth: "420px", marginLeft: "auto", marginRight: "auto"}}>
                                    {t("documents.upgrade_description")}
                                </p>
                                <Link
                                    href="/billing"
                                    style={{
                                        display: "inline-flex", alignItems: "center", gap: "6px",
                                        padding: "8px 20px", fontSize: "13px", fontWeight: 600,
                                        fontFamily: fontStack, color: "#fff",
                                        background: "rgba(46,31,8,0.80)",
                                        border: "0.5px solid rgba(46,31,8,0.15)",
                                        borderRadius: "10px", textDecoration: "none", cursor: "pointer",
                                        transition: "opacity 0.15s",
                                    }}
                                >
                                    {t("documents.upgrade_button")}
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                                        stroke="currentColor" strokeWidth="2"
                                        strokeLinecap="round" strokeLinejoin="round">
                                        <line x1="5" y1="12" x2="19" y2="12"/>
                                        <polyline points="12 5 19 12 12 19"/>
                                    </svg>
                                </Link>
                            </div>
                        </motion.div>
                    ) : (
                        <motion.div
                            variants={V3_ITEM_VARIANT}
                            className={glassCardClass}
                            style={{...glassCard, marginBottom: "16px"}}
                        >
                            <div style={{...cardHeaderSep, padding: "16px 20px"}}>
                                <h3 style={{fontSize: "14px", fontWeight: 600, color: "#1e1208", margin: 0, fontFamily: fontStack}}>
                                    {t("documents.upload_document")}
                                </h3>
                            </div>
                            <div style={{padding: "16px 20px"}}>
                                <UploadZone onUpload={handleUpload} uploadProgress={uploadProgress} zipResult={zipResult}/>
                            </div>
                        </motion.div>
                    )}

                    {/* Collections / folder view */}
                    <motion.div
                        variants={V3_ITEM_VARIANT}
                        className={glassCardClass}
                        style={glassCard}
                    >
                        <div style={{...cardHeaderSep, padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                            <div>
                                <h3 style={{fontSize: "14px", fontWeight: 600, color: "#1e1208", margin: 0, fontFamily: fontStack}}>
                                    {t("documents.collections")}
                                    {documents.length > 0 && (
                                        <span style={{marginLeft: "8px", fontSize: "13px", fontWeight: 400, color: "rgba(46,31,8,0.55)"}}>
                                            ({documents.length} {documents.length === 1 ? t("documents.document") : t("documents.documents")})
                                        </span>
                                    )}
                                </h3>
                                <p style={{fontSize: "11px", color: "rgba(46,31,8,0.45)", margin: "3px 0 0", fontFamily: fontStack}}>
                                    {t("documents.collections_subtitle")}
                                </p>
                            </div>
                        </div>
                        <div style={{padding: "16px 20px"}}>
                            <FolderView
                                documents={documents}
                                loading={loading}
                                onDelete={deleteDocument}
                                onRefresh={fetchDocuments}
                            />
                        </div>
                    </motion.div>

                    {/* Legal Index Library */}
                    <div style={{marginTop: "24px"}}>
                        <h2
                            style={{
                                fontSize: "11px", fontWeight: 600,
                                textTransform: "uppercase" as const, letterSpacing: "0.08em",
                                color: "rgba(46,31,8,0.40)", margin: "0 0 12px", fontFamily: fontStack,
                            }}
                        >
                            {t("documents.legal_index_library")}
                        </h2>
                        <LegalIndexLibrary />
                    </div>
                </motion.div>
            )}
            </div>{/* end scrollable content wrapper */}
        </div>
    );
}
