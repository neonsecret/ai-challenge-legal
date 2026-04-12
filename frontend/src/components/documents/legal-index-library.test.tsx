/**
 * Unit tests for expand/collapse interaction in LegalIndexLibrary.
 * Covers NEO-1653: expandable Czech statute listing in legal-index-library.tsx.
 *
 * Tests:
 * - Czech card (czech-civil) has role="button", tabIndex=0, aria-expanded
 * - DIFC, UK, AU cards are non-interactive (no role, tabIndex, or aria-expanded)
 * - aria-expanded toggles correctly on click
 * - Enter / Space keyboard events toggle the panel
 * - Expansion panel renders all 11 Czech statute rows when open; absent when closed
 * - Chevron span has aria-hidden="true" in both collapsed and expanded states
 * - Both dark-mode and light-mode rendering branches are exercised
 */

import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"

// ─── Mocks ────────────────────────────────────────────────────────────────────
// vi.mock calls are hoisted before imports — mocks are active before LegalIndexLibrary loads.

vi.mock("@/lib/i18n", () => ({
    useI18n: () => ({ t: (key: string) => key, locale: "en", setLocale: vi.fn() }),
}))

// Module-level variable — updated per describe block so the hook returns the right mode.
let isDarkMode = false

vi.mock("@/lib/color-mode", () => ({
    useColorMode: () => ({
        isDark: isDarkMode,
        mode: isDarkMode ? "dark" : "light",
        resolvedMode: isDarkMode ? "dark" : "light",
        setMode: vi.fn(),
    }),
}))

import { LegalIndexLibrary } from "./legal-index-library"

// ─── Real Czech statute local names (sourced directly from component constants) ─

const CZECH_STATUTE_LOCAL_NAMES = [
    "Občanský zákoník",
    "Zákoník práce",
    "Trestní zákoník",
    "Daňový řád",
    "Zákon o daních z příjmů",
    "Zákon o DPH",
    "Zákon o důchodovém pojištění",
    "Zákon o nemocenském pojištění",
    "Zákon o obchodních korporacích",
    "Správní řád",
    "Živnostenský zákon",
] as const

// ─── Helper ───────────────────────────────────────────────────────────────────

/** Returns the one interactive button in the library — the Czech card. */
function getCzechButton() {
    return screen.getByRole("button", { name: /czech/i })
}

// ─── Shared behaviour tests (run for both light and dark mode) ────────────────

function sharedTests() {
    it("Czech card has role='button' and tabIndex=0", () => {
        render(<LegalIndexLibrary />)
        const btn = getCzechButton()
        expect(btn).toBeInTheDocument()
        expect(btn).toHaveAttribute("tabindex", "0")
    })

    it("Czech card has aria-expanded=false initially", () => {
        render(<LegalIndexLibrary />)
        expect(getCzechButton()).toHaveAttribute("aria-expanded", "false")
    })

    it("only the Czech card is interactive (exactly one role=button in the document)", () => {
        render(<LegalIndexLibrary />)
        expect(screen.getAllByRole("button")).toHaveLength(1)
    })

    it("statute panel is absent before any interaction", () => {
        render(<LegalIndexLibrary />)
        for (const name of CZECH_STATUTE_LOCAL_NAMES) {
            expect(screen.queryByText(name)).not.toBeInTheDocument()
        }
    })

    it("click opens the panel: aria-expanded=true and all 11 statute rows visible", () => {
        render(<LegalIndexLibrary />)
        fireEvent.click(getCzechButton())
        expect(getCzechButton()).toHaveAttribute("aria-expanded", "true")
        for (const name of CZECH_STATUTE_LOCAL_NAMES) {
            expect(screen.getByText(name)).toBeInTheDocument()
        }
    })

    it("second click closes the panel: aria-expanded=false and statutes removed", () => {
        render(<LegalIndexLibrary />)
        fireEvent.click(getCzechButton())
        fireEvent.click(getCzechButton())
        expect(getCzechButton()).toHaveAttribute("aria-expanded", "false")
        for (const name of CZECH_STATUTE_LOCAL_NAMES) {
            expect(screen.queryByText(name)).not.toBeInTheDocument()
        }
    })

    it("Enter key opens the panel", () => {
        render(<LegalIndexLibrary />)
        fireEvent.keyDown(getCzechButton(), { key: "Enter" })
        expect(getCzechButton()).toHaveAttribute("aria-expanded", "true")
        expect(screen.getByText(CZECH_STATUTE_LOCAL_NAMES[0])).toBeInTheDocument()
    })

    it("Space key opens the panel", () => {
        render(<LegalIndexLibrary />)
        fireEvent.keyDown(getCzechButton(), { key: " " })
        expect(getCzechButton()).toHaveAttribute("aria-expanded", "true")
    })

    it("Enter key on an open panel closes it", () => {
        render(<LegalIndexLibrary />)
        fireEvent.keyDown(getCzechButton(), { key: "Enter" })
        fireEvent.keyDown(getCzechButton(), { key: "Enter" })
        expect(getCzechButton()).toHaveAttribute("aria-expanded", "false")
        expect(screen.queryByText(CZECH_STATUTE_LOCAL_NAMES[0])).not.toBeInTheDocument()
    })

    it("collapsed chevron span (▸) has aria-hidden='true'", () => {
        render(<LegalIndexLibrary />)
        const chevron = screen.getByText("\u25b8")
        expect(chevron).toHaveAttribute("aria-hidden", "true")
    })

    it("expanded chevron span (▾) has aria-hidden='true'", () => {
        render(<LegalIndexLibrary />)
        fireEvent.click(getCzechButton())
        const chevron = screen.getByText("\u25be")
        expect(chevron).toHaveAttribute("aria-hidden", "true")
    })
}

// ─── Light-mode describe ──────────────────────────────────────────────────────

describe("LegalIndexLibrary (light mode)", () => {
    beforeEach(() => {
        isDarkMode = false
    })

    sharedTests()
})

// ─── Dark-mode describe ───────────────────────────────────────────────────────

describe("LegalIndexLibrary (dark mode)", () => {
    beforeEach(() => {
        isDarkMode = true
    })

    sharedTests()
})
