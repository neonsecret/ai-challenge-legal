/**
 * Shared types for document drafting feature (NEO-843).
 */

export interface Template {
    slug: string
    name: string
    description: string
    category: string
    jurisdiction: string
}

export interface ChatDocument {
    doc_id: string
    template_slug: string
    template_name: string
    version: number
    generated_at: string   // ISO 8601 — from SSE event or client-side fallback
}
