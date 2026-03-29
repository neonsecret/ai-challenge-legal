import type {NextConfig} from "next";

const isDev = process.env.NODE_ENV === "development";
const apiOrigin = "https://api.vitreon.app";
const devOrigin = "http://localhost:8000";

const nextConfig: NextConfig = {
    allowedDevOrigins: isDev ? ["192.168.0.150"] : [],
    async headers() {
        const connectSrc = isDev
            ? `connect-src 'self' ${apiOrigin} ${devOrigin}`
            : `connect-src 'self' ${apiOrigin}`;
        const frameSrc = isDev
            ? `frame-src 'self' blob: ${apiOrigin} ${devOrigin}`
            : `frame-src 'self' blob: ${apiOrigin}`;
        const scriptSrc = isDev
            ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
            : "script-src 'self' 'unsafe-inline'";
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
                source: "/((?!_next/static|favicon).*)",
                headers: [
                    {key: "Cache-Control", value: "no-cache, no-store, must-revalidate"},
                ],
            },
            {
                source: "/(.*)",
                headers: [
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
                            "img-src 'self' data: blob: https://lh3.googleusercontent.com",
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
