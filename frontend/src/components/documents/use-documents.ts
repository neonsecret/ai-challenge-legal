"use client";

import { useState, useCallback } from "react";

export interface Document {
  document_id: string;
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface ReindexJob {
  job_id: string;
  status: "queued" | "processing" | "complete" | "failed";
  progress?: number;
  started_at?: string;
  completed_at?: string;
}

const API_BASE = `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/v1`;

function getApiKey(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("neolex_api_key") ?? "";
  }
  return "";
}

function authHeaders(): Record<string, string> {
  return { Authorization: `Bearer ${getApiKey()}` };
}

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [reindexJob, setReindexJob] = useState<ReindexJob | null>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/documents`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
      const data = await res.json();
      setDocuments(data.documents ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  const uploadDocument = useCallback(
    async (file: File): Promise<Document | null> => {
      setUploadProgress(0);
      setError(null);
      try {
        const formData = new FormData();
        formData.append("file", file);

        const xhr = new XMLHttpRequest();
        const result = await new Promise<Document>((resolve, reject) => {
          xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
              setUploadProgress(Math.round((e.loaded / e.total) * 100));
            }
          });
          xhr.addEventListener("load", () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(JSON.parse(xhr.responseText));
            } else {
              try {
                const err = JSON.parse(xhr.responseText);
                reject(new Error(err.detail ?? `Upload failed: ${xhr.status}`));
              } catch {
                reject(new Error(`Upload failed: ${xhr.status}`));
              }
            }
          });
          xhr.addEventListener("error", () => reject(new Error("Network error during upload")));
          xhr.open("POST", `${API_BASE}/documents/upload`);
          xhr.setRequestHeader("Authorization", `Bearer ${getApiKey()}`);
          xhr.send(formData);
        });

        await fetchDocuments();
        return result;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
        return null;
      } finally {
        setUploadProgress(null);
      }
    },
    [fetchDocuments]
  );

  const deleteDocument = useCallback(
    async (documentId: string): Promise<boolean> => {
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/documents/${documentId}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
        if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
        setDocuments((prev) => prev.filter((d) => d.document_id !== documentId));
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Delete failed");
        return false;
      }
    },
    []
  );

  const triggerReindex = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/documents/reindex`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`Reindex failed: ${res.status}`);
      const job: ReindexJob = await res.json();
      setReindexJob(job);
      pollReindexStatus(job.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reindex failed");
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pollReindexStatus = useCallback(async (jobId: string) => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/documents/reindex/${jobId}`, {
          headers: authHeaders(),
        });
        if (!res.ok) return;
        const job: ReindexJob = await res.json();
        setReindexJob(job);
        if (job.status !== "complete" && job.status !== "failed") {
          setTimeout(poll, 2000);
        }
      } catch {
        // silent poll failure
      }
    };
    setTimeout(poll, 1000);
  }, []);

  return {
    documents,
    loading,
    error,
    uploadProgress,
    reindexJob,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    triggerReindex,
  };
}
