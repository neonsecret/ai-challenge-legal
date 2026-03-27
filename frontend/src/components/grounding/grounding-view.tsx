"use client"

import { useState } from "react"
import Split from "react-split"
import { PdfViewer } from "./pdf-viewer"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface SourceRef {
  doc_id: string
  page_numbers: number[]
}

interface GroundingViewProps {
  answer: string
  sources: SourceRef[]
}

export function GroundingView({ answer, sources }: GroundingViewProps) {
  const [activeSource, setActiveSource] = useState<SourceRef | null>(
    sources.length > 0 ? sources[0] : null
  )
  const [activePage, setActivePage] = useState<number>(
    sources.length > 0 && sources[0].page_numbers.length > 0 ? sources[0].page_numbers[0] : 1
  )

  const handleSourceClick = (source: SourceRef, page: number) => {
    setActiveSource(source)
    setActivePage(page)
  }

  return (
    <Split
      className="flex h-full"
      sizes={[45, 55]}
      minSize={280}
      gutterSize={6}
      gutterStyle={() => ({
        backgroundColor: "hsl(var(--border))",
        cursor: "col-resize",
      })}
    >
      {/* Left panel: answer + source cards */}
      <div className="flex flex-col gap-4 overflow-y-auto p-5">
        <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer}</p>
        </div>

        {sources.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Sources
            </p>
            {sources.map((source, i) => (
              <SourceCitationCard
                key={`${source.doc_id}-${i}`}
                source={source}
                isActive={activeSource?.doc_id === source.doc_id}
                activePage={activeSource?.doc_id === source.doc_id ? activePage : null}
                onPageClick={(page) => handleSourceClick(source, page)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Right panel: PDF viewer */}
      <div className="h-full overflow-hidden">
        {activeSource ? (
          <PdfViewer
            docId={activeSource.doc_id}
            page={activePage}
            className="h-full"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No source selected
          </div>
        )}
      </div>
    </Split>
  )
}

interface SourceCitationCardProps {
  source: SourceRef
  isActive: boolean
  activePage: number | null
  onPageClick: (page: number) => void
}

function SourceCitationCard({
  source,
  isActive,
  activePage,
  onPageClick,
}: SourceCitationCardProps) {
  const displayId =
    source.doc_id.length > 28 ? `…${source.doc_id.slice(-28)}` : source.doc_id

  return (
    <div
      className={cn(
        "rounded-lg border p-3 transition-colors",
        isActive
          ? "border-amber-500/40 bg-amber-500/5"
          : "border-border bg-muted/30 hover:border-border/80"
      )}
    >
      <p className="mb-2 font-mono text-xs text-muted-foreground" title={source.doc_id}>
        {displayId}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {source.page_numbers.map((page) => (
          <button
            key={page}
            onClick={() => onPageClick(page)}
            className={cn(
              "inline-flex h-6 items-center rounded px-2 text-[11px] font-medium transition-colors",
              isActive && activePage === page
                ? "bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/40"
                : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            )}
          >
            p.{page}
          </button>
        ))}
      </div>
    </div>
  )
}
