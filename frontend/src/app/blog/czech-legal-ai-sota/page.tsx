import Link from "next/link";
import type {Metadata} from "next";
import { StrictNav } from "@/components/landing/strict/strict-nav";
import { StrictFooter } from "@/components/landing/strict/strict-footer";

export const metadata: Metadata = {
    title: "Jak Vitreon dosahuje +36% nad SOTA v českém právním AI — Vitreon Legal Blog",
    description:
        "Technický rozbor benchmarku GaRAGe (ACL 2025): Vitreon Legal dosahuje 0.824 RAF, +36% nad publikovaný SOTA 0.607. Jak funguje retrieval pipeline pro judikaturu a právní výzkum v ČR.",
    openGraph: {
        title: "Jak Vitreon dosahuje +36% nad SOTA v českém právním AI",
        description:
            "GaRAGe benchmark 0.824 RAF, +36% nad SOTA. Technický rozbor retrieval pipeline pro českou judikaturu.",
        url: "https://vitreon.app/blog/czech-legal-ai-sota",
        siteName: "Vitreon Legal",
        type: "article",
        locale: "cs_CZ",
    },
};

export default function CzechLegalAIPost() {
    return (
        <div className="min-h-screen" style={{background: "var(--strict-bg-html)"}}>
            <StrictNav />

            <main className="max-w-[880px] mx-auto px-4 sm:px-8 pt-16 pb-20">
                {/* Header */}
                <div className="mb-12">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-xs" style={{color: "var(--strict-text-dim)"}}>
                            12. dubna 2026
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
                        Jak Vitreon dosahuje +36% nad SOTA v českém právním AI
                    </h1>
                    <p className="text-sm" style={{color: "var(--strict-text-secondary)", lineHeight: 1.7}}>
                        Viacheslav Ivannikov, zakladatel Vitreon Legal
                    </p>
                </div>

                {/* Article Body */}
                <article className="space-y-6">
                    <BodyText>
                        Když právník hledá relevantní judikaturu nebo potřebuje ověřit, jak soud rozhodl
                        v konkrétní právní otázce, má v České republice dvě hlavní možnosti: Beck-online
                        a ASPI. Obě databáze fungují na principu klíčových slov &mdash; zadáte hledaný
                        výraz a procházíte desítky až stovky výsledků. Vitreon Legal tento přístup zásadně
                        mění. Místo seznamu dokumentů dostanete přesnou odpověď s citací na konkrétní
                        stránku a paragraf.
                    </BodyText>

                    <BodyText>
                        Ale jak víme, že naše odpovědi jsou skutečně přesné? Nestačí to jen tvrdit &mdash;
                        je potřeba to měřit. Proto jsme náš systém otestovali na nezávislých, veřejně
                        dostupných benchmarcích.
                    </BodyText>

                    <Heading>Co je SOTA a proč na něm záleží</Heading>

                    <BodyText>
                        <strong style={{color: "var(--strict-text-primary)"}}>SOTA</strong> (State of the Art)
                        znamená &ldquo;nejlepší publikovaný výsledek&rdquo; na daném benchmarku. Když řekneme,
                        že Vitreon dosahuje +36% nad SOTA, znamená to, že náš systém překonává dosud nejlepší
                        publikovaný výsledek o 36 procentních bodů. To není marginální zlepšení &mdash; je to
                        kvalitativní skok.
                    </BodyText>

                    <BodyText>
                        V kontextu právního výzkumu to znamená: odpovědi jsou přesnější, relevantní dokumenty
                        se nacházejí spolehlivěji a citace jsou ověřitelnější.
                    </BodyText>

                    <Heading>Benchmark GaRAGe (ACL 2025)</Heading>

                    <BodyText>
                        GaRAGe (General-purpose RAG evaluation) je benchmark publikovaný na konferenci ACL 2025
                        společností Amazon Science. Hodnotí celý pipeline systémů pro Retrieval-Augmented
                        Generation &mdash; tedy schopnost najít relevantní pasáže v dokumentech a na jejich
                        základě vygenerovat správnou, podloženou odpověď.
                    </BodyText>

                    <BodyText>
                        Hlavní metrikou je <strong style={{color: "var(--strict-text-primary)"}}>RAF (Retrieval
                        Accuracy Factor)</strong>, který kombinuje přesnost vyhledávání s věrností odpovědi.
                    </BodyText>

                    <div
                        className="rounded-xl overflow-hidden my-6"
                        style={{
                            background: "var(--strict-glass-bg)",
                            border: "1px solid var(--strict-glass-border)",
                            backdropFilter: "var(--strict-glass-blur)",
                            borderRadius: "14px",
                        }}
                    >
                        <table className="w-full text-sm">
                            <thead>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Systém</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>RAF skóre</th>
                                <th className="text-left px-5 py-3 font-semibold" style={{color: "var(--strict-text-primary)"}}>Rozdíl</th>
                            </tr>
                            </thead>
                            <tbody>
                            <tr style={{borderBottom: "1px solid var(--strict-glass-border)"}}>
                                <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>Vitreon Legal</td>
                                <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>0.824</td>
                                <td className="px-5 py-3 font-semibold" style={{color: "var(--strict-gold-text)"}}>+36% nad SOTA</td>
                            </tr>
                            <tr>
                                <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>Publikovaný SOTA (ACL 2025)</td>
                                <td className="px-5 py-3" style={{color: "var(--strict-text-body)"}}>0.607</td>
                                <td className="px-5 py-3" style={{color: "var(--strict-text-secondary)"}}>baseline</td>
                            </tr>
                            </tbody>
                        </table>
                    </div>

                    <Heading>Jak funguje Vitreon retrieval pipeline</Heading>

                    <BodyText>
                        Klíčem k těmto výsledkům je vícestupňový vyhledávací pipeline, který kombinuje několik
                        přístupů. Každý stupeň řeší jiný aspekt problému vyhledávání v právních dokumentech.
                    </BodyText>

                    <SubHeading>Stupeň 1: Hybridní vyhledávání</SubHeading>
                    <BodyText>
                        Každý dotaz prochází současně dvěma vyhledávacími systémy. <strong style={{color: "var(--strict-text-primary)"}}>BM25</strong> (lexikální
                        vyhledávání) nachází přesné shody &mdash; čísla paragrafů, specifické právní termíny,
                        spisové značky. <strong style={{color: "var(--strict-text-primary)"}}>Vektorové vyhledávání</strong> (sémantické)
                        nachází obsahově podobné pasáže, i když jsou formulovány jinak než dotaz.
                    </BodyText>
                    <BodyText>
                        Výsledky obou systémů se spojí pomocí <strong style={{color: "var(--strict-text-primary)"}}>Reciprocal
                        Rank Fusion (RRF)</strong> &mdash; algoritmu, který kombinuje rankingy z různých zdrojů
                        a upřednostňuje dokumenty, které se umístily vysoko v obou systémech.
                    </BodyText>

                    <SubHeading>Stupeň 2: Asymetrické embeddingové modely</SubHeading>
                    <BodyText>
                        Pro vektorové vyhledávání používáme model <strong style={{color: "var(--strict-text-primary)"}}>Qwen3-Embedding-8B</strong> s
                        asymetrickým kódováním. To znamená, že dotazy a dokumenty se kódují odlišně &mdash;
                        dotaz je optimalizován pro &ldquo;hledání odpovědi&rdquo;, zatímco dokument je
                        optimalizován pro &ldquo;poskytnutí odpovědi&rdquo;. Tento přístup je zásadní pro
                        právní texty, kde se otázka formuluje zcela jinak než odpověď v zákoně.
                    </BodyText>

                    <SubHeading>Stupeň 3: Cross-encoder reranking</SubHeading>
                    <BodyText>
                        Kandidátské pasáže z hybridního vyhledávání projdou cross-encoder modelem, který
                        společně zakóduje dvojici (dotaz, pasáž) a vyhodnotí relevanci. Tento stupeň je
                        výpočetně náročný, ale přináší rozhodující zpřesnění &mdash; v právním výzkumu může
                        rozdíl mezi &ldquo;podobnou&rdquo; a &ldquo;správnou&rdquo; pasáží spočívat v jediné
                        podmínce nebo kvalifikaci.
                    </BodyText>

                    <SubHeading>Stupeň 4: Podložená generace odpovědí</SubHeading>
                    <BodyText>
                        Nejlépe hodnocené pasáže se předají jazykovému modelu se striktní instrukcí:
                        generovat odpověď výhradně z dodaného kontextu a každé tvrzení opatřit citací
                        na zdrojový dokument, stránku a paragraf. Pokud odpověď v dokumentech není,
                        systém to explicitně uvede &mdash; místo toho, aby si odpověď vymyslel.
                    </BodyText>

                    <Heading>Proč je to důležité pro český právní výzkum</Heading>

                    <BodyText>
                        Česká republika má jednu z nejrozsáhlejších sbírek judikatury v Evropě. Vitreon
                        Legal indexuje <strong style={{color: "var(--strict-text-primary)"}}>více než 295 000 soudních
                        rozhodnutí</strong> a <strong style={{color: "var(--strict-text-primary)"}}>6 800+ zákonů
                        a vyhlášek</strong>. Tradiční vyhledávání v takto rozsáhlém korpusu je časově náročné
                        a závisí na tom, zda uživatel zvolí správná klíčová slova.
                    </BodyText>

                    <BodyText>
                        S Vitreon pipeline může právník položit otázku přirozeným jazykem &mdash; česky
                        nebo anglicky &mdash; a získat podloženou odpověď s přesnými citacemi. Nemusí
                        procházet stovky výsledků a hádat, které klíčové slovo použít. Systém rozumí
                        právní terminologii nativně: &ldquo;judikatura&rdquo;, &ldquo;občanský zákoník&rdquo;,
                        &ldquo;soudní rozhodnutí&rdquo;, &ldquo;dovolání&rdquo;.
                    </BodyText>

                    <Heading>Benchmark LEXam Open EN (ICLR 2026)</Heading>

                    <BodyText>
                        Kromě GaRAGe jsme testovali i na benchmarku LEXam, publikovaném na konferenci
                        ICLR 2026. LEXam hodnotí schopnost AI systémů odpovídat na právní otázky z
                        profesních zkoušek. Na variantě Open EN (anglické otevřené otázky) Vitreon
                        dosahuje <strong style={{color: "var(--strict-gold-text)"}}>0.691</strong>, což je{" "}
                        <strong style={{color: "var(--strict-gold-text)"}}>+21% nad baseline Claude 3.7 Sonnet (0.572)</strong>.
                    </BodyText>

                    <BodyText>
                        Tento výsledek ukazuje, že retrieval-augmented přístup (vyhledávání + generace)
                        výrazně překonává čistý jazykový model i na úrovni profesních právních zkoušek.
                    </BodyText>

                    <Heading>ARLC 2026: 4. místo z 80 týmů</Heading>

                    <BodyText>
                        V únoru 2026 jsme se pod týmovým jménem &ldquo;Neon Team&rdquo; zúčastnili
                        mezinárodní soutěže Agentic RAG Legal Challenge (ARLC 2026) v rámci Dubai AI Week.
                        Soutěžilo 80 týmů z celého světa o prize pool $32 000. Na warmup kole jsme
                        dosáhli <strong style={{color: "var(--strict-gold-text)"}}>skóre 0.958 (1. místo)</strong>,
                        ve finále <strong style={{color: "var(--strict-gold-text)"}}>0.719 (4. místo)</strong>.
                    </BodyText>

                    <BodyText>
                        Stejný retrieval pipeline, který dosáhl těchto soutěžních výsledků, nyní
                        pohání produkční platformu Vitreon Legal. Podrobný popis soutěže najdete
                        v článku{" "}
                        <Link href="/blog/arlc-2026-results" style={{color: "var(--strict-gold-text)"}} className="hover:underline">
                            How Vitreon Placed 4th in ARLC 2026
                        </Link>{" "}
                        (anglicky).
                    </BodyText>

                    <Heading>100% pokrytí citací</Heading>

                    <BodyText>
                        Každá odpověď vygenerovaná Vitreon Legal obsahuje citace na přesnou stránku,
                        paragraf a zdrojový dokument. To není statistický průměr &mdash; je to
                        architektonická záruka systému. Jazykový model generuje odpovědi výhradně
                        z nalezených pasáží a každé tvrzení musí být podložené.
                    </BodyText>

                    <BodyText>
                        Pro právníka to znamená: každou citaci si můžete okamžitě ověřit v původním
                        dokumentu. Žádné halucinace. Žádná nepodložená tvrzení.
                    </BodyText>

                    <Heading>Jak začít</Heading>

                    <BodyText>
                        Vitreon Legal je dostupný na{" "}
                        <Link href="/" style={{color: "var(--strict-gold-text)"}} className="hover:underline">
                            vitreon.app
                        </Link>
                        . Bezplatný plán zahrnuje 3 dotazy denně bez nutnosti platební karty.
                        Stačí se registrovat pomocí Google účtu nebo emailu a začít vyhledávat
                        v české judikatuře a legislativě.
                    </BodyText>

                    <BodyText>
                        Kompletní přehled benchmarkových výsledků najdete na stránce{" "}
                        <Link href="/benchmarks" style={{color: "var(--strict-gold-text)"}} className="hover:underline">
                            Benchmarks
                        </Link>
                        .
                    </BodyText>
                </article>
            </main>

            <StrictFooter />
        </div>
    );
}

/* -- Layout primitives -- */

function Heading({children}: { children: React.ReactNode }) {
    return (
        <h2
            className="font-heading font-bold mt-10 mb-4"
            style={{
                fontSize: "1.25rem",
                color: "var(--strict-text-primary)",
                letterSpacing: "-0.01em",
            }}
        >
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
            style={{fontSize: "16px", lineHeight: 1.8, color: "var(--strict-text-body)"}}
        >
            {children}
        </p>
    );
}
