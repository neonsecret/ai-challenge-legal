import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Our Commitment to Learning and Growth — Vitreon Legal Blog",
    description:
        "At Vitreon Legal, continuous learning is how we build. We publish our methodology, benchmark openly, and stay at the frontier of legal AI.",
    keywords: [
        "legal AI research",
        "continuous learning",
        "open benchmarks",
        "legal tech career",
        "retrieval methodology",
        "AI transparency",
        "ARLC competition",
    ],
    alternates: {
        canonical: "https://vitreon.app/blog/commitment-career-growth",
        languages: {
            en: "https://vitreon.app/blog/commitment-career-growth",
        },
    },
    openGraph: {
        title: "Our Commitment to Learning and Growth",
        description:
            "At Vitreon Legal, continuous learning is how we build. We publish our methodology, benchmark openly, and stay at the frontier of legal AI.",
        url: "https://vitreon.app/blog/commitment-career-growth",
        siteName: "Vitreon Legal",
        locale: "en_US",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Our Commitment to Learning and Growth — Vitreon Legal",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Our Commitment to Learning and Growth",
        description:
            "At Vitreon Legal, continuous learning is how we build. We publish our methodology, benchmark openly, and stay at the frontier of legal AI.",
    },
};

export default function CommitmentCareerGrowthPost() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "Our Commitment to Learning and Growth",
        description:
            "At Vitreon Legal, continuous learning is how we build. We publish our methodology, benchmark openly, and stay at the frontier of legal AI.",
        datePublished: "2026-04-26",
        inLanguage: "en",
        keywords: [
            "legal AI research",
            "continuous learning",
            "open benchmarks",
            "legal tech career",
            "retrieval methodology",
            "AI transparency",
            "ARLC competition",
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
        url: "https://vitreon.app/blog/commitment-career-growth",
        mainEntityOfPage: "https://vitreon.app/blog/commitment-career-growth",
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
                        Our Commitment to Learning and Growth
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        By Viacheslav Ivannikov, Founder of Vitreon Legal
                    </p>
                </div>

                {/* Article Body */}
                <article className="space-y-6">
                    <BodyText>
                        At Vitreon Legal, we believe the best legal AI is built by people who never stop
                        learning &mdash; and we hold ourselves to that standard.
                    </BodyText>

                    <BodyText>
                        When I started building Vitreon, I made a decision early on: whatever we figure out
                        about making AI work better for legal research, we publish it. Our benchmark results,
                        our methodology, our failures. This isn&apos;t altruism &mdash; it&apos;s how you stay
                        honest. When your results are public, you can&apos;t let the bar drift quietly downward.
                    </BodyText>

                    <Heading>Learning is embedded in how we build</Heading>

                    <BodyText>
                        Legal AI is a fast-moving field. State-of-the-art retrieval models, reasoning
                        benchmarks, hallucination mitigation &mdash; these evolve month to month. Our team
                        reads the research, runs experiments, and stays at the frontier because the alternative
                        is building on stale assumptions.
                    </BodyText>

                    <BodyText>
                        Our GaRAGe retrieval pipeline scores 0.824 RAF &mdash; 36% above the published state
                        of the art. Our LEXam Open EN benchmark result is 0.691, surpassing Claude 3.7 Sonnet
                        by 21%. These aren&apos;t marketing numbers &mdash; they&apos;re results from
                        standardised benchmarks you can reproduce. We publish them because we want to be held
                        accountable to them.
                    </BodyText>

                    <Heading>Open methodology, not a black box</Heading>

                    <BodyText>
                        Too much legal AI is a black box. You get an answer; you don&apos;t know why. At
                        Vitreon, we document how our retrieval works, what our training data covers, what our
                        limitations are. The blog at vitreon.app/blog exists precisely for this reason &mdash;
                        to share what we learn so the broader legal tech community benefits.
                    </BodyText>

                    <BodyText>
                        In 2026, we competed in ARLC (Automated Research in Legal Corpus), the first public
                        international legal AI competition. We placed first in warmup with a score of 0.958,
                        and fourth in finals. We published our post-mortem: what went well, what didn&apos;t,
                        what we&apos;d do differently. That&apos;s the learning culture we operate in &mdash;
                        performance is a process, not a destination.
                    </BodyText>

                    <Heading>Async work enables real learning</Heading>

                    <BodyText>
                        There&apos;s a practical side to this commitment. Our team is fully remote and
                        async-first. That means people have time to read, think, and experiment &mdash; not
                        just ship tickets. I don&apos;t believe you can build thoughtful AI systems on a
                        treadmill of mandatory meetings and reactive work. The flexibility we&apos;ve built
                        into how we operate is partly what makes a genuine learning culture possible.
                    </BodyText>

                    <Heading>What growth means at Vitreon&apos;s stage</Heading>

                    <BodyText>
                        We&apos;re an early-stage startup, which means growth isn&apos;t about climbing a
                        career ladder &mdash; it&apos;s about building frontier competence in a domain that is
                        defining how law will work for the next decade. Every person on the team is both a
                        contributor and a student. We work at the edge of what has been figured out, and we
                        document what we find.
                    </BodyText>

                    <BodyText>
                        That&apos;s the commitment: keep learning, publish what we discover, and build AI that
                        reflects genuine understanding of how legal research actually works.
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
