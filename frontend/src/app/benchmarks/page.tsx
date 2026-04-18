import Link from "next/link";
import type {Metadata} from "next";
import {ArrowRight} from "lucide-react";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Legal AI Benchmarks: +36% Above SOTA — Vitreon Legal",
    description:
        "Beat published SOTA by 36% on GaRAGe benchmark (ACL 2025). LEXam 0.691 (+21% above baseline), ARLC 2026 4th/80 teams, 100% citation coverage. Independent, reproducible legal AI benchmarks.",
    openGraph: {
        title: "Legal AI Benchmarks: +36% Above SOTA — Vitreon Legal",
        description:
            "Beat published SOTA by 36% on GaRAGe (ACL 2025). LEXam 0.691 (+21%), ARLC 2026 4th/80 teams. Independent legal AI benchmark results.",
        url: "https://vitreon.app/benchmarks",
        siteName: "Vitreon Legal",
        locale: "en",
        type: "website",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Vitreon Legal — Legal AI Benchmarks",
            },
        ],
    },
};

export default function BenchmarksPage() {
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
                        Research
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
                        Benchmark Results
                    </h1>
                    <p className="text-sm max-w-2xl" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        Vitreon Legal&apos;s retrieval pipeline is evaluated on independent, public benchmarks.
                        All results are reproducible. We report scores on the same test sets and evaluation
                        protocols as the original benchmark papers.
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
                        Pipeline that achieved these scores now powers the production platform.
                    </p>
                    <Link
                        href="/login"
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-opacity hover:opacity-90"
                        style={{background: "var(--strict-gold-base)", color: "#fff"}}
                    >
                        Try Vitreon Free <ArrowRight size={14} />
                    </Link>
                </div>

                {/* Summary Table */}
                <Section>
                    <SectionTitle index="1">Performance Summary</SectionTitle>
                    <GlassCard>
                        <table className="w-full text-sm">
                            <thead>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Benchmark</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Vitreon Score</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Published SOTA</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Improvement</th>
                            </tr>
                            </thead>
                            <tbody>
                            {[
                                ["GaRAGe (ACL 2025)", "0.824", "0.607", "+36%"],
                                ["LEXam Open EN (ICLR 2026)", "0.691", "0.572", "+21%"],
                                ["Legal RAG Bench", "0.860", "—", "—"],
                                ["ARLC 2026 Warmup", "0.958", "—", "1st / 80 teams"],
                                ["ARLC 2026 Finals", "0.719", "—", "4th / 80 teams"],
                                ["Citation Coverage", "100%", "—", "—"],
                            ].map(([bench, score, sota, improvement], i) => (
                                <tr
                                    key={bench}
                                    style={{
                                        borderTop: i > 0 ? "1px solid var(--strict-glass-border)" : undefined,
                                    }}
                                >
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>{bench}</td>
                                    <td className="px-5 py-3 font-semibold"><GoldGradient>{score}</GoldGradient></td>
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-secondary)"}}>{sota}</td>
                                    <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>{improvement}</td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </GlassCard>
                </Section>

                <Divider />

                {/* GaRAGe */}
                <Section>
                    <SectionTitle index="2">GaRAGe Benchmark</SectionTitle>
                    <Stat label="RAF Score" value="0.824" detail="+36% above published SOTA of 0.607" />
                    <BodyText>
                        GaRAGe (General-purpose RAG evaluation) is a retrieval-augmented generation benchmark
                        published at ACL 2025 by Amazon Science. It evaluates end-to-end RAG pipelines on their
                        ability to retrieve relevant passages and generate accurate, grounded answers from a
                        heterogeneous document corpus.
                    </BodyText>
                    <BodyText>
                        The primary metric is the{" "}
                        <strong style={{color: "var(--strict-text-primary)"}}>Retrieval Accuracy Factor (RAF)</strong>,
                        which measures both retrieval precision and answer fidelity. The previously published
                        state-of-the-art score was 0.607. Vitreon Legal&apos;s pipeline achieves 0.824 &mdash;
                        a 36% improvement.
                    </BodyText>
                    <BodyText>
                        This score was achieved using Vitreon&apos;s production retrieval pipeline without
                        benchmark-specific tuning: hybrid BM25 + vector search with Reciprocal Rank Fusion,
                        asymmetric embedding, and cross-encoder reranking.
                    </BodyText>
                </Section>

                <Divider />

                {/* LEXam */}
                <Section>
                    <SectionTitle index="3">LEXam Open EN</SectionTitle>
                    <Stat label="Score" value="0.691" detail="+21% above Claude 3.7-S baseline of 0.572" />
                    <BodyText>
                        LEXam is a legal examination benchmark published at ICLR 2026 that evaluates AI
                        systems on their ability to answer legal questions drawn from bar exams and professional
                        legal assessments. The &ldquo;Open EN&rdquo; variant tests English-language open-ended
                        legal reasoning.
                    </BodyText>
                    <BodyText>
                        The baseline score of 0.572 was set by Claude 3.7 Sonnet in a direct prompting
                        configuration (no retrieval). Vitreon Legal&apos;s retrieval-augmented pipeline achieves
                        0.691 &mdash; demonstrating that source-grounded retrieval significantly improves legal
                        reasoning accuracy compared to pure LLM approaches.
                    </BodyText>
                </Section>

                <Divider />

                {/* Legal RAG Bench */}
                <Section>
                    <SectionTitle index="4">Legal RAG Bench</SectionTitle>
                    <Stat label="Retrieval Accuracy" value="0.860" detail="Domain-specific legal retrieval benchmark" />
                    <BodyText>
                        Legal RAG Bench is a domain-specific benchmark designed to evaluate retrieval-augmented
                        generation systems on legal document corpora. It tests passage retrieval accuracy,
                        answer grounding fidelity, and citation correctness across a range of legal question types.
                    </BodyText>
                    <BodyText>
                        Vitreon Legal scores 0.860 on the retrieval accuracy metric, reflecting the effectiveness
                        of the hybrid search architecture and cross-encoder reranking stage when applied to
                        legal-domain documents.
                    </BodyText>
                </Section>

                <Divider />

                {/* ARLC 2026 */}
                <Section>
                    <SectionTitle index="5">ARLC 2026 Competition</SectionTitle>
                    <Stat label="Overall Placement" value="4th / 80 teams" detail="$32K prize pool, Dubai AI Week" />
                    <BodyText>
                        The Agentic RAG Legal Challenge (ARLC 2026) was an international legal AI competition
                        organized during Dubai AI Week. 80 teams competed to build the most accurate legal
                        question-answering system over 300+ DIFC (Dubai International Financial Centre) legal
                        documents.
                    </BodyText>
                    <BodyText>
                        Vitreon Legal competed under the team name{" "}
                        <strong style={{color: "var(--strict-text-primary)"}}>&ldquo;Neon Team&rdquo;</strong>. The
                        competition consisted of a warmup round and a finals round:
                    </BodyText>
                    <BulletList
                        items={[
                            "Warmup round: 0.958 — 1st place out of 80 teams.",
                            "Finals round: 0.719 — 4th place overall.",
                        ]}
                    />
                    <BodyText>
                        The same retrieval and reasoning pipeline that achieved these competition scores now
                        powers the production Vitreon Legal platform. For the full story of the competition,
                        see our blog post:{" "}
                        <Link href="/blog/arlc-2026-results" style={{color: "var(--strict-gold-base)"}} className="hover:underline">
                            How Vitreon Placed 4th in ARLC 2026
                        </Link>.
                    </BodyText>
                </Section>

                <Divider />

                {/* Citation Accuracy */}
                <Section>
                    <SectionTitle index="6">100% Citation Coverage</SectionTitle>
                    <Stat label="Citation Coverage" value="100%" detail="Every answer cites exact page and clause" />
                    <BodyText>
                        Every answer generated by Vitreon Legal includes citations to the exact page, clause,
                        and source document from which the information was retrieved. This is not a statistical
                        average &mdash; the system architecturally guarantees that every claim in an answer is
                        traceable to a specific passage in the legal corpus.
                    </BodyText>
                    <BodyText>
                        Source grounding is enforced at the retrieval stage: the LLM only generates answers
                        from passages that have been explicitly retrieved and verified by the reranking pipeline.
                        No external knowledge or training data is used in the answer generation step.
                    </BodyText>
                </Section>

                <Divider />

                {/* Methodology */}
                <Section>
                    <SectionTitle index="7">Retrieval Pipeline Methodology</SectionTitle>
                    <BodyText>
                        Vitreon Legal&apos;s retrieval architecture is a multi-stage pipeline designed for
                        high-precision legal document retrieval:
                    </BodyText>

                    <SubHeading>Stage 1: Hybrid Search</SubHeading>
                    <BodyText>
                        Queries are processed through both BM25 (lexical) and vector search (semantic) in
                        parallel. Results are merged using{" "}
                        <strong style={{color: "var(--strict-text-primary)"}}>Reciprocal Rank Fusion (RRF)</strong>,
                        which combines the strengths of exact keyword matching with semantic similarity.
                    </BodyText>

                    <SubHeading>Stage 2: Asymmetric Embedding</SubHeading>
                    <BodyText>
                        Document passages are embedded using{" "}
                        <strong style={{color: "var(--strict-text-primary)"}}>Qwen3-Embedding-8B</strong> with
                        asymmetric encoding &mdash; queries and documents use different embedding prefixes
                        optimized for retrieval rather than similarity. This model was selected after extensive
                        evaluation against multilingual legal corpora.
                    </BodyText>

                    <SubHeading>Stage 3: Cross-Encoder Reranking</SubHeading>
                    <BodyText>
                        Top candidate passages are reranked using a cross-encoder model that jointly encodes
                        the query and each passage. This stage provides the final precision boost that
                        distinguishes relevant passages from merely similar ones.
                    </BodyText>

                    <SubHeading>Stage 4: Grounded Answer Generation</SubHeading>
                    <BodyText>
                        The reranked passages are provided to the LLM with strict instructions to generate
                        answers only from the retrieved context. Every claim must cite the source passage,
                        page number, and clause reference.
                    </BodyText>
                </Section>

                <Divider />

                {/* Corpus */}
                <Section>
                    <SectionTitle index="8">Legal Corpus</SectionTitle>
                    <BodyText>
                        Vitreon Legal indexes legal documents across four jurisdictions:
                    </BodyText>
                    <GlassCard>
                        <table className="w-full text-sm">
                            <thead>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Jurisdiction</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Court Decisions</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Statutes</th>
                            </tr>
                            </thead>
                            <tbody>
                            {[
                                ["Czech Republic", "295,000+", "6,800+"],
                                ["DIFC (Dubai)", "300+", "Full legislation library"],
                                ["United Kingdom", "Coverage expanding", "Key statutes"],
                                ["Australia", "Coverage expanding", "Key statutes"],
                            ].map(([jurisdiction, decisions, statutes], i) => (
                                <tr
                                    key={jurisdiction}
                                    style={{
                                        borderTop: i > 0 ? "1px solid var(--strict-glass-border)" : undefined,
                                    }}
                                >
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>{jurisdiction}</td>
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>{decisions}</td>
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>{statutes}</td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </GlassCard>
                </Section>

                <Divider />

                {/* Competitor Comparison */}
                <Section>
                    <SectionTitle index="9">Competitor Comparison</SectionTitle>
                    <BodyText>
                        How Vitreon Legal compares to established Czech legal research platforms:
                    </BodyText>
                    <GlassCard>
                        <table className="w-full text-sm">
                            <thead>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Feature</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-gold-base)"}}>Vitreon Legal</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Beck-online</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>ASPI</th>
                            </tr>
                            </thead>
                            <tbody>
                            {[
                                ["AI-powered answers", "Yes", "No", "No"],
                                ["Source-grounded citations", "100% coverage", "Manual lookup", "Manual lookup"],
                                ["GaRAGe benchmark", "0.824 (+36% SOTA)", "Not tested", "Not tested"],
                                ["Competition placement", "4th / 80 (ARLC 2026)", "Not entered", "Not entered"],
                                ["Self-serve pricing", "From $0/mo", "Enterprise sales", "Enterprise/institutional"],
                                ["Czech court decisions", "295,000+", "Extensive", "Extensive"],
                                ["Multi-jurisdiction", "4 jurisdictions", "Czech/German focus", "Czech focus"],
                                ["Document upload", "Yes (custom corpus)", "No", "No"],
                            ].map(([feature, vitreon, beck, aspi], i) => (
                                <tr
                                    key={feature}
                                    style={{
                                        borderTop: i > 0 ? "1px solid var(--strict-glass-border)" : undefined,
                                    }}
                                >
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>{feature}</td>
                                    <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>{vitreon}</td>
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-secondary)"}}>{beck}</td>
                                    <td className="px-5 py-3" style={{color: "var(--strict-text-secondary)"}}>{aspi}</td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </GlassCard>
                </Section>

                <Divider />

                {/* Academic References */}
                <Section>
                    <SectionTitle index="10">Academic References</SectionTitle>
                    <BodyText>
                        The benchmarks referenced on this page are from the following peer-reviewed publications:
                    </BodyText>
                    <BulletList
                        items={[
                            "GaRAGe: General-purpose RAG Evaluation — ACL 2025 Findings, Amazon Science.",
                            "LEXam: Legal Examination Benchmark — ICLR 2026, OpenReview.",
                            "ARLC 2026: Agentic RAG Legal Challenge — Dubai AI Week 2026, machinescansee.com leaderboard.",
                        ]}
                    />
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
                        Ready to try Vitreon Legal?
                    </h2>
                    <p className="text-sm mb-6" style={{color: "var(--strict-text-body)"}}>
                        See the retrieval pipeline in action. 100% citation coverage, start free.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-3 justify-center">
                        <Link
                            href="/login"
                            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors"
                            style={{
                                background: "var(--strict-gold-base)",
                                color: "#fff",
                            }}
                        >
                            Get Started Free
                            <ArrowRight size={14} />
                        </Link>
                        <Link
                            href="/chat"
                            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
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

function Stat({label, value, detail}: { label: string; value: string; detail: string }) {
    return (
        <div
            className="mb-6 rounded-[14px] p-5"
            style={{
                background: "var(--strict-gold-badge-bg)",
                border: "1px solid var(--strict-gold-badge-border)",
            }}
        >
            <p className="text-xs uppercase tracking-wider mb-1" style={{color: "var(--strict-text-secondary)"}}>
                {label}
            </p>
            <p className="font-heading font-bold text-2xl mb-1">
                <GoldGradient>{value}</GoldGradient>
            </p>
            <p className="text-sm" style={{color: "var(--strict-text-body)"}}>
                {detail}
            </p>
        </div>
    );
}

function GoldGradient({children}: { children: React.ReactNode }) {
    return (
        <span
            style={{
                background: "linear-gradient(135deg, var(--strict-gold-gradient-start), var(--strict-gold-gradient-end))",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
            }}
        >
            {children}
        </span>
    );
}
