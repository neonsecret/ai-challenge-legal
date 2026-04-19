import Link from "next/link";
import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

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

const FAQ_ITEMS: { question: string; answer: string }[] = [
    {
        question: "What is Vitreon Legal?",
        answer:
            "Vitreon Legal is an AI-powered legal research platform that provides source-grounded answers from statutes and court decisions. It helps legal professionals find relevant case law, legislation, and legal precedents across Czech, DIFC, UK, and Australian jurisdictions. Every answer includes exact page and clause citations so you can verify any claim instantly.",
    },
    {
        question: "How does Vitreon differ from Beck-online or ASPI?",
        answer:
            "Beck-online and ASPI are traditional legal databases that require manual keyword searches and browsing. Vitreon Legal uses AI to understand your question in natural language and returns precise, source-grounded answers with citations — not a list of documents to read through. Vitreon's retrieval pipeline scores +36% above published state-of-the-art on the GaRAGe benchmark (ACL 2025) and offers self-serve pricing starting at $0/month.",
    },
    {
        question: "What jurisdictions does Vitreon support?",
        answer:
            "Vitreon Legal currently supports four jurisdictions: Czech Republic (295,000+ court decisions, 6,800+ statutes), DIFC / Dubai International Financial Centre (full legislation library and court judgments), United Kingdom, and Australia. Czech coverage is the most comprehensive. Additional jurisdictions are added based on user demand.",
    },
    {
        question: "How accurate are the answers?",
        answer:
            "Vitreon Legal achieves 100% citation coverage — every answer includes citations traceable to specific passages in the legal corpus. On the GaRAGe benchmark (ACL 2025), Vitreon scores 0.824 RAF, which is 36% above the published state-of-the-art of 0.607. On LEXam Open EN (ICLR 2026), Vitreon scores 0.691, 21% above the Claude 3.7-S baseline. These are independently reproducible benchmarks.",
    },
    {
        question: "What does \"source-grounded\" mean?",
        answer:
            "Source-grounded means every answer is generated exclusively from documents in the legal corpus — not from the AI model's training data. The system retrieves relevant passages first, then generates an answer citing only those passages. This architectural guarantee prevents hallucination: if the answer isn't in the documents, the system says so rather than making something up.",
    },
    {
        question: "Can I use Vitreon for court filings?",
        answer:
            "Vitreon Legal is a research assistance tool, not a law firm. You can use it to find relevant case law, statutes, and legal precedents for your filings, but the output should be reviewed by a qualified legal professional before use in court documents. Every citation includes the source document, page number, and clause reference so you can independently verify accuracy.",
    },
    {
        question: "What is the pricing?",
        answer:
            "Vitreon Legal offers four plans: Free ($0/month, 3 queries per day), Starter ($29/month, 30 queries per day), Pro ($179/month, 200 queries per day), and Enterprise ($499/month, unlimited queries). All plans include all jurisdictions and source citations. Paid plans add document upload and priority support. No credit card is required for the free plan.",
    },
    {
        question: "Is there a free plan?",
        answer:
            "Yes. The Free plan includes 3 queries per day at no cost. No credit card is required to sign up — create an account with Google or email and start researching immediately. The Free plan includes access to all jurisdictions and full source citations.",
    },
    {
        question: "How does the AI find relevant case law?",
        answer:
            "Vitreon uses a multi-stage retrieval pipeline: (1) hybrid BM25 + vector search runs in parallel to find candidate passages using both keyword matching and semantic similarity, (2) Reciprocal Rank Fusion merges the results, (3) a cross-encoder reranker scores each passage against your question, and (4) the top passages are provided to the LLM to generate a cited answer. The embedding model (Qwen3-Embedding-8B) was evaluated specifically for multilingual legal document retrieval.",
    },
    {
        question: "Is my data secure?",
        answer:
            "Yes. All connections use TLS 1.2+ encryption. Passwords are hashed with bcrypt. Sessions use HttpOnly, SameSite cookies. Your queries and documents are never used to train AI models. Payment processing is handled by Stripe (PCI DSS Level 1). Vitreon complies with GDPR and is governed by Czech data protection law. See our Privacy Policy for full details.",
    },
    {
        question: "What are the document templates?",
        answer:
            "Vitreon Legal includes 9 Czech legal document templates for common legal documents. Templates are pre-structured with statutory grounding — the AI fills in the specifics based on your input while ensuring the document references relevant legislation. Templates are available on all paid plans.",
    },
    {
        question: "Can I try Vitreon before paying?",
        answer:
            "Yes. The Free plan gives you 3 queries per day at no cost, with no credit card required. This lets you evaluate the quality of answers, citation accuracy, and relevance to your practice area before committing to a paid plan.",
    },
    {
        question: "Do you support multi-jurisdiction research?",
        answer:
            "Yes. You can research across Czech, DIFC, UK, and Australian law within the same conversation. The system automatically identifies which jurisdiction is relevant to your question and retrieves from the appropriate corpus. You can also specify a jurisdiction explicitly in your query.",
    },
    {
        question: "What languages does Vitreon support?",
        answer:
            "The platform interface is available in English and Czech. Legal research queries can be submitted in either language. Czech law documents are indexed in their original Czech text, and the system handles Czech legal terminology natively — including \"judikatura\" (case law), \"zákony\" (statutes), and \"soudní rozhodnutí\" (court decisions).",
    },
    {
        question: "How do I contact support?",
        answer:
            "For general enquiries, email legal@vitreon.app. For enterprise and partnership enquiries, email enterprise@vitreon.app. For privacy and data protection requests, email privacy@vitreon.app. For security disclosures, email security@vitreon.app. We typically respond within 24 hours on business days.",
    },
    {
        question: "Can I upload my own documents?",
        answer:
            "Yes. Paid plans allow you to upload your own PDF or TXT documents to create a custom research corpus. Uploaded documents are indexed and searchable alongside the built-in legal corpus. This is useful for firm-specific precedents, contract databases, or specialized document collections.",
    },
];

function faqJsonLd() {
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: FAQ_ITEMS.map((item) => ({
            "@type": "Question",
            name: item.question,
            acceptedAnswer: {
                "@type": "Answer",
                text: item.answer,
            },
        })),
    };
}

export default function FAQPage() {
    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            {/* JSON-LD */}
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(faqJsonLd())}}
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
                    <Link
                        href="/"
                        className="inline-block px-6 py-2.5 rounded-lg text-sm font-semibold transition-opacity hover:opacity-90"
                        style={{
                            background: "var(--strict-gold-base)",
                            color: "var(--strict-bg-html)",
                        }}
                    >
                        Get Started Free
                    </Link>
                </div>
            </main>

            <StrictFooter />
        </div>
    );
}
