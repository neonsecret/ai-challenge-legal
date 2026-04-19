import Link from "next/link";
import type {Metadata} from "next";
import {StrictNav} from "@/components/landing/strict/strict-nav";
import {StrictFooter} from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Zákoník práce 2026: AI odpovídá na 10 nejčastějších pracovněprávních otázek — Vitreon Legal",
    description:
        "Výpověď, mzda, dovolená, práce z domova — AI právní asistent Vitreon odpovídá na nejčastější otázky zákoníku práce s přesnou citací z judikatury. Zdarma pro zaměstnance i zaměstnavatele.",
    keywords: [
        "zákoník práce 2026",
        "zákoník práce AI",
        "pracovní právo otázky",
        "výpověď ze zaměstnání",
        "mzda zákoník práce",
        "AI právní asistent pracovní právo",
        "judikatura zákoník práce",
    ],
    alternates: {
        canonical: "https://vitreon.app/blog/zakonik-prace-2026-ai",
        languages: {
            cs: "https://vitreon.app/blog/zakonik-prace-2026-ai",
        },
    },
    openGraph: {
        title: "Zákoník práce 2026: AI odpovídá na 10 nejčastějších pracovněprávních otázek",
        description:
            "AI asistent Vitreon Legal odpovídá na pracovněprávní otázky s citacemi z judikatury. Výpověď, mzda, dovolená, home office — vše podloženo zákoníkem práce.",
        url: "https://vitreon.app/blog/zakonik-prace-2026-ai",
        siteName: "Vitreon Legal",
        locale: "cs_CZ",
        type: "article",
        images: [
            {
                url: "/opengraph-image",
                width: 1200,
                height: 630,
                alt: "Zákoník práce 2026 a AI — Vitreon Legal",
            },
        ],
    },
};

const QA_ITEMS = [
    {
        q: "Může zaměstnavatel jednostranně snížit mzdu?",
        a: "Zákoník práce (§ 113) stanoví, že mzda musí být sjednána nebo stanovena před zahájením výkonu práce. Jednostranné snížení mzdy zaměstnavatelem je nepřípustné bez souhlasu zaměstnance. NSS ve svých rozhodnutích opakovaně potvrdil, že změna mzdových podmínek vyžaduje souhlas obou stran pracovní smlouvy nebo změnu vnitřního mzdového předpisu, pokud mzda není sjednána v individuální smlouvě.",
        tag: "§ 113 ZP",
    },
    {
        q: "Jak dlouhá je výpovědní doba při výpovědi dané zaměstnavatelem?",
        a: "Základní výpovědní doba je 2 měsíce (§ 51 ZP). Pokud zaměstnanec pracoval u zaměstnavatele alespoň 2 roky, výpovědní doba se prodlužuje na 3 měsíce, pokud to bylo v pracovní smlouvě nebo kolektivní smlouvě sjednáno. Výpovědní doba začíná prvním dnem kalendářního měsíce následujícího po doručení výpovědi.",
        tag: "§ 51–52 ZP",
    },
    {
        q: "Kolik dnů dovolené má zaměstnanec nárok?",
        a: "Od 1. 1. 2021 se dovolená vypočítává hodinově. Základní výměra dovolené je 4 týdny (20 dní při 5denním pracovním týdnu). Zaměstnanci státní správy, školství a zdravotnictví mají nárok na 5 týdnů, vedoucí zaměstnanci na 6 týdnů (§ 213 ZP). Zaměstnavatel může kolektivní smlouvou nebo pracovní smlouvou dovolenou prodloužit.",
        tag: "§ 213 ZP",
    },
    {
        q: "Za jakých podmínek může zaměstnanec pracovat z domova?",
        a: "Home office (práce na dálku) musí být sjednána písemně v pracovní smlouvě nebo dodatku k ní. Zaměstnavatel je povinnen hradit zaměstnanci náklady vzniklé při práci na dálku (§ 317 ZP). Od novely z roku 2023 platí, že zaměstnanec má právo žádat o home office a zaměstnavatel musí odmítnutí písemně odůvodnit, pokud na žádost nepřistoupí.",
        tag: "§ 317 ZP",
    },
    {
        q: "Má zaměstnanec nárok na odstupné při výpovědi ze strany zaměstnavatele?",
        a: "Odstupné náleží zaměstnanci při výpovědi z organizačních důvodů (§ 52 písm. a–c ZP) nebo dohodou z týchž důvodů. Výše odstupného závisí na délce pracovního poměru: méně než 1 rok — 1 průměrný měsíční výdělek, 1–2 roky — 2 měsíční výdělky, více než 2 roky — 3 měsíční výdělky (§ 67 ZP). Odvětví s kolektivní smlouvou mohou stanovit vyšší odstupné.",
        tag: "§ 67–68 ZP",
    },
    {
        q: "Kdy je výpověď daná zaměstnanci neplatná?",
        a: "Výpověď je neplatná, pokud zaměstnavatel nedodržel zákonné důvody výpovědi (§ 52 ZP), nevyžádal si stanovisko odborové organizace (§ 61 ZP), nebo ji dal v době ochranné lhůty (dočasná pracovní neschopnost, těhotenství, čerpání mateřské dovolené — § 53 ZP). Zaměstnanec může neplatnost výpovědi napadnout u soudu do 2 měsíců od jejího doručení.",
        tag: "§ 53–54 ZP",
    },
    {
        q: "Jaký je maximální rozsah přesčasové práce?",
        a: "Přesčasová práce nesmí přesáhnout 8 hodin týdně a 150 hodin ročně nařízených zaměstnavatelem. Celkový objem přesčasů (včetně dohodnutých) nesmí překročit průměrně 8 hodin týdně za 26 týdnů (nebo 52 týdnů, je-li to dohodnuto v kolektivní smlouvě) — § 93 ZP. Za přesčas náleží zaměstnanci příplatek nejméně 25 % průměrného výdělku.",
        tag: "§ 93–94 ZP",
    },
    {
        q: "Může zaměstnavatel kontrolovat emailovou komunikaci zaměstnance?",
        a: "Zaměstnavatel nesmí bez závažného důvodu narušovat soukromí zaměstnance (§ 316 ZP). Monitorování pracovní emailové komunikace je přípustné pouze pokud byl zaměstnanec předem a prokazatelně informován o rozsahu a způsobu kontroly. Osobní emailová komunikace je chráněna ústavně zaručeným právem na soukromí a monitorování bez souhlasu je protiprávní.",
        tag: "§ 316 ZP",
    },
    {
        q: "Jak se postupuje při pracovním úrazu?",
        a: "Zaměstnavatel je povinen sepsat záznam o pracovním úrazu a odeslat jej příslušné zdravotní pojišťovně a orgánu inspekce práce (§ 105 ZP). Zaměstnanci náleží náhrada za ztrátu na výdělku, bolestné, náhrada za ztížení společenského uplatnění a věcná škoda. Zaměstnavatel se odpovědnosti zprostí pouze při prokázání, že zaměstnanec porušil bezpečnostní předpisy vlastním zaviněním.",
        tag: "§ 105, § 269 ZP",
    },
    {
        q: "Může zaměstnanec odmítnout přesun na jiné pracovní místo?",
        a: "Zákoník práce rozlišuje mezi přeložením (§ 43 ZP), které vyžaduje souhlas zaměstnance, a pracovní cestou (§ 42 ZP), kde souhlas není potřeba, pokud to bylo sjednáno v pracovní smlouvě. Přeložení do jiného místa výkonu práce bez souhlasu zaměstnance je neplatné. Výkon práce na jiném pracovišti v rámci sjednaného místa výkonu práce souhlas nevyžaduje.",
        tag: "§ 42–43 ZP",
    },
];

export default function ZakonikPrace2026Post() {
    const articleJsonLd = {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "Zákoník práce 2026: AI odpovídá na 10 nejčastějších pracovněprávních otázek",
        description: "AI asistent odpovídá na pracovněprávní otázky s citacemi ze zákoníku práce a judikatury.",
        datePublished: "2026-04-18",
        inLanguage: "cs",
        author: {
            "@type": "Person",
            name: "Viacheslav Ivannikov",
        },
        publisher: {
            "@type": "Organization",
            name: "Vitreon Legal",
            url: "https://vitreon.app",
        },
        url: "https://vitreon.app/blog/zakonik-prace-2026-ai",
        mainEntityOfPage: "https://vitreon.app/blog/zakonik-prace-2026-ai",
    };

    const faqJsonLd = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: QA_ITEMS.map(item => ({
            "@type": "Question",
            name: item.q,
            acceptedAnswer: {
                "@type": "Answer",
                text: item.a,
            },
        })),
    };

    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(articleJsonLd)}}
            />
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{__html: JSON.stringify(faqJsonLd)}}
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
                            Pracovní právo
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
                        Zákoník práce 2026: AI odpovídá na 10 nejčastějších pracovněprávních otázek
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        Viacheslav Ivannikov, zakladatel Vitreon Legal &mdash; Praha
                    </p>
                </div>

                <article className="space-y-6">
                    <Intro />

                    {QA_ITEMS.map((item, i) => (
                        <QABlock key={i} number={i + 1} question={item.q} answer={item.a} tag={item.tag} />
                    ))}

                    <Outro />
                </article>
            </main>

            <StrictFooter />
        </div>
    );
}

function Intro() {
    return (
        <div className="p-5 rounded-lg mb-8" style={{border: "1px solid var(--strict-border)", background: "var(--strict-card-bg)"}}>
            <p style={{fontSize: "16px", lineHeight: 1.8, color: "var(--strict-text-body)"}}>
                Zákoník práce (zákon č. 262/2006 Sb.) je jedním z nejčastěji vyhledávaných právních předpisů
                v České republice. Zaměstnanci i zaměstnavatelé se denně potýkají s otázkami výpovědí, mezd,
                přesčasů nebo home office. Níže shrnujeme 10 nejčastějších otázek, na které Vitreon Legal
                odpovídá s přesnou citací ze zákoníku práce a judikatury Nejvyššího soudu a NSS.
            </p>
            <p className="mt-4" style={{fontSize: "14px", lineHeight: 1.7, color: "var(--strict-text-secondary)"}}>
                <strong style={{color: "var(--strict-gold-text)"}}>Upozornění:</strong> Tento článek
                slouží jako obecný přehled a nenáhrazuje právní poradenství. Pro konkrétní právní situaci
                doporučujeme konzultaci s advokátem nebo{" "}
                <Link href="/cs" style={{color: "var(--strict-gold-text)"}} className="hover:underline">
                    využití Vitreon Legal pro podrobné právní výzkum s citacemi
                </Link>
                .
            </p>
        </div>
    );
}

function QABlock({number, question, answer, tag}: {number: number; question: string; answer: string; tag: string}) {
    return (
        <div style={{borderTop: "1px solid var(--strict-border)", paddingTop: "1.5rem"}}>
            <div className="flex items-start gap-4">
                <span
                    className="text-xs font-mono font-bold shrink-0 mt-1"
                    style={{color: "var(--strict-gold-text)", minWidth: "1.5rem"}}
                >
                    {String(number).padStart(2, "0")}
                </span>
                <div>
                    <h2
                        className="font-semibold mb-3"
                        style={{fontSize: "1rem", color: "var(--strict-text-primary)", lineHeight: 1.4}}
                    >
                        {question}
                    </h2>
                    <p style={{fontSize: "15px", lineHeight: 1.8, color: "var(--strict-text-body)"}}>{answer}</p>
                    <span
                        className="inline-block mt-3 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded"
                        style={{
                            background: "var(--strict-gold-badge-bg)",
                            color: "var(--strict-gold-badge-text)",
                            border: "1px solid var(--strict-gold-badge-border)",
                        }}
                    >
                        {tag}
                    </span>
                </div>
            </div>
        </div>
    );
}

function Outro() {
    return (
        <div
            className="mt-12 p-6 rounded-lg"
            style={{border: "1px solid var(--strict-gold-border)", background: "var(--strict-gold-badge-bg)"}}
        >
            <h3
                className="font-heading font-bold mb-3"
                style={{fontSize: "1.1rem", color: "var(--strict-text-primary)"}}
            >
                Vyzkoušejte Vitreon Legal pro pracovněprávní výzkum
            </h3>
            <p className="text-sm mb-4" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                Místo hledání paragrafů ručně se zeptejte Vitreon Legal přímo. Systém prohledá judikaturu
                Nejvyššího soudu, NSS a obecných soudů a vrátí přesnou citaci s odkazem na zdrojový dokument.
                Bezplatný plán zahrnuje 3 dotazy denně bez platební karty.
            </p>
            <Link
                href="/cs"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg"
                style={{
                    background: "linear-gradient(135deg, var(--strict-gold-gradient-start), var(--strict-gold-gradient-end))",
                    color: "var(--strict-bg-html)",
                }}
            >
                Začít zdarma na vitreon.app/cs
            </Link>
        </div>
    );
}
