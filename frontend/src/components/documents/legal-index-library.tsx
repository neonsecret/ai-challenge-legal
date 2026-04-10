"use client";

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

export function LegalIndexLibrary() {
    const {t} = useI18n();
    const {isDark} = useColorMode();

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
                    {PLANNED_INDEXES.map((idx) => (
                        <div
                            key={idx.id}
                            style={{
                                padding: "8px 14px",
                                borderRadius: "8px",
                                border: "1px solid rgba(201,168,76,0.06)",
                                background: "rgba(255,255,255,0.015)",
                                display: "flex", alignItems: "center", gap: "8px",
                                transition: "background 0.12s, border-color 0.12s",
                            }}
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

                            {/* Name */}
                            <span style={{
                                fontSize: "12px", lineHeight: 1.3, fontFamily: "Georgia, serif",
                                color: "rgba(230,235,245,0.88)", opacity: 0.7,
                                whiteSpace: "nowrap",
                            }}>
                                {idx.name}
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
                    ))}
                </div>

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
                {PLANNED_INDEXES.map((idx) => (
                    <div key={idx.id} style={{display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(255,255,255,0.14)", border: "0.5px solid rgba(255,255,255,0.28)", borderRadius: "12px", padding: "12px 16px", gap: "12px", opacity: 0.72}}>
                        <div style={{display: "flex", alignItems: "center", gap: "12px", minWidth: 0}}>
                            <span style={{fontSize: "22px", lineHeight: 1, flexShrink: 0}} role="img" aria-label={idx.jurisdiction}>{idx.flag}</span>
                            <div style={{minWidth: 0}}>
                                <div style={{fontSize: "13px", fontWeight: 600, color: "#1e1208", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis"}}>{idx.name}</div>
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
                ))}
                <p style={{fontSize: "11px", color: labelColor, margin: "4px 0 0", lineHeight: 1.5}}>{t("documents.library_footer")}</p>
            </div>
        </div>
    );
}
