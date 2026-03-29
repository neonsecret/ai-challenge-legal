"use client"

import dynamic from "next/dynamic"
import {Loader2} from "lucide-react"
import type {PdfViewerProps} from "./pdf-viewer-impl"

/**
 * Dynamically import the react-pdf implementation to avoid SSR issues.
 * pdfjs-dist references browser-only APIs (DOMMatrix, canvas) at module
 * evaluation time, which breaks during Next.js static generation.
 */
const PdfViewerImpl = dynamic(() => import("./pdf-viewer-impl"), {
    ssr: false,
    loading: () => <PdfViewerSkeleton/>,
})

function PdfViewerSkeleton() {
    return (
        <div className="flex h-full items-center justify-center rounded-xl"
             style={{background: "rgba(255,255,255,0.04)"}}
        >
            <Loader2 className="size-5 animate-spin" style={{color: "rgba(201,168,76,0.60)"}}/>
        </div>
    )
}

export function PdfViewer(props: PdfViewerProps) {
    return <PdfViewerImpl {...props} />
}
