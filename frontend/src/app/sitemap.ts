import type {MetadataRoute} from "next";

export default function sitemap(): MetadataRoute.Sitemap {
    const staticDate = new Date("2026-04-01");
    const blogDate = new Date("2026-04-27");

    return [
        {
            url: "https://vitreon.app",
            changeFrequency: "weekly",
            priority: 1.0,
            lastModified: new Date(),
        },
        {
            url: "https://vitreon.app/privacy",
            changeFrequency: "monthly",
            priority: 0.3,
            lastModified: staticDate,
        },
        {
            url: "https://vitreon.app/terms",
            changeFrequency: "monthly",
            priority: 0.3,
            lastModified: staticDate,
        },
        {
            url: "https://vitreon.app/about",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: staticDate,
        },
        {
            url: "https://vitreon.app/benchmarks",
            changeFrequency: "monthly",
            priority: 0.8,
            lastModified: staticDate,
        },
        {
            url: "https://vitreon.app/blog",
            changeFrequency: "weekly",
            priority: 0.6,
            lastModified: new Date(),
        },
        {
            url: "https://vitreon.app/blog/arlc-2026-results",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/blog/czech-legal-ai-sota",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/faq",
            changeFrequency: "monthly",
            priority: 0.5,
            lastModified: staticDate,
        },
        {
            url: "https://vitreon.app/cs",
            changeFrequency: "weekly",
            priority: 0.9,
            lastModified: new Date(),
        },
        {
            url: "https://vitreon.app/blog/zakonik-prace-2026-ai",
            changeFrequency: "monthly",
            priority: 0.8,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/blog/ai-pro-advokaty-2026",
            changeFrequency: "monthly",
            priority: 0.8,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/blog/commitment-career-growth",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/blog/commitment-dei",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/blog/commitment-environmental-sustainability",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/blog/commitment-social-impact",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: blogDate,
        },
        {
            url: "https://vitreon.app/blog/commitment-work-life-balance",
            changeFrequency: "monthly",
            priority: 0.7,
            lastModified: blogDate,
        },
    ];
}
