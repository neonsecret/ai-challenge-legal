import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

/**
 * Proxy (formerly middleware in Next.js <16) that reads the Cloudflare
 * CF-IPCountry header and stores the 2-letter country code in a cookie
 * so client components can access it without a server round-trip.
 *
 * Fallback: when the header is absent (local dev), no cookie is set
 * and the frontend defaults to "en" content.
 */
export function proxy(request: NextRequest) {
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
