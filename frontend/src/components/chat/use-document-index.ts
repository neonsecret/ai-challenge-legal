"use client"

import {useMemo} from "react"
import type {Message} from "./chat-state"

export interface IndexEntry {
    docId: string
    lawName: string
    sectionNumber: string
    pages: number[]
    score: number
    text: string
    turnIndices: number[]
    citationCount: number
}

const LAW_NAMES: Record<string, string> = {
    zakonik_prace: "Zakonik prace",
    obcansky_zakonik: "Obcansky zakonik",
    trestni_zakonik: "Trestni zakonik",
    zakon_obch_korporace: "Zakon o obch. korporacich",
    spravni_rad: "Spravni rad",
    zivnostensky_zakon: "Zivnostensky zakon",
    zakon_duchodove_pojisteni: "Zakon o duch. pojisteni",
    zakon_dph: "Zakon o DPH",
    zakon_dane_prijmu: "Zakon o danich z prijmu",
    zakon_nemocenske_pojisteni: "Zakon o nem. pojisteni",
    danovy_rad: "Danovy rad",
}

const SECTION_RE = /\u00a7\s*\d+[a-z]?/

function parseLawName(docId: string, text: string): string {
    // Check known Czech doc_id prefixes
    for (const [prefix, name] of Object.entries(LAW_NAMES)) {
        if (docId.startsWith(prefix)) return name
    }
    // DIFC docs have hash-based doc_ids — extract law name from text header
    if (/^[0-9a-f]{20,}$/i.test(docId) && text) {
        const headerMatch = text.match(/^\[([^\]]+)\]/)
        if (headerMatch) return headerMatch[1]
    }
    // Fallback: humanize the doc_id
    return docId.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

function parseSectionNumber(text: string): string {
    if (!text) return ""
    const match = text.match(SECTION_RE)
    if (match) return match[0]
    // Try Article N pattern for DIFC
    const articleMatch = text.match(/Article\s+\d+(?:\(\d+\))?/)
    if (articleMatch) return articleMatch[0]
    return ""
}

export function useDocumentIndex(messages: Message[]): IndexEntry[] {
    return useMemo(() => {
        const map = new Map<string, {
            docId: string
            pages: Set<number>
            score: number
            text: string
            turnIndices: Set<number>
            citationCount: number
        }>()

        messages.forEach((msg, idx) => {
            if (msg.role !== "assistant" || !msg.sources) return
            for (const source of msg.sources) {
                const existing = map.get(source.doc_id)
                if (existing) {
                    for (const p of source.page_numbers) existing.pages.add(p)
                    existing.turnIndices.add(idx)
                    existing.citationCount += 1
                    // Keep the longest text (more context)
                    if (source.text && source.text.length > existing.text.length) {
                        existing.text = source.text
                    }
                } else {
                    map.set(source.doc_id, {
                        docId: source.doc_id,
                        pages: new Set(source.page_numbers),
                        score: 0,
                        text: source.text ?? "",
                        turnIndices: new Set([idx]),
                        citationCount: 1,
                    })
                }
            }
        })

        return Array.from(map.values())
            .map(entry => ({
                docId: entry.docId,
                lawName: parseLawName(entry.docId, entry.text),
                sectionNumber: parseSectionNumber(entry.text),
                pages: Array.from(entry.pages).sort((a, b) => a - b),
                score: entry.score,
                text: entry.text,
                turnIndices: Array.from(entry.turnIndices).sort((a, b) => a - b),
                citationCount: entry.citationCount,
            }))
            .sort((a, b) => b.citationCount - a.citationCount)
    }, [messages])
}
