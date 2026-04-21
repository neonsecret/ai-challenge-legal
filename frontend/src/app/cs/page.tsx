import Link from "next/link";
import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";
import {ArrowRight, Scale, Search, FileText, Shield, BookOpen, Gavel} from "lucide-react";

export const metadata: Metadata = {
    title: "Vitreon Legal — AI právní asistent pro českou judikaturu",
    description:
        "Pokládejte právní otázky v češtině a získejte odpovědi podložené citacemi z judikatury NSS, ÚS a obecných soudů. Alternativa k Beck-online a ASPI s AI. Zdarma 3 dotazy denně.",
    keywords: [
        "AI právní asistent",
        "česká judikatura AI",
        "právní výzkum software",
        "Beck-online alternativa",
        "ASPI alternativa",
        "zákoník práce AI",
        "správní právo AI",
        "AI pro advokáty",
        "judikatura AI",
        "právní AI platforma",
        "právní databáze česká",
        "rozsudky NSS AI",
    ],
    alternates: {
        canonical: "https://vitreon.app/cs",
        languages: {
            "cs": "https://vitreon.app/cs",
            "en": "https://vitreon.app",
        },
    },
    openGraph: {
        title: "Vitreon Legal — AI právní asistent pro českou judikaturu",
        description:
            "AI asistent pro právní výzkum s citacemi z české judikatury a legislativy. NSS, ÚS, obecné soudy. Bezplatný plán — 3 dotazy denně bez platební karty.",
        url: "https://vitreon.app/cs",
        siteName: "Vitreon Legal",
        locale: "cs_CZ",
        type: "website",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Vitreon Legal — AI právní asistent",
            },
        ],
    },
};

const FEATURES = [
    {
        icon: Search,
        title: "Vyhledávání v judikatuře",
        body: "Přes 295 000 rozhodnutí NSS, ÚS a obecných soudů. Ptejte se přirozenou češtinou, dostaňte přesnou citaci.",
    },
    {
        icon: FileText,
        title: "Česká legislativa",
        body: "Kompletní sbírka zákonů včetně zákoníku práce, občanského zákoníku, správního řádu a stavebního zákona.",
    },
    {
        icon: Scale,
        title: "Citace ke každé odpovědi",
        body: "Každé tvrzení je podloženo přesnou stránkou a paragrafem zdrojového dokumentu. Žádné halucinace.",
    },
    {
        icon: Gavel,
        title: "Správní a pracovní právo",
        body: "Specializace na oblasti nejčastěji vyhledávané českými advokáty a právníky ve firemní praxi.",
    },
    {
        icon: Shield,
        title: "Soukromí a bezpečnost",
        body: "Vaše dotazy nejsou sdíleny s třetími stranami. Data zpracováváme na zabezpečené EU infrastruktuře.",
    },
    {
        icon: BookOpen,
        title: "Dokumentové šablony",
        body: "9 českých právních šablon: žaloba, odvolání, smlouva o dílo, nájemní smlouva a další.",
    },
];

const USECASES = [
    {
        query: "Může zaměstnavatel jednostranně snížit mzdu bez souhlasu zaměstnance?",
        tag: "Zákoník práce",
    },
    {
        query: "Jaká je lhůta pro podání správní žaloby po doručení rozhodnutí?",
        tag: "Správní právo",
    },
    {
        query: "Jak NSS posuzuje nepřezkoumatelnost správního rozhodnutí?",
        tag: "Judikatura NSS",
    },
    {
        query: "Podmínky pro výpověď z nájmu bytu ze strany pronajímatele",
        tag: "Občanský zákoník",
    },
];

const PRICING = [
    {name: "Zdarma", price: "0 Kč", desc: "3 dotazy denně", cta: "Začít zdarma", href: "/login", highlight: false},
    {name: "Starter", price: "680 Kč/měs", desc: "30 dotazů denně", cta: "Vybrat plán", href: "/login", highlight: true},
    {name: "Pro", price: "4 190 Kč/měs", desc: "200 dotazů denně + nahrání dokumentů", cta: "Vybrat plán", href: "/login", highlight: false},
];

export default function CzechLandingPage() {
    const jsonLd = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        name: "Vitreon Legal",
        url: "https://vitreon.app",
        inLanguage: "cs",
        applicationCategory: "BusinessApplication",
        description:
            "AI asistent pro právní výzkum s citacemi z české judikatury a legislativy. Alternativa k Beck-online a ASPI.",
        offers: [
            {"@type": "Offer", name: "Zdarma", price: "0", priceCurrency: "CZK"},
            {"@type": "Offer", name: "Starter", price: "680", priceCurrency: "CZK"},
            {"@type": "Offer", name: "Pro", price: "4190", priceCurrency: "CZK"},
        ],
        provider: {
            "@type": "Organization",
            name: "Vitreon Legal",
            url: "https://vitreon.app",
            address: {
                "@type": "PostalAddress",
                addressLocality: "Praha",
                addressCountry: "CZ",
            },
        },
        featureList: [
            "Česká judikatura — přes 295 000 rozhodnutí",
            "Citace ke každé odpovědi",
            "Zákoník práce, občanský zákoník, správní řád",
            "Přirozený jazyk — ptejte se česky",
            "9 českých právních šablon",
        ],
    };

    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(jsonLd)}}
            />
            <StrictNav />

            <main>
                {/* Hero */}
                <section className="max-w-[880px] mx-auto px-4 sm:px-8 pt-20 pb-16">
                    <p
                        className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-5"
                        style={{color: "var(--strict-gold-text)"}}
                    >
                        Právní AI pro českou praxi
                    </p>
                    <h1
                        className="font-heading font-bold mb-6"
                        style={{
                            fontSize: "clamp(2rem, 4vw, 3rem)",
                            letterSpacing: "-0.03em",
                            lineHeight: 1.1,
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Česká judikatura a legislativa<br />
                        <span style={{
                            background: "linear-gradient(135deg, var(--strict-gold-gradient-start), var(--strict-gold-gradient-end))",
                            WebkitBackgroundClip: "text",
                            WebkitTextFillColor: "transparent",
                            backgroundClip: "text",
                        }}>
                            s přesnými citacemi
                        </span>
                    </h1>
                    <p
                        className="text-base mb-8 max-w-[600px]"
                        style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}
                    >
                        Pokládejte právní otázky v češtině. Vitreon Legal odpovídá z judikatury NSS,
                        ÚS a obecných soudů s odkazem na přesnou stránku a paragraf. Alternativa
                        k Beck-online a ASPI s AI od&nbsp;roku&nbsp;2026.
                    </p>
                    <div className="flex flex-wrap gap-3">
                        <Link
                            href="/login"
                            className="inline-flex items-center gap-2 px-5 py-3 text-sm font-semibold rounded-lg transition-all duration-200"
                            style={{
                                background: "linear-gradient(135deg, var(--strict-gold-gradient-start), var(--strict-gold-gradient-end))",
                                color: "var(--strict-bg-html)",
                            }}
                        >
                            Začít zdarma <ArrowRight size={14} />
                        </Link>
                        <Link
                            href="/benchmarks"
                            className="inline-flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-lg transition-all duration-200"
                            style={{
                                border: "1px solid var(--strict-border)",
                                color: "var(--strict-text-secondary)",
                            }}
                        >
                            Výsledky benchmarků
                        </Link>
                    </div>

                    {/* Trust bar */}
                    <div className="mt-10 flex flex-wrap gap-4 text-xs" style={{color: "var(--strict-text-dim)"}}>
                        <span>✓ 3 dotazy denně zdarma</span>
                        <span>✓ Bez platební karty</span>
                        <span>✓ +36 % nad SOTA (GaRAGe ACL&nbsp;2025)</span>
                        <span>✓ 4. místo ARLC&nbsp;2026 z 80 týmů</span>
                    </div>
                </section>

                {/* Example queries */}
                <section
                    className="max-w-[880px] mx-auto px-4 sm:px-8 py-14"
                    style={{borderTop: "1px solid var(--strict-border)"}}
                >
                    <p
                        className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-6"
                        style={{color: "var(--strict-gold-text)"}}
                    >
                        Příklady dotazů
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2">
                        {USECASES.map(uc => (
                            <Link
                                key={uc.query}
                                href="/login"
                                className="group p-4 rounded-lg transition-all duration-200"
                                style={{
                                    border: "1px solid var(--strict-border)",
                                    background: "var(--strict-card-bg)",
                                }}
                            >
                                <span
                                    className="text-[10px] uppercase tracking-wider mb-2 block"
                                    style={{color: "var(--strict-gold-text)"}}
                                >
                                    {uc.tag}
                                </span>
                                <p
                                    className="text-sm leading-relaxed"
                                    style={{color: "var(--strict-text-secondary)"}}
                                >
                                    &ldquo;{uc.query}&rdquo;
                                </p>
                            </Link>
                        ))}
                    </div>
                </section>

                {/* Features */}
                <section
                    className="max-w-[880px] mx-auto px-4 sm:px-8 py-14"
                    style={{borderTop: "1px solid var(--strict-border)"}}
                >
                    <p
                        className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-2"
                        style={{color: "var(--strict-gold-text)"}}
                    >
                        Funkce
                    </p>
                    <h2
                        className="font-heading font-bold mb-10"
                        style={{
                            fontSize: "clamp(1.4rem, 2.5vw, 1.9rem)",
                            letterSpacing: "-0.025em",
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Proč Vitreon Legal?
                    </h2>
                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                        {FEATURES.map(f => {
                            const Icon = f.icon;
                            return (
                                <div key={f.title} className="p-5 rounded-lg" style={{border: "1px solid var(--strict-border)", background: "var(--strict-card-bg)"}}>
                                    <Icon size={18} className="mb-3" style={{color: "var(--strict-gold-text)"}} />
                                    <h3
                                        className="font-semibold mb-2 text-sm"
                                        style={{color: "var(--strict-text-primary)"}}
                                    >
                                        {f.title}
                                    </h3>
                                    <p className="text-xs leading-relaxed" style={{color: "var(--strict-text-secondary)"}}>
                                        {f.body}
                                    </p>
                                </div>
                            );
                        })}
                    </div>
                </section>

                {/* Pricing */}
                <section
                    className="max-w-[880px] mx-auto px-4 sm:px-8 py-14"
                    style={{borderTop: "1px solid var(--strict-border)"}}
                >
                    <p
                        className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-2"
                        style={{color: "var(--strict-gold-text)"}}
                    >
                        Ceník
                    </p>
                    <h2
                        className="font-heading font-bold mb-10"
                        style={{
                            fontSize: "clamp(1.4rem, 2.5vw, 1.9rem)",
                            letterSpacing: "-0.025em",
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Transparentní ceny v korunách
                    </h2>
                    <div className="grid gap-4 sm:grid-cols-3">
                        {PRICING.map(p => (
                            <div
                                key={p.name}
                                className="p-5 rounded-lg"
                                style={{
                                    border: p.highlight
                                        ? "1px solid var(--strict-gold-border)"
                                        : "1px solid var(--strict-border)",
                                    background: p.highlight ? "var(--strict-gold-badge-bg)" : "var(--strict-card-bg)",
                                }}
                            >
                                <p className="text-xs uppercase tracking-wider mb-1" style={{color: "var(--strict-text-dim)"}}>{p.name}</p>
                                <p className="font-heading font-bold text-xl mb-1" style={{color: "var(--strict-text-primary)"}}>{p.price}</p>
                                <p className="text-xs mb-4" style={{color: "var(--strict-text-secondary)"}}>{p.desc}</p>
                                <Link
                                    href={p.href}
                                    className="inline-flex items-center gap-1.5 text-xs font-semibold"
                                    style={{color: "var(--strict-gold-text)"}}
                                >
                                    {p.cta} <ArrowRight size={12} />
                                </Link>
                            </div>
                        ))}
                    </div>
                </section>

                {/* CTA */}
                <section
                    className="max-w-[880px] mx-auto px-4 sm:px-8 py-14"
                    style={{borderTop: "1px solid var(--strict-border)"}}
                >
                    <h2
                        className="font-heading font-bold mb-4"
                        style={{
                            fontSize: "clamp(1.4rem, 2.5vw, 1.9rem)",
                            letterSpacing: "-0.025em",
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        Začněte dnes — zdarma
                    </h2>
                    <p className="text-sm mb-6" style={{color: "var(--strict-text-secondary)"}}>
                        Registrace trvá 30 sekund. Platební karta není potřeba.
                        Bezplatný plán zahrnuje 3 dotazy denně trvale.
                    </p>
                    <div className="flex flex-wrap gap-3">
                        <Link
                            href="/login"
                            className="inline-flex items-center gap-2 px-5 py-3 text-sm font-semibold rounded-lg"
                            style={{
                                background: "linear-gradient(135deg, var(--strict-gold-gradient-start), var(--strict-gold-gradient-end))",
                                color: "var(--strict-bg-html)",
                            }}
                        >
                            Začít zdarma <ArrowRight size={14} />
                        </Link>
                        <Link
                            href="/faq"
                            className="inline-flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-lg"
                            style={{
                                border: "1px solid var(--strict-border)",
                                color: "var(--strict-text-secondary)",
                            }}
                        >
                            Časté dotazy
                        </Link>
                    </div>
                </section>
            </main>

            <StrictFooter />
        </div>
    );
}
