"use client";

import { useState } from "react";
import {useI18n} from "@/lib/i18n";
import {useColorMode} from "@/lib/color-mode";

interface PlannedIndex {
    id: string;
    flag: string;
    name: string;
    jurisdiction: string;
    description: string;
    passages: string;
}

interface CorpusStatute {
    file: string;
    nameLocal: string;
    nameEn: string;
}

const PLANNED_INDEXES: PlannedIndex[] = [
    {
        id: "difc",
        flag: "🇦🇪",
        name: "DIFC Legal Corpus",
        jurisdiction: "Dubai International Financial Centre",
        description: "DIFC statutes, regulations, court rules, and reported case law.",
        passages: "11,556 passages",
    },
    {
        id: "czech-civil",
        flag: "🇨🇿",
        name: "Czech Legal Corpus",
        jurisdiction: "Czech Republic",
        description: "Czech civil, labour, criminal, tax, and administrative law.",
        passages: "6,826 passages",
    },
    {
        id: "uk",
        flag: "🇬🇧",
        name: "UK Legal Corpus",
        jurisdiction: "United Kingdom",
        description: "Companies Act, Employment Rights, Consumer Rights, Data Protection, and more.",
        passages: "5,063 passages",
    },
    {
        id: "au",
        flag: "🇦🇺",
        name: "Australian Legal Corpus",
        jurisdiction: "Australia",
        description: "Corporations Act, Fair Work, Consumer Law, Privacy Act, and more.",
        passages: "20,488 passages",
    },
];

const CORPUS_STATUTES: Record<string, CorpusStatute[]> = {
    "czech-civil": [
        { file: "obcansky_zakonik.txt",           nameLocal: "Občanský zákoník",               nameEn: "Civil Code" },
        { file: "zakonik_prace.txt",              nameLocal: "Zákoník práce",                  nameEn: "Labour Code" },
        { file: "trestni_zakonik.txt",            nameLocal: "Trestní zákoník",                nameEn: "Criminal Code" },
        { file: "danovy_rad.txt",                 nameLocal: "Daňový řád",                     nameEn: "Tax Code" },
        { file: "zakon_dane_prijmu.txt",          nameLocal: "Zákon o daních z příjmů",        nameEn: "Income Tax Act" },
        { file: "zakon_dph.txt",                  nameLocal: "Zákon o DPH",                    nameEn: "VAT Act" },
        { file: "zakon_duchodove_pojisteni.txt",  nameLocal: "Zákon o důchodovém pojištění",   nameEn: "Pension Insurance Act" },
        { file: "zakon_nemocenske_pojisteni.txt", nameLocal: "Zákon o nemocenském pojištění",  nameEn: "Sickness Insurance Act" },
        { file: "zakon_obch_korporace.txt",       nameLocal: "Zákon o obchodních korporacích", nameEn: "Business Corporations Act" },
        { file: "spravni_rad.txt",                nameLocal: "Správní řád",                    nameEn: "Administrative Procedure Code" },
        { file: "zivnostensky_zakon.txt",         nameLocal: "Živnostenský zákon",             nameEn: "Trade Licensing Act" },
    ],
};

export function LegalIndexLibrary() {
    const {t} = useI18n();
    const {isDark} = useColorMode();
    const [expandedCorpusId, setExpandedCorpusId] = useState<string | null>(null);

    const toggleExpanded = (id: string) => {
        setExpandedCorpusId(id === expandedCorpusId ? null : id);
    };

    // ── Dark mode: compact list, mockup aesthetic ─────────────────────────────
    if (isDark) {
        return (
            <div style={{display: "flex", flexDirection: "column", gap: "0"}}>
                {/* Section label */}
                <div style={{
                    fontSize: "9px", fontFamily: "system-ui, sans-serif",
                    letterSpacing: "1.2px", textTransform: "uppercase",
                    color: "rgba(201,168,76,0.4)", marginBottom: "14px",
                }}>
                    {t("documents.library_title")}
                </div>

                {/* Cards — flex wrap */}
                <div style={{display: "flex", flexWrap: "wrap", gap: "8px"}}>
                    {PLANNED_INDEXES.map((idx) => {
                        const hasStatutes = Boolean(CORPUS_STATUTES[idx.id]);
                        const isExpanded = expandedCorpusId === idx.id;

                        return (
                            <div
                                key={idx.id}
                                style={{
                                    padding: "8px 14px",
                                    borderRadius: "8px",
                                    border: "1px solid rgba(201,168,76,0.06)",
                                    background: "rgba(255,255,255,0.015)",
                                    display: "flex", alignItems: "center", gap: "8px",
                                    transition: "background 0.12s, border-color 0.12s",
                                    cursor: hasStatutes ? "pointer" : "default",
                                }}
                                onClick={hasStatutes ? () => toggleExpanded(idx.id) : undefined}
                                onKeyDown={hasStatutes ? (e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        toggleExpanded(idx.id);
                                    }
                                } : undefined}
                                role={hasStatutes ? "button" : undefined}
                                tabIndex={hasStatutes ? 0 : undefined}
                                aria-expanded={hasStatutes ? isExpanded : undefined}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = "rgba(201,168,76,0.02)";
                                    e.currentTarget.style.borderColor = "rgba(201,168,76,0.12)";
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = "rgba(255,255,255,0.015)";
                                    e.currentTarget.style.borderColor = "rgba(201,168,76,0.06)";
                                }}
                            >
                                {/* Flag */}
                                <span style={{fontSize: "14px", lineHeight: 1, flexShrink: 0}} role="img" aria-label={idx.jurisdiction}>
                                    {idx.flag}
                                </span>

                                {/* Name + optional chevron */}
                                <span style={{
                                    fontSize: "12px", lineHeight: 1.3, fontFamily: "Georgia, serif",
                                    color: "rgba(230,235,245,0.88)", opacity: 0.7,
                                    whiteSpace: "nowrap",
                                }}>
                                    {idx.name}
                                    {hasStatutes && (
                                        <span aria-hidden="true" style={{marginLeft: "4px", fontSize: "10px", fontFamily: "system-ui, sans-serif"}}>
                                            {isExpanded ? "\u25be" : "\u25b8"}
                                        </span>
                                    )}
                                </span>

                                {/* Passage count */}
                                <span style={{
                                    fontSize: "9px", lineHeight: 1, fontFamily: "system-ui, sans-serif",
                                    color: "rgba(200,210,230,0.22)", flexShrink: 0,
                                    fontVariantNumeric: "tabular-nums",
                                }}>
                                    {idx.passages}
                                </span>
                            </div>
                        );
                    })}
                </div>

                {/* Statute detail panel — shown below the card row when expanded */}
                {expandedCorpusId && CORPUS_STATUTES[expandedCorpusId] && (
                    <div style={{
                        background: "rgba(255,255,255,0.025)",
                        border: "1px solid rgba(201,168,76,0.08)",
                        borderRadius: "8px",
                        padding: "10px 14px",
                        marginTop: "8px",
                    }}>
                        {CORPUS_STATUTES[expandedCorpusId].map((s) => (
                            <div key={s.file} style={{display: "flex", justifyContent: "space-between", alignItems: "baseline", padding: "3px 0"}}>
                                <span style={{
                                    fontSize: "11px", fontFamily: "Georgia, serif",
                                    color: "rgba(230,235,245,0.75)",
                                }}>
                                    {s.nameLocal}
                                </span>
                                <span style={{
                                    fontSize: "10px", fontFamily: "system-ui, sans-serif",
                                    color: "rgba(200,210,230,0.40)",
                                }}>
                                    {s.nameEn}
                                </span>
                            </div>
                        ))}
                    </div>
                )}

                <div style={{
                    fontSize: "9px", fontFamily: "system-ui, sans-serif",
                    color: "rgba(200,210,230,0.22)", marginTop: "10px", lineHeight: 1.5,
                }}>
                    {t("documents.library_footer")}
                </div>
            </div>
        );
    }

    // ── Light mode: original design unchanged ─────────────────────────────────
    const fontStack = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";
    const labelColor = "rgba(46,31,8,0.45)";

    const glassCard: React.CSSProperties = {
        background: "rgba(255,250,235,0.22)",
        backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        border: "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: "20px",
        boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    return (
        <div style={glassCard}>
            <div style={{borderBottom: "0.5px solid rgba(255,255,255,0.30)", padding: "16px 20px", display: "flex", alignItems: "center", gap: "8px"}}>
                <div>
                    <h2 style={{fontSize: "14px", fontWeight: 600, color: "#1e1208", margin: 0, fontFamily: fontStack}}>
                        {t("documents.library_title")}
                    </h2>
                    <p style={{fontSize: "11px", color: labelColor, margin: "2px 0 0", fontFamily: fontStack}}>
                        {t("documents.library_subtitle")}
                    </p>
                </div>
            </div>
            <div style={{padding: "16px 20px", display: "flex", flexDirection: "column", gap: "10px", fontFamily: fontStack}}>
                {PLANNED_INDEXES.map((idx) => {
                    const hasStatutes = Boolean(CORPUS_STATUTES[idx.id]);
                    const isExpanded = expandedCorpusId === idx.id;

                    return (
                        <div key={idx.id}>
                            <div
                                style={{display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(255,255,255,0.14)", border: "0.5px solid rgba(255,255,255,0.28)", borderRadius: "12px", padding: "12px 16px", gap: "12px", opacity: 0.72, cursor: hasStatutes ? "pointer" : "default"}}
                                onClick={hasStatutes ? () => toggleExpanded(idx.id) : undefined}
                                onKeyDown={hasStatutes ? (e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        toggleExpanded(idx.id);
                                    }
                                } : undefined}
                                role={hasStatutes ? "button" : undefined}
                                tabIndex={hasStatutes ? 0 : undefined}
                                aria-expanded={hasStatutes ? isExpanded : undefined}
                            >
                                <div style={{display: "flex", alignItems: "center", gap: "12px", minWidth: 0}}>
                                    <span style={{fontSize: "22px", lineHeight: 1, flexShrink: 0}} role="img" aria-label={idx.jurisdiction}>{idx.flag}</span>
                                    <div style={{minWidth: 0}}>
                                        <div style={{fontSize: "13px", fontWeight: 600, color: "#1e1208", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis"}}>
                                            {idx.name}
                                            {hasStatutes && (
                                                <span aria-hidden="true" style={{marginLeft: "5px", fontSize: "10px", fontFamily: fontStack}}>
                                                    {isExpanded ? "\u25be" : "\u25b8"}
                                                </span>
                                            )}
                                        </div>
                                        <div style={{fontSize: "11px", color: labelColor, marginTop: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis"}}>{idx.description}</div>
                                    </div>
                                </div>
                                <div style={{display: "flex", alignItems: "center", gap: "10px", flexShrink: 0}}>
                                    <span style={{fontSize: "11px", color: labelColor, fontVariantNumeric: "tabular-nums"}}>{idx.passages}</span>
                                    <span style={{fontSize: "10px", fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.06em", color: "#16a34a", background: "rgba(34,197,94,0.08)", border: "0.5px solid rgba(34,197,94,0.20)", borderRadius: "6px", padding: "3px 8px", whiteSpace: "nowrap" as const}}>
                                        {t("documents.index_status_active")}
                                    </span>
                                </div>
                            </div>

                            {/* Statute detail panel — shown immediately after the row */}
                            {isExpanded && CORPUS_STATUTES[idx.id] && (
                                <div style={{
                                    background: "rgba(255,255,255,0.10)",
                                    border: "0.5px solid rgba(255,255,255,0.22)",
                                    borderRadius: "10px",
                                    padding: "10px 14px",
                                    marginTop: "-2px",
                                }}>
                                    {CORPUS_STATUTES[idx.id].map((s) => (
                                        <div key={s.file} style={{display: "flex", justifyContent: "space-between", alignItems: "baseline", padding: "3px 0"}}>
                                            <span style={{fontSize: "13px", color: "#1e1208", fontWeight: 500, fontFamily: fontStack}}>
                                                {s.nameLocal}
                                            </span>
                                            <span style={{fontSize: "11px", color: "rgba(46,31,8,0.45)", fontFamily: fontStack}}>
                                                {s.nameEn}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    );
                })}
                <p style={{fontSize: "11px", color: labelColor, margin: "4px 0 0", lineHeight: 1.5}}>{t("documents.library_footer")}</p>
            </div>
        </div>
    );
}
