"use client";

import { useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { UploadZone } from "@/components/documents/upload-zone";
import { DocumentList } from "@/components/documents/document-list";
import { ReindexButton } from "@/components/documents/reindex-button";
import { useDocuments } from "@/components/documents/use-documents";

export default function DocumentsPage() {
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

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Documents</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage the PDF documents used for legal research
        </p>
      </div>

      {/* Global error banner */}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Upload section */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle>Upload Document</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <UploadZone onUpload={uploadDocument} uploadProgress={uploadProgress} />
        </CardContent>
      </Card>

      {/* Document list section */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle>
            Uploaded Documents
            {documents.length > 0 && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                ({documents.length})
              </span>
            )}
          </CardTitle>
          <CardAction>
            <ReindexButton onReindex={triggerReindex} job={reindexJob} />
          </CardAction>
        </CardHeader>
        <CardContent className="pt-4">
          <DocumentList
            documents={documents}
            loading={loading}
            onDelete={deleteDocument}
          />
        </CardContent>
      </Card>
    </div>
  );
}
