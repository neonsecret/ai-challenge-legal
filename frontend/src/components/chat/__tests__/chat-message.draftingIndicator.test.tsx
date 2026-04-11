/**
 * Unit tests for the "Drafting document..." indicator in ChatMessage.
 *
 * Covers:
 * - Indicator rendered when isStreaming=true, isDraftingMode=true, documents=[]
 * - Indicator NOT rendered when isDraftingMode=false (normal query)
 * - Indicator NOT rendered when documents.length > 0 (document arrived)
 * - Indicator NOT rendered when isStreaming=false
 */

import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"

// ─── Mock heavy dependencies before static import of ChatMessage ──────────────
// vi.mock() calls are hoisted by Vitest to run before any imports below.

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }))
vi.mock("react-markdown", () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }))
vi.mock("remark-gfm", () => ({ default: () => () => {} }))
vi.mock("unist-util-visit", () => ({ visit: () => {} }))
vi.mock("mdast-util-find-and-replace", () => ({ findAndReplace: () => {} }))
vi.mock("@/components/chat/feedback-buttons", () => ({ FeedbackButtons: () => null }))
vi.mock("@/components/chat/sources-panel", () => ({ SourcesPanel: () => null }))
vi.mock("@/components/chat/confidence-badge", () => ({ ConfidenceBadge: () => null }))
vi.mock("@/components/chat/pipeline-status-bar", () => ({ PipelineStatusBar: () => null }))
vi.mock("@/components/chat/document-card/DocumentCard", () => ({ DocumentCard: () => null }))
vi.mock("@/components/chat/message-parts/MessageCitations", () => ({ CitationButton: () => null }))
vi.mock("@/components/chat/message-parts/MessageFootnotes", () => ({ MessageFootnotes: () => null }))
vi.mock("@/components/chat/message-parts/MessageStatus", () => ({ MessageStatus: () => null }))

// Static import — mocks above are guaranteed to be applied first.
import { ChatMessage } from "../chat-message"

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("ChatMessage — drafting indicator", () => {
    it("renders indicator (data-testid) when isStreaming=true, isDraftingMode=true, documents=[]", () => {
        render(
            <ChatMessage
                role="assistant"
                content="Drafting your document, please wait..."
                isStreaming={true}
                isDraftingMode={true}
                documents={[]}
            />,
        )

        expect(screen.getByTestId("drafting-indicator")).toBeInTheDocument()
        expect(screen.getByText("Drafting document...")).toBeInTheDocument()
    })

    it("renders indicator even when content is empty (status-only mode)", () => {
        // content="" + isStreaming=true triggers isStatusOnly=true in the component.
        // The indicator is outside the answer card and must still render.
        render(
            <ChatMessage
                role="assistant"
                content=""
                isStreaming={true}
                isDraftingMode={true}
                documents={[]}
            />,
        )

        expect(screen.getByTestId("drafting-indicator")).toBeInTheDocument()
    })

    it("does NOT render indicator when isDraftingMode=false (normal query)", () => {
        render(
            <ChatMessage
                role="assistant"
                content="Here is your answer."
                isStreaming={true}
                isDraftingMode={false}
                documents={[]}
            />,
        )

        expect(screen.queryByTestId("drafting-indicator")).not.toBeInTheDocument()
    })

    it("does NOT render indicator when isStreaming=false", () => {
        render(
            <ChatMessage
                role="assistant"
                content="Done."
                isStreaming={false}
                isDraftingMode={true}
                documents={[]}
            />,
        )

        expect(screen.queryByTestId("drafting-indicator")).not.toBeInTheDocument()
    })

    it("does NOT render indicator when documents.length > 0 (document arrived)", () => {
        render(
            <ChatMessage
                role="assistant"
                content=""
                isStreaming={true}
                isDraftingMode={true}
                documents={[
                    {
                        doc_id: "12345678-1234-1234-1234-123456789abc",
                        template_slug: "nda",
                        template_name: "NDA",
                        version: 1,
                    },
                ]}
            />,
        )

        expect(screen.queryByTestId("drafting-indicator")).not.toBeInTheDocument()
    })

    it("does NOT render indicator for user role messages", () => {
        render(
            <ChatMessage
                role="user"
                content="Draft me an NDA"
                isStreaming={false}
                isDraftingMode={true}
                documents={[]}
            />,
        )

        expect(screen.queryByTestId("drafting-indicator")).not.toBeInTheDocument()
    })
})
