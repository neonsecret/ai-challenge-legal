"use client";

import { useRef, useState, useCallback } from "react";
import { Upload, FileText, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const MAX_SIZE = 50 * 1024 * 1024; // 50MB

interface UploadZoneProps {
  onUpload: (file: File) => Promise<unknown>;
  uploadProgress: number | null;
}

export function UploadZone({ onUpload, uploadProgress }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 transition-colors cursor-pointer",
        isDragging
          ? "border-[#d4af37] bg-[#d4af37]/5"
          : "border-border hover:border-[#d4af37]/60 hover:bg-muted/30",
        isUploading && "pointer-events-none opacity-70"
      )}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => !isUploading && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={handleInputChange}
      />

      {isUploading ? (
        <div className="flex flex-col items-center gap-3 w-full max-w-xs">
          <FileText className="size-8 text-[#d4af37]" />
          <p className="text-sm font-medium text-foreground truncate max-w-full">
            {pendingFile?.name}
          </p>
          <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-[#d4af37] transition-all duration-200"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">{uploadProgress}%</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="rounded-full bg-muted p-3">
            <Upload className="size-6 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              Drop a PDF here, or{" "}
              <span className="text-[#d4af37] underline underline-offset-2">browse</span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">PDF only · max 50 MB</p>
          </div>
        </div>
      )}

      {validationError && (
        <div
          className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-lg bg-destructive/10 px-3 py-1.5 text-xs text-destructive"
          onClick={(e) => e.stopPropagation()}
        >
          <X className="size-3 shrink-0" />
          {validationError}
          <button
            className="ml-1 hover:opacity-70"
            onClick={(e) => { e.stopPropagation(); setValidationError(null); }}
          >
            <X className="size-3" />
          </button>
        </div>
      )}
    </div>
  );
}
