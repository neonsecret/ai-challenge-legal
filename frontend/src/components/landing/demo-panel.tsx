"use client";

import {useState, useEffect, useRef, useCallback} from "react";
import {motion, AnimatePresence} from "motion/react";
import {useTypewriter} from "./typewriter";
import {FakePdf} from "./fake-pdf";

/* ------------------------------------------------------------------ */
/*  Jurisdiction demo scenarios                                        */

/* ------------------------------------------------------------------ */

export interface SourceCard {
    title: string;
    articleHeader: string;
    clauses: { id: string; text: string }[];
    highlightRange: [number, number];
    badge: string;
    pageBadge: string;
    type?: "statute" | "court_decision";
}

export interface DemoScenario {
    jurisdiction: string;
    question: string;
    answer: string;
    /** Primary source (always shown) */
    pdfTitle: string;
    pdfArticleHeader: string;
    pdfClauses: { id: string; text: string }[];
    highlightRange: [number, number];
    sourceBadge: string;
    pageBadge: string;
    /** Optional additional sources — shown as stacked cards */
    sources?: SourceCard[];
}

const SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "CZ",
        question:
            "Kdy je zaměstnanec nadbytečný podle zákoníku práce?",
        answer:
            "Podle § 52 písm. c) zákoníku práce může dát zaměstnavatel zaměstnanci výpověď z důvodu nadbytečnosti, pokud:\n\n1. Se zaměstnanec stal nadbytečným vzhledem k rozhodnutí zaměstnavatele o změně jeho úkolů, technického vybavení nebo snížení stavu zaměstnanců.\n\n2. Rozhodnutí o organizační změně musí být přijato před doručením výpovědi a musí existovat příčinná souvislost mezi organizační změnou a nadbytečností konkrétního zaměstnance.\n\n3. Dle judikatury Nejvyššího soudu (sp. zn. 21 Cdo 262/2006) zaměstnavatel není povinen prokázat, že organizační změna vedla ke zvýšení efektivity — postačí, že rozhodnutí bylo přijato a zaměstnanec se stal nadbytečným.",
        pdfTitle: "Zákoník práce (zákon č. 262/2006 Sb.)",
        pdfArticleHeader: "Část druhá — Pracovní poměr",
        pdfClauses: [
            {
                id: "§ 52(c)",
                text: "Zaměstnavatel může dát zaměstnanci výpověď, stane-li se zaměstnanec nadbytečným vzhledem k rozhodnutí zaměstnavatele nebo příslušného orgánu o změně jeho úkolů, technického vybavení, o snížení stavu zaměstnanců za účelem zvýšení efektivnosti práce nebo o jiných organizačních změnách.",
            },
            {
                id: "§ 67(1)",
                text: "Zaměstnanci, u něhož dochází k rozvázání pracovního poměru výpovědí danou zaměstnavatelem z důvodů uvedených v § 52 písm. a) až c), přísluší od zaměstnavatele při skončení pracovního poměru odstupné ve výši nejméně trojnásobku průměrného výdělku.",
            },
            {
                id: "§ 73a(2)",
                text: "Odvoláním nebo vzdáním se pracovního místa vedoucího zaměstnance pracovní poměr nekončí; zaměstnavatel je povinen tomuto zaměstnanci navrhnout změnu jeho dalšího pracovního zařazení u zaměstnavatele na jinou práci odpovídající jeho zdravotnímu stavu a kvalifikaci.",
            },
            {
                id: "NS 21 Cdo 262/2006",
                text: "Pro platnost výpovědi z důvodu nadbytečnosti není rozhodné, zda organizační změna skutečně vedla ke zvýšení efektivity práce; postačuje, že zaměstnavatel rozhodl o organizační změně a zaměstnanec se v důsledku tohoto rozhodnutí stal nadbytečným.",
            },
        ],
        highlightRange: [0, 0],
        sourceBadge: "§ 52(c) · Zákoník práce · Str. 28",
        pageBadge: "Str. 28",
        sources: [
            {
                title: "Zákoník práce (zákon č. 262/2006 Sb.)",
                articleHeader: "§ 52 písm. c) — Nadbytečnost",
                clauses: [
                    {
                        id: "§ 52(c)",
                        text: "Zaměstnavatel může dát zaměstnanci výpověď, stane-li se zaměstnanec nadbytečným vzhledem k rozhodnutí zaměstnavatele o změně jeho úkolů, technického vybavení, o snížení stavu zaměstnanců nebo o jiných organizačních změnách.",
                    },
                    {
                        id: "§ 67(1)",
                        text: "Zaměstnanci, u něhož dochází k rozvázání pracovního poměru výpovědí danou zaměstnavatelem z důvodů uvedených v § 52 písm. a) až c), přísluší odstupné ve výši nejméně trojnásobku průměrného výdělku.",
                    },
                ],
                highlightRange: [0, 0],
                badge: "Zákoník práce · § 52 písm. c) · Str. 28",
                pageBadge: "Str. 28",
                type: "statute",
            },
            {
                title: "NS 21 Cdo 262/2006",
                articleHeader: "Rozsudek Nejvyššího soudu",
                clauses: [
                    {
                        id: "Právní věta",
                        text: "Pro platnost výpovědi z důvodu nadbytečnosti postačuje, že zaměstnavatel rozhodl o organizační změně a zaměstnanec se v důsledku tohoto rozhodnutí stal nadbytečným.",
                    },
                ],
                highlightRange: [0, 0],
                badge: "NS · 21 Cdo 262/2006",
                pageBadge: "Str. 1",
                type: "court_decision",
            },
        ],
    },
    {
        jurisdiction: "DIFC",
        question:
            "What are the penalty clauses under Article 14.3 of the Supply Agreement?",
        answer:
            "Under Article 14.3 of the Supply Agreement, the penalty clauses stipulate that:\n\n1. Late delivery incurs a penalty of 0.5% of the contract value per day of delay, capped at 10% of the total contract price.\n\n2. Material breach requires written notice and a 30-day cure period before penalties apply.\n\n3. Force majeure events as defined in Article 18 suspend penalty accrual for the duration of the qualifying event.",
        pdfTitle: "Supply Agreement",
        pdfArticleHeader: "Article 14 \u2014 Penalties and Liquidated Damages",
        pdfClauses: [
            {
                id: "14.1",
                text: "The Parties acknowledge that timely performance is of the essence of this Agreement, and any failure to deliver in accordance with the agreed schedule shall constitute a material default.",
            },
            {
                id: "14.2",
                text: "Without prejudice to other remedies available at law or in equity, the Purchaser reserves the right to claim compensatory damages in excess of the liquidated amounts set forth herein.",
            },
            {
                id: "14.3",
                text: "In the event of late delivery, the Supplier shall pay to the Purchaser a penalty equal to zero point five percent (0.5%) of the total Contract Price for each day of delay, provided that the total amount of penalties shall not exceed ten percent (10%) of the total Contract Price. Material breach of any obligation under this Agreement shall require written notice specifying the nature of the breach and granting the defaulting Party a cure period of thirty (30) calendar days from receipt of such notice.",
            },
            {
                id: "14.4",
                text: "The provisions of this Article shall survive termination or expiration of the Agreement and shall remain in full force until all obligations are discharged.",
            },
        ],
        highlightRange: [2, 2],
        sourceBadge: "Article 14.3 \u00b7 Supply Agreement \u00b7 Page 7",
        pageBadge: "Page 7",
    },
    {
        jurisdiction: "EU",
        question: "What are the data subject rights under GDPR Article 15?",
        answer:
            "Under GDPR Article 15, data subjects have the right of access, specifically:\n\n1. The right to obtain confirmation as to whether personal data concerning them is being processed, and where that is the case, access to the personal data.\n\n2. The controller shall provide information including the purposes of processing, the categories of data concerned, and the recipients or categories of recipients.\n\n3. The right to obtain a copy of the personal data undergoing processing, provided free of charge for the first copy.",
        pdfTitle: "General Data Protection Regulation",
        pdfArticleHeader: "Article 15 \u2014 Right of Access by the Data Subject",
        pdfClauses: [
            {
                id: "15(1)",
                text: "The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the following information.",
            },
            {
                id: "15(1)(a)",
                text: "The purposes of the processing; the categories of personal data concerned; the recipients or categories of recipient to whom the personal data have been or will be disclosed.",
            },
            {
                id: "15(1)(d)",
                text: "Where possible, the envisaged period for which the personal data will be stored, or, if not possible, the criteria used to determine that period.",
            },
            {
                id: "15(3)",
                text: "The controller shall provide a copy of the personal data undergoing processing. For any further copies requested by the data subject, the controller may charge a reasonable fee based on administrative costs.",
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "Article 15 \u00b7 GDPR \u00b7 Page 43",
        pageBadge: "Page 43",
    },
    {
        jurisdiction: "UK",
        question:
            "What constitutes unfair dismissal under the Employment Rights Act 1996?",
        answer:
            "Under the Employment Rights Act 1996, unfair dismissal is established when:\n\n1. An employee with at least two years\u2019 continuous service is dismissed, and the employer cannot show the reason falls within the permitted categories (capability, conduct, redundancy, statutory restriction, or SOSR).\n\n2. Even where a permitted reason exists, the dismissal may be unfair if the employer did not act reasonably in treating it as sufficient grounds.\n\n3. Certain dismissals are automatically unfair regardless of length of service, including those related to pregnancy, trade union membership, or whistleblowing.",
        pdfTitle: "Employment Rights Act 1996",
        pdfArticleHeader: "Part X \u2014 Unfair Dismissal",
        pdfClauses: [
            {
                id: "s.94(1)",
                text: "An employee has the right not to be unfairly dismissed by his employer.",
            },
            {
                id: "s.98(1)",
                text: "In determining for the purposes of this Part whether the dismissal of an employee is fair or unfair, it is for the employer to show the reason (or, if more than one, the principal reason) for the dismissal.",
            },
            {
                id: "s.98(2)",
                text: "A reason falls within this subsection if it relates to the capability or qualifications of the employee, the conduct of the employee, that the employee was redundant, or that a statutory duty or restriction prohibited the continued employment.",
            },
            {
                id: "s.98(4)",
                text: "Where the employer has fulfilled the requirements of subsection (1), the determination of the question whether the dismissal is fair or unfair depends on whether in the circumstances the employer acted reasonably or unreasonably in treating it as a sufficient reason for dismissing the employee.",
            },
        ],
        highlightRange: [1, 2],
        sourceBadge: "s.98 \u00b7 Employment Rights Act 1996 \u00b7 Page 112",
        pageBadge: "Page 112",
    },
    {
        jurisdiction: "US",
        question:
            "What are the fiduciary duties of directors under Delaware corporate law?",
        answer:
            "Under Delaware corporate law, directors owe two primary fiduciary duties:\n\n1. Duty of Care: Directors must inform themselves of all material information reasonably available before making a business decision, and act with the care that a reasonably prudent person would use.\n\n2. Duty of Loyalty: Directors must act in good faith and in the honest belief that their actions are in the best interests of the corporation, avoiding self-dealing and conflicts of interest.\n\n3. The business judgment rule presumes that directors acted on an informed basis, in good faith, and with the honest belief that the action was in the company\u2019s best interest.",
        pdfTitle: "Delaware General Corporation Law",
        pdfArticleHeader: "Title 8 \u2014 Fiduciary Duties of Directors",
        pdfClauses: [
            {
                id: "141(a)",
                text: "The business and affairs of every corporation organized under this chapter shall be managed by or under the direction of a board of directors, except as may be otherwise provided in this chapter or in its certificate of incorporation.",
            },
            {
                id: "141(e)",
                text: "A member of the board of directors shall, in the performance of such member\u2019s duties, be fully protected in relying in good faith upon the records of the corporation and upon information, opinions, reports or statements presented by officers, employees, or committees of the board.",
            },
            {
                id: "102(b)(7)",
                text: "The certificate of incorporation may contain a provision eliminating or limiting the personal liability of a director to the corporation or its stockholders for monetary damages for breach of fiduciary duty as a director, provided that such provision shall not eliminate or limit the liability of a director for any breach of the director\u2019s duty of loyalty.",
            },
            {
                id: "144",
                text: "No contract or transaction between a corporation and one or more of its directors or officers shall be void or voidable solely for this reason if the material facts as to the director\u2019s relationship or interest are disclosed and the transaction is approved in good faith.",
            },
        ],
        highlightRange: [2, 3],
        sourceBadge: "s.102(b)(7) \u00b7 DGCL \u00b7 Page 28",
        pageBadge: "Page 28",
    },
    {
        jurisdiction: "AU",
        question:
            "What are the elements of murder under Victorian criminal law?",
        answer:
            "Under the Crimes Act 1958 (Vic), the elements of murder are:\n\n1. The accused committed a voluntary act or omission that caused the death of another person.\n\n2. The accused had the requisite mental element: either an intention to kill, an intention to cause really serious injury, or knowledge that the act would probably cause death.\n\n3. Reckless murder is established where the accused foresaw the probability of death resulting from their conduct and consciously chose to disregard that risk.\n\n4. There was no lawful justification or excuse such as self-defence.",
        pdfTitle: "Crimes Act 1958 (Vic)",
        pdfArticleHeader: "Part I Division 1 \u2014 Homicide",
        pdfClauses: [
            {
                id: "s.3",
                text: "A person who without lawful justification or excuse and with the requisite mental element causes the death of another person by a voluntary act or omission is guilty of murder.",
            },
            {
                id: "s.3A(1)",
                text: "A person who, without lawful justification or excuse, kills another person intending to kill that person or intending to cause that person really serious injury is guilty of murder.",
            },
            {
                id: "s.3A(2)",
                text: "A person who, without lawful justification or excuse, kills another person knowing that their act or omission would probably result in death is guilty of murder (reckless murder).",
            },
            {
                id: "s.3B",
                text: "The prosecution must prove beyond reasonable doubt each element of the offence. The burden of proving any defence of lawful justification or excuse lies upon the accused on the balance of probabilities.",
            },
        ],
        highlightRange: [1, 2],
        sourceBadge: "s.3A \u00b7 Crimes Act 1958 (Vic) \u00b7 Page 4",
        pageBadge: "Page 4",
    },
];

/* ------------------------------------------------------------------ */
/*  Timing constants                                                   */
/* ------------------------------------------------------------------ */

const TIMING = {
    thinkingDelay: 800,
    typingSpeed: 38,
    streamingSpeed: 14,
    highlightDelay: 500,
    autoCycleDelay: 12000,
};

type Phase = "idle" | "typing-question" | "thinking" | "streaming-answer" | "done";

/* ------------------------------------------------------------------ */
/*  Component                                                          */

/* ------------------------------------------------------------------ */

interface DemoPanelProps {
    /** Index into SCENARIOS to start on (default 0). Use to pre-select CZ for Czech visitors. */
    defaultScenarioIndex?: number;
}

export { SCENARIOS };

export function DemoPanel({ defaultScenarioIndex = 0 }: DemoPanelProps = {}) {
    const [activeIdx, setActiveIdx] = useState(defaultScenarioIndex);
    const [phase, setPhase] = useState<Phase>("idle");
    const [streamedAnswer, setStreamedAnswer] = useState("");
    const [showHighlights, setShowHighlights] = useState(false);
    const [userInteracted, setUserInteracted] = useState(false);

    const answerIndexRef = useRef(0);
    const streamIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const autoCycleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const chatScrollRef = useRef<HTMLDivElement>(null);
    const chatBottomRef = useRef<HTMLDivElement>(null);
    // Keep activeIdx in a ref so streaming callback reads the latest value
    const activeIdxRef = useRef(activeIdx);
    activeIdxRef.current = activeIdx;

    const scenario = SCENARIOS[activeIdx];

    /* ---- cleanup helper ---- */
    const clearTimers = useCallback(() => {
        if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
        if (autoCycleRef.current) clearTimeout(autoCycleRef.current);
        if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
        streamIntervalRef.current = null;
        autoCycleRef.current = null;
        highlightTimerRef.current = null;
    }, []);

    /* ---- switch to a specific scenario ---- */
    const switchTo = useCallback(
        (idx: number) => {
            clearTimers();
            setActiveIdx(idx);
            setPhase("idle");
            setStreamedAnswer("");
            setShowHighlights(false);
            answerIndexRef.current = 0;
            setTimeout(() => setPhase("typing-question"), 300);
        },
        [clearTimers]
    );

    /* ---- streaming logic ---- */
    const startStreaming = useCallback(() => {
        setPhase("streaming-answer");
        answerIndexRef.current = 0;
        setStreamedAnswer("");

        highlightTimerRef.current = setTimeout(
            () => setShowHighlights(true),
            TIMING.highlightDelay
        );

        const currentIdx = activeIdxRef.current;
        const answerText = SCENARIOS[currentIdx].answer;

        streamIntervalRef.current = setInterval(() => {
            const next = answerIndexRef.current + 1;
            setStreamedAnswer(answerText.slice(0, next));
            answerIndexRef.current = next;
            if (next >= answerText.length) {
                if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
                setPhase("done");
            }
        }, TIMING.streamingSpeed);
    }, []);

    /* ---- auto-cycle after done ---- */
    useEffect(() => {
        if (phase === "done" && !userInteracted) {
            autoCycleRef.current = setTimeout(() => {
                const nextIdx = (activeIdxRef.current + 1) % SCENARIOS.length;
                switchTo(nextIdx);
            }, TIMING.autoCycleDelay);
            return () => {
                if (autoCycleRef.current) clearTimeout(autoCycleRef.current);
            };
        }
    }, [phase, userInteracted, switchTo]);

    /* ---- initial kick-off ---- */
    useEffect(() => {
        const init = setTimeout(() => setPhase("typing-question"), 600);
        return () => {
            clearTimeout(init);
            clearTimers();
        };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    /* ---- scroll ONLY the chat container, not the page ---- */
    useEffect(() => {
        if (chatScrollRef.current) {
            chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
        }
    }, [streamedAnswer]);

    /* ---- typewriter ---- */
    const {displayed: typedQuestion, done: questionDone} = useTypewriter({
        text: scenario.question,
        speed: TIMING.typingSpeed,
        startDelay: 0,
        onComplete: () => {
            setTimeout(() => setPhase("thinking"), 100);
        },
    });

    const questionText = phase === "typing-question" ? typedQuestion : "";
    const showQuestionFull =
        phase === "thinking" || phase === "streaming-answer" || phase === "done";

    /* ---- thinking -> streaming transition ---- */
    useEffect(() => {
        if (phase === "thinking") {
            const t = setTimeout(startStreaming, TIMING.thinkingDelay);
            return () => clearTimeout(t);
        }
    }, [phase, startStreaming]);

    const answerLines = streamedAnswer.split("\n");

    /* ---- user switches jurisdiction ---- */
    const handleTabClick = (idx: number) => {
        if (idx === activeIdx) return;
        setUserInteracted(true);
        switchTo(idx);
    };

    const handlePrev = () => {
        setUserInteracted(true);
        switchTo((activeIdx - 1 + SCENARIOS.length) % SCENARIOS.length);
    };

    const handleNext = () => {
        setUserInteracted(true);
        switchTo((activeIdx + 1) % SCENARIOS.length);
    };

    return (
        <div
            className="w-full max-w-5xl mx-auto rounded-2xl overflow-hidden"
            style={{
                background: "rgba(255,255,255,0.05)",
                backdropFilter: "blur(24px)",
                WebkitBackdropFilter: "blur(24px)",
                border: "1px solid rgba(255,255,255,0.10)",
                boxShadow:
                    "0 40px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(201,168,76,0.10), inset 0 1px 0 rgba(255,255,255,0.08)",
            }}
        >
            {/* Window chrome + jurisdiction tabs */}
            <div
                className="flex flex-col"
                style={{borderBottom: "1px solid rgba(255,255,255,0.08)"}}
            >
                {/* Traffic lights + title */}
                <div className="flex items-center gap-2 px-4 py-3">
                    <div className="flex gap-1.5">
                        <div className="size-3 rounded-full bg-red-500/60"/>
                        <div className="size-3 rounded-full bg-yellow-500/60"/>
                        <div className="size-3 rounded-full bg-green-500/60"/>
                    </div>
                    <div
                        className="flex-1 text-center text-[11px] font-mono"
                        style={{color: "rgba(255,255,255,0.25)"}}
                    >
                        vitreon.app — Research Assistant
                    </div>
                </div>

                {/* Jurisdiction pills */}
                <div className="flex items-center gap-1.5 px-4 pb-3">
                    <button
                        onClick={handlePrev}
                        className="shrink-0 flex items-center justify-center size-6 min-h-[44px] min-w-[44px] rounded-md transition-colors hover:bg-white/10"
                        style={{
                            background: "rgba(255,255,255,0.06)",
                            border: "1px solid rgba(255,255,255,0.08)",
                            color: "rgba(255,255,255,0.5)",
                        }}
                        aria-label="Previous jurisdiction"
                    >
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                            <path d="M6.5 2L3.5 5L6.5 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"
                                  strokeLinejoin="round"/>
                        </svg>
                    </button>

                    <div className="flex gap-1.5 overflow-x-auto flex-1 justify-center">
                        {SCENARIOS.map((s, i) => (
                            <button
                                key={s.jurisdiction}
                                onClick={() => handleTabClick(i)}
                                className="shrink-0 flex items-center gap-1.5 rounded-full px-3 py-1 min-h-[44px] text-[11px] font-medium transition-all"
                                style={{
                                    background:
                                        i === activeIdx
                                            ? "rgba(201,168,76,0.18)"
                                            : "rgba(255,255,255,0.04)",
                                    border:
                                        i === activeIdx
                                            ? "1px solid rgba(201,168,76,0.4)"
                                            : "1px solid rgba(255,255,255,0.08)",
                                    color:
                                        i === activeIdx ? "#C9A84C" : "rgba(255,255,255,0.45)",
                                }}
                            >
                                {s.jurisdiction}
                            </button>
                        ))}
                    </div>

                    <button
                        onClick={handleNext}
                        className="shrink-0 flex items-center justify-center size-6 min-h-[44px] min-w-[44px] rounded-md transition-colors hover:bg-white/10"
                        style={{
                            background: "rgba(255,255,255,0.06)",
                            border: "1px solid rgba(255,255,255,0.08)",
                            color: "rgba(255,255,255,0.5)",
                        }}
                        aria-label="Next jurisdiction"
                    >
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                            <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"
                                  strokeLinejoin="round"/>
                        </svg>
                    </button>
                </div>
            </div>

            {/* Split pane */}
            <div className="grid grid-cols-1 md:grid-cols-2 md:min-h-[420px]">
                {/* LEFT: Chat — overflow-y-auto scoped so scrollIntoView stays here */}
                <div
                    ref={chatScrollRef}
                    className="flex flex-col p-5 gap-4 overflow-y-auto max-h-[420px]"
                    style={{borderRight: "1px solid rgba(255,255,255,0.08)"}}
                >
                    <p
                        className="text-[10px] uppercase tracking-widest font-semibold"
                        style={{color: "rgba(201,168,76,0.7)"}}
                    >
                        Research Query
                    </p>

                    {/* User bubble */}
                    <AnimatePresence mode="wait">
                        {phase !== "idle" && (
                            <motion.div
                                key={`q-${activeIdx}`}
                                initial={{opacity: 0, y: 6}}
                                animate={{opacity: 1, y: 0}}
                                exit={{opacity: 0, y: -4}}
                                className="flex justify-end"
                            >
                                <div
                                    className="max-w-[85%] rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-[12px] leading-relaxed"
                                    style={{
                                        background: "rgba(201,168,76,0.15)",
                                        border: "1px solid rgba(201,168,76,0.25)",
                                        color: "rgba(255,255,255,0.9)",
                                    }}
                                >
                                    {showQuestionFull ? scenario.question : questionText}
                                    {phase === "typing-question" && !questionDone && (
                                        <span
                                            className="inline-block w-[2px] h-[13px] ml-0.5 align-middle animate-pulse"
                                            style={{backgroundColor: "#C9A84C"}}
                                        />
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Thinking dots */}
                    <AnimatePresence>
                        {phase === "thinking" && (
                            <motion.div
                                initial={{opacity: 0}}
                                animate={{opacity: 1}}
                                exit={{opacity: 0}}
                                className="flex items-center gap-1.5 px-1"
                            >
                                {[0, 1, 2].map((i) => (
                                    <motion.div
                                        key={i}
                                        className="size-1.5 rounded-full"
                                        style={{backgroundColor: "#C9A84C"}}
                                        animate={{opacity: [0.3, 1, 0.3]}}
                                        transition={{
                                            duration: 0.8,
                                            repeat: Infinity,
                                            delay: i * 0.18,
                                        }}
                                    />
                                ))}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Streaming answer */}
                    <AnimatePresence mode="wait">
                        {(phase === "streaming-answer" || phase === "done") &&
                            streamedAnswer && (
                                <motion.div
                                    key={`a-${activeIdx}`}
                                    initial={{opacity: 0, y: 4}}
                                    animate={{opacity: 1, y: 0}}
                                    exit={{opacity: 0}}
                                    className="flex-1"
                                >
                                    <div
                                        className="rounded-2xl rounded-tl-sm px-3.5 py-3 text-[11.5px] leading-[1.65]"
                                        style={{
                                            background: "rgba(27,43,75,0.5)",
                                            border: "1px solid rgba(255,255,255,0.08)",
                                            color: "rgba(255,255,255,0.82)",
                                        }}
                                    >
                                        {answerLines.map((line, i) => (
                                            <span key={i}>
                        {line}
                                                {i < answerLines.length - 1 && <br/>}
                      </span>
                                        ))}
                                        {phase === "streaming-answer" && (
                                            <span
                                                className="inline-block w-[2px] h-[13px] ml-0.5 align-middle"
                                                style={{
                                                    backgroundColor: "#C9A84C",
                                                    animation: "blink-cursor 0.7s step-end infinite",
                                                }}
                                            />
                                        )}
                                    </div>

                                    {/* Source badge */}
                                    <AnimatePresence>
                                        {phase === "done" && (
                                            <motion.div
                                                initial={{opacity: 0, y: 4}}
                                                animate={{opacity: 1, y: 0}}
                                                transition={{delay: 0.2}}
                                                className="mt-2 inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5"
                                                style={{
                                                    background: "rgba(201,168,76,0.12)",
                                                    border: "1px solid rgba(201,168,76,0.3)",
                                                }}
                                            >
                                                <div className="size-1.5 rounded-full bg-[#C9A84C]"/>
                                                <span
                                                    className="text-[10px] font-mono"
                                                    style={{color: "#C9A84C"}}
                                                >
                          {scenario.sourceBadge
                              .split(" \u00b7 ")
                              .slice(0, 2)
                              .join(" \u00b7 ")}
                        </span>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </motion.div>
                            )}
                    </AnimatePresence>

                    <div ref={chatBottomRef}/>
                </div>

                {/* Mobile: source badge strip */}
                <div
                    className="md:hidden px-5 py-3"
                    style={{borderTop: "1px solid rgba(255,255,255,0.06)"}}
                >
                    <p
                        className="text-[10px] uppercase tracking-widest font-semibold mb-2"
                        style={{color: "rgba(201,168,76,0.7)"}}
                    >
                        Source Document
                    </p>
                    <div
                        className="inline-flex items-center gap-2 rounded-lg px-3 py-2"
                        style={{
                            background: "rgba(201,168,76,0.10)",
                            border: "1px solid rgba(201,168,76,0.25)",
                        }}
                    >
                        <div className="size-1.5 rounded-full bg-[#C9A84C] shrink-0"/>
                        <span className="text-[11px] font-mono" style={{color: "#C9A84C"}}>
              {scenario.sourceBadge}
            </span>
                    </div>
                </div>

                {/* RIGHT: Fake PDF — hidden on mobile */}
                <div className="hidden md:block p-5">
                    <p
                        className="text-[10px] uppercase tracking-widest font-semibold mb-3"
                        style={{color: "rgba(201,168,76,0.7)"}}
                    >
                        Source Document
                    </p>
                    <div className="h-[360px]">
                        <FakePdf scenario={scenario} showHighlights={showHighlights}/>
                    </div>
                </div>
            </div>
        </div>
    );
}
