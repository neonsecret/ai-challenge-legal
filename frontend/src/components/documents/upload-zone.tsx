"use client";

import {useRef, useState, useCallback, useEffect} from "react";
import {Upload, FileText, X, CheckCircle} from "lucide-react";
import {useTheme} from "next-themes";
import {useI18n} from "@/lib/i18n";
import type {ZipUploadResult} from "@/components/documents/use-documents";

const MAX_SIZE = 50 * 1024 * 1024; // 50MB
const MAX_ZIP_SIZE = 200 * 1024 * 1024; // 200MB

interface UploadZoneProps {
    onUpload: (file: File, collection?: string) => Promise<unknown>;
    uploadProgress: number | null;
    zipResult?: ZipUploadResult | null;
}

export function UploadZone({onUpload, uploadProgress, zipResult}: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [isHovering, setIsHovering] = useState(false);
    const [validationError, setValidationError] = useState<string | null>(null);
    const [pendingFile, setPendingFile] = useState<File | null>(null);
    const [zipBanner, setZipBanner] = useState<ZipUploadResult | null>(null);
    const [collectionName, setCollectionName] = useState("My Documents");
    const inputRef = useRef<HTMLInputElement>(null);

    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    const isDark = mounted && resolvedTheme === "dark";
    const {t} = useI18n();

    // Show ZIP result banner when zipResult prop changes
    useEffect(() => {
        if (zipResult) {
            setZipBanner(zipResult);
            const timer = setTimeout(() => setZipBanner(null), 5000);
            return () => clearTimeout(timer);
        }
    }, [zipResult]);

    const validate = (file: File): string | null => {
        const isPdf = file.type.includes("pdf") || file.name.toLowerCase().endsWith(".pdf");
        const isZip = file.type.includes("zip") || file.name.toLowerCase().endsWith(".zip");
        if (!isPdf && !isZip) {
            return t("documents.upload_pdf_or_zip_only");
        }
        if (isPdf && file.size > MAX_SIZE) {
            return `${t("documents.upload_too_large")} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
        }
        if (isZip && file.size > MAX_ZIP_SIZE) {
            return `${t("documents.upload_zip_too_large")} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
        }
        return null;
    };

    const handleFile = useCallback(
        async (file: File) => {
            setValidationError(null);
            setZipBanner(null);
            const err = validate(file);
            if (err) {
                setValidationError(err);
                return;
            }
            setPendingFile(file);
            const col = collectionName.trim() || "My Documents";
            await onUpload(file, col);
            setPendingFile(null);
        },
        [onUpload, collectionName]
    );

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setIsDragging(false);
            const file = e.dataTransfer.files[0];
            if (file) handleFile(file);
        },
        [handleFile]
    );

    const handleInputChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
            e.target.value = "";
        },
        [handleFile]
    );

    const isUploading = uploadProgress !== null;

    const dropZoneBg = isDark
        ? isDragging
            ? "rgba(201,168,76,0.08)"
            : isHovering
                ? "rgba(201,168,76,0.14)"
                : "rgba(201,168,76,0.08)"
        : isDragging
            ? "rgba(196,124,0,0.10)"
            : isHovering
                ? "rgba(255,255,255,0.22)"
                : "rgba(255,255,255,0.15)";

    const dropZoneBorder = isDark
        ? "1.5px dashed rgba(201,168,76,0.30)"
        : isDragging
            ? "1.5px dashed rgba(196,124,0,0.55)"
            : "1.5px dashed rgba(255,255,255,0.45)";

    return (
        <div style={{display: "flex", flexDirection: "column", gap: "12px"}}>
            {/* Collection name input */}
            <div style={{display: "flex", alignItems: "center", gap: "8px"}}>
                <label
                    htmlFor="collection-name"
                    style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.55)",
                        whiteSpace: "nowrap",
                        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                    }}
                >
                    Collection
                </label>
                <input
                    id="collection-name"
                    type="text"
                    value={collectionName}
                    onChange={(e) => setCollectionName(e.target.value)}
                    placeholder="My Documents"
                    style={{
                        flex: 1,
                        fontSize: "13px",
                        fontWeight: 500,
                        padding: "6px 12px",
                        borderRadius: "8px",
                        border: isDark
                            ? "0.5px solid rgba(255,255,255,0.15)"
                            : "0.5px solid rgba(255,255,255,0.40)",
                        background: isDark
                            ? "rgba(255,255,255,0.06)"
                            : "rgba(255,255,255,0.25)",
                        color: isDark ? "rgba(255,255,255,0.85)" : "#2e1f08",
                        outline: "none",
                        transition: "border-color 0.15s",
                        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
                    }}
                    onFocus={(e) => {
                        e.currentTarget.style.borderColor = isDark
                            ? "rgba(201,168,76,0.40)"
                            : "rgba(196,124,0,0.40)";
                    }}
                    onBlur={(e) => {
                        e.currentTarget.style.borderColor = isDark
                            ? "rgba(255,255,255,0.15)"
                            : "rgba(255,255,255,0.40)";
                    }}
                />
            </div>
        <div
            style={{
                position: "relative",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                background: dropZoneBg,
                border: dropZoneBorder,
                borderRadius: "14px",
                padding: "32px",
                cursor: isUploading ? "default" : "pointer",
                transition: "background 0.15s, border-color 0.15s",
                opacity: isUploading ? 0.7 : 1,
                pointerEvents: isUploading ? "none" : "auto",
                fontFamily:
                    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
            }}
            onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => setIsHovering(false)}
            onClick={() => !isUploading && inputRef.current?.click()}
        >
            <input
                ref={inputRef}
                type="file"
                accept=".pdf,application/pdf,.zip,application/zip,application/x-zip-compressed"
                style={{display: "none"}}
                onChange={handleInputChange}
            />

            {isUploading ? (
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: "12px",
                        width: "100%",
                        maxWidth: "280px",
                    }}
                >
                    <FileText
                        size={32}
                        style={{color: "#c47c00"}}
                    />
                    <p
                        style={{
                            fontSize: "13px",
                            fontWeight: 500,
                            color: isDark ? "rgba(255,255,255,0.80)" : "#2e1f08",
                            margin: 0,
                            maxWidth: "100%",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                        }}
                    >
                        {pendingFile?.name}
                    </p>
                    <div
                        style={{
                            width: "100%",
                            height: "6px",
                            borderRadius: "9999px",
                            background: isDark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.25)",
                            overflow: "hidden",
                        }}
                    >
                        <div
                            style={{
                                height: "100%",
                                background: "#c47c00",
                                borderRadius: "9999px",
                                transition: "width 0.2s",
                                width: `${uploadProgress}%`,
                            }}
                        />
                    </div>
                    <p
                        style={{
                            fontSize: "11px",
                            color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.55)",
                            margin: 0,
                        }}
                    >
                        {uploadProgress}%
                    </p>
                </div>
            ) : (
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: "12px",
                        textAlign: "center",
                    }}
                >
                    <div
                        style={{
                            background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)",
                            border: isDark
                                ? "0.5px solid rgba(255,255,255,0.15)"
                                : "0.5px solid rgba(255,255,255,0.45)",
                            borderRadius: "50%",
                            padding: "12px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        <Upload
                            size={24}
                            style={{color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)"}}
                        />
                    </div>
                    <div>
                        <p
                            style={{
                                fontSize: "13px",
                                fontWeight: 500,
                                color: isDark ? "rgba(255,255,255,0.75)" : "#2e1f08",
                                margin: 0,
                            }}
                        >
                            {t("documents.upload_drop_v2")}{" "}
                            <span
                                style={{
                                    color: isDark ? "#C9A84C" : "#c47c00",
                                    textDecoration: "underline",
                                    textUnderlineOffset: "2px",
                                }}
                            >
                                {t("documents.upload_browse")}
                            </span>
                        </p>
                        <p
                            style={{
                                fontSize: "11px",
                                color: isDark ? "rgba(255,255,255,0.38)" : "rgba(46,31,8,0.55)",
                                marginTop: "4px",
                            }}
                        >
                            {t("documents.upload_hint_v2")}
                        </p>
                    </div>
                </div>
            )}

            {validationError && (
                <div
                    style={{
                        position: "absolute",
                        bottom: "12px",
                        left: "50%",
                        transform: "translateX(-50%)",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        background: "rgba(139,53,32,0.10)",
                        border: "0.5px solid rgba(139,53,32,0.25)",
                        borderRadius: "8px",
                        padding: "5px 12px",
                        fontSize: "11px",
                        color: "#8b3520",
                        whiteSpace: "nowrap",
                    }}
                    onClick={(e) => e.stopPropagation()}
                >
                    <X size={12} style={{flexShrink: 0}}/>
                    {validationError}
                    <button
                        style={{
                            marginLeft: "4px",
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                            padding: 0,
                            color: "#8b3520",
                            display: "flex",
                            alignItems: "center",
                        }}
                        onClick={(e) => {
                            e.stopPropagation();
                            setValidationError(null);
                        }}
                    >
                        <X size={12}/>
                    </button>
                </div>
            )}

            {zipBanner && (
                <div
                    style={{
                        position: "absolute",
                        bottom: "12px",
                        left: "50%",
                        transform: "translateX(-50%)",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        background: isDark ? "rgba(201,168,76,0.12)" : "rgba(212,168,67,0.12)",
                        border: isDark
                            ? "0.5px solid rgba(201,168,76,0.30)"
                            : "0.5px solid rgba(212,168,67,0.35)",
                        borderRadius: "8px",
                        padding: "5px 12px",
                        fontSize: "11px",
                        color: isDark ? "#C9A84C" : "#9a7a2a",
                        whiteSpace: "nowrap",
                    }}
                    onClick={(e) => e.stopPropagation()}
                >
                    <CheckCircle size={12} style={{flexShrink: 0}}/>
                    <span>
                        {t("documents.zip_result").replace("{count}", String(zipBanner.uploaded_count))}
                        {zipBanner.skipped_count > 0 && (
                            <>
                                {" \u00b7 "}
                                {t("documents.zip_skipped").replace("{count}", String(zipBanner.skipped_count))}
                            </>
                        )}
                    </span>
                    <button
                        style={{
                            marginLeft: "4px",
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                            padding: 0,
                            color: isDark ? "#C9A84C" : "#9a7a2a",
                            display: "flex",
                            alignItems: "center",
                        }}
                        onClick={(e) => {
                            e.stopPropagation();
                            setZipBanner(null);
                        }}
                    >
                        <X size={12}/>
                    </button>
                </div>
            )}
        </div>
        </div>
    );
}
