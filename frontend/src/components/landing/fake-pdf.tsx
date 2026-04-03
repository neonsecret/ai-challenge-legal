"use client";

import {motion, AnimatePresence} from "motion/react";
import type {DemoScenario, SourceCard} from "./demo-panel";

interface FakePdfProps {
    scenario: DemoScenario;
    showHighlights: boolean;
}

function SingleSourceCard({
    title,
    articleHeader,
    clauses,
    highlightRange,
    badge,
    pageBadge,
    type,
    showHighlights,
    compact = false,
}: SourceCard & { showHighlights: boolean; compact?: boolean }) {
    const isCourtDecision = type === "court_decision";

    return (
        <div
            className="relative bg-white rounded-xl shadow-lg overflow-hidden"
            style={{fontFamily: "Georgia, serif", flex: compact ? "1 1 0%" : undefined}}
        >
            <div className={compact ? "p-3 h-full overflow-hidden text-[#1a1a1a]" : "p-5 h-full overflow-hidden text-[#1a1a1a]"}>
                {/* Document title */}
                <div className="text-center mb-3">
                    <p className={`${compact ? "text-[9px]" : "text-[10px]"} font-bold tracking-widest text-[#333] uppercase mb-1`}>
                        {isCourtDecision && (
                            <span
                                style={{
                                    display: "inline-block",
                                    fontSize: 8,
                                    fontWeight: 700,
                                    padding: "1px 4px",
                                    borderRadius: 3,
                                    background: "rgba(201,168,76,0.15)",
                                    color: "#8B6914",
                                    marginRight: 4,
                                    verticalAlign: "middle",
                                    letterSpacing: 0,
                                }}
                            >
                                NS
                            </span>
                        )}
                        {title}
                    </p>
                    <div className="w-10 h-px bg-[#ccc] mx-auto"/>
                </div>

                {/* Article header */}
                <p className={`${compact ? "text-[9px]" : "text-[10px]"} font-bold text-[#1B2B4B] mb-2 uppercase tracking-wide`}>
                    {articleHeader}
                </p>

                {/* Clauses */}
                {clauses.map((clause, i) => {
                    const isHighlighted = i >= highlightRange[0] && i <= highlightRange[1];
                    return (
                        <div key={clause.id} className="relative mb-1.5">
                            <p className={`${compact ? "text-[9px] leading-[1.45]" : "text-[10px] leading-[1.55]"} text-[#333] relative z-10`}>
                                <span className="font-semibold">{clause.id}</span>{" "}
                                {clause.text}
                            </p>
                            {isHighlighted && (
                                <motion.div
                                    initial={{opacity: 0}}
                                    animate={{opacity: showHighlights ? 1 : 0}}
                                    transition={{duration: 0.4, delay: (i - highlightRange[0]) * 0.15}}
                                    className="absolute inset-0 rounded-sm pointer-events-none"
                                    style={{
                                        backgroundColor: isCourtDecision
                                            ? "rgba(201, 168, 76, 0.30)"
                                            : "rgba(201, 168, 76, 0.22)",
                                        zIndex: 0,
                                    }}
                                />
                            )}
                        </div>
                    );
                })}

                {/* Source badge */}
                <motion.div
                    initial={{opacity: 0, y: 4}}
                    animate={{
                        opacity: showHighlights ? 1 : 0,
                        y: showHighlights ? 0 : 4,
                    }}
                    transition={{duration: 0.3, delay: 0.5}}
                    className="absolute bottom-2 left-2 right-2 flex items-center gap-1.5 bg-[#1B2B4B]/90 backdrop-blur-sm rounded-md px-2 py-1"
                >
                    <div className="size-1.5 rounded-full bg-[#C9A84C] shrink-0"/>
                    <span className="text-[8px] text-white font-mono">
                        {badge}
                    </span>
                </motion.div>
            </div>
        </div>
    );
}

export function FakePdf({scenario, showHighlights}: FakePdfProps) {
    const hasMultipleSources = scenario.sources && scenario.sources.length > 0;

    if (hasMultipleSources) {
        return (
            <AnimatePresence mode="wait">
                <motion.div
                    key={scenario.jurisdiction}
                    initial={{opacity: 0}}
                    animate={{opacity: 1}}
                    exit={{opacity: 0}}
                    transition={{duration: 0.25}}
                    className="relative h-full flex flex-col gap-2.5"
                >
                    {scenario.sources!.map((source, i) => (
                        <SingleSourceCard
                            key={source.title}
                            {...source}
                            showHighlights={showHighlights}
                            compact={true}
                        />
                    ))}
                </motion.div>
            </AnimatePresence>
        );
    }

    // Legacy single-document rendering
    const {pdfTitle, pdfArticleHeader, pdfClauses, highlightRange, sourceBadge, pageBadge} = scenario;
    return (
        <AnimatePresence mode="wait">
            <motion.div
                key={scenario.jurisdiction}
                initial={{opacity: 0}}
                animate={{opacity: 1}}
                exit={{opacity: 0}}
                transition={{duration: 0.25}}
                className="relative h-full flex flex-col"
            >
                <div className="absolute top-3 right-3 z-10 bg-[#1B2B4B] text-white text-[10px] font-mono px-2 py-0.5 rounded">
                    {pageBadge}
                </div>
                <div className="relative flex-1 bg-white rounded-xl shadow-lg overflow-hidden" style={{fontFamily: "Georgia, serif"}}>
                    <div className="p-5 h-full overflow-hidden text-[#1a1a1a]">
                        <div className="text-center mb-4">
                            <p className="text-[10px] font-bold tracking-widest text-[#333] uppercase mb-1">{pdfTitle}</p>
                            <div className="w-12 h-px bg-[#ccc] mx-auto"/>
                        </div>
                        <p className="text-[10px] font-bold text-[#1B2B4B] mb-2 uppercase tracking-wide">{pdfArticleHeader}</p>
                        {pdfClauses.map((clause, i) => {
                            const isHighlighted = i >= highlightRange[0] && i <= highlightRange[1];
                            return (
                                <div key={clause.id} className="relative mb-2">
                                    <p className="text-[10px] leading-[1.55] text-[#333] relative z-10">
                                        <span className="font-semibold">{clause.id}</span>{" "}{clause.text}
                                    </p>
                                    {isHighlighted && (
                                        <motion.div
                                            initial={{opacity: 0}}
                                            animate={{opacity: showHighlights ? 1 : 0}}
                                            transition={{duration: 0.4, delay: (i - highlightRange[0]) * 0.15}}
                                            className="absolute inset-0 rounded-sm pointer-events-none"
                                            style={{backgroundColor: "rgba(201, 168, 76, 0.22)", zIndex: 0}}
                                        />
                                    )}
                                </div>
                            );
                        })}
                        <motion.div
                            initial={{opacity: 0, y: 4}}
                            animate={{opacity: showHighlights ? 1 : 0, y: showHighlights ? 0 : 4}}
                            transition={{duration: 0.3, delay: 0.5}}
                            className="absolute bottom-3 left-3 right-3 flex items-center gap-1.5 bg-[#1B2B4B]/90 backdrop-blur-sm rounded-md px-2.5 py-1.5"
                        >
                            <div className="size-1.5 rounded-full bg-[#C9A84C] shrink-0"/>
                            <span className="text-[9px] text-white font-mono">{sourceBadge}</span>
                        </motion.div>
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
}
