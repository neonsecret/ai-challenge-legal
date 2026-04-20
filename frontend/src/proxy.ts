import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

/**
 * Proxy (formerly middleware in Next.js <16).
 *
 * 1. HTTP → HTTPS 301 redirect in production (fixes duplicate indexing
 *    where Google sees http://vitreon.app and https://vitreon.app as
 *    separate pages). Uses the x-forwarded-proto header set by Cloudflare.
 *
 * 2. Reads the Cloudflare CF-IPCountry header and stores the 2-letter
 *    country code in a cookie so client components can access it without
 *    a server round-trip.
 *
 * Fallback: when headers are absent (local dev), neither redirect nor
 * cookie is applied — the frontend defaults to "en" content.
 */
export function proxy(request: NextRequest) {
    // --- HTTP → HTTPS redirect (production only) ---
    if (process.env.NODE_ENV === "production") {
        const proto = request.headers.get("x-forwarded-proto")
        if (proto === "http") {
            const httpsUrl = new URL(request.url)
            httpsUrl.protocol = "https:"
            return NextResponse.redirect(httpsUrl, 301)
        }
    }

    // --- Geo-country cookie from Cloudflare ---
    const country = request.headers.get("cf-ipcountry")
    const response = NextResponse.next()

    if (country) {
        response.cookies.set("geo_country", country, {
            path: "/",
            httpOnly: false,
            secure: false,
            sameSite: "lax",
            /* Refresh on every request so it stays current */
            maxAge: 60 * 60, // 1 hour
        })
    }

    return response
}

export const config = {
    matcher: [
        /*
         * Run on all page routes but skip API, static files, images,
         * and common metadata files.
         */
        "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
    ],
}
