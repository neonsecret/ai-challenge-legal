"use client";

import { useState } from "react";
import { FileText, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Document } from "./use-documents";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface DocumentListProps {
  documents: Document[];
  loading: boolean;
  onDelete: (documentId: string) => Promise<boolean>;
}

export function DocumentList({ documents, loading, onDelete }: DocumentListProps) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDeleteClick = (documentId: string) => {
    setConfirmingId(documentId);
  };

  const handleConfirmDelete = async (documentId: string) => {
    setDeletingId(documentId);
    setConfirmingId(null);
    await onDelete(documentId);
    setDeletingId(null);
  };

  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-12 rounded-lg bg-muted/50 animate-pulse" />
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-12 text-center">
        <FileText className="size-8 text-muted-foreground/50 mb-3" />
        <p className="text-sm text-muted-foreground">No documents uploaded yet</p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Upload a PDF above to get started
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      {/* Header row */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 border-b border-border bg-muted/30 px-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
        <span>Filename</span>
        <span className="w-20 text-right">Size</span>
        <span className="w-36 text-right">Uploaded</span>
        <span className="w-16 text-right">Actions</span>
      </div>

      {/* Document rows */}
      {documents.map((doc) => (
        <div
          key={doc.document_id}
          className="grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center border-b border-border last:border-0 px-4 py-3 hover:bg-muted/20 transition-colors"
        >
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="size-4 shrink-0 text-[#d4af37]" />
            <span className="truncate text-sm font-medium text-foreground" title={doc.filename}>
              {doc.filename}
            </span>
          </div>

          <span className="w-20 text-right text-xs text-muted-foreground tabular-nums">
            {formatSize(doc.size_bytes)}
          </span>

          <span className="w-36 text-right text-xs text-muted-foreground tabular-nums">
            {formatDate(doc.uploaded_at)}
          </span>

          <div className="w-16 flex justify-end">
            {confirmingId === doc.document_id ? (
              <div className="flex items-center gap-1">
                <button
                  className="rounded px-1.5 py-0.5 text-xs text-destructive hover:bg-destructive/10 transition-colors"
                  onClick={() => handleConfirmDelete(doc.document_id)}
                >
                  Yes
                </button>
                <button
                  className="rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted transition-colors"
                  onClick={() => setConfirmingId(null)}
                >
                  No
                </button>
              </div>
            ) : (
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={deletingId === doc.document_id}
                onClick={() => handleDeleteClick(doc.document_id)}
                className="text-muted-foreground hover:text-destructive"
              >
                {deletingId === doc.document_id ? (
                  <span className="size-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
                ) : (
                  <Trash2 className="size-3.5" />
                )}
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
