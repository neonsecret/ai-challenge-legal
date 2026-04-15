export interface SourceRef {
    doc_id: string
    page_numbers: number[]
    text?: string | null
    url?: string | null
    title?: string | null
    chunk_id?: string | null
    source_type?: "statute" | "court_decision" | "txt" | null
    case_number?: string | null
    decision_date?: string | null
    court?: string | null
    category?: string | null
    ecli?: string | null
    legal_thesis?: string | null
    media_type?: string | null
}

/** Check if a source is a TXT document.
 *  Priority order:
 *  1. source_type === "txt"  — authoritative once NEO-2092 backend propagation lands
 *  2. media_type === "text/plain" — MIME-based fallback
 *  3. doc_id ends with ".txt" — last-resort for hypothetical named doc_ids (UUIDs won't match) */
export function isTxtSource(source: {
    doc_id: string
    source_type?: string | null
    media_type?: string | null
}): boolean {
    if (source.source_type === "txt") return true
    if (source.media_type === "text/plain") return true
    return source.doc_id.toLowerCase().endsWith(".txt")
}

/**
 * Strip the SAC context prefix that the indexer prepends to stored chunk text.
 * Format: "[DOCUMENT: summary | context]\n\nraw body" or "[doc_id] breadcrumb\n\nbody"
 * We want only the raw body for PDF text layer matching.
 */
export function stripChunkPrefix(text: string | null | undefined): string | undefined {
    if (!text) return undefined
    // Match [ANYTHING] optionally followed by text on the same line, then newlines
    let stripped = text.replace(/^\[[^\]]*\][^\n]*\n+/, "").trim()
    // Also strip continuation breadcrumb lines (e.g. "Preamble (continued)")
    stripped = stripped.replace(/^[^\n]*\(continued\)\s*\n+/i, "").trim()
    return stripped || undefined
}

/** Remove overlapping text between consecutive chunks.
 *  Chunks use 200-char overlap for retrieval; when displayed together the overlap duplicates text. */
export function deduplicateChunkTexts(texts: string[]): string[] {
    if (texts.length <= 1) return texts
    const result = [texts[0]]
    for (let i = 1; i < texts.length; i++) {
        const prev = texts[i - 1]
        const curr = texts[i]
        // Find longest suffix of prev that matches a prefix of curr
        let overlap = 0
        const maxCheck = Math.min(400, prev.length, curr.length)
        for (let size = maxCheck; size >= 20; size--) {
            if (prev.endsWith(curr.slice(0, size))) {
                overlap = size
                break
            }
        }
        result.push(overlap > 0 ? curr.slice(overlap).trim() : curr)
    }
    return result
}

/** Check if a URL has a safe protocol (http/https only — blocks javascript: etc). */
export function isSafeUrl(raw: string): boolean {
    try { return ["https:", "http:"].includes(new URL(raw).protocol) }
    catch { return false }
}

/** Check if a source is a web source (doc_id starts with "web:" or has a url field). */
export function isWebSource(source: SourceRef): boolean {
    return source.doc_id.startsWith("web:") || !!source.url
}

/** Extract the domain from a URL string. */
export function getDomain(url: string): string {
    try {
        return new URL(url).hostname
    } catch {
        return url.slice(0, 40)
    }
}

export function isCourtDecision(source: SourceRef): boolean {
    return source.source_type === "court_decision"
}

/** Format ISO date string "2023-06-15" → "15. 6. 2023" (Czech convention). */
export function formatCzechDate(iso: string | null | undefined): string | null {
    if (!iso) return null
    const parts = iso.split("-")
    if (parts.length !== 3) return iso
    return `${parseInt(parts[2])}. ${parseInt(parts[1])}. ${parts[0]}`
}

/** Navigation/boilerplate lines to strip from raw judgment text.
 *  Matches lines that consist entirely of common nav items. */
export const NAV_BOILERPLATE_RE = /^\s*(DIFC Courts?|Home|About|FAQs?|Careers?|Contact|Login|Sign [Ii]n|Newsroom|News|Media|Press|Subscribe|Newsletter|Search|Menu|Skip to (?:content|main)|Cookie|Privacy|Terms|Accessibility|Sitemap|Follow us|Share|Print|Back to top|Copyright|All [Rr]ights [Rr]eserved|\u00a9.*$|Toggle navigation|Close)\s*$/i

/** Maximum character count before truncation in the source panel */
export const TEXT_TRUNCATE_LIMIT = 2000

export const API_BASE = process.env.NEXT_PUBLIC_SSE_URL ?? ""

/** Strip navigation boilerplate, insert paragraph breaks, and clean up raw judgment text.
 *  DIFC judgment TXT files are scraped webpage text — one continuous blob
 *  with navigation menus, breadcrumbs, and no paragraph breaks. */
export function cleanJudgmentText(raw: string): string {
    let text = raw
    // Strip everything before the first case-like heading (e.g. "Claim No:", "IN THE COURT").
    // Patterns require start-of-line + specific structure to avoid matching normal words
    // like "before" in statute text (e.g. "before the commencement of this section").
    const caseStart = text.search(/(?:^Claim No[.:]|^IN THE\s+(?:COURT|MATTER)|^BETWEEN\s*\n|^BEFORE\s*[:;]|^Hearing\s*:|^Judgment\s*:)/im)
    if (caseStart > 100) text = text.slice(caseStart)

    // Insert paragraph breaks before numbered paragraphs (1. 2. 3. etc.)
    text = text.replace(/([.!?"'])\s*(\d{1,3}\.\s+[A-Z])/g, "$1\n\n$2")
    // Insert breaks before common legal section headers
    text = text.replace(/((?:IT IS HEREBY ORDERED|JUDGMENT OF|Background|Parties|The Claimant|The Defendant|Conclusion|Analysis|Discussion|Issues?|Decision|Orders?)\s*(?:that)?:?)/gi, "\n\n$1")
    // Insert breaks before ALLCAPS headings (3+ consecutive caps words)
    text = text.replace(/([.!?])\s*([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})*)/g, "$1\n\n$2")

    // Now filter lines
    return text
        .split("\n")
        .filter((line) => !NAV_BOILERPLATE_RE.test(line))
        .join("\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim()
}
