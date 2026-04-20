import Link from "next/link";
import type {Metadata} from "next";
import { StrictNav } from "@/components/landing/strict/strict-nav";
import { StrictFooter } from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Blog — Vitreon Legal",
    description:
        "Technical blog from Vitreon Legal: benchmark results, competition reports, Czech legal AI research, and retrieval pipeline methodology.",
    alternates: {
        canonical: "https://vitreon.app/blog",
    },
    openGraph: {
        title: "Blog — Vitreon Legal",
        description:
            "Technical blog: benchmark results, competition reports, Czech legal AI research.",
        url: "https://vitreon.app/blog",
        siteName: "Vitreon Legal",
        type: "website",
    },
};

const POSTS = [
    {
        slug: "ai-pro-advokaty-2026",
        title: "AI pro advokáty 2026: Beck-online vs. Vitreon Legal — srovnání pro českou praxi",
        description:
            "Jak AI šetří 3–5 hodin týdně při právním výzkumu. Podrobné srovnání Beck-online, ASPI a Vitreon Legal — ceník v CZK, judikatura NSS a ÚS, citace ke každé odpovědi.",
        date: "18. dubna 2026",
        lang: "CS",
    },
    {
        slug: "zakonik-prace-2026-ai",
        title: "Zákoník práce 2026: AI odpovídá na 10 nejčastějších pracovněprávních otázek",
        description:
            "Výpověď, mzda, dovolená, home office — AI právní asistent odpovídá na nejčastější otázky zákoníku práce s přesnou citací z judikatury. Zdarma pro zaměstnance i zaměstnavatele.",
        date: "18. dubna 2026",
        lang: "CS",
    },
    {
        slug: "arlc-2026-results",
        title: "How Vitreon Placed 4th in ARLC 2026",
        description:
            "The story of team Neon Team at the Agentic RAG Legal Challenge 2026: methodology, scores, and what it means for legal AI.",
        date: "April 10, 2026",
        lang: "EN",
    },
    {
        slug: "czech-legal-ai-sota",
        title: "Jak Vitreon dosahuje +36% nad SOTA v českém právním AI",
        description:
            "Technický rozbor benchmarku GaRAGe, co znamená SOTA, jak funguje Vitreon retrieval pipeline a proč je to důležité pro judikaturu a právní výzkum.",
        date: "April 12, 2026",
        lang: "CS",
    },
];

export default function BlogIndexPage() {
    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            <StrictNav />

            <main className="max-w-[880px] mx-auto px-4 sm:px-8 pt-16 pb-20">
                {/* Header */}
                <div className="mb-12">
                    <p
                        className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-4"
                        style={{color: "var(--strict-gold-text)"}}
                    >
                        Blog
                    </p>
                    <h1
                        className="font-heading font-bold mb-4"
                        style={{
                            fontSize: "clamp(2rem, 4vw, 3rem)",
                            letterSpacing: "-0.025em",
                            lineHeight: 1.15,
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Vitreon Legal Blog
                    </h1>
                    <p className="text-sm max-w-2xl" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        Technical posts about legal AI, benchmark results, competition reports, and retrieval
                        pipeline research.
                    </p>
                </div>

                {/* Post List */}
                <div className="space-y-5">
                    {POSTS.map((post) => (
                        <Link
                            key={post.slug}
                            href={`/blog/${post.slug}`}
                            className="block p-6 group transition-shadow duration-200"
                            style={{
                                background: "var(--strict-glass-bg)",
                                border: "1px solid var(--strict-glass-border)",
                                backdropFilter: "var(--strict-glass-blur)",
                                borderRadius: "14px",
                            }}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <span
                                    className="text-xs"
                                    style={{color: "var(--strict-text-dim)"}}
                                >
                                    {post.date}
                                </span>
                                <span
                                    className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded"
                                    style={{
                                        background: "var(--strict-gold-badge-bg)",
                                        color: "var(--strict-gold-badge-text)",
                                        border: "1px solid var(--strict-gold-badge-border)",
                                    }}
                                >
                                    {post.lang}
                                </span>
                            </div>
                            <h2
                                className="font-heading font-bold mb-2 group-hover:opacity-80 transition-opacity"
                                style={{
                                    fontSize: "1.25rem",
                                    color: "var(--strict-text-primary)",
                                    letterSpacing: "-0.01em",
                                }}
                            >
                                {post.title}
                            </h2>
                            <p
                                className="text-sm leading-6"
                                style={{color: "var(--strict-text-body)"}}
                            >
                                {post.description}
                            </p>
                            <span
                                className="inline-block mt-3 text-sm font-medium"
                                style={{color: "var(--strict-gold-text)"}}
                            >
                                Read more &rarr;
                            </span>
                        </Link>
                    ))}
                </div>
            </main>

            <StrictFooter />
        </div>
    );
}
