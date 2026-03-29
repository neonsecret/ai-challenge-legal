"use client";

import {RefreshCw} from "lucide-react";
import type {ReindexJob} from "./use-documents";
import {useI18n} from "@/lib/i18n";

interface ReindexButtonProps {
    onReindex: () => Promise<void>;
    job: ReindexJob | null;
}

const STATUS_KEY: Record<ReindexJob["status"], string> = {
    queued: "documents.reindex_queued",
    processing: "documents.reindex_processing",
    complete: "documents.reindex_complete",
    failed: "documents.reindex_failed",
};

const STATUS_STYLE: Record<ReindexJob["status"], React.CSSProperties> = {
    queued: {
        background: "rgba(196,124,0,0.15)",
        color: "#7a4a00",
        border: "0.5px solid rgba(196,124,0,0.30)",
    },
    processing: {
        background: "rgba(53,118,174,0.14)",
        color: "#1a3f6e",
        border: "0.5px solid rgba(53,118,174,0.30)",
    },
    complete: {
        background: "rgba(46,31,8,0.08)",
        color: "rgba(46,31,8,0.60)",
        border: "0.5px solid rgba(46,31,8,0.15)",
    },
    failed: {
        background: "rgba(139,53,32,0.12)",
        color: "#8b3520",
        border: "0.5px solid rgba(139,53,32,0.25)",
    },
};

const isActive = (status: ReindexJob["status"]) =>
    status === "queued" || status === "processing";

export function ReindexButton({onReindex, job}: ReindexButtonProps) {
    const running = job ? isActive(job.status) : false;
    const {t} = useI18n();

    return (
        <div
            style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontFamily:
                    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
            }}
        >
            {job && (
                <span
                    style={{
                        ...STATUS_STYLE[job.status],
                        borderRadius: "9999px",
                        padding: "3px 10px",
                        fontSize: "11px",
                        fontWeight: 600,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        whiteSpace: "nowrap",
                    }}
                >
          {isActive(job.status) && (
              <span
                  style={{
                      display: "inline-block",
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      border: "1.5px solid currentColor",
                      borderTopColor: "transparent",
                      animation: "spin 0.6s linear infinite",
                  }}
              />
          )}
                    {t(STATUS_KEY[job.status])}
                    {job.status === "processing" && job.progress != null && (
                        <span
                            style={{
                                marginLeft: "2px",
                                fontVariantNumeric: "tabular-nums",
                            }}
                        >
              {job.progress}%
            </span>
                    )}
        </span>
            )}
            <button
                style={{
                    background: "rgba(255,255,255,0.25)",
                    border: "0.5px solid rgba(255,255,255,0.45)",
                    borderRadius: "10px",
                    padding: "7px 14px",
                    fontSize: "12.5px",
                    color: "rgba(46,31,8,0.70)",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    cursor: running ? "default" : "pointer",
                    opacity: running ? 0.5 : 1,
                    fontFamily: "inherit",
                    fontWeight: 500,
                    transition: "opacity 0.12s",
                }}
                disabled={running}
                onClick={onReindex}
            >
                <RefreshCw
                    size={14}
                    style={{
                        animation: running ? "spin 1s linear infinite" : "none",
                    }}
                />
                {t("documents.reindex")}
            </button>
        </div>
    );
}
