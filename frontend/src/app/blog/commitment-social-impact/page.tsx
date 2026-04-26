import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Our Commitment to Access to Justice — Vitreon Legal Blog",
    description:
        "Legal research costs are a barrier to access to justice. Vitreon Legal is building to lower that barrier with a free tier and multi-jurisdiction coverage.",
    keywords: [
        "access to justice",
        "legal research AI",
        "affordable legal tech",
        "legal empowerment",
        "social impact",
        "underserved legal markets",
        "legal AI democratisation",
    ],
    alternates: {
        canonical: "https://vitreon.app/blog/commitment-social-impact",
        languages: {
            en: "https://vitreon.app/blog/commitment-social-impact",
        },
    },
    openGraph: {
        title: "Our Commitment to Access to Justice",
        description:
            "Legal research costs are a barrier to access to justice. Vitreon Legal is building to lower that barrier with a free tier and multi-jurisdiction coverage.",
        url: "https://vitreon.app/blog/commitment-social-impact",
        siteName: "Vitreon Legal",
        locale: "en_US",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Our Commitment to Access to Justice — Vitreon Legal",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Our Commitment to Access to Justice",
        description:
            "Legal research costs are a barrier to access to justice. Vitreon Legal is building to lower that barrier with a free tier and multi-jurisdiction coverage.",
    },
};

export default function CommitmentSocialImpactPost() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "Our Commitment to Access to Justice",
        description:
            "Legal research costs are a barrier to access to justice. Vitreon Legal is building to lower that barrier with a free tier and multi-jurisdiction coverage.",
        datePublished: "2026-04-26",
        inLanguage: "en",
        keywords: [
            "access to justice",
            "legal research AI",
            "affordable legal tech",
            "legal empowerment",
            "social impact",
            "underserved legal markets",
            "legal AI democratisation",
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
        url: "https://vitreon.app/blog/commitment-social-impact",
        mainEntityOfPage: "https://vitreon.app/blog/commitment-social-impact",
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
                        Our Commitment to Access to Justice
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        By Viacheslav Ivannikov, Founder of Vitreon Legal
                    </p>
                </div>

                {/* Article Body */}
                <article className="space-y-6">
                    <BodyText>
                        There&apos;s a phrase lawyers use: &ldquo;access to justice.&rdquo; It refers to the
                        practical ability for people to exercise their legal rights &mdash; not just
                        theoretically, but through real legal representation and research that they can
                        actually afford and access.
                    </BodyText>

                    <BodyText>
                        The gap between &ldquo;technically has rights&rdquo; and &ldquo;can actually enforce
                        them&rdquo; is often a resource gap. Legal research is expensive. Expertise is
                        expensive. Time is expensive.
                    </BodyText>

                    <BodyText>
                        AI doesn&apos;t close all of those gaps. But it can make one critical part &mdash; the
                        research itself &mdash; dramatically more accessible. That&apos;s what we&apos;re
                        building.
                    </BodyText>

                    <Heading>Who legal AI has traditionally served</Heading>

                    <BodyText>
                        The major legal research platforms were built for BigLaw. Their pricing assumes
                        enterprise-scale contracts. Their interfaces are optimised for partners at global
                        firms. Their coverage is heavily weighted toward US and UK common law.
                    </BodyText>

                    <BodyText>
                        That&apos;s a consequence of where the venture money went, not where the legal need
                        was greatest. A solo practitioner in Brno, a public defender in any jurisdiction, a
                        small NGO trying to understand compliance obligations &mdash; these users have
                        historically been either priced out or ignored.
                    </BodyText>

                    <Heading>What Vitreon Legal is building instead</Heading>

                    <BodyText>
                        We started with Czech Republic law &mdash; a market consistently ignored by major
                        legal AI players because it&apos;s smaller and operates in a non-English language.
                        Czech law is complex, frequently amended, and governs the rights of over 10 million
                        people. We built a real corpus for it and built retrieval that works in that legal
                        context.
                    </BodyText>

                    <BodyText>
                        We then added DIFC (Dubai International Financial Centre) &mdash; a common law hub
                        serving a region that is rapidly expanding its legal and financial infrastructure.
                        Then UK. Then Australia. We haven&apos;t built a US corpus. Not because US law
                        doesn&apos;t matter, but because US legal research already has well-funded tools. We
                        went where there was genuine unmet coverage.
                    </BodyText>

                    <Heading>The free tier is a policy decision, not a funnel</Heading>

                    <BodyText>
                        Our free tier &mdash; 3 queries per day, no account required, no credit card &mdash;
                        is a deliberate commitment. Is 3 queries/day sufficient for serious sustained legal
                        work? No. But it&apos;s enough for a student to verify a citation, for a paralegal to
                        check a statutory reference, for a small business owner to understand whether a
                        contract clause is standard.
                    </BodyText>

                    <BodyText>
                        We price our paid plans to be accessible to small firms: $29/month for Starter,
                        $179/month for Pro. These are not enterprise price points.
                    </BodyText>

                    <BodyText>
                        We&apos;re actively seeking investment and partnerships to expand free-tier capacity.
                        The goal is a product where ability to pay does not determine ability to do legal
                        research.
                    </BodyText>

                    <Heading>What impact looks like at our stage</Heading>

                    <BodyText>
                        We&apos;re pre-revenue and small. We can&apos;t claim we&apos;ve closed the
                        access-to-justice gap &mdash; that&apos;s a decades-long systemic challenge. What we
                        can claim is a consistent direction: more coverage, lower barriers, underserved markets
                        first.
                    </BodyText>

                    <BodyText>
                        Every jurisdiction covered that no other legal AI covers, every free query answered
                        for someone who couldn&apos;t afford a subscription, every small firm that saves hours
                        on a research task &mdash; that&apos;s the direction.
                    </BodyText>

                    <BodyText>
                        Social impact for a legal AI company isn&apos;t a programme or a fund. It&apos;s a
                        set of design decisions made consistently over time, starting with who you build for.
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
