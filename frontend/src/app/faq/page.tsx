import Link from "next/link";
import type {Metadata} from "next";
import {ArrowRight} from "lucide-react";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";
import {FAQ_ITEMS, buildFaqJsonLd} from "@/lib/faq-data";

export const metadata: Metadata = {
    title: "FAQ — Vitreon Legal: AI Legal Research for Czech, DIFC, UK & AU Law",
    description:
        "Frequently asked questions about Vitreon Legal: AI-powered legal research, pricing, accuracy, Czech law coverage, DIFC, UK, Australian jurisdictions, source grounding, and data security.",
    keywords: [
        "Vitreon Legal FAQ",
        "AI legal research questions",
        "Czech legal AI FAQ",
        "legal AI pricing",
        "AI law assistant accuracy",
        "Beck-online alternativa FAQ",
        "česká judikatura AI dotazy",
    ],
    alternates: {
        canonical: "https://vitreon.app/faq",
        languages: {
            en: "https://vitreon.app/faq",
            cs: "https://vitreon.app/cs",
        },
    },
    openGraph: {
        title: "FAQ — Vitreon Legal: AI Legal Research for Czech, DIFC, UK & AU Law",
        description:
            "Frequently asked questions about Vitreon Legal: AI legal research, pricing, accuracy, Czech law coverage, jurisdictions, and data security.",
        url: "https://vitreon.app/faq",
        siteName: "Vitreon Legal",
        locale: "en",
        type: "website",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Vitreon Legal — FAQ",
            },
        ],
    },
};


export default function FAQPage() {
    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            {/* JSON-LD */}
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(buildFaqJsonLd())}}
            />

            <StrictNav />

            <main className="max-w-[880px] mx-auto px-4 sm:px-8 pt-16 pb-20">
                {/* Header */}
                <div className="mb-12">
                    <p
                        className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-4"
                        style={{color: "var(--strict-gold-text)"}}
                    >
                        Support
                    </p>
                    <h1
                        className="font-heading font-bold mb-4"
                        style={{
                            fontSize: "clamp(1.8rem, 3vw, 2.6rem)",
                            letterSpacing: "-0.03em",
                            lineHeight: 1.15,
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Frequently Asked Questions
                    </h1>
                    <p className="text-sm max-w-2xl" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        Everything you need to know about Vitreon Legal &mdash; our AI-powered legal research
                        platform, pricing, accuracy, and supported jurisdictions.
                    </p>
                </div>

                {/* Above-fold CTA */}
                <div
                    className="mb-12 rounded-2xl px-6 py-5 flex flex-col sm:flex-row items-center justify-between gap-4"
                    style={{
                        background: "var(--strict-gold-badge-bg)",
                        border: "1px solid var(--strict-gold-badge-border)",
                    }}
                >
                    <p className="text-sm font-medium" style={{color: "var(--strict-text-body)"}}>
                        Try it free &mdash; 10 queries per day, all jurisdictions, full source citations.
                    </p>
                    <Link
                        href="/login?mode=register"
                        className="inline-flex items-center gap-2 px-5 py-3 min-h-[44px] rounded-lg text-sm font-semibold whitespace-nowrap transition-opacity hover:opacity-90"
                        style={{background: "var(--strict-gold-base)", color: "var(--strict-bg-html)"}}
                    >
                        Get Started Free <ArrowRight size={14} />
                    </Link>
                </div>

                {/* FAQ Items */}
                <div className="space-y-0">
                    {FAQ_ITEMS.map((item, i) => (
                        <div key={i}>
                            <section className="py-8">
                                <h2
                                    className="font-heading font-bold mb-3"
                                    style={{
                                        fontSize: "1.1rem",
                                        color: "var(--strict-text-primary)",
                                        letterSpacing: "-0.01em",
                                    }}
                                >
                                    <span style={{
                                        color: "var(--strict-gold-text)",
                                        marginRight: "0.5rem",
                                        fontFamily: "var(--font-sans), sans-serif",
                                        fontSize: "0.85em",
                                        fontWeight: 500,
                                    }}>
                                        {String(i + 1).padStart(2, "0")}.
                                    </span>
                                    {item.question}
                                </h2>
                                <p
                                    className="text-sm leading-7 pl-0 sm:pl-8"
                                    style={{color: "var(--strict-text-body)"}}
                                >
                                    {item.answer}
                                </p>
                            </section>
                            {i < FAQ_ITEMS.length - 1 && (
                                <hr style={{borderColor: "var(--strict-hr-border)"}} />
                            )}
                        </div>
                    ))}
                </div>

                {/* CTA */}
                <div
                    className="mt-16 rounded-[14px] p-6 text-center"
                    style={{
                        background: "var(--strict-gold-badge-bg)",
                        border: "1px solid var(--strict-gold-badge-border)",
                    }}
                >
                    <p className="font-heading font-semibold text-base mb-2"
                       style={{color: "var(--strict-text-primary)"}}>
                        Still have questions?
                    </p>
                    <p className="text-sm mb-4" style={{color: "var(--strict-text-secondary)"}}>
                        Contact us at{" "}
                        <a href="mailto:legal@vitreon.app" style={{color: "var(--strict-gold-base)"}} className="hover:underline">
                            legal@vitreon.app
                        </a>{" "}
                        and we&apos;ll respond within 24 hours.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-3 justify-center">
                        <Link
                            href="/login?mode=register"
                            className="inline-flex items-center justify-center gap-2 px-5 py-3 min-h-[44px] rounded-lg text-sm font-semibold transition-opacity hover:opacity-90"
                            style={{
                                background: "var(--strict-gold-base)",
                                color: "var(--strict-bg-html)",
                            }}
                        >
                            Get Started Free <ArrowRight size={14} />
                        </Link>
                        <Link
                            href="/chat"
                            className="inline-flex items-center justify-center gap-2 px-5 py-3 min-h-[44px] rounded-lg text-sm font-medium transition-colors"
                            style={{
                                background: "var(--strict-glass-bg)",
                                border: "1px solid var(--strict-glass-border)",
                                color: "var(--strict-text-primary)",
                            }}
                        >
                            Try the Demo
                        </Link>
                    </div>
                </div>
            </main>

            <StrictFooter />
        </div>
    );
}
