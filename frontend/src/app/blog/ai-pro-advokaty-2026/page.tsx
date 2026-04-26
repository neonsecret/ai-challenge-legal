import Link from "next/link";
import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "AI pro advokáty 2026: Beck-online vs. Vitreon Legal — srovnání pro českou praxi — Vitreon Legal",
    description:
        "Podrobné srovnání Beck-online, ASPI a Vitreon Legal pro českou advokátní praxi. Jak AI šetří 3–5 hodin týdně při právním výzkumu, ceník v CZK, citace z judikatury NSS a ÚS.",
    keywords: [
        "Beck-online alternativa",
        "ASPI alternativa",
        "AI pro advokáty",
        "právní výzkum software",
        "právní databáze srovnání",
        "judikatura vyhledávání AI",
        "advokát AI nástroj",
        "česká judikatura vyhledávač",
        "AI právní asistent advokát",
    ],
    alternates: {
        canonical: "https://vitreon.app/blog/ai-pro-advokaty-2026",
        languages: {
            cs: "https://vitreon.app/blog/ai-pro-advokaty-2026",
        },
    },
    openGraph: {
        title: "AI pro advokáty 2026: Beck-online vs. Vitreon Legal — srovnání pro českou praxi",
        description:
            "Jak AI šetří 3–5 hodin týdně při právním výzkumu. Srovnání Beck-online, ASPI a Vitreon Legal — ceník, funkce, judikatura NSS a ÚS.",
        url: "https://vitreon.app/blog/ai-pro-advokaty-2026",
        siteName: "Vitreon Legal",
        locale: "cs_CZ",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "AI pro advokáty: Beck-online vs. Vitreon Legal",
            },
        ],
    },
};

const COMPARISON_DATA = [
    {
        feature: "Přirozený jazyk (dotaz česky)",
        beckonline: "Ne — klíčová slova",
        aspi: "Částečně",
        vitreon: "Ano — plné NLP",
    },
    {
        feature: "Citace ke každé odpovědi",
        beckonline: "Manuální",
        aspi: "Manuální",
        vitreon: "Automatické s odkazem na stránku",
    },
    {
        feature: "Judikatura NSS",
        beckonline: "Ano",
        aspi: "Ano",
        vitreon: "Ano — 295 000+ rozhodnutí",
    },
    {
        feature: "Dostupnost bez instalace",
        beckonline: "Web",
        aspi: "Klient",
        vitreon: "Web — vitreon.app",
    },
    {
        feature: "Základní cena",
        beckonline: "~3 500 Kč/měs",
        aspi: "~4 800 Kč/měs",
        vitreon: "Zdarma (3/den)",
    },
    {
        feature: "Právní šablony",
        beckonline: "Omezené",
        aspi: "Ano",
        vitreon: "9 českých šablon",
    },
    {
        feature: "Benchmark (GaRAGe)",
        beckonline: "Neměřeno",
        aspi: "Neměřeno",
        vitreon: "0.824 (+36 % nad SOTA)",
    },
];

export default function AIProAdvokatyPost() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "AI pro advokáty 2026: Beck-online vs. Vitreon Legal — srovnání pro českou praxi",
        description:
            "Podrobné srovnání Beck-online, ASPI a Vitreon Legal pro českou advokátní praxi. Jak AI šetří 3–5 hodin týdně při právním výzkumu, ceník v CZK, citace z judikatury NSS a ÚS.",
        datePublished: "2026-04-18",
        inLanguage: "cs",
        keywords: [
            "Beck-online alternativa",
            "ASPI alternativa",
            "AI pro advokáty",
            "právní výzkum software",
            "právní databáze srovnání",
            "judikatura vyhledávání AI",
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
        url: "https://vitreon.app/blog/ai-pro-advokaty-2026",
        mainEntityOfPage: "https://vitreon.app/blog/ai-pro-advokaty-2026",
    };

    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(articleJsonLd)}}
            />
            <StrictNav />

            <main className="max-w-[880px] mx-auto px-4 sm:px-8 pt-16 pb-20">
                <div className="mb-12">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-xs" style={{color: "var(--strict-text-dim)"}}>
                            18. dubna 2026
                        </span>
                        <span
                            className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded"
                            style={{
                                background: "var(--strict-gold-badge-bg)",
                                color: "var(--strict-gold-badge-text)",
                                border: "1px solid var(--strict-gold-badge-border)",
                            }}
                        >
                            Česky
                        </span>
                        <span
                            className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded"
                            style={{
                                background: "var(--strict-card-bg)",
                                color: "var(--strict-text-dim)",
                                border: "1px solid var(--strict-border)",
                            }}
                        >
                            Pro advokáty
                        </span>
                    </div>
                    <h1
                        className="font-heading font-bold mb-4"
                        style={{
                            fontSize: "clamp(1.75rem, 4vw, 2.5rem)",
                            letterSpacing: "-0.025em",
                            lineHeight: 1.2,
                            color: "var(--strict-text-primary)",
                        }}
                    >
                        AI pro advokáty 2026: Jak AI šetří 3–5 hodin týdně při právním výzkumu
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        Viacheslav Ivannikov, zakladatel Vitreon Legal &mdash; Praha
                    </p>
                </div>

                <article>
                    <Section title="Proč tradiční právní databáze nestačí">
                        <BodyText>
                            Beck-online a ASPI jsou dnes základem každé české advokátní kanceláře. Ale jejich
                            design vznikal v době, kdy neexistovaly jazykové modely. Výsledkem je, že advokát
                            musí formulovat přesná klíčová slova, procházet desítky výsledků a ručně ověřovat
                            relevanci každého rozhodnutí. Průměrný právní výzkum trvá 2–4 hodiny.
                        </BodyText>
                        <BodyText>
                            AI asistenti druhé generace jako Vitreon Legal mění tento postup: dostanete
                            přesnou odpověď s citací zdrojového dokumentu v průměru do 30 sekund od zadání
                            otázky v přirozeném jazyce.
                        </BodyText>
                    </Section>

                    <Section title="Srovnání: Beck-online vs. ASPI vs. Vitreon Legal">
                        <BodyText>
                            Níže porovnáváme tři nástroje z pohledu efektivity pro českou advokátní praxi.
                            Cílem není nahradit Beck-online nebo ASPI &mdash; ty mají jiný záběr a jsou
                            dlouhodobě prověřeny. Cílem je ukázat, kde AI přidává hodnotu jako doplněk.
                        </BodyText>

                        {/* Comparison table */}
                        <div className="mt-6 overflow-x-auto">
                            <table style={{width: "100%", borderCollapse: "collapse", fontSize: "13px"}}>
                                <thead>
                                    <tr style={{borderBottom: "1px solid var(--strict-border)"}}>
                                        <th className="text-left py-2 pr-4" style={{color: "var(--strict-text-dim)", fontWeight: 500}}>Funkce</th>
                                        <th className="text-left py-2 pr-4" style={{color: "var(--strict-text-dim)", fontWeight: 500}}>Beck-online</th>
                                        <th className="text-left py-2 pr-4" style={{color: "var(--strict-text-dim)", fontWeight: 500}}>ASPI</th>
                                        <th className="text-left py-2" style={{color: "var(--strict-gold-text)", fontWeight: 600}}>Vitreon Legal</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {COMPARISON_DATA.map((row, i) => (
                                        <tr
                                            key={i}
                                            style={{borderBottom: "1px solid var(--strict-border)", background: i % 2 === 0 ? "transparent" : "var(--strict-card-bg)"}}
                                        >
                                            <td className="py-2.5 pr-4" style={{color: "var(--strict-text-secondary)"}}>{row.feature}</td>
                                            <td className="py-2.5 pr-4" style={{color: "var(--strict-text-dim)"}}>{row.beckonline}</td>
                                            <td className="py-2.5 pr-4" style={{color: "var(--strict-text-dim)"}}>{row.aspi}</td>
                                            <td className="py-2.5 font-medium" style={{color: "var(--strict-gold-text)"}}>{row.vitreon}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </Section>

                    <Section title="Kde AI přidává největší hodnotu pro advokáty">
                        <BodyText>
                            Na základě zpětné vazby od českých právníků jsou tři situace, kde AI nejvíce
                            šetří čas:
                        </BodyText>
                        <ul className="mt-4 space-y-3">
                            {[
                                {
                                    heading: "1. Rychlý přehled judikatury k novému problému",
                                    body: "Klient přijde s otázkou z oblasti, ve které advokát nepraktikuje denně. AI poskytne přehled relevantní judikatury NSS nebo NS za 30 sekund, místo 2 hodin rešerše.",
                                },
                                {
                                    heading: "2. Ověření argumentace protějšku",
                                    body: "Protistrana cituje rozhodnutí NSS. AI okamžitě načte kontext citovaného rozhodnutí, identifikuje odlišné okolnosti případu a navrhne protiargumenty.",
                                },
                                {
                                    heading: "3. Příprava smluv s legislativní oporou",
                                    body: "Vitreon Legal propojuje každé ustanovení smlouvy s příslušným paragrafem zákoníku nebo judikátem. Klient vidí právní základ každého bodu.",
                                },
                            ].map(item => (
                                <li key={item.heading} className="p-4 rounded-lg" style={{border: "1px solid var(--strict-border)", background: "var(--strict-card-bg)"}}>
                                    <p className="font-semibold text-sm mb-1" style={{color: "var(--strict-text-primary)"}}>{item.heading}</p>
                                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>{item.body}</p>
                                </li>
                            ))}
                        </ul>
                    </Section>

                    <Section title="Benchmarky: proč výsledky záleží">
                        <BodyText>
                            Výběr AI nástroje pro právní práci nemůže stát jen na marketingových slibech.
                            Vitreon Legal publikuje a udržuje nezávislé benchmarkové výsledky:
                        </BodyText>
                        <div className="mt-4 grid gap-3 sm:grid-cols-3">
                            {[
                                {label: "GaRAGe RAF (ACL 2025)", value: "0.824", badge: "+36 % nad SOTA"},
                                {label: "ContractNLI F1", value: "0.630", badge: "+76 % nad SOTA"},
                                {label: "LEXam Open EN (ICLR 2026)", value: "0.691", badge: "+21 % nad SOTA"},
                            ].map(b => (
                                <div key={b.label} className="p-4 rounded-lg text-center" style={{border: "1px solid var(--strict-border)", background: "var(--strict-card-bg)"}}>
                                    <p className="font-heading font-bold text-2xl mb-1" style={{color: "var(--strict-gold-text)"}}>{b.value}</p>
                                    <p className="text-xs mb-1" style={{color: "var(--strict-text-dim)"}}>{b.label}</p>
                                    <span
                                        className="text-[10px] px-2 py-0.5 rounded"
                                        style={{
                                            background: "var(--strict-gold-badge-bg)",
                                            color: "var(--strict-gold-badge-text)",
                                            border: "1px solid var(--strict-gold-badge-border)",
                                        }}
                                    >
                                        {b.badge}
                                    </span>
                                </div>
                            ))}
                        </div>
                        <BodyText>
                            Podrobný popis metodologie a srovnání s ostatními systémy najdete na{" "}
                            <Link href="/benchmarks" style={{color: "var(--strict-gold-text)"}} className="hover:underline">
                                stránce benchmarků
                            </Link>
                            .
                        </BodyText>
                    </Section>

                    <Section title="Jak začít — 3 kroky">
                        <ol className="mt-2 space-y-4">
                            {[
                                "Registrace na vitreon.app/cs — Google účet nebo email, bez platební karty.",
                                "Bezplatný plán: 3 dotazy denně. Pro intenzivnější využití Starter za 680 Kč/měs.",
                                "Prvních 5 minut: zadejte konkrétní právní otázku a ověřte citaci v původním rozhodnutí.",
                            ].map((step, i) => (
                                <li key={i} className="flex gap-4">
                                    <span
                                        className="text-sm font-bold shrink-0"
                                        style={{color: "var(--strict-gold-text)", minWidth: "1.5rem"}}
                                    >
                                        {i + 1}.
                                    </span>
                                    <p className="text-sm" style={{color: "var(--strict-text-body)", lineHeight: 1.7}}>{step}</p>
                                </li>
                            ))}
                        </ol>
                    </Section>

                    {/* CTA */}
                    <div
                        className="mt-12 p-6 rounded-lg"
                        style={{border: "1px solid var(--strict-gold-border)", background: "var(--strict-gold-badge-bg)"}}
                    >
                        <h3
                            className="font-heading font-bold mb-3"
                            style={{fontSize: "1.1rem", color: "var(--strict-text-primary)"}}
                        >
                            Vyzkoušejte Vitreon Legal pro svou advokátní praxi
                        </h3>
                        <p className="text-sm mb-4" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                            Bezplatný plán zahrnuje 3 dotazy denně. Pokud vás Vitreon přesvědčí, Starter plán
                            za 680 Kč/měs vrátí investici po prvním ušetřeném výzkumném billi.
                        </p>
                        <Link
                            href="/cs"
                            className="inline-flex items-center gap-2 px-4 py-2 min-h-[44px] text-sm font-semibold rounded-lg"
                            style={{
                                background: "linear-gradient(135deg, var(--strict-gold-gradient-start), var(--strict-gold-gradient-end))",
                                color: "var(--strict-bg-html)",
                            }}
                        >
                            Začít zdarma — vitreon.app/cs
                        </Link>
                    </div>
                </article>
            </main>

            <StrictFooter />
        </div>
    );
}

function Section({title, children}: {title: string; children: React.ReactNode}) {
    return (
        <section style={{borderTop: "1px solid var(--strict-border)", paddingTop: "2rem", marginTop: "2rem"}}>
            <h2
                className="font-heading font-bold mb-4"
                style={{
                    fontSize: "1.2rem",
                    color: "var(--strict-text-primary)",
                    letterSpacing: "-0.01em",
                }}
            >
                {title}
            </h2>
            <div className="space-y-4">{children}</div>
        </section>
    );
}

function BodyText({children}: {children: React.ReactNode}) {
    return (
        <p style={{fontSize: "16px", lineHeight: 1.8, color: "var(--strict-text-body)"}}>
            {children}
        </p>
    );
}
