import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

/** HTTP→HTTPS redirect (vitreon.app only) + geo-country cookie from Cloudflare. */
export function proxy(request: NextRequest) {
    // --- HTTP → HTTPS redirect (production domain only) ---
    if (process.env.NODE_ENV === "production") {
        const proto = request.headers.get("x-forwarded-proto")
        const host = request.headers.get("host") || ""
        if (proto === "http" && host.includes("vitreon.app")) {
            return NextResponse.redirect(
                `https://${host}${request.nextUrl.pathname}${request.nextUrl.search}`,
                301,
            )
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
