import type {Metadata, Viewport} from "next";
import {Playfair_Display, Inter} from "next/font/google";
import "./globals.css";
import {ColorModeProvider} from "@/lib/color-mode";
import {TooltipProvider} from "@/components/ui/tooltip";
import {ToastProvider} from "@/components/ui/toast";
import {I18nProvider} from "@/lib/i18n";

const playfair = Playfair_Display({
    subsets: ["latin"],
    variable: "--font-heading",
    display: "swap",
});

const inter = Inter({
    subsets: ["latin"],
    variable: "--font-sans",
    display: "swap",
});

export const metadata: Metadata = {
    metadataBase: new URL("https://vitreon.app"),
    title: {
        default: "Vitreon Legal — Your AI Legal Counsel",
        template: "%s | Vitreon Legal",
    },
    description:
        "AI-powered legal research platform providing source-grounded answers from statutes and court decisions. Every answer cites the exact page and clause. Supports Czech, DIFC, UK, and Australian jurisdictions.",
    keywords: [
        "legal research",
        "AI legal assistant",
        "legal AI",
        "court decisions",
        "case law",
        "Czech law",
        "DIFC law",
        "legal document drafting",
    ],
    authors: [{name: "Viacheslav Ivannikov"}],
    creator: "Vitreon Legal",
    publisher: "Vitreon Legal",
    icons: {
        icon: [
            {url: "/favicon-192.png", sizes: "192x192", type: "image/png"},
            {url: "/favicon-512.png", sizes: "512x512", type: "image/png"},
        ],
        apple: [{url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png"}],
    },
    manifest: "/manifest.json",
    robots: {
        index: true,
        follow: true,
        googleBot: {
            index: true,
            follow: true,
            "max-video-preview": -1,
            "max-image-preview": "large",
            "max-snippet": -1,
        },
    },
    alternates: {
        canonical: "https://vitreon.app",
        languages: {
            en: "https://vitreon.app",
            cs: "https://vitreon.app/cs",
        },
    },
    openGraph: {
        title: "Vitreon Legal — Your AI Legal Counsel",
        description:
            "AI-powered legal research platform with source-grounded answers from statutes and court decisions. 100% citation coverage across Czech, DIFC, UK, and Australian jurisdictions.",
        url: "https://vitreon.app",
        siteName: "Vitreon Legal",
        locale: "en",
        alternateLocale: "cs",
        type: "website",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Vitreon Legal — AI-Powered Legal Research Platform",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Vitreon Legal — Your AI Legal Counsel",
        description:
            "AI-powered legal research with source-grounded answers. 100% citation coverage across Czech, DIFC, UK, and Australian jurisdictions.",
        images: ["/opengraph-image"],
    },
    verification: {
        google: "google-site-verification-code",
    },
};

export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    maximumScale: 5,
};

const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Organization",
            "@id": "https://vitreon.app/#organization",
            "name": "Vitreon Legal",
            "url": "https://vitreon.app",
            "logo": {
                "@type": "ImageObject",
                "url": "https://vitreon.app/vitreon-logo.svg",
            },
            "description":
                "AI-powered legal research platform providing source-grounded answers from statutes and court decisions for Czech, DIFC, UK, and Australian law.",
            "foundingDate": "2025",
            "founder": {
                "@type": "Person",
                "@id": "https://vitreon.app/#founder",
                "name": "Viacheslav Ivannikov",
                "jobTitle": "Founder & CEO",
                "knowsAbout": [
                    "Legal AI",
                    "Retrieval Augmented Generation",
                    "Legal Research",
                    "Czech Law",
                    "Embedding Models",
                    "Natural Language Processing",
                ],
            },
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "Prague",
                "addressCountry": "CZ",
            },
            "contactPoint": [
                {
                    "@type": "ContactPoint",
                    "email": "legal@vitreon.app",
                    "contactType": "customer service",
                },
                {
                    "@type": "ContactPoint",
                    "email": "enterprise@vitreon.app",
                    "contactType": "sales",
                },
            ],
            "sameAs": [],
            "knowsAbout": [
                "Legal Research",
                "Czech Law",
                "DIFC Law",
                "UK Law",
                "Australian Law",
                "Court Decisions",
                "Legal AI",
                "Retrieval Augmented Generation",
                "Legal Document Drafting",
                "Case Law Analysis",
            ],
        },
        {
            "@type": "SoftwareApplication",
            "@id": "https://vitreon.app/#software",
            "name": "Vitreon Legal",
            "url": "https://vitreon.app",
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Web",
            "description":
                "AI legal research platform with source-grounded answers from statutes and court decisions. Supports Czech, DIFC, UK, and Australian jurisdictions.",
            "offers": [
                {
                    "@type": "Offer",
                    "name": "Free",
                    "price": "0",
                    "priceCurrency": "USD",
                    "description": "3 queries per day",
                },
                {
                    "@type": "Offer",
                    "name": "Starter",
                    "price": "29",
                    "priceCurrency": "USD",
                    "description": "30 queries per day",
                },
                {
                    "@type": "Offer",
                    "name": "Pro",
                    "price": "179",
                    "priceCurrency": "USD",
                    "description": "200 queries per day",
                },
                {
                    "@type": "Offer",
                    "name": "Enterprise",
                    "price": "499",
                    "priceCurrency": "USD",
                    "description": "Unlimited queries",
                },
            ],
            "featureList": [
                "Source-grounded legal answers with page and clause citations",
                "Czech law coverage including statutes and court decisions",
                "DIFC, UK, and Australian jurisdiction support",
                "9 Czech legal document templates",
                "Legal document drafting with statutory grounding",
                "Multi-jurisdiction legal research",
                "100% citation coverage",
            ],
            "provider": {
                "@id": "https://vitreon.app/#organization",
            },
        },
        {
            "@type": "WebSite",
            "@id": "https://vitreon.app/#website",
            "name": "Vitreon Legal",
            "url": "https://vitreon.app",
            "description": "AI-powered legal research and document analysis",
            "inLanguage": ["cs", "en"],
            "publisher": {
                "@id": "https://vitreon.app/#organization",
            },
        },
    ],
};

export default function RootLayout({
                                       children,
                                   }: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        // TODO: Make lang dynamic when URL-based locale routing is added (e.g. /cs/ -> lang="cs")
        <html
            lang="en"
            suppressHydrationWarning
            className={`${playfair.variable} ${inter.variable} h-full antialiased`}
        >
        <head>
            {/* JSON-LD structured data for search engines and AI crawlers */}
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(jsonLd)}}
            />
            {/* Unified color-mode FOUC prevention — runs sync before paint.
                Priority: vitreon-color-mode > vitreon-design-version (migration) > theme (migration) > system */}
            {/* Tell dark-mode browser extensions this page manages its own colors */}
            <meta name="color-scheme" content="light dark" />
            {/* Dark Reader: official opt-out — skip this site entirely */}
            <meta name="darkreader-lock" />
            <script dangerouslySetInnerHTML={{__html: `try{var cm=localStorage.getItem('vitreon-color-mode'),isDark=false;if(cm==='dark'){isDark=true}else if(cm==='light'){isDark=false}else if(cm==='system'||!cm){var dv=localStorage.getItem('vitreon-design-version');if(dv==='strict'){isDark=true;localStorage.setItem('vitreon-color-mode','dark')}else if(dv==='neon'){isDark=false;localStorage.setItem('vitreon-color-mode','light')}else{var th=localStorage.getItem('theme');if(th==='dark'){isDark=true}else if(th==='light'){isDark=false}else{isDark=true}}};if(isDark){document.documentElement.classList.add('dark');document.documentElement.classList.remove('light');document.documentElement.style.colorScheme='dark'}else{document.documentElement.classList.add('light');document.documentElement.classList.remove('dark');document.documentElement.style.colorScheme='light'}}catch(e){document.documentElement.classList.add('light');document.documentElement.style.colorScheme='light'}`}} />
        </head>
        <body className="h-full bg-background text-foreground">
        <ColorModeProvider>
            <I18nProvider>
                <TooltipProvider>
                    <ToastProvider>
                        {children}
                    </ToastProvider>
                </TooltipProvider>
            </I18nProvider>
        </ColorModeProvider>
        </body>
        </html>
    );
}
