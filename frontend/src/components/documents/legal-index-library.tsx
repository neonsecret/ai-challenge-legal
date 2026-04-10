"use client";

import {Library} from "lucide-react";
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
    const fontStack =
        "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

    const labelColor = isDark ? "var(--strict-text-dim, rgba(255,255,255,0.40))" : "rgba(46,31,8,0.45)";

    const cardHeaderSep: React.CSSProperties = {
        borderBottom: isDark
            ? "0.5px solid rgba(201,168,76,0.06)"
            : "0.5px solid rgba(255,255,255,0.30)",
    };

    const glassCard: React.CSSProperties = {
        background: isDark
            ? "rgba(255,255,255,0.02)"
            : "rgba(255,250,235,0.22)",
        backdropFilter: isDark ? "blur(24px)" : "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: isDark ? "blur(24px)" : "blur(32px) saturate(180%) brightness(106%)",
        border: isDark
            ? "0.5px solid rgba(201,168,76,0.06)"
            : "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: isDark ? "14px" : "20px",
        boxShadow: isDark
            ? "0 2px 16px rgba(0,0,0,0.45), inset 0 1px 0 rgba(201,168,76,0.04)"
            : "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    return (
        <div style={glassCard}>
            {/* Header */}
            <div
                style={{
                    ...cardHeaderSep,
                    padding: "16px 20px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                }}
            >
                <Library
                    size={16}
                    style={{color: isDark ? "#C9A84C" : "rgba(46,31,8,0.45)"}}
                />
                <div>
                    <h2
                        style={{
                            fontSize: "14px",
                            fontWeight: 600,
                            color: isDark ? "var(--strict-text-primary, rgba(255,255,255,0.92))" : "#1e1208",
                            margin: 0,
                            fontFamily: fontStack,
                        }}
                    >
                        {t("documents.library_title")}
                    </h2>
                    <p
                        style={{
                            fontSize: "11px",
                            color: labelColor,
                            margin: "2px 0 0",
                            fontFamily: fontStack,
                        }}
                    >
                        {t("documents.library_subtitle")}
                    </p>
                </div>
            </div>

            {/* Index cards */}
            <div
                style={{
                    padding: "16px 20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                    fontFamily: fontStack,
                }}
            >
                {PLANNED_INDEXES.map((idx) => (
                    <div
                        key={idx.id}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            background: isDark
                                ? "rgba(255,255,255,0.02)"
                                : "rgba(255,255,255,0.14)",
                            border: isDark
                                ? "0.5px solid rgba(201,168,76,0.06)"
                                : "0.5px solid rgba(255,255,255,0.28)",
                            borderRadius: isDark ? "10px" : "12px",
                            padding: "12px 16px",
                            gap: "12px",
                            opacity: isDark ? 1 : 0.72,
                        }}
                    >
                        {/* Left: flag + text */}
                        <div style={{display: "flex", alignItems: "center", gap: "12px", minWidth: 0}}>
              <span
                  style={{fontSize: "22px", lineHeight: 1, flexShrink: 0}}
                  role="img"
                  aria-label={idx.jurisdiction}
              >
                {idx.flag}
              </span>
                            <div style={{minWidth: 0}}>
                                <div
                                    style={{
                                        fontSize: "13px",
                                        fontWeight: 600,
                                        color: isDark ? "var(--strict-text-primary, rgba(255,255,255,0.92))" : "#1e1208",
                                        whiteSpace: "nowrap",
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                    }}
                                >
                                    {idx.name}
                                </div>
                                <div
                                    style={{
                                        fontSize: "11px",
                                        color: labelColor,
                                        marginTop: "2px",
                                        whiteSpace: "nowrap",
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                    }}
                                >
                                    {idx.description}
                                </div>
                            </div>
                        </div>

                        {/* Right: passage count + coming soon badge */}
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                                flexShrink: 0,
                            }}
                        >
              <span
                  style={{
                      fontSize: "11px",
                      color: labelColor,
                      fontVariantNumeric: "tabular-nums",
                  }}
              >
                {idx.passages}
              </span>
                            <span
                                style={{
                                    fontSize: "10px",
                                    fontWeight: 600,
                                    textTransform: "uppercase" as const,
                                    letterSpacing: "0.06em",
                                    color: isDark ? "#4ade80" : "#16a34a",
                                    background: isDark
                                        ? "rgba(34,197,94,0.10)"
                                        : "rgba(34,197,94,0.08)",
                                    border: isDark
                                        ? "0.5px solid rgba(34,197,94,0.25)"
                                        : "0.5px solid rgba(34,197,94,0.20)",
                                    borderRadius: "6px",
                                    padding: "3px 8px",
                                    whiteSpace: "nowrap" as const,
                                }}
                            >
                                {t("documents.index_status_active")}
                            </span>
                        </div>
                    </div>
                ))}

                <p
                    style={{
                        fontSize: "11px",
                        color: labelColor,
                        margin: "4px 0 0",
                        lineHeight: 1.5,
                    }}
                >
                    {t("documents.library_footer")}
                </p>
            </div>
        </div>
    );
}
