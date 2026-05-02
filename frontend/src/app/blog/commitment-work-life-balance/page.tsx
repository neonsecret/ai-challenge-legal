import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Vitreon Legal — Our Commitment to Sustainable Work",
    description:
        "Vitreon Legal is async-first and fully remote. Here's what work-life balance actually means when there's no office, no fixed hours, and no performance theater.",
    keywords: [
        "async work",
        "remote-first",
        "work-life balance",
        "sustainable startup",
        "flexible work",
        "no-meeting culture",
        "remote legal tech",
    ],
    alternates: {
        canonical: "https://vitreon.app/blog/commitment-work-life-balance",
        languages: {
            en: "https://vitreon.app/blog/commitment-work-life-balance",
        },
    },
    openGraph: {
        title: "Vitreon Legal — Our Commitment to Sustainable Work",
        description:
            "Vitreon Legal is async-first and fully remote. Here's what work-life balance actually means when there's no office, no fixed hours, and no performance theater.",
        url: "https://vitreon.app/blog/commitment-work-life-balance",
        siteName: "Vitreon Legal",
        locale: "en_US",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Our Commitment to Sustainable Work — Vitreon Legal",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Vitreon Legal — Our Commitment to Sustainable Work",
        description:
            "Vitreon Legal is async-first and fully remote. Here's what work-life balance actually means when there's no office, no fixed hours, and no performance theater.",
    },
};

export default function CommitmentWorkLifeBalancePost() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "Our Commitment to Sustainable Work",
        description:
            "Vitreon Legal is async-first and fully remote. Here's what work-life balance actually means when there's no office, no fixed hours, and no performance theater.",
        datePublished: "2026-04-26",
        inLanguage: "en",
        keywords: [
            "async work",
            "remote-first",
            "work-life balance",
            "sustainable startup",
            "flexible work",
            "no-meeting culture",
            "remote legal tech",
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
        url: "https://vitreon.app/blog/commitment-work-life-balance",
        mainEntityOfPage: "https://vitreon.app/blog/commitment-work-life-balance",
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
                        Our Commitment to Sustainable Work
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        By Viacheslav Ivannikov, Founder of Vitreon Legal
                    </p>
                </div>

                {/* Article Body */}
                <article className="space-y-6">
                    <BodyText>
                        Work-life balance at a startup is a contested concept. Most startup culture celebrates
                        overwork as a badge of intensity. Ship fast, sleep later. Merge at midnight. The grind
                        is the point.
                    </BodyText>

                    <BodyText>
                        I want to say plainly: that&apos;s not how we operate at Vitreon Legal &mdash; and
                        not just because it&apos;s now fashionable to say so. It&apos;s a considered position
                        I&apos;ve arrived at by thinking carefully about what produces good work in our domain.
                    </BodyText>

                    <Heading>What async-first actually means in practice</Heading>

                    <BodyText>
                        We have no mandatory meetings. No daily standups. No &ldquo;core hours&rdquo; that
                        everyone must be online for. Work happens when the person doing it is focused and at
                        their best &mdash; not when a recurring calendar invite says they should be.
                    </BodyText>

                    <BodyText>
                        This isn&apos;t an experiment or a perks initiative. It&apos;s a design principle for
                        how serious knowledge work gets done. The evidence for synchronous communication as
                        the default is weak for the kind of work we do. Async-first means better
                        documentation &mdash; because you can&apos;t just grab someone in a corridor &mdash;
                        more deliberate communication, and the ability to do deep, uninterrupted work.
                    </BodyText>

                    <BodyText>
                        For a legal AI company, deep work is non-negotiable. The decisions we make about
                        retrieval architecture, benchmark methodology, legal corpus curation, and answer
                        quality all require sustained concentration. A culture of constant interruption is
                        incompatible with building this kind of system well.
                    </BodyText>

                    <Heading>No office, no commute, no presence theater</Heading>

                    <BodyText>
                        Our team is fully remote. There&apos;s no office where presence must be performed.
                        No commute consuming hours of people&apos;s days. No &ldquo;butts-in-seats&rdquo;
                        accountability model that confuses visibility with output.
                    </BodyText>

                    <BodyText>
                        I&apos;ve worked in office environments. The hours spent visibly being there rarely
                        correlate with the hours where meaningful work happened. Remote-first removes that
                        theater and focuses the relationship on what actually matters: what gets built, how
                        well it works, and whether users are served by it.
                    </BodyText>

                    <Heading>The founder&apos;s honest position</Heading>

                    <BodyText>
                        I&apos;ll be direct: as a solo founder, I&apos;ve also had periods of working too
                        much. Building a startup from scratch is genuinely intense. But I&apos;ve made a
                        deliberate choice not to instill a culture where that intensity is mandatory,
                        performed, or expected.
                    </BodyText>

                    <BodyText>
                        We don&apos;t have &ldquo;ship at midnight&rdquo; culture. When a feature needs to go
                        out, we plan it properly and deploy it with care. Rushing produces bugs. In legal
                        research, bugs have real consequences &mdash; a wrong citation or a missed statute is
                        not a trivial UI glitch.
                    </BodyText>

                    <BodyText>
                        We also believe that people who aren&apos;t burned out produce better work. This
                        isn&apos;t only an ethical position &mdash; it&apos;s an engineering judgment. Legal
                        AI built thoughtfully by people who have enough space to think is better legal AI.
                    </BodyText>

                    <Heading>What sustainable work looks like long-term</Heading>

                    <BodyText>
                        Sustainable means: you can do this for years, not just months. Our team should be
                        able to work at Vitreon Legal without sacrificing their health, their relationships,
                        or their time to grow as people. The pressure that comes from building something hard
                        should come from the challenge itself &mdash; not from an artificially imposed culture
                        of overwork.
                    </BodyText>

                    <BodyText>
                        That&apos;s not a policy document. It&apos;s a commitment we make through every
                        decision about how we work, what we build, and who we ask to build it.
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
