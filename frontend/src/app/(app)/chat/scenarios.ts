import type {DemoScenario} from "@/components/landing/demo-panel"

export const DIFC_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "DIFC",
        question: "What is the limitation period under DIFC Law No. 5 of 2005?",
        answer: "",
        pdfTitle: "DIFC Limitation Law No. 5 of 2005",
        pdfArticleHeader: "Article 4 — General Limitation Period",
        pdfClauses: [
            {
                id: "4(1)",
                text: "An action founded on contract shall not be brought after the end of six years beginning with the date on which the cause of action accrued."
            },
            {
                id: "4(2)",
                text: "An action in tort shall not be brought after three years beginning with the date on which the claimant first had knowledge of all relevant facts."
            },
            {
                id: "4(3)",
                text: "Knowledge includes facts which a claimant might reasonably be expected to acquire from observable facts or from expert advice."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "DIFC Law No. 5 of 2005 · Art. 4 · p.12",
        pageBadge: "Page 12",
    },
    {
        jurisdiction: "DIFC",
        question: "What are the grounds for termination under DIFC Employment Law?",
        answer: "",
        pdfTitle: "DIFC Employment Law No. 2 of 2019",
        pdfArticleHeader: "Article 59 — Termination by Employer",
        pdfClauses: [
            {
                id: "59(1)",
                text: "An employer may terminate without notice where the employee has committed a fundamental breach of the employment contract."
            },
            {
                id: "59(2)",
                text: "An employer may terminate for cause by providing written notice of not less than the minimum notice period, setting out the grounds."
            },
            {
                id: "59(3)",
                text: "Termination shall not be on grounds related to pregnancy, maternity leave, or the exercise of any statutory right."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "DIFC Employment Law · Art. 59 · p.31",
        pageBadge: "Page 31",
    },
]

export const CZ_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "Czech Republic",
        question: "Může zaměstnavatel dát výpověď zaměstnanci z důvodu nadbytečnosti, pokud pracovní místo fakticky zrušeno nebylo?",
        answer: "",
        pdfTitle: "Zákoník práce (262/2006 Sb.)",
        pdfArticleHeader: "§ 52 písm. c)",
        pdfClauses: [],
        highlightRange: [0, 0],
        sourceBadge: "Zákoník práce · § 52(c) + NS judikatura",
        pageBadge: "",
        sources: [
            {
                title: "Zákoník práce (262/2006 Sb.)",
                articleHeader: "§ 52 písm. c) — Nadbytečnost",
                clauses: [
                    {
                        id: "§52(c)",
                        text: "Zaměstnavatel může dát zaměstnanci výpověď, stane-li se zaměstnanec nadbytečným vzhledem k rozhodnutí zaměstnavatele o změně jeho úkolů, technického vybavení, o snížení stavu zaměstnanců nebo o jiných organizačních změnách."
                    },
                ],
                highlightRange: [0, 0],
                badge: "Zákoník práce · § 52 písm. c)",
                pageBadge: "§ 52",
                type: "statute",
            },
            {
                title: "21 Cdo 4117/2012 · Nejvyšší soud",
                articleHeader: "Právní věta — Nadbytečnost",
                clauses: [
                    {
                        id: "NS",
                        text: "Organizační změna musí být skutečná — výpověď je neplatná, bylo-li rozhodnutí o zrušení pracovního místa pouze formální a zaměstnanec byl vzápětí nahrazen jinou osobou na totožné pozici."
                    },
                ],
                highlightRange: [0, 0],
                badge: "21 Cdo 4117/2012 · kat. A · judikatura",
                pageBadge: "NS",
                type: "court_decision",
            },
        ],
    },
    {
        jurisdiction: "Czech Republic",
        question: "Může podnikatel požadovat ochranu jako slabší smluvní strana vůči jinému podnikateli při nepřiměřeně vysokých úrocích ze zápůjčky?",
        answer: "",
        pdfTitle: "Občanský zákoník (89/2012 Sb.)",
        pdfArticleHeader: "§ 1796",
        pdfClauses: [],
        highlightRange: [0, 0],
        sourceBadge: "Občanský zákoník · § 1796 + NS judikatura",
        pageBadge: "",
        sources: [
            {
                title: "Občanský zákoník (89/2012 Sb.)",
                articleHeader: "§ 1796 — Lichva",
                clauses: [
                    {
                        id: "§1796",
                        text: "Neplatná je smlouva, ke které bylo použito tísně, nezkušenosti, rozumové slabosti nebo rozrušení druhé strany a sjednaná protiplnění jsou ke vzájemnému plnění v hrubém nepoměru."
                    },
                ],
                highlightRange: [0, 0],
                badge: "Občanský zákoník · § 1796",
                pageBadge: "§ 1796",
                type: "statute",
            },
            {
                title: "23 ICdo 56/2019 · Nejvyšší soud",
                articleHeader: "Právní věta — Lichva mezi podnikateli",
                clauses: [
                    {
                        id: "NS",
                        text: "I fyzická osoba podnikatel může být spotřebitelem mimo rámec své podnikatelské činnosti. Sjednání úroku mnohonásobně převyšujícího obvyklou míru může naplnit znaky lichvy i mezi podnikateli."
                    },
                ],
                highlightRange: [0, 0],
                badge: "23 ICdo 56/2019 · kat. A · judikatura",
                pageBadge: "NS",
                type: "court_decision",
            },
        ],
    },
]

export const UK_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "United Kingdom",
        question: "What are the statutory duties of a director under the Companies Act 2006?",
        answer: "",
        pdfTitle: "Companies Act 2006",
        pdfArticleHeader: "Section 172 — Duty to promote the success of the company",
        pdfClauses: [
            {
                id: "172(1)",
                text: "A director of a company must act in the way he considers, in good faith, would be most likely to promote the success of the company for the benefit of its members as a whole."
            },
            {
                id: "172(1)(a)",
                text: "In doing so, he must have regard to the likely consequences of any decision in the long term."
            },
            {
                id: "172(1)(b)",
                text: "The interests of the company's employees, the impact on the community and the environment, and the desirability of maintaining a reputation for high standards of business conduct."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "Companies Act 2006 · s.172 · p.329",
        pageBadge: "Page 329",
    },
    {
        jurisdiction: "United Kingdom",
        question: "What constitutes unfair dismissal under the Employment Rights Act 1996?",
        answer: "",
        pdfTitle: "Employment Rights Act 1996",
        pdfArticleHeader: "Section 98 — General right not to be unfairly dismissed",
        pdfClauses: [
            {
                id: "98(1)",
                text: "In determining whether the dismissal of an employee is fair or unfair, it is for the employer to show the reason for the dismissal."
            },
            {
                id: "98(2)",
                text: "A reason falls within this subsection if it relates to the capability or qualifications of the employee, the conduct of the employee, or that the employee was redundant."
            },
            {
                id: "98(4)",
                text: "The determination of whether the dismissal is fair or unfair shall depend on whether the employer acted reasonably in treating it as a sufficient reason."
            },
        ],
        highlightRange: [0, 2],
        sourceBadge: "Employment Rights Act 1996 · s.98 · p.432",
        pageBadge: "Page 432",
    },
]

export const AU_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "Australia",
        question: "What is the insolvent trading duty under the Corporations Act 2001?",
        answer: "",
        pdfTitle: "Corporations Act 2001",
        pdfArticleHeader: "Section 588G — Director's duty to prevent insolvent trading",
        pdfClauses: [
            {
                id: "588G(1)",
                text: "This section applies if a company incurs a debt at a time when the company is insolvent, or becomes insolvent by incurring that debt."
            },
            {
                id: "588G(2)",
                text: "The director contravenes this section if the director was aware that there were grounds for suspecting the company was insolvent, or a reasonable person would have been so aware."
            },
            {
                id: "588G(3)",
                text: "A person who contravenes this section commits an offence punishable by imprisonment for up to 5 years or 200 penalty units."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "Corporations Act 2001 · s.588G · p.5290",
        pageBadge: "Page 5290",
    },
    {
        jurisdiction: "Australia",
        question: "What constitutes unconscionable conduct under Australian Consumer Law?",
        answer: "",
        pdfTitle: "Competition and Consumer Act 2010 — Schedule 2",
        pdfArticleHeader: "Section 21 — Unconscionable conduct in connection with goods or services",
        pdfClauses: [
            {
                id: "21(1)",
                text: "A person must not, in trade or commerce, in connection with the supply or acquisition of goods or services, engage in conduct that is, in all the circumstances, unconscionable."
            },
            {
                id: "21(4)(a)",
                text: "The court may have regard to the relative bargaining strengths of the parties and whether any conditions were reasonably necessary for the protection of legitimate interests."
            },
            {
                id: "21(4)(b)",
                text: "Whether the consumer was able to understand any documents relating to the supply or acquisition of the goods or services."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "ACL Schedule 2 · s.21 · p.2396",
        pageBadge: "Page 2396",
    },
]

export const PREVIEW_SCENARIOS_MAP: Record<string, DemoScenario[]> = {
    difc: DIFC_SCENARIOS,
    cz: CZ_SCENARIOS,
    uk: UK_SCENARIOS,
    au: AU_SCENARIOS,
}
