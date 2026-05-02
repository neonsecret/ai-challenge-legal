import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Vitreon Legal — Our Commitment to Equity in Legal AI",
    description:
        "Legal AI equity means removing barriers by jurisdiction, firm size, and income. Here's how Vitreon Legal is building more accessible legal research.",
    keywords: [
        "legal AI equity",
        "access to justice",
        "affordable legal research",
        "multi-jurisdiction",
        "inclusive legal technology",
        "legal tech accessibility",
        "DEI",
    ],
    alternates: {
        canonical: "https://vitreon.app/blog/commitment-dei",
        languages: {
            en: "https://vitreon.app/blog/commitment-dei",
        },
    },
    openGraph: {
        title: "Vitreon Legal — Our Commitment to Equity in Legal AI",
        description:
            "Legal AI equity means removing barriers by jurisdiction, firm size, and income. Here's how Vitreon Legal is building more accessible legal research.",
        url: "https://vitreon.app/blog/commitment-dei",
        siteName: "Vitreon Legal",
        locale: "en_US",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Our Commitment to Equity in Legal AI — Vitreon Legal",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Vitreon Legal — Our Commitment to Equity in Legal AI",
        description:
            "Legal AI equity means removing barriers by jurisdiction, firm size, and income. Here's how Vitreon Legal is building more accessible legal research.",
    },
};

export default function CommitmentDEIPost() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "Our Commitment to Equity in Legal AI",
        description:
            "Legal AI equity means removing barriers by jurisdiction, firm size, and income. Here's how Vitreon Legal is building more accessible legal research.",
        datePublished: "2026-04-26",
        inLanguage: "en",
        keywords: [
            "legal AI equity",
            "access to justice",
            "affordable legal research",
            "multi-jurisdiction",
            "inclusive legal technology",
            "legal tech accessibility",
            "DEI",
        ],
        articleSection: "Legal AI",
        author: {
            "@type": "Person",
            name: "Viacheslav Ivannikov",
        },
        publisher: {
            "@type": "Organization",
            "@id": "https://vitreon.app/#organization",
            name: "Vitreon Legal",
            url: "https://vitreon.app",
        },
        url: "https://vitreon.app/blog/commitment-dei",
        mainEntityOfPage: "https://vitreon.app/blog/commitment-dei",
        image: "https://vitreon.app/opengraph-image",
    };

    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(articleJsonLd)}}
            />
            <StrictNav />

            <main className="max-w-[880px] mx-auto px-4 sm:px-8 pt-16 pb-20">
                {/* Header */}
                <div className="mb-12">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-xs" style={{color: "var(--strict-text-dim)"}}>
                            April 26, 2026
                        </span>
                        <span
                            className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded"
                            style={{
                                background: "var(--strict-gold-badge-bg)",
                                color: "var(--strict-gold-badge-text)",
                                border: "1px solid var(--strict-gold-badge-border)",
                            }}
                        >
                            EN
                        </span>
                    </div>
                    <h1
                        className="font-heading font-bold mb-4"
                        style={{
                            fontSize: "clamp(2rem, 4vw, 2.75rem)",
                            letterSpacing: "-0.025em",
                            lineHeight: 1.2,
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Our Commitment to Equity in Legal AI
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        By Viacheslav Ivannikov, Founder of Vitreon Legal
                    </p>
                </div>

                {/* Article Body */}
                <article className="space-y-6">
                    <BodyText>
                        Diversity, equity, and inclusion in a legal AI company &mdash; what does that actually
                        mean when you&apos;re a small team?
                    </BodyText>

                    <BodyText>
                        I&apos;m not going to pretend we have a 50-person diversity council or a structured ERG
                        programme. We&apos;re an early-stage startup. But there&apos;s a form of equity I think
                        about every day, and it&apos;s built directly into our product: who gets access to good
                        legal research tools.
                    </BodyText>

                    <Heading>The access problem in legal technology</Heading>

                    <BodyText>
                        Legal research software has historically been expensive, jurisdiction-specific, and
                        designed for large firms. Established platforms price at enterprise levels. A solo
                        practitioner in Prague, a junior lawyer at a small firm in Dubai, a student in
                        Sydney &mdash; these users have been either priced out entirely or forced to use
                        inferior tools.
                    </BodyText>

                    <BodyText>
                        That&apos;s an equity problem. It means the quality of legal research available to you
                        depends substantially on where you work and how much your employer pays. We
                        don&apos;t think that&apos;s acceptable.
                    </BodyText>

                    <Heading>How Vitreon addresses it</Heading>

                    <BodyText>
                        Our free tier &mdash; 10 research queries per day, no credit card required &mdash;
                        isn&apos;t a loss-leader funnel. It&apos;s a deliberate decision that someone who
                        cannot pay should still be able to run a meaningful research query and get a grounded,
                        cited answer.
                    </BodyText>

                    <BodyText>
                        Our jurisdictional coverage is also deliberate. We cover Czech Republic law &mdash; a
                        market consistently overlooked by major legal AI players focused on English-language
                        common law jurisdictions. Czech law is complex, frequently updated, and governs over
                        10 million people. We built a real corpus for it. We also cover DIFC (Dubai
                        International Financial Centre), serving a rapidly growing Middle East legal market;
                        UK; and Australia &mdash; alongside each other in the same product.
                    </BodyText>

                    <BodyText>
                        Legal AI that only works in the US, or only in English, reinforces existing
                        inequalities. We started where there was genuine unmet need.
                    </BodyText>

                    <Heading>Pricing designed for accessibility</Heading>

                    <BodyText>
                        Our Starter plan is $29/month &mdash; lower than a single module from major
                        incumbents. Our Pro plan at $179/month brings per-query costs that make it viable for
                        small firms doing serious research volume. The free tier has real functionality, not
                        just a demo mode.
                    </BodyText>

                    <BodyText>
                        We&apos;re actively seeking investment and partnerships specifically to expand
                        free-tier capacity. The goal is a system where the ability to pay does not determine
                        the ability to do legal research.
                    </BodyText>

                    <Heading>What we can&apos;t claim &mdash; and what we can</Heading>

                    <BodyText>
                        I&apos;ll be direct: we&apos;re a small team at an early stage. We don&apos;t yet
                        have comprehensive hiring diversity data to publish. What we do have is a product
                        philosophy grounded in the question:{" "}
                        <em style={{color: "var(--strict-text-primary)"}}>
                            who doesn&apos;t currently have access to this, and why?
                        </em>
                    </BodyText>

                    <BodyText>
                        That question shapes our roadmap. It shapes how we price. It shapes which legal
                        corpora we build next.
                    </BodyText>

                    <BodyText>
                        Equity in legal AI isn&apos;t a checkbox. It&apos;s a design decision you make with
                        every corpus you choose to include, every pricing tier you build, every jurisdiction
                        you decide to support.
                    </BodyText>

                    <Callout>
                        <em style={{color: "var(--strict-text-secondary)"}}>
                            &mdash; Viacheslav Ivannikov, Founder, Vitreon Legal
                        </em>
                    </Callout>
                </article>
            </main>

            <StrictFooter />
        </div>
    );
}

function Heading({children}: {children: React.ReactNode}) {
    return (
        <h2
            className="font-heading font-bold mt-10 mb-4"
            style={{
                fontSize: "1.25rem",
                color: "var(--strict-text-primary)",
                letterSpacing: "-0.01em",
            }}
        >
            {children}
        </h2>
    );
}

function BodyText({children}: {children: React.ReactNode}) {
    return (
        <p style={{fontSize: "16px", lineHeight: 1.8, color: "var(--strict-text-body)"}}>
            {children}
        </p>
    );
}

function Callout({children}: {children: React.ReactNode}) {
    return (
        <div
            className="mt-6 rounded-xl px-5 py-4 text-sm leading-6"
            style={{
                background: "var(--strict-blockquote-bg)",
                borderLeft: "3px solid var(--strict-gold-base)",
                color: "var(--strict-text-body)",
            }}
        >
            {children}
        </div>
    );
}
