"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { ReindexJob } from "./use-documents";

interface ReindexButtonProps {
  onReindex: () => Promise<void>;
  job: ReindexJob | null;
}

const STATUS_LABEL: Record<ReindexJob["status"], string> = {
  queued: "Queued",
  processing: "Processing",
  complete: "Complete",
  failed: "Failed",
};

const STATUS_VARIANT: Record<
  ReindexJob["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  queued: "secondary",
  processing: "default",
  complete: "outline",
  failed: "destructive",
};

const isActive = (status: ReindexJob["status"]) =>
  status === "queued" || status === "processing";

export function ReindexButton({ onReindex, job }: ReindexButtonProps) {
  const running = job ? isActive(job.status) : false;

  return (
    <div className="flex items-center gap-2">
      {job && (
        <Badge variant={STATUS_VARIANT[job.status]} className="gap-1">
          {isActive(job.status) && (
            <span className="size-2 rounded-full border border-current border-t-transparent animate-spin inline-block" />
          )}
          {STATUS_LABEL[job.status]}
          {job.status === "processing" && job.progress != null && (
            <span className="ml-0.5 tabular-nums">{job.progress}%</span>
          )}
        </Badge>
      )}
      <Button
        variant="outline"
        size="sm"
        disabled={running}
        onClick={onReindex}
        className="gap-1.5"
      >
        <RefreshCw className={running ? "animate-spin" : ""} />
        Reindex
      </Button>
    </div>
  );
}
