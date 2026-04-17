"use client"

import { useState, useEffect, startTransition } from "react"

/**
 * Reads the `geo_country` cookie set by the proxy (from Cloudflare's
 * CF-IPCountry header). Returns the 2-letter country code or null
 * when unknown (local dev without Cloudflare).
 */
export function useGeoCountry(): string | null {
    const [country, setCountry] = useState<string | null>(null)

    useEffect(() => {
        const match = document.cookie
            .split("; ")
            .find((row) => row.startsWith("geo_country="))
        if (match) {
            startTransition(() => setCountry(match.split("=")[1] ?? null))
        }
    }, [])

    return country
}
