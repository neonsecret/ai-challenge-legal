/**
 * Unit tests for isDraftingMode state machine in use-query-stream.ts
 *
 * Covers:
 * - Initial state (false)
 * - Set true when templateSlug provided
 * - Stays false when no templateSlug
 * - Cleared on: document_generated, done, error, abort(), HTTP error, connection error
 */

import { renderHook, act, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

// ─── Mock next/navigation before importing the hook ───────────────────────────
// vi.mock is hoisted by Vitest when used with static imports.
// Dynamic await import() bypasses hoisting — always use static imports here.

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: vi.fn() }),
}))

import { useQueryStream } from "../use-query-stream"

// ─── SSE stream helpers ───────────────────────────────────────────────────────

function makeSseStream(events: Array<{ event: string; data: string }>): ReadableStream<Uint8Array> {
    const encoder = new TextEncoder()
    return new ReadableStream<Uint8Array>({
        start(controller) {
            for (const { event, data } of events) {
                controller.enqueue(encoder.encode(`event: ${event}\ndata: ${data}\n\n`))
            }
            controller.close()
        },
    })
}

function makeSseResponse(events: Array<{ event: string; data: string }>): Response {
    return new Response(makeSseStream(events), {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
    })
}

const VALID_UUID = "12345678-1234-1234-1234-123456789abc"

const DONE_EVENTS = [{ event: "done", data: JSON.stringify({}) }]
const ERROR_EVENTS = [{ event: "error", data: JSON.stringify({ detail: "Test error" }) }]
const DOC_EVENTS = [
    {
        event: "document_generated",
        data: JSON.stringify({
            doc_id: VALID_UUID,
            template_slug: "nda",
            template_name: "NDA",
            version: 1,
            fields: { party: "Acme" },
        }),
    },
    { event: "done", data: JSON.stringify({}) },
]

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("useQueryStream — isDraftingMode state machine", () => {
    let originalFetch: typeof global.fetch

    beforeEach(() => {
        originalFetch = global.fetch
    })

    afterEach(() => {
        global.fetch = originalFetch
        vi.clearAllMocks()
    })

    it("initialises isDraftingMode to false", () => {
        const { result } = renderHook(() => useQueryStream())
        expect(result.current.isDraftingMode).toBe(false)
    })

    it("sets isDraftingMode=true on sendQuery when templateSlug is provided", () => {
        global.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft an NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        expect(result.current.isDraftingMode).toBe(true)
        expect(result.current.isStreaming).toBe(true)
    })

    it("keeps isDraftingMode=false on sendQuery when no templateSlug provided", () => {
        global.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("What is DIFC?", "difc")
        })

        expect(result.current.isDraftingMode).toBe(false)
        expect(result.current.isStreaming).toBe(true)
    })

    it("clears isDraftingMode on abort()", () => {
        global.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft contract", "difc", undefined, undefined, undefined, undefined, "nda")
        })
        expect(result.current.isDraftingMode).toBe(true)

        act(() => {
            result.current.abort()
        })

        expect(result.current.isDraftingMode).toBe(false)
        expect(result.current.isStreaming).toBe(false)
    })

    it("clears isDraftingMode when done event fires", async () => {
        global.fetch = vi.fn().mockResolvedValue(makeSseResponse(DONE_EVENTS)) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        await waitFor(() => expect(result.current.isStreaming).toBe(false))

        expect(result.current.isDraftingMode).toBe(false)
    })

    it("clears isDraftingMode when error event fires", async () => {
        global.fetch = vi.fn().mockResolvedValue(makeSseResponse(ERROR_EVENTS)) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        await waitFor(() => expect(result.current.isStreaming).toBe(false))

        expect(result.current.isDraftingMode).toBe(false)
    })

    it("clears isDraftingMode when document_generated event fires", async () => {
        global.fetch = vi.fn().mockResolvedValue(makeSseResponse(DOC_EVENTS)) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        await waitFor(() => expect(result.current.documents.length).toBeGreaterThan(0))

        expect(result.current.isDraftingMode).toBe(false)
    })

    it("clears isDraftingMode on HTTP error (non-2xx response)", async () => {
        global.fetch = vi.fn().mockResolvedValue(
            new Response(JSON.stringify({ detail: "Rate limited" }), { status: 429 }),
        ) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        await waitFor(() => expect(result.current.isStreaming).toBe(false))

        expect(result.current.isDraftingMode).toBe(false)
    })

    it("stream-end fallback clears isDraftingMode when stream closes without done event", async () => {
        // Empty event list — stream closes immediately, no done event
        global.fetch = vi.fn().mockResolvedValue(makeSseResponse([])) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        await waitFor(() => expect(result.current.isStreaming).toBe(false))

        expect(result.current.isDraftingMode).toBe(false)
    })

    it("document_generated populates documents array with correct data", async () => {
        global.fetch = vi.fn().mockResolvedValue(makeSseResponse(DOC_EVENTS)) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        await waitFor(() => expect(result.current.documents.length).toBe(1))

        expect(result.current.documents[0].doc_id).toBe(VALID_UUID)
        expect(result.current.documents[0].template_slug).toBe("nda")
    })

    it("document_generated with invalid UUID is silently dropped", async () => {
        const INVALID_EVENTS = [
            {
                event: "document_generated",
                data: JSON.stringify({ doc_id: "not-a-valid-uuid", template_slug: "nda" }),
            },
            { event: "done", data: JSON.stringify({}) },
        ]

        global.fetch = vi.fn().mockResolvedValue(makeSseResponse(INVALID_EVENTS)) as unknown as typeof fetch

        const { result } = renderHook(() => useQueryStream())

        act(() => {
            result.current.sendQuery("Draft NDA", "difc", undefined, undefined, undefined, undefined, "nda")
        })

        await waitFor(() => expect(result.current.isStreaming).toBe(false))

        expect(result.current.documents.length).toBe(0)
    })
})
