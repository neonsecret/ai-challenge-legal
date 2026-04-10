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
                    fontSize: "7px", fontFamily: "system-ui, sans-serif",
                    letterSpacing: "1px", textTransform: "uppercase",
                    color: "rgba(200,210,230,0.22)", marginBottom: "6px",
                }}>
                    {t("documents.library_title")}
                </div>

                {PLANNED_INDEXES.map((idx, i) => (
                    <div key={idx.id}>
                        {/* Subtle separator between items */}
                        {i > 0 && (
                            <div style={{height: "1px", background: "rgba(201,168,76,0.03)", margin: "0 4px"}} />
                        )}
                        <div style={{
                            display: "flex", alignItems: "center", gap: "8px",
                            padding: "5px 8px", borderRadius: "6px",
                            transition: "background 0.12s",
                        }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(201,168,76,0.02)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                        >
                            {/* Flag */}
                            <span style={{fontSize: "13px", lineHeight: 1, flexShrink: 0}} role="img" aria-label={idx.jurisdiction}>
                                {idx.flag}
                            </span>

                            {/* Name */}
                            <span style={{
                                flex: 1, font: "11px/1.3 Georgia, serif",
                                color: "rgba(255,255,255,0.56)",
                                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            }}>
                                {idx.name}
                            </span>

                            {/* Passage count */}
                            <span style={{
                                font: "9px/1 system-ui, sans-serif",
                                color: "var(--strict-text-dim)", flexShrink: 0,
                                fontVariantNumeric: "tabular-nums",
                            }}>
                                {idx.passages}
                            </span>

                            {/* Active badge */}
                            <span style={{
                                font: "7px/1 system-ui, sans-serif",
                                textTransform: "uppercase", letterSpacing: "0.3px",
                                color: "#4ade80",
                                background: "rgba(34,197,94,0.08)",
                                border: "1px solid rgba(34,197,94,0.15)",
                                borderRadius: "3px", padding: "2px 5px",
                                flexShrink: 0,
                            }}>
                                {t("documents.index_status_active")}
                            </span>
                        </div>
                    </div>
                ))}

                <div style={{
                    fontSize: "7px", fontFamily: "system-ui, sans-serif",
                    color: "rgba(200,210,230,0.16)", marginTop: "6px", lineHeight: 1.5,
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
