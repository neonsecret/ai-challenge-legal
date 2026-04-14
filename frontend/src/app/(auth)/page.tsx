import type {Metadata} from "next";
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
};

export default function LandingPage() {
    return <LandingClient />;
}
