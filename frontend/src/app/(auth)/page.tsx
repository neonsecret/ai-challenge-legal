import type {Metadata} from "next";
import type {CSSProperties} from "react";
import {LandingClient} from "./landing-client";

export const metadata: Metadata = {
    title: "Vitreon Legal — AI-Powered Legal Research Platform",
    description:
        "AI-powered legal research platform providing source-grounded answers from statutes and court decisions. Every answer cites the exact page and clause. Supports Czech, DIFC, UK, and Australian jurisdictions. GaRAGe benchmark: 0.824 RAF (+36% above SOTA).",
    keywords: [
        "legal research",
        "AI legal assistant",
        "legal AI",
        "court decisions",
        "case law",
        "Czech law",
        "DIFC law",
        "UK law",
        "Australian law",
        "legal document drafting",
        "RAG",
        "právní výzkum",
        "judikatura",
        "AI právní asistent",
    ],
    authors: [{name: "Viacheslav Ivannikov"}],
    openGraph: {
        title: "Vitreon Legal — AI-Powered Legal Research Platform",
        description:
            "Source-grounded legal research with 100% citation coverage. Covers Czech, DIFC, UK, and Australian jurisdictions. GaRAGe benchmark: +36% above SOTA.",
        url: "https://vitreon.app",
        siteName: "Vitreon Legal",
        locale: "en",
        type: "website",
        images: [
            {
                url: "/opengraph-image.png",
                width: 1200,
                height: 630,
                alt: "Vitreon Legal — AI-Powered Legal Research Platform",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Vitreon Legal — AI-Powered Legal Research Platform",
        description:
            "Source-grounded legal research with 100% citation coverage. Covers Czech, DIFC, UK, and Australian jurisdictions.",
        images: ["/opengraph-image.png"],
    },
    alternates: {
        canonical: "https://vitreon.app",
    },
};

const HERO_H1_STYLE: CSSProperties = {
    fontFamily: "Georgia, 'Times New Roman', serif",
    fontSize: "clamp(2.2rem, 5vw, 4.5rem)",
    fontWeight: 700,
    letterSpacing: "-0.03em",
    lineHeight: 1.1,
    color: "#1a0e04",
    marginBottom: 20,
    maxWidth: 780,
};

const HERO_HIGHLIGHT_STYLE: CSSProperties = {
    background: "linear-gradient(90deg, #c47c00 0%, #e8a020 50%, #c47c00 100%)",
    backgroundSize: "200% auto",
    WebkitBackgroundClip: "text",
    backgroundClip: "text",
    WebkitTextFillColor: "transparent",
    animation: "shimmer 3s linear infinite",
};

export default function LandingPage() {
    const heroTitle = (
        <h1 style={HERO_H1_STYLE}>
            Legal Research at the{" "}
            <span style={HERO_HIGHLIGHT_STYLE}>Speed of Thought</span>
        </h1>
    );
    return <LandingClient heroTitle={heroTitle} />;
}
