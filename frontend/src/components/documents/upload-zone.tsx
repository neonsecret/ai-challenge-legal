"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { Upload, FileText, X } from "lucide-react";
import { useTheme } from "next-themes";

const MAX_SIZE = 50 * 1024 * 1024; // 50MB

interface UploadZoneProps {
  onUpload: (file: File) => Promise<unknown>;
  uploadProgress: number | null;
}

export function UploadZone({ onUpload, uploadProgress }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";

  const validate = (file: File): string | null => {
    if (!file.type.includes("pdf") && !file.name.toLowerCase().endsWith(".pdf")) {
      return "Only PDF files are allowed";
    }
    if (file.size > MAX_SIZE) {
      return `File exceeds 50MB limit (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
    }
    return null;
  };

  const handleFile = useCallback(
    async (file: File) => {
      setValidationError(null);
      const err = validate(file);
      if (err) {
        setValidationError(err);
        return;
      }
      setPendingFile(file);
      await onUpload(file);
      setPendingFile(null);
    },
    [onUpload]
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
        accept=".pdf,application/pdf"
        style={{ display: "none" }}
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
            style={{ color: "#c47c00" }}
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
              style={{ color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)" }}
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
              Drop a PDF here, or{" "}
              <span
                style={{
                  color: isDark ? "#C9A84C" : "#c47c00",
                  textDecoration: "underline",
                  textUnderlineOffset: "2px",
                }}
              >
                browse
              </span>
            </p>
            <p
              style={{
                fontSize: "11px",
                color: isDark ? "rgba(255,255,255,0.38)" : "rgba(46,31,8,0.55)",
                marginTop: "4px",
              }}
            >
              PDF only · max 50 MB
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
          <X size={12} style={{ flexShrink: 0 }} />
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
            <X size={12} />
          </button>
        </div>
      )}
    </div>
  );
}
