"use client"

import {
    createContext,
    useContext,
    useState,
    useCallback,
    useEffect,
    type ReactNode,
} from "react"

export type Locale = "en" | "cs" | "de" | "ru" | "ar"

export const LOCALES: { code: Locale; label: string; flag: string }[] = [
    { code: "en", label: "English", flag: "\ud83c\uddec\ud83c\udde7" },
    { code: "cs", label: "\u010ce\u0161tina", flag: "\ud83c\udde8\ud83c\uddff" },
    { code: "de", label: "Deutsch", flag: "\ud83c\udde9\ud83c\uddea" },
    { code: "ru", label: "\u0420\u0443\u0441\u0441\u043a\u0438\u0439", flag: "\ud83c\uddf7\ud83c\uddfa" },
    { code: "ar", label: "\u0627\u0644\u0639\u0631\u0628\u064a\u0629", flag: "\ud83c\udde6\ud83c\uddea" },
]

const STORAGE_KEY = "vitreon_locale"

interface I18nContextValue {
    locale: Locale
    setLocale: (l: Locale) => void
    t: (key: string) => string
}

const I18nContext = createContext<I18nContextValue>({
    locale: "en",
    setLocale: () => {},
    t: (key: string) => key,
})

// Static imports so the JSON is bundled (no dynamic fetch needed)
import en from "@/lib/locales/en.json"
import cs from "@/lib/locales/cs.json"
import de from "@/lib/locales/de.json"
import ru from "@/lib/locales/ru.json"
import ar from "@/lib/locales/ar.json"

const dictionaries: Record<Locale, Record<string, string>> = { en, cs, de, ru, ar }

function isLocale(v: string): v is Locale {
    return ["en", "cs", "de", "ru", "ar"].includes(v)
}

function detectBrowserLocale(): Locale {
    if (typeof navigator === "undefined") return "en"
    const langs = navigator.languages ?? [navigator.language]
    for (const lang of langs) {
        const code = lang.split("-")[0].toLowerCase()
        if (isLocale(code)) return code
    }
    return "en"
}

export function I18nProvider({ children }: { children: ReactNode }) {
    const [locale, setLocaleState] = useState<Locale>("en")
    const [hydrated, setHydrated] = useState(false)

    // Read stored or browser locale once on mount.
    // Cloudflare geo cookie (set by proxy.ts) is a stronger signal than browser locale
    // for first-time visitors — a Czech user with English browser UI still gets Czech.
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored && isLocale(stored)) {
            setLocaleState(stored)
        } else {
            // Check Cloudflare geo cookie first
            const geoMatch = document.cookie.split("; ").find(r => r.startsWith("geo_country="))
            const geoCountry = geoMatch?.split("=")[1]
            const GEO_TO_LOCALE: Record<string, Locale> = { CZ: "cs", DE: "de", AT: "de", RU: "ru", AE: "ar" }
            const geoLocale = geoCountry ? GEO_TO_LOCALE[geoCountry] : undefined
            setLocaleState(geoLocale ?? detectBrowserLocale())
        }
        setHydrated(true)
    }, [])

    // Apply dir="rtl" for Arabic on <html>
    useEffect(() => {
        if (!hydrated) return
        const html = document.documentElement
        html.dir = locale === "ar" ? "rtl" : "ltr"
        html.lang = locale
    }, [locale, hydrated])

    const setLocale = useCallback((l: Locale) => {
        setLocaleState(l)
        localStorage.setItem(STORAGE_KEY, l)
    }, [])

    const t = useCallback(
        (key: string): string => {
            return dictionaries[locale]?.[key] ?? dictionaries.en[key] ?? key
        },
        [locale],
    )

    return (
        <I18nContext.Provider value={{ locale, setLocale, t }}>
            {children}
        </I18nContext.Provider>
    )
}

export function useI18n() {
    return useContext(I18nContext)
}
