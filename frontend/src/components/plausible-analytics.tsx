"use client";

import Script from "next/script";
import {usePathname} from "next/navigation";

const APP_PATHS = ["/chat", "/documents", "/settings", "/billing"];

export function PlausibleAnalytics() {
    const pathname = usePathname();
    if (APP_PATHS.some((p) => pathname.startsWith(p))) return null;
    return (
        <Script
            defer
            data-domain="vitreon.app"
            src="https://plausible.io/js/script.js"
            strategy="afterInteractive"
        />
    );
}
