import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Our Commitment to Lean AI Infrastructure — Vitreon Legal Blog",
    description:
        "Vitreon Legal runs on a Mac and one GPU — no massive compute cluster. Here's why lean AI infrastructure is both an environmental and engineering commitment.",
    keywords: [
        "sustainable AI",
        "lean infrastructure",
        "green tech",
        "low-carbon AI",
        "environmental sustainability",
        "efficient machine learning",
        "remote work sustainability",
    ],
    alternates: {
        canonical: "https://vitreon.app/blog/commitment-environmental-sustainability",
        languages: {
            en: "https://vitreon.app/blog/commitment-environmental-sustainability",
        },
    },
    openGraph: {
        title: "Our Commitment to Lean AI Infrastructure",
        description:
            "Vitreon Legal runs on a Mac and one GPU — no massive compute cluster. Here's why lean AI infrastructure is both an environmental and engineering commitment.",
        url: "https://vitreon.app/blog/commitment-environmental-sustainability",
        siteName: "Vitreon Legal",
        locale: "en_US",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Our Commitment to Lean AI Infrastructure — Vitreon Legal",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Our Commitment to Lean AI Infrastructure",
        description:
            "Vitreon Legal runs on a Mac and one GPU — no massive compute cluster. Here's why lean AI infrastructure is both an environmental and engineering commitment.",
    },
};

export default function CommitmentEnvironmentalPost() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "Our Commitment to Lean AI Infrastructure",
        description:
            "Vitreon Legal runs on a Mac and one GPU — no massive compute cluster. Here's why lean AI infrastructure is both an environmental and engineering commitment.",
        datePublished: "2026-04-26",
        inLanguage: "en",
        keywords: [
            "sustainable AI",
            "lean infrastructure",
            "green tech",
            "low-carbon AI",
            "environmental sustainability",
            "efficient machine learning",
            "remote work sustainability",
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
        url: "https://vitreon.app/blog/commitment-environmental-sustainability",
        mainEntityOfPage: "https://vitreon.app/blog/commitment-environmental-sustainability",
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
                        Our Commitment to Lean AI Infrastructure
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        By Viacheslav Ivannikov, Founder of Vitreon Legal
                    </p>
                </div>

                {/* Article Body */}
                <article className="space-y-6">
                    <BodyText>
                        Most conversations about AI and the environment focus on the enormous energy cost of
                        large model training. That&apos;s a fair concern. But there&apos;s a related question
                        that gets less attention: what does it cost, environmentally, to{" "}
                        <em>run</em> AI in production &mdash; every day, for every user?
                    </BodyText>

                    <BodyText>
                        At Vitreon Legal, we&apos;ve made deliberate architectural choices that result in a
                        minimal environmental footprint. Not as a marketing position, but because building
                        lean is how we believe AI should be engineered.
                    </BodyText>

                    <Heading>What our infrastructure actually looks like</Heading>

                    <BodyText>
                        Our production stack runs on a Mac Studio and a single RTX 3070 consumer GPU.
                        That&apos;s the compute that powers our embedding pipeline, our reranker, and our AI
                        research assistant &mdash; serving real users across four jurisdictions every day.
                    </BodyText>

                    <BodyText>
                        No A100 cluster. No rented GPU racks. No cloud instances scaling elastically to
                        hundreds of cores on demand. We&apos;ve built an efficient, purpose-built retrieval
                        pipeline that punches well above its weight class &mdash; our GaRAGe retrieval scores
                        36% above published state of the art &mdash; without needing massive compute to do it.
                    </BodyText>

                    <BodyText>
                        Efficiency-first AI architecture has a direct environmental benefit: less compute means
                        less energy. That&apos;s not incidental &mdash; it&apos;s a consequence of refusing to
                        solve hard problems by throwing more hardware at them. When your infrastructure budget
                        is limited, you&apos;re forced to think carefully. That constraint has made us better
                        engineers and produced a smaller carbon footprint.
                    </BodyText>

                    <Heading>Remote and async-first means zero office footprint</Heading>

                    <BodyText>
                        Our team has no office. There are no commutes, no building to heat or cool, no
                        cafeteria, no infrastructure overhead of a physical workspace.
                    </BodyText>

                    <BodyText>
                        Async-first work is our default operating model &mdash; not a pandemic-era holdover.
                        It means no mandatory travel for meetings, no relocations, no flights for offsites.
                        The environmental consequence is real: our organisational footprint is essentially the
                        footprint of the people themselves, wherever they already live.
                    </BodyText>

                    <Heading>What we&apos;re not claiming</Heading>

                    <BodyText>
                        We don&apos;t publish formal carbon metrics. We&apos;re not audited by an
                        environmental third party. We&apos;re a startup, not a regulated entity, and we
                        won&apos;t pretend otherwise.
                    </BodyText>

                    <BodyText>
                        What we can say plainly: the structural choices we&apos;ve made &mdash; lean inference
                        architecture, no cloud GPU clusters, no office, no mandatory travel &mdash; have
                        genuine environmental consequences that are worth stating directly.
                    </BodyText>

                    <Heading>As we scale</Heading>

                    <BodyText>
                        As Vitreon grows, we&apos;re committed to maintaining this philosophy: add compute
                        only when efficiency improvements have been exhausted first. Prefer smaller models
                        where accuracy holds. Avoid the arms-race approach to AI infrastructure that has made
                        &ldquo;AI&rdquo; synonymous with enormous energy consumption in public perception.
                    </BodyText>

                    <BodyText>
                        Legal research AI doesn&apos;t need to cost the planet. We&apos;ve demonstrated that
                        a retrieval pipeline purpose-built for legal text can outperform much more expensive
                        infrastructure. That efficiency is both a competitive advantage and an environmental
                        one.
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
