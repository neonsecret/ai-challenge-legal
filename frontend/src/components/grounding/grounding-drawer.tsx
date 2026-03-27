"use client"

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { GroundingView } from "./grounding-view"

interface SourceRef {
  doc_id: string
  page_numbers: number[]
}

interface GroundingDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  answer: string
  sources: SourceRef[]
}

export function GroundingDrawer({
  open,
  onOpenChange,
  answer,
  sources,
}: GroundingDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[90vw] p-0 flex flex-col gap-0"
        showCloseButton
      >
        <SheetHeader className="px-5 pt-4 pb-3 border-b border-border shrink-0">
          <SheetTitle className="text-sm font-semibold text-amber-400 tracking-wide uppercase">
            Source Grounding
          </SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-hidden min-h-0">
          <GroundingView answer={answer} sources={sources} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
