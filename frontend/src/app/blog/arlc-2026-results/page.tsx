import Link from "next/link";
import type {Metadata} from "next";
import { StrictNav } from "@/components/landing/strict/strict-nav";
import { StrictFooter } from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Vitreon Legal — How Vitreon Placed 4th in ARLC 2026",
    description:
        "Team Neon Team (Vitreon Legal) placed 4th out of 80 teams at the ARLC 2026 competition during Dubai AI Week. 0.958 on warmup (1st place), 0.719 on finals. Full methodology and score breakdown.",
    openGraph: {
        title: "Vitreon Legal — How Vitreon Placed 4th in ARLC 2026",
        description:
            "Team Neon Team placed 4th/80 at ARLC 2026. 0.958 warmup (1st), 0.719 finals. Full methodology breakdown.",
        url: "https://vitreon.app/blog/arlc-2026-results",
        siteName: "Vitreon Legal",
        locale: "en",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "How Vitreon Placed 4th in ARLC 2026 — Vitreon Legal",
            },
        ],
    },
    alternates: {
        canonical: "https://vitreon.app/blog/arlc-2026-results",
        languages: {
            en: "https://vitreon.app/blog/arlc-2026-results",
        },
    },
    keywords: ["ARLC 2026", "Czech legal AI", "legal AI benchmark", "Vitreon Legal", "Czech law", "legal research AI"],
    twitter: {
        card: "summary_large_image",
        title: "Vitreon Legal — How Vitreon Placed 4th in ARLC 2026",
        description:
            "Team Neon Team placed 4th/80 at ARLC 2026. 0.958 warmup (1st), 0.719 finals. Full methodology breakdown.",
    },
};

export default function ARLCResultsPost() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "How Vitreon Placed 4th in ARLC 2026",
        description:
            "Team Neon Team (Vitreon Legal) placed 4th out of 80 teams at the ARLC 2026 competition during Dubai AI Week. 0.958 on warmup (1st place), 0.719 on finals. Full methodology and score breakdown.",
        datePublished: "2026-04-10",
        inLanguage: "en",
        keywords: ["ARLC 2026", "Czech legal AI", "legal AI benchmark", "Vitreon Legal", "Czech law", "legal research AI"],
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
        url: "https://vitreon.app/blog/arlc-2026-results",
        mainEntityOfPage: "https://vitreon.app/blog/arlc-2026-results",
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
                            April 10, 2026
                        </span>
                        <span
                            className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded"
                            style={{
                                background: "var(--strict-gold-badge-bg)",
                                color: "var(--strict-gold-badge-text)",
                                border: "1px solid var(--strict-gold-badge-border)",
                            }}
                        >
                            English
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
                        How Vitreon Placed 4th in ARLC 2026
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        By Viacheslav Ivannikov, Founder of Vitreon Legal
                    </p>
                </div>

                {/* Article Body */}
                <article className="space-y-6">
                    <BodyText>
                        In February 2026, the Agentic RAG Legal Challenge (ARLC) was announced as part of Dubai AI
                        Week &mdash; an international competition challenging teams to build AI systems capable of
                        answering complex legal questions from over 300 DIFC (Dubai International Financial Centre)
                        legal documents. The prize pool was $32,000. 80 teams from around the world registered.
                    </BodyText>

                    <BodyText>
                        We entered as team <strong style={{color: "var(--strict-text-primary)"}}>&ldquo;Neon Team&rdquo;</strong>.
                        This is the story of how we built our system, what worked, what we learned, and how the
                        competition shaped what Vitreon Legal is today.
                    </BodyText>

                    <Heading>The Challenge</Heading>

                    <BodyText>
                        ARLC 2026 tested something specific: given a corpus of 300+ DIFC legal documents &mdash;
                        legislation, regulations, court judgments, and practice directions &mdash; build an AI
                        system that can answer legal questions accurately and cite its sources. The evaluation was
                        automated: answers were scored on factual accuracy, completeness, and citation correctness.
                    </BodyText>

                    <BodyText>
                        This wasn&apos;t a general-knowledge quiz. The questions required understanding legal
                        hierarchy (primary vs. secondary legislation), temporal reasoning (which version of a law
                        applies), and cross-reference resolution (one regulation referencing another). Simple RAG
                        wasn&apos;t going to cut it.
                    </BodyText>

                    <Heading>Our Approach</Heading>

                    <BodyText>
                        The core of our system was a multi-stage retrieval pipeline that we had been developing
                        for Czech legal research. We adapted it for the DIFC corpus:
                    </BodyText>

                    <SubHeading>1. Hybrid Search with Reciprocal Rank Fusion</SubHeading>
                    <BodyText>
                        Every query was processed through both BM25 (lexical search) and dense vector search
                        simultaneously. BM25 catches exact legal terminology &mdash; section numbers, specific
                        defined terms, case names &mdash; that embedding models sometimes miss. Vector search
                        catches semantic similarity when the question uses different words than the source text.
                        Reciprocal Rank Fusion merged the two result sets, giving us the best of both.
                    </BodyText>

                    <SubHeading>2. Asymmetric Embedding</SubHeading>
                    <BodyText>
                        We used asymmetric embedding with different prefixes for queries and documents. This
                        is critical for legal retrieval: a question like &ldquo;What is the notice period for
                        terminating a tenancy?&rdquo; should match a passage that says &ldquo;The landlord shall
                        provide not less than 30 days written notice&rdquo; &mdash; even though the surface-level
                        wording is completely different. Asymmetric encoding optimizes for this query-to-passage
                        matching rather than passage-to-passage similarity.
                    </BodyText>

                    <SubHeading>3. Cross-Encoder Reranking</SubHeading>
                    <BodyText>
                        After the initial retrieval stage returned candidate passages, we ran a cross-encoder
                        model that jointly encoded each (query, passage) pair. This is computationally expensive
                        but dramatically improves precision. In legal retrieval, the difference between a relevant
                        passage and a merely similar one can be a single qualifying clause. The cross-encoder
                        catches these distinctions.
                    </BodyText>

                    <SubHeading>4. Grounded Answer Generation</SubHeading>
                    <BodyText>
                        The top-ranked passages were provided to the LLM with strict instructions: generate
                        answers only from the provided context, cite every claim with the source document and
                        section, and explicitly state when the available documents don&apos;t contain an answer.
                        This source-grounding constraint is what gives us 100% citation coverage in production.
                    </BodyText>

                    <Heading>Results</Heading>

                    <BodyText>
                        The competition had two rounds:
                    </BodyText>

                    <div
                        className="rounded-xl overflow-hidden my-6"
                        style={{
                            background: "var(--strict-glass-bg)",
                            border: "1px solid var(--strict-glass-border)",
                            backdropFilter: "var(--strict-glass-blur)",
                            borderRadius: "14px",
                        }}
                    >
                        <table className="w-full text-sm">
                            <thead>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Round</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Score</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Ranking</th>
                            </tr>
                            </thead>
                            <tbody>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>Warmup</td>
                                <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>0.958</td>
                                <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>1st / 80 teams</td>
                            </tr>
                            <tr>
                                <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>Finals</td>
                                <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>0.719</td>
                                <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>4th / 80 teams</td>
                            </tr>
                            </tbody>
                        </table>
                    </div>

                    <BodyText>
                        We scored <strong style={{color: "var(--strict-gold-text)"}}>0.958 on the warmup round &mdash; first place</strong> out
                        of all 80 teams. The warmup round tested the core retrieval and answer quality on a set
                        of representative questions with known answers.
                    </BodyText>

                    <BodyText>
                        In the finals, the questions were significantly harder &mdash; requiring multi-document
                        reasoning, temporal analysis across legislative amendments, and synthesis of conflicting
                        provisions. We scored 0.719, placing 4th overall. The gap between warmup and finals
                        performance is instructive: the most challenging legal questions require reasoning across
                        documents, not just better retrieval of single passages.
                    </BodyText>

                    <Heading>What We Learned</Heading>

                    <BodyText>
                        The competition confirmed several things we had hypothesized but couldn&apos;t prove on
                        internal benchmarks alone:
                    </BodyText>

                    <BodyText>
                        <strong style={{color: "var(--strict-text-primary)"}}>Hybrid search is non-negotiable for legal.</strong>{" "}
                        Pure vector search misses exact statutory references. Pure BM25 misses semantic intent.
                        You need both, fused properly. Our warmup score of 0.958 would not have been possible
                        with either approach alone.
                    </BodyText>

                    <BodyText>
                        <strong style={{color: "var(--strict-text-primary)"}}>Cross-encoder reranking is the precision multiplier.</strong>{" "}
                        The difference between top-10 and top-3 retrieval accuracy is where cross-encoders earn
                        their compute cost. In legal research, returning the second-most-relevant provision instead
                        of the correct one can change the answer entirely.
                    </BodyText>

                    <BodyText>
                        <strong style={{color: "var(--strict-text-primary)"}}>Source grounding prevents hallucination at scale.</strong>{" "}
                        By architecturally constraining the LLM to only cite retrieved passages, we achieved
                        100% citation coverage across all competition submissions. This isn&apos;t a prompt trick
                        &mdash; it&apos;s a system design decision.
                    </BodyText>

                    <BodyText>
                        <strong style={{color: "var(--strict-text-primary)"}}>Multi-document reasoning is the next frontier.</strong>{" "}
                        Our warmup-to-finals drop shows where single-hop retrieval hits its limits. The hardest
                        legal questions require chaining information across multiple documents. This is what we&apos;re
                        investing in for the next generation of the platform.
                    </BodyText>

                    <Heading>From Competition to Product</Heading>

                    <BodyText>
                        After ARLC, we took the competition pipeline and scaled it. The DIFC corpus of 300+
                        documents became a starting point; we added Czech law (295,000+ court decisions,
                        6,800+ statutes), UK law, and Australian law. The core architecture remained the same:
                        hybrid search, cross-encoder reranking, grounded generation.
                    </BodyText>

                    <BodyText>
                        The result is Vitreon Legal &mdash; a production platform that delivers the same quality
                        of legal research that placed 4th in an international competition, accessible to any
                        legal professional at{" "}
                        <Link href="/" style={{color: "var(--strict-gold-text)"}} className="hover:underline">
                            vitreon.app
                        </Link>
                        .
                    </BodyText>

                    <BodyText>
                        For detailed benchmark numbers across all evaluations, see our{" "}
                        <Link href="/benchmarks" style={{color: "var(--strict-gold-text)"}} className="hover:underline">
                            Benchmarks
                        </Link>{" "}
                        page.
                    </BodyText>

                    <Callout>
                        <strong style={{color: "var(--strict-text-primary)"}}>Note:</strong> Team
                        &ldquo;Neon Team&rdquo; on the official ARLC 2026 leaderboard is Vitreon Legal.
                        The team name was chosen before the product name was finalized.
                    </Callout>
                </article>
            </main>

            <StrictFooter />
        </div>
    );
}

/* -- Layout primitives -- */

function Heading({children}: { children: React.ReactNode }) {
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

function SubHeading({children}: { children: React.ReactNode }) {
    return (
        <h3
            className="font-semibold mb-2 mt-6"
            style={{fontSize: "0.9375rem", color: "var(--strict-text-primary)"}}
        >
            {children}
        </h3>
    );
}

function BodyText({children}: { children: React.ReactNode }) {
    return (
        <p
            style={{fontSize: "16px", lineHeight: 1.8, color: "var(--strict-text-body)"}}
        >
            {children}
        </p>
    );
}

function Callout({children}: { children: React.ReactNode }) {
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
