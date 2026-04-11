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
    /** Index of the conversation turn (0-based pair index) that generated this document.
     *  Undefined for documents restored from backend without turn info (shown on latest pair as fallback). */
    turn_index?: number
}
