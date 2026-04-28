import type {Metadata} from "next";
import type {CSSProperties} from "react";
import dynamic from "next/dynamic";
import {buildFaqJsonLd} from "@/lib/faq-data";

// Client component for interactive parts only (theme toggle, auth, demo panel)
const LandingClient = dynamic(() => import("./landing-client").then(m => ({ default: m.LandingClient })), {
    ssr: true,
    loading: () => null, // Don't render anything during loading - hero is server-rendered
});

export const metadata: Metadata = {
    title: "AI Legal Research with Cited Sources — Vitreon",
    description:
        "Find the exact statute or court decision in seconds. Every answer cites the page and clause. Czech, DIFC, UK, AU jurisdictions. 3 free queries/day, no card.",
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
        "právní výzkum",
        "judikatura",
        "AI právní asistent",
    ],
    authors: [{name: "Viacheslav Ivannikov"}],
    openGraph: {
        title: "AI Legal Research with Cited Sources — Vitreon",
        description:
            "Find the exact statute or court decision in seconds. Every answer cites the page and clause. Czech, DIFC, UK, AU jurisdictions. 3 free queries/day, no card.",
        url: "https://vitreon.app",
        siteName: "Vitreon Legal",
        locale: "en",
        type: "website",
        images: [
            {
                url: "/opengraph-image.png",
                width: 1200,
                height: 630,
                alt: "Vitreon Legal — AI Legal Research Platform",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "AI Legal Research with Cited Sources — Vitreon",
        description:
            "Find the exact statute or court decision in seconds. Every answer cites the page and clause. Czech, DIFC, UK, AU jurisdictions. 3 free queries/day, no card.",
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
    color: "#c47c00",
    fontWeight: 700,
    // Simplified for LCP - removed gradient effect that was expensive to render
    // Original gradient effect can be added via CSS class after LCP fires
};

export default function LandingPage() {
    const heroTitle = (
        <h1 style={HERO_H1_STYLE}>
            Legal Research at the{" "}
            <span style={HERO_HIGHLIGHT_STYLE}>Speed of Thought</span>
        </h1>
    );

    return (
        <>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(buildFaqJsonLd())}}
            />
            {/* Server-rendered above-fold content - LCP fires immediately */}
            <div className="landing-light-hero" style={{fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif"}}>
                <section style={{
                    position: "relative",
                    minHeight: "100vh",
                    display: "flex",
                    flexDirection: "column",
                    overflow: "hidden",
                    background: "linear-gradient(145deg, #dfc090 0%, #e8d4b8 45%, #dbb870 100%)"
                }}>
                    {/* Hero content - server rendered, no JS needed for LCP */}
                    <div style={{
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        paddingLeft: "24px",
                        paddingRight: "24px",
                        position: "relative",
                        zIndex: 1,
                        textAlign: "center"
                    }}>
                        <p style={{
                            fontSize: 11,
                            textTransform: "uppercase",
                            letterSpacing: "0.20em",
                            fontWeight: 600,
                            color: "#5c2e08",
                            marginBottom: 20
                        }}>AI LEGAL RESEARCH</p>
                        {heroTitle}
                        <p style={{
                            fontSize: 16,
                            color: "rgba(46,31,8,0.60)",
                            lineHeight: 1.6,
                            maxWidth: 520,
                            marginBottom: 48,
                            whiteSpace: "pre-line"
                        }}>Find the exact statute or court decision in seconds. Every answer cites the page and clause.</p>
                    </div>
                    
                    {/* Client-side interactive overlay - loads after LCP */}  
                    <LandingClient />
                </section>
            </div>
        </>
    );
}
