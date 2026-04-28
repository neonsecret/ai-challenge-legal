import type {NextConfig} from "next";

const isDev = process.env.NODE_ENV === "development";
const apiOrigin = "https://api.vitreon.app";
const devOrigin = "http://localhost:8000";

const nextConfig: NextConfig = {
    poweredByHeader: false,
    allowedDevOrigins: isDev ? ["192.168.0.150"] : [],
    async headers() {
        const connectSrc = isDev
            ? `connect-src 'self' ${apiOrigin} ${devOrigin}`
            : `connect-src 'self' ${apiOrigin}`;
        const frameSrc = isDev
            ? `frame-src 'self' blob: ${apiOrigin} ${devOrigin}`
            : `frame-src 'self' blob: ${apiOrigin}`;
        // https://static.cloudflareinsights.com is injected by Cloudflare Tunnel automatically
        const scriptSrc = isDev
            ? "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://static.cloudflareinsights.com"
            : "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com";
        const workerSrc = "worker-src 'self' blob:";

        return [
            {
                // Static assets — immutable, cache forever (filenames include content hash)
                source: "/_next/static/:path*",
                headers: [
                    {key: "Cache-Control", value: "public, max-age=31536000, immutable"},
                ],
            },
            {
                // HTML pages — never cache so deploys take effect immediately
                source: "/((?!_next/static|favicon|opengraph-image|apple-touch-icon|manifest.json).*)",
                headers: [
                    {key: "Cache-Control", value: "no-cache, no-store, must-revalidate"},
                ],
            },
            {
                // OG image — cache for 24 hours (static asset, doesn't change often)
                source: "/opengraph-image(.*)",
                headers: [
                    {key: "Cache-Control", value: "public, max-age=86400, stale-while-revalidate=3600"},
                ],
            },
            {
                // Other static assets — cache for 24 hours
                source: "/(apple-touch-icon|manifest.json)",
                headers: [
                    {key: "Cache-Control", value: "public, max-age=86400"},
                ],
            },
            {
                source: "/(.*)",
                headers: [
                    {key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload"},
                    {key: "X-Frame-Options", value: "DENY"},
                    {key: "X-Content-Type-Options", value: "nosniff"},
                    {key: "Referrer-Policy", value: "strict-origin-when-cross-origin"},
                    {key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()"},
                    {
                        key: "Content-Security-Policy",
                        value: [
                            "default-src 'self'",
                            scriptSrc,
                            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                            "font-src 'self' https://fonts.gstatic.com",
                            "img-src 'self' data: blob: https://lh3.googleusercontent.com https://icons.duckduckgo.com",
                            connectSrc,
                            workerSrc,
                            frameSrc,
                            "frame-ancestors 'none'",
                        ].join("; "),
                    },
                ],
            },
        ];
    },
    async redirects() {
        return [
            {
                source: "/pricing",
                destination: "/#pricing",
                permanent: true,
            },
        ];
    },
    async rewrites() {
        // BACKEND_URL is server-side only (not NEXT_PUBLIC_) — safe for secrets
        const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
        return [
            {
                source: "/api/:path*",
                destination: `${backend}/api/:path*`,
            },
            {
                source: "/health",
                destination: `${backend}/health`,
            },
        ];
    },
};

export default nextConfig;
