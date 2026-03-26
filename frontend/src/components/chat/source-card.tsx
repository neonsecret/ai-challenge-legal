import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface SourceCardProps {
  doc_id: string
  page_numbers: number[]
  className?: string
}

export function SourceCard({ doc_id, page_numbers, className }: SourceCardProps) {
  const displayId = doc_id.length > 22 ? `…${doc_id.slice(-22)}` : doc_id

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/50 px-2.5 py-1 text-xs",
        className
      )}
    >
      <span className="font-mono text-muted-foreground" title={doc_id}>
        {displayId}
      </span>
      {page_numbers.map((page) => (
        <Badge key={page} variant="outline" className="h-4 px-1 text-[10px]">
          p.{page}
        </Badge>
      ))}
    </div>
  )
}
