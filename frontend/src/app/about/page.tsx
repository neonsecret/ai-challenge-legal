import Link from "next/link";
import type {Metadata} from "next";
import {ArrowRight} from "lucide-react";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "About Vitreon Legal — AI-Powered Legal Research from Prague",
    description:
        "Vitreon Legal is an AI-powered legal research platform built by Viacheslav Ivannikov in Prague. 4th place at ARLC 2026, +36% above SOTA on GaRAGe benchmark. Czech legal AI startup democratizing legal research.",
    keywords: [
        "Vitreon Legal about",
        "Czech legal AI startup",
        "Prague legal tech",
        "AI legal research platform",
        "ARLC 2026",
        "Viacheslav Ivannikov",
    ],
    alternates: {
        canonical: "https://vitreon.app/about",
        languages: {
            en: "https://vitreon.app/about",
            cs: "https://vitreon.app/cs",
        },
    },
    openGraph: {
        title: "About Vitreon Legal — AI-Powered Legal Research",
        description:
            "Built by Viacheslav Ivannikov in Prague. 4th place at ARLC 2026, +36% above SOTA. Democratizing legal research through AI.",
        url: "https://vitreon.app/about",
        siteName: "Vitreon Legal",
        locale: "en",
        type: "website",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Vitreon Legal — AI-Powered Legal Research",
            },
        ],
    },
};

function personJsonLd() {
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        name: "Viacheslav Ivannikov",
        jobTitle: "Founder & CEO",
        worksFor: {
            "@type": "Organization",
            name: "Vitreon Legal",
            url: "https://vitreon.app",
        },
        address: {
            "@type": "PostalAddress",
            addressLocality: "Prague",
            addressCountry: "CZ",
        },
    };
}

export default function AboutPage() {
    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(personJsonLd())}}
            />
            <StrictNav />

            <main className="max-w-[880px] mx-auto px-4 sm:px-8 pt-16 pb-20">
                {/* Header */}
                <div className="mb-12">
                    <p
                        className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-4"
                        style={{color: "var(--strict-gold-text)"}}
                    >
                        About
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
                        About Vitreon Legal
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)"}}>
                        AI-powered legal research, built in Prague
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
                        10 queries per day, all jurisdictions, full source citations.
                    </p>
                    <Link
                        href="/login?mode=register"
                        className="inline-flex items-center gap-2 px-5 py-3 min-h-[44px] rounded-lg text-sm font-semibold whitespace-nowrap transition-opacity hover:opacity-90"
                        style={{background: "var(--strict-gold-base)", color: "var(--strict-bg-html)"}}
                    >
                        Get Started Free <ArrowRight size={14} />
                    </Link>
                </div>

                {/* Mission */}
                <Section>
                    <SectionTitle index="1">Our Mission</SectionTitle>
                    <BodyText>
                        Vitreon Legal exists to democratize access to legal research through artificial intelligence.
                        Every lawyer deserves the same quality of legal research regardless of firm size, budget,
                        or geography. A solo practitioner in Brno should have the same research capabilities as a
                        Magic Circle firm in London.
                    </BodyText>
                    <BodyText>
                        We build AI systems that deliver precise, source-grounded answers from statutes and court
                        decisions. Every answer cites the exact page and clause. No hallucinations. No unsourced
                        claims. Just verifiable legal research at the speed of thought.
                    </BodyText>
                </Section>

                <Divider />

                {/* Founder */}
                <Section>
                    <SectionTitle index="2">Founder</SectionTitle>
                    <BodyText>
                        Vitreon Legal was founded by{" "}
                        <strong style={{color: "var(--strict-text-primary)"}}>
                            Viacheslav &ldquo;Neon&rdquo; Ivannikov
                        </strong>
                        , a solo founder based in Prague, Czech Republic. The platform was born from firsthand
                        frustration with expensive, clunky legal databases that locked critical legal knowledge
                        behind enterprise paywalls and outdated interfaces.
                    </BodyText>
                    <BodyText>
                        What started as an entry in the ARLC 2026 competition evolved into a full platform
                        serving legal professionals across four jurisdictions. The core conviction remains the
                        same: AI should make legal research more accessible, not more opaque.
                    </BodyText>
                </Section>

                <Divider />

                {/* Story */}
                <Section>
                    <SectionTitle index="3">The Story</SectionTitle>
                    <BodyText>
                        In early 2026, the Agentic RAG Legal Challenge (ARLC 2026) was announced as part of
                        Dubai AI Week &mdash; an international competition with a $32,000 prize pool, challenging
                        teams to build AI systems capable of answering complex legal questions from 300+ DIFC
                        legal documents.
                    </BodyText>
                    <BodyText>
                        Vitreon entered the competition under the team name{" "}
                        <strong style={{color: "var(--strict-text-primary)"}}>&ldquo;Neon Team&rdquo;</strong>. Competing
                        against 80 teams from around the world, Neon Team placed{" "}
                        <strong style={{color: "var(--strict-text-primary)"}}>4th overall</strong>, scoring{" "}
                        <GoldText>0.958 on the warmup round (1st place)</GoldText> and{" "}
                        <GoldText>0.719 on the finals</GoldText>.
                    </BodyText>
                    <BodyText>
                        The competition proved that the underlying retrieval and reasoning architecture could
                        compete at the highest level. After ARLC, the system was expanded to cover Czech law
                        &mdash; 295,000+ court decisions and 6,800+ statutes &mdash; along with UK and
                        Australian jurisdictions. Vitreon Legal launched as a commercial platform in 2026.
                    </BodyText>
                </Section>

                <Divider />

                {/* ARLC Results */}
                <Section>
                    <SectionTitle index="4">ARLC 2026 Competition Results</SectionTitle>
                    <BodyText>
                        The Agentic RAG Legal Challenge 2026 was organized during Dubai AI Week with a $32,000
                        prize pool. 80 teams competed to build the most accurate legal question-answering system
                        over 300+ DIFC legal documents.
                    </BodyText>
                    <GlassCard>
                        <table className="w-full text-sm">
                            <thead>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Round</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Score</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Ranking</th>
                            </tr>
                            </thead>
                            <tbody>
                            {[
                                ["Warmup Round", "0.958", "1st / 80 teams"],
                                ["Finals", "0.719", "4th / 80 teams"],
                            ].map(([round, score, rank], i) => (
                                <tr
                                    key={round}
                                    style={{
                                        borderTop: i > 0 ? "1px solid var(--strict-glass-border)" : undefined,
                                    }}
                                >
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>{round}</td>
                                    <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-base)"}}>{score}</td>
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>{rank}</td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </GlassCard>
                    <BodyText>
                        <span className="mt-4 block">
                            Team &ldquo;Neon Team&rdquo; on the ARLC leaderboard is Vitreon Legal. The same retrieval
                            pipeline that achieved these scores now powers the production platform.
                        </span>
                    </BodyText>
                </Section>

                <Divider />

                {/* Technology */}
                <Section>
                    <SectionTitle index="5">Technology</SectionTitle>
                    <BodyText>
                        Vitreon Legal&apos;s retrieval pipeline is built on custom-trained embedding models and
                        a hybrid search architecture that consistently outperforms published state-of-the-art
                        systems on independent benchmarks:
                    </BodyText>
                    <BulletList
                        items={[
                            "GaRAGe benchmark (ACL 2025): 0.824 RAF score, +36% above the published SOTA of 0.607.",
                            "LEXam Open EN (ICLR 2026): 0.691, +21% above the Claude 3.7-S baseline of 0.572.",
                            "Legal RAG Bench: 0.860 retrieval accuracy.",
                            "100% citation coverage: every answer cites the exact page and clause from the source document.",
                        ]}
                    />
                    <BodyText>
                        The system uses hybrid BM25 + vector search with Reciprocal Rank Fusion, asymmetric
                        embedding via Qwen3-Embedding-8B, and cross-encoder reranking. The Czech legal corpus
                        includes 295,000+ court decisions and 6,800+ statutes.
                    </BodyText>
                    <BodyText>
                        For detailed benchmark methodology and results, see the{" "}
                        <Link href="/benchmarks" style={{color: "var(--strict-gold-base)"}} className="hover:underline">
                            Benchmarks
                        </Link>{" "}
                        page.
                    </BodyText>
                </Section>

                <Divider />

                {/* Contact */}
                <Section>
                    <SectionTitle index="6">Contact</SectionTitle>
                    <BodyText>
                        We are always happy to hear from legal professionals, researchers, and potential partners.
                    </BodyText>
                    <div
                        className="mt-4 rounded-[14px] p-5"
                        style={{
                            background: "var(--strict-gold-badge-bg)",
                            border: "1px solid var(--strict-gold-badge-border)",
                        }}
                    >
                        <p className="font-heading font-semibold text-base mb-3"
                           style={{color: "var(--strict-text-primary)"}}>
                            Vitreon Legal
                        </p>
                        <p className="text-sm mb-2" style={{color: "var(--strict-text-body)"}}>
                            General enquiries:{" "}
                            <a href="mailto:legal@vitreon.app" style={{color: "var(--strict-gold-base)"}} className="hover:underline">
                                legal@vitreon.app
                            </a>
                        </p>
                        <p className="text-sm mb-2" style={{color: "var(--strict-text-body)"}}>
                            Enterprise &amp; partnerships:{" "}
                            <a href="mailto:enterprise@vitreon.app" style={{color: "var(--strict-gold-base)"}} className="hover:underline">
                                enterprise@vitreon.app
                            </a>
                        </p>
                        <p className="text-sm mb-4" style={{color: "var(--strict-text-body)"}}>
                            Based in Prague, Czech Republic
                        </p>
                        <Link
                            href="mailto:enterprise@vitreon.app"
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-opacity hover:opacity-90"
                            style={{background: "var(--strict-gold-base)", color: "var(--strict-bg-html)"}}
                        >
                            Request Enterprise Demo <ArrowRight size={14} />
                        </Link>
                    </div>
                </Section>

                {/* CTA Section */}
                <section
                    className="mt-8 rounded-2xl p-8 text-center"
                    style={{
                        background: "var(--strict-gold-badge-bg)",
                        border: "1px solid var(--strict-gold-badge-border)",
                    }}
                >
                    <h2
                        className="font-heading font-bold mb-3"
                        style={{
                            fontSize: "1.25rem",
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Ready to streamline your legal research?
                    </h2>
                    <p className="text-sm mb-6" style={{color: "var(--strict-text-body)"}}>
                        Get source-grounded answers with 100% citation coverage. Start free, no credit card.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-3 justify-center">
                        <Link
                            href="/login?mode=register"
                            className="inline-flex items-center justify-center gap-2 px-5 py-3 min-h-[44px] rounded-lg text-sm font-semibold transition-colors"
                            style={{
                                background: "var(--strict-gold-base)",
                                color: "var(--strict-bg-html)",
                            }}
                        >
                            Get Started Free
                            <ArrowRight size={14} />
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
                </section>
            </main>

            <StrictFooter />
        </div>
    );
}

/* -- Shared layout primitives -- */

function Section({children}: { children: React.ReactNode }) {
    return <section className="mb-10">{children}</section>;
}

function Divider() {
    return (
        <hr
            className="my-10"
            style={{borderColor: "var(--strict-hr-border)"}}
        />
    );
}

function SectionTitle({
                          index,
                          children,
                      }: {
    index: string;
    children: React.ReactNode;
}) {
    return (
        <h2
            className="font-heading font-bold mb-4"
            style={{
                fontSize: "1.25rem",
                color: "var(--strict-text-primary)",
                letterSpacing: "-0.01em",
            }}
        >
      <span style={{
          color: "var(--strict-gold-text)",
          marginRight: "0.5rem",
          fontFamily: "var(--font-sans), sans-serif",
          fontSize: "0.85em",
          fontWeight: 500
      }}>
        {index}.
      </span>
            {children}
        </h2>
    );
}

function BodyText({children}: { children: React.ReactNode }) {
    return (
        <p
            className="mb-3 text-sm leading-7"
            style={{color: "var(--strict-text-body)"}}
        >
            {children}
        </p>
    );
}

function BulletList({items}: { items: string[] }) {
    return (
        <ul className="mb-4 space-y-1.5 pl-1">
            {items.map((item) => (
                <li
                    key={item.slice(0, 40)}
                    className="flex items-start gap-2.5 text-sm leading-6"
                    style={{color: "var(--strict-text-body)"}}
                >
          <span
              className="mt-2 shrink-0 size-1 rounded-full"
              style={{background: "var(--strict-gold-base)", opacity: 0.7}}
          />
                    {item}
                </li>
            ))}
        </ul>
    );
}

function GlassCard({children}: { children: React.ReactNode }) {
    return (
        <div
            className="mt-4 rounded-[14px] overflow-hidden"
            style={{
                background: "var(--strict-glass-bg)",
                border: "1px solid var(--strict-glass-border)",
                backdropFilter: "var(--strict-glass-blur)",
            }}
        >
            {children}
        </div>
    );
}

function GoldText({children}: { children: React.ReactNode }) {
    return (
        <strong style={{color: "var(--strict-gold-base)"}}>
            {children}
        </strong>
    );
}
