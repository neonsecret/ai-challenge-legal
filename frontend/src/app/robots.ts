import type {MetadataRoute} from "next";

export default function robots(): MetadataRoute.Robots {
    return {
        rules: [
            {
                userAgent: "*",
                allow: "/",
                disallow: ["/chat", "/billing", "/documents", "/settings", "/login", "/register", "/verify-email", "/reset-password", "/dashboard", "/api/"],
            },
            {
                userAgent: [
                    "GPTBot",
                    "OAI-SearchBot",
                    "ChatGPT-User",
                    "ClaudeBot",
                    "PerplexityBot",
                    "Google-Extended",
                    "Applebot-Extended",
                    "Amazonbot",
                    "FacebookBot",
                ],
                allow: "/",
            },
            {
                userAgent: ["Bytespider", "SemrushBot"],
                disallow: "/",
            },
        ],
        sitemap: "https://vitreon.app/sitemap.xml",
    };
}
