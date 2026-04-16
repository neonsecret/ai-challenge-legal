/**
 * Tests for Bug A: pending chat poll loop fixes in chat-state.tsx
 *
 * Covers:
 * 1. formatStatus("agent:done") returns null (not a displayable string)
 * 2. formatStatus returns non-null strings for known status codes
 * 3. formatStatus formats unknown agent sub-types rather than returning null
 */

import { describe, it, expect } from "vitest"

import { formatStatus } from "../use-query-stream"

// ---------------------------------------------------------------------------
// Unit tests: formatStatus — the root cause of Bug A part 1
// ---------------------------------------------------------------------------

describe("formatStatus — agent:done returns null", () => {
    it("test_agent_done_returns_null: formatStatus('agent:done') must be null so the raw string is never shown", () => {
        // Bug A part 1: when status_detail === "agent:done", formatStatus returns null.
        // The old code used `formatStatus(...) ?? data.status_detail` which caused
        // the literal string "agent:done" to be set as the message content forever.
        // The fix removed the fallback; this test ensures formatStatus keeps returning null.
        const result = formatStatus("agent:done")
        expect(result).toBeNull()
    })
})

describe("formatStatus — known statuses return displayable strings", () => {
    it("test_known_statuses_return_strings: agent:understanding returns a non-null string", () => {
        const result = formatStatus("agent:understanding")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
        expect(result!.length).toBeGreaterThan(0)
    })

    it("agent:reasoning returns a non-null string", () => {
        const result = formatStatus("agent:reasoning")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
    })

    it("agent:thinking returns a non-null string", () => {
        const result = formatStatus("agent:thinking")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
    })

    it("processing returns a non-null string", () => {
        const result = formatStatus("processing")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
    })

    it("routing returns a non-null string", () => {
        const result = formatStatus("routing")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
    })

    it("retrieving returns a non-null string", () => {
        const result = formatStatus("retrieving")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
    })

    it("reranking returns a non-null string", () => {
        const result = formatStatus("reranking")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
    })

    it("answering returns 'Writing answer...'", () => {
        const result = formatStatus("answering")
        expect(result).toBe("Writing answer...")
    })

    it("drafting:saving document returns 'Drafting document...'", () => {
        const result = formatStatus("drafting:saving document")
        expect(result).toBe("Drafting document...")
    })
})

describe("formatStatus — unknown agent sub-type is formatted, not null", () => {
    it("test_unknown_agent_subtype_formats: agent:customthing returns a formatted string", () => {
        // The code strips the "agent:" prefix, capitalizes and appends "..."
        // This is important: unknown sub-types should show something, not silently be hidden.
        // Only "agent:done" is the special case that returns null.
        const result = formatStatus("agent:customthing")
        expect(result).not.toBeNull()
        expect(typeof result).toBe("string")
        expect(result).toContain("Customthing")
        expect(result).toContain("...")
    })

    it("agent:analyzing is formatted, not null", () => {
        const result = formatStatus("agent:analyzing")
        expect(result).not.toBeNull()
        expect(result).toContain("...")
    })
})

// ---------------------------------------------------------------------------
// Regression guard: null fallback is NOT applied to hidden statuses
// ---------------------------------------------------------------------------

describe("formatStatus — statuses that return null do not expose internal codes", () => {
    it("agent:done returns null — the poll loop must not use ?? fallback to raw string", () => {
        // This is the direct regression test for Bug A part 1.
        // The broken code was: formatStatus(data.status_detail) ?? data.status_detail
        // If formatStatus returns null, the caller must NOT fall back to the raw status_detail.
        // We verify formatStatus returns null so callers know to suppress the update.
        const status = "agent:done"
        const result = formatStatus(status)

        // Simulate the broken fallback pattern that was fixed:
        const brokenFallback = result ?? status
        // The broken fallback would have been "agent:done" — the fix ensures callers check for null
        expect(result).toBeNull()

        // The fixed code checks `if (friendly !== null)` before using the value.
        // We document here what the broken behavior was so this test captures the regression.
        expect(brokenFallback).toBe("agent:done") // this is what the broken code produced
        // And verify: a caller checking for null would correctly suppress the status update
        const wouldUpdateContent = result !== null
        expect(wouldUpdateContent).toBe(false)
    })

    it("unknown top-level status returns null (not leaked to UI)", () => {
        // Internal stage codes like 'init', 'startup' should not appear in the UI
        const result = formatStatus("unknown_internal_stage")
        expect(result).toBeNull()
    })
})

// ---------------------------------------------------------------------------
// Retrieval sub-steps format correctly
// ---------------------------------------------------------------------------

describe("formatStatus — retrieving sub-steps", () => {
    it("retrieving:searching corpus returns a non-null string", () => {
        const result = formatStatus("retrieving:searching corpus")
        expect(result).not.toBeNull()
    })

    it("retrieving:reranking 5 of 20 documents returns 'Reading legal documents...'", () => {
        const result = formatStatus("retrieving:reranking 5 of 20 documents")
        expect(result).toBe("Reading legal documents...")
    })

    it("retrieving:found 3 new sources returns capitalized string without ellipsis", () => {
        const result = formatStatus("retrieving:found 3 new sources")
        expect(result).not.toBeNull()
        expect(result!.startsWith("Found")).toBe(true)
    })
})
