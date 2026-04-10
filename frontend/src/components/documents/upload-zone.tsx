"use client";

import {useRef, useState, useCallback, useEffect} from "react";
import {X, CheckCircle} from "lucide-react";
import {useColorMode} from "@/lib/color-mode";
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

    const {isDark} = useColorMode();
    const {t} = useI18n();

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
        if (!isPdf && !isZip) return t("documents.upload_pdf_or_zip_only");
        if (isPdf && file.size > MAX_SIZE)
            return `${t("documents.upload_too_large")} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
        if (isZip && file.size > MAX_ZIP_SIZE)
            return `${t("documents.upload_zip_too_large")} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
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

    // Light mode: unchanged original styling
    if (!isDark) {
        const dropZoneBg = isDragging
            ? "rgba(196,124,0,0.10)"
            : isHovering
                ? "rgba(255,255,255,0.22)"
                : "rgba(255,255,255,0.15)";
        const dropZoneBorder = isDragging
            ? "1.5px dashed rgba(196,124,0,0.55)"
            : "1.5px dashed rgba(255,255,255,0.45)";
        const labelColor = "rgba(46,31,8,0.55)";
        const textPrimary = "#2e1f08";
        const fontFamily = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

        return (
            <div style={{display: "flex", flexDirection: "column", gap: "12px"}}>
                <div style={{display: "flex", alignItems: "center", gap: "8px"}}>
                    <label
                        htmlFor="collection-name-light"
                        style={{fontSize: "12px", fontWeight: 600, color: labelColor, whiteSpace: "nowrap", fontFamily}}
                    >
                        Collection
                    </label>
                    <input
                        id="collection-name-light"
                        type="text"
                        value={collectionName}
                        onChange={(e) => setCollectionName(e.target.value)}
                        placeholder="My Documents"
                        style={{
                            flex: 1, fontSize: "13px", fontWeight: 500, padding: "6px 12px",
                            borderRadius: "8px", border: "0.5px solid rgba(255,255,255,0.40)",
                            background: "rgba(255,255,255,0.25)", color: textPrimary,
                            outline: "none", transition: "border-color 0.15s", fontFamily,
                        }}
                        onFocus={(e) => { e.currentTarget.style.borderColor = "rgba(196,124,0,0.40)"; }}
                        onBlur={(e) => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.40)"; }}
                    />
                </div>
                <div
                    style={{
                        position: "relative", display: "flex", flexDirection: "column",
                        alignItems: "center", justifyContent: "center",
                        background: dropZoneBg, border: dropZoneBorder,
                        borderRadius: "14px", padding: "32px", cursor: isUploading ? "default" : "pointer",
                        transition: "background 0.15s, border-color 0.15s",
                        opacity: isUploading ? 0.7 : 1, pointerEvents: isUploading ? "none" : "auto", fontFamily,
                    }}
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                    onMouseEnter={() => setIsHovering(true)}
                    onMouseLeave={() => setIsHovering(false)}
                    onClick={() => !isUploading && inputRef.current?.click()}
                >
                    <input
                        ref={inputRef} type="file"
                        accept=".pdf,application/pdf,.zip,application/zip,application/x-zip-compressed"
                        style={{display: "none"}} onChange={handleInputChange}
                    />
                    {isUploading ? (
                        <div style={{display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", width: "100%", maxWidth: "280px"}}>
                            <p style={{fontSize: "13px", fontWeight: 500, color: textPrimary, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%"}}>{pendingFile?.name}</p>
                            <div style={{width: "100%", height: "6px", borderRadius: "9999px", background: "rgba(255,255,255,0.25)", overflow: "hidden"}}>
                                <div style={{height: "100%", background: "#c47c00", borderRadius: "9999px", transition: "width 0.2s", width: `${uploadProgress}%`}} />
                            </div>
                            <p style={{fontSize: "11px", color: labelColor, margin: 0}}>{uploadProgress}%</p>
                        </div>
                    ) : (
                        <div style={{display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", textAlign: "center"}}>
                            <div style={{background: "rgba(255,255,255,0.25)", border: "0.5px solid rgba(255,255,255,0.45)", borderRadius: "50%", padding: "12px", display: "flex", alignItems: "center", justifyContent: "center"}}>
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="rgba(46,31,8,0.45)" strokeWidth="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                            </div>
                            <div>
                                <p style={{fontSize: "13px", fontWeight: 500, color: textPrimary, margin: 0}}>
                                    {t("documents.upload_drop_v2")}{" "}
                                    <span style={{color: "#c47c00", textDecoration: "underline", textUnderlineOffset: "2px"}}>{t("documents.upload_browse")}</span>
                                </p>
                                <p style={{fontSize: "11px", color: labelColor, marginTop: "4px"}}>{t("documents.upload_hint_v2")}</p>
                            </div>
                        </div>
                    )}
                    {validationError && (
                        <div style={{position: "absolute", bottom: "12px", left: "50%", transform: "translateX(-50%)", display: "flex", alignItems: "center", gap: "6px", background: "rgba(139,53,32,0.10)", border: "0.5px solid rgba(139,53,32,0.25)", borderRadius: "8px", padding: "5px 12px", fontSize: "11px", color: "#8b3520", whiteSpace: "nowrap"}} onClick={(e) => e.stopPropagation()}>
                            <X size={12} style={{flexShrink: 0}}/>{validationError}
                            <button style={{marginLeft: "4px", background: "transparent", border: "none", cursor: "pointer", padding: 0, color: "#8b3520", display: "flex", alignItems: "center"}} onClick={(e) => { e.stopPropagation(); setValidationError(null); }}><X size={12}/></button>
                        </div>
                    )}
                    {zipBanner && (
                        <div style={{position: "absolute", bottom: "12px", left: "50%", transform: "translateX(-50%)", display: "flex", alignItems: "center", gap: "6px", background: "rgba(212,168,67,0.12)", border: "0.5px solid rgba(212,168,67,0.35)", borderRadius: "8px", padding: "5px 12px", fontSize: "11px", color: "#9a7a2a", whiteSpace: "nowrap"}} onClick={(e) => e.stopPropagation()}>
                            <CheckCircle size={12} style={{flexShrink: 0}}/>
                            <span>{t("documents.zip_result").replace("{count}", String(zipBanner.uploaded_count))}{zipBanner.skipped_count > 0 && (<>{" · "}{t("documents.zip_skipped").replace("{count}", String(zipBanner.skipped_count))}</>)}</span>
                            <button style={{marginLeft: "4px", background: "transparent", border: "none", cursor: "pointer", padding: 0, color: "#9a7a2a", display: "flex", alignItems: "center"}} onClick={(e) => { e.stopPropagation(); setZipBanner(null); }}><X size={12}/></button>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Dark mode: mockup-matched minimal design
    const zoneBg = isDragging
        ? "rgba(201,168,76,0.03)"
        : isHovering
            ? "rgba(201,168,76,0.03)"
            : "rgba(201,168,76,0.015)";
    const zoneBorder = isDragging
        ? "1px dashed rgba(201,168,76,0.25)"
        : isHovering
            ? "1px dashed rgba(201,168,76,0.25)"
            : "1px dashed rgba(201,168,76,0.15)";

    return (
        <div style={{display: "flex", flexDirection: "column", gap: "10px"}}>
            {/* Collection name input — compact dark */}
            <div style={{display: "flex", alignItems: "center", gap: "8px"}}>
                <label
                    htmlFor="collection-name-dark"
                    style={{
                        fontSize: "10px",
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                        color: "rgba(201,168,76,0.5)",
                        whiteSpace: "nowrap",
                        fontFamily: "system-ui, sans-serif",
                    }}
                >
                    Collection
                </label>
                <input
                    id="collection-name-dark"
                    type="text"
                    value={collectionName}
                    onChange={(e) => setCollectionName(e.target.value)}
                    placeholder="My Documents"
                    style={{
                        flex: 1,
                        fontSize: "11px",
                        padding: "4px 10px",
                        borderRadius: "5px",
                        border: "1px solid rgba(201,168,76,0.10)",
                        background: "rgba(255,255,255,0.02)",
                        color: "rgba(230,235,245,0.88)",
                        outline: "none",
                        fontFamily: "Georgia, serif",
                        transition: "border-color 0.15s",
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = "rgba(201,168,76,0.30)"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "rgba(201,168,76,0.10)"; }}
                />
            </div>

            {/* Drop zone */}
            <div
                style={{
                    position: "relative",
                    border: zoneBorder,
                    borderRadius: "8px",
                    padding: isUploading ? "20px 16px" : "16px",
                    textAlign: "center",
                    background: zoneBg,
                    cursor: isUploading ? "default" : "pointer",
                    transition: "background 0.2s, border-color 0.2s",
                    opacity: isUploading ? 0.75 : 1,
                    pointerEvents: isUploading ? "none" : "auto",
                }}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
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
                    /* Upload progress */
                    <div style={{display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", width: "100%"}}>
                        <div style={{
                            fontSize: "11px",
                            color: "rgba(230,235,245,0.7)",
                            fontFamily: "Georgia, serif",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            maxWidth: "100%",
                        }}>
                            {pendingFile?.name}
                        </div>
                        <div style={{width: "100%", height: "3px", borderRadius: "2px", background: "rgba(201,168,76,0.08)", overflow: "hidden"}}>
                            <div style={{height: "100%", background: "linear-gradient(90deg, rgba(201,168,76,0.5), rgba(201,168,76,0.25))", borderRadius: "2px", transition: "width 0.2s", width: `${uploadProgress}%`}} />
                        </div>
                        <div style={{fontSize: "9px", color: "rgba(200,210,230,0.42)", fontFamily: "system-ui, sans-serif"}}>{uploadProgress}%</div>
                    </div>
                ) : (
                    /* Idle state */
                    <>
                        <div style={{fontSize: "18px", color: "rgba(201,168,76,0.3)", marginBottom: "4px", lineHeight: 1}}>↑</div>
                        <div style={{fontSize: "9px", color: "rgba(200,210,230,0.22)", fontFamily: "system-ui, sans-serif", lineHeight: 1.4, marginBottom: "6px"}}>
                            {t("documents.upload_drop_v2")}
                        </div>
                        <button
                            style={{
                                display: "inline-block",
                                padding: "4px 10px",
                                borderRadius: "5px",
                                background: "rgba(201,168,76,0.06)",
                                border: "1px solid rgba(201,168,76,0.12)",
                                fontSize: "8px",
                                color: "rgba(201,168,76,0.7)",
                                cursor: "pointer",
                                fontFamily: "system-ui, sans-serif",
                                lineHeight: 1,
                            }}
                            onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
                        >
                            {t("documents.upload_browse")}
                        </button>
                    </>
                )}

                {/* Validation error */}
                {validationError && (
                    <div
                        style={{
                            position: "absolute", bottom: "8px", left: "50%", transform: "translateX(-50%)",
                            display: "flex", alignItems: "center", gap: "6px",
                            background: "rgba(139,53,32,0.10)", border: "0.5px solid rgba(139,53,32,0.25)",
                            borderRadius: "6px", padding: "4px 10px",
                            fontSize: "10px", color: "#8b3520", whiteSpace: "nowrap",
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <X size={10} style={{flexShrink: 0}}/>{validationError}
                        <button style={{marginLeft: "4px", background: "transparent", border: "none", cursor: "pointer", padding: 0, color: "#8b3520", display: "flex", alignItems: "center"}}
                            onClick={(e) => { e.stopPropagation(); setValidationError(null); }}>
                            <X size={10}/>
                        </button>
                    </div>
                )}

                {/* ZIP success banner */}
                {zipBanner && (
                    <div
                        style={{
                            position: "absolute", bottom: "8px", left: "50%", transform: "translateX(-50%)",
                            display: "flex", alignItems: "center", gap: "6px",
                            background: "rgba(201,168,76,0.08)", border: "0.5px solid rgba(201,168,76,0.20)",
                            borderRadius: "6px", padding: "4px 10px",
                            fontSize: "10px", color: "#C9A84C", whiteSpace: "nowrap",
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <CheckCircle size={10} style={{flexShrink: 0}}/>
                        <span>
                            {t("documents.zip_result").replace("{count}", String(zipBanner.uploaded_count))}
                            {zipBanner.skipped_count > 0 && (<>{" · "}{t("documents.zip_skipped").replace("{count}", String(zipBanner.skipped_count))}</>)}
                        </span>
                        <button style={{marginLeft: "4px", background: "transparent", border: "none", cursor: "pointer", padding: 0, color: "#C9A84C", display: "flex", alignItems: "center"}}
                            onClick={(e) => { e.stopPropagation(); setZipBanner(null); }}>
                            <X size={10}/>
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
