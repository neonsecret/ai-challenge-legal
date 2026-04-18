import type {MetadataRoute} from "next";

export default function sitemap(): MetadataRoute.Sitemap {
    return [
        {
            url: "https://vitreon.app",
            changeFrequency: "weekly",
            priority: 1.0,
        },
        {
            url: "https://vitreon.app/privacy",
            changeFrequency: "monthly",
            priority: 0.3,
        },
        {
            url: "https://vitreon.app/terms",
            changeFrequency: "monthly",
            priority: 0.3,
        },
        {
            url: "https://vitreon.app/about",
            changeFrequency: "monthly",
            priority: 0.7,
        },
        {
            url: "https://vitreon.app/benchmarks",
            changeFrequency: "monthly",
            priority: 0.8,
        },
        {
            url: "https://vitreon.app/blog",
            changeFrequency: "weekly",
            priority: 0.6,
        },
        {
            url: "https://vitreon.app/blog/arlc-2026-results",
            changeFrequency: "monthly",
            priority: 0.7,
        },
        {
            url: "https://vitreon.app/blog/czech-legal-ai-sota",
            changeFrequency: "monthly",
            priority: 0.7,
        },
        {
            url: "https://vitreon.app/faq",
            changeFrequency: "monthly",
            priority: 0.5,
        },
        {
            url: "https://vitreon.app/cs",
            changeFrequency: "weekly",
            priority: 0.9,
        },
        {
            url: "https://vitreon.app/blog/zakonik-prace-2026-ai",
            changeFrequency: "monthly",
            priority: 0.8,
        },
        {
            url: "https://vitreon.app/blog/ai-pro-advokaty-2026",
            changeFrequency: "monthly",
            priority: 0.8,
        },
    ];
}
