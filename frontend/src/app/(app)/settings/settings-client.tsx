"use client";

import {useState, useEffect} from "react";
import {LogOut, User, Loader2, ChevronDown} from "lucide-react";
import {useColorMode} from "@/lib/color-mode";
import {motion} from "motion/react";
import {V3_LIST_VARIANT, V3_ITEM_VARIANT} from "@/lib/v3-motion";
import {useRouter} from "next/navigation";
import {useI18n, LOCALES, type Locale} from "@/lib/i18n";
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING} from "@/lib/tokens";

const API = process.env.NEXT_PUBLIC_SSE_URL ?? "";

const fontStack = FONT.sans;

type ThemeOption = "light" | "dark" | "system";

interface UserInfo {
    id: string;
    email: string;
    name: string | null;
    avatar_url: string | null;
    subscription_status: string;
    monthly_queries_used: number;
    max_corpora: number;
}

export default function SettingsPage() {
    const {isDark, mode, setMode} = useColorMode();
    const router = useRouter();
    const {t, locale, setLocale} = useI18n();
    const [user, setUser] = useState<UserInfo | null>(null);
    const [userLoading, setUserLoading] = useState(true);
    const [loggingOut, setLoggingOut] = useState(false);
    const [deleteConfirmEmail, setDeleteConfirmEmail] = useState("");
    const [deleting, setDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    useEffect(() => {
        fetch(`${API}/auth/me`, {credentials: "include"})
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => setUser(data))
            .catch(() => setUser(null))
            .finally(() => setUserLoading(false));
    }, []);

    const handleLogout = async () => {
        setLoggingOut(true);
        try {
            await fetch(`${API}/auth/logout`, {method: "POST", credentials: "include", headers: {"X-Requested-With": "XMLHttpRequest"}});
        } catch { /* ignore */
        }
        router.push("/");
    };

    const deleteEmailMatches =
        user != null &&
        deleteConfirmEmail.toLowerCase() === user.email.toLowerCase();

    const handleDeleteAccount = async () => {
        if (!deleteEmailMatches) return;
        setDeleting(true);
        setDeleteError(null);
        try {
            const res = await fetch(`${API}/auth/delete-account`, {
                method: "DELETE",
                credentials: "include",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            if (!res.ok && res.status !== 204) {
                const body = await res.json().catch(() => null);
                setDeleteError(
                    body?.detail || body?.message || `Deletion failed (${res.status})`
                );
                setDeleting(false);
                return;
            }
            localStorage.clear();
            router.push("/");
        } catch {
            setDeleteError("Cannot reach the server. Please try again.");
            setDeleting(false);
        }
    };

    const themeOptions: { value: ThemeOption; labelKey: string }[] = [
        {value: "light", labelKey: "settings.light"},
        {value: "dark", labelKey: "settings.dark"},
        {value: "system", labelKey: "settings.system"},
    ];

    // -- Light mode styles (unchanged) --

    const glassCardLight: React.CSSProperties = {
        background: "var(--dt-glass-bg)",
        backdropFilter: "var(--dt-glass-blur)",
        WebkitBackdropFilter: "var(--dt-glass-blur)",
        border: "0.5px solid var(--dt-glass-border-subtle)",
        borderRadius: "20px",
        boxShadow: "var(--dt-glass-inner-glow), var(--dt-glass-shadow)",
        overflow: "clip",
    };

    const cardHeaderLight: React.CSSProperties = {
        padding: "16px 20px",
        borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
    };

    const cardBodyLight: React.CSSProperties = {padding: "20px"};

    const cardHeadingLight: React.CSSProperties = {
        fontSize: "14px",
        fontWeight: 600,
        color: "var(--dt-text-primary)",
        fontFamily: fontStack,
        margin: 0,
    };

    const statusBadgeLight = (status: string): React.CSSProperties => {
        const isActive = status === "active" || status === "trial";
        return {
            background: isActive ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            border: isActive ? "0.5px solid rgba(34,197,94,0.30)" : "0.5px solid rgba(239,68,68,0.30)",
            color: isActive ? "#16a34a" : "#dc2626",
            borderRadius: "9999px",
            padding: "2px 10px",
            fontSize: "11px",
            fontWeight: 600,
            textTransform: "capitalize" as const,
        };
    };

    const themeButtonLight = (active: boolean): React.CSSProperties => ({
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        borderRadius: "10px",
        padding: "8px 16px",
        minHeight: "44px",
        fontSize: "13px",
        fontWeight: 500,
        fontFamily: fontStack,
        cursor: "pointer",
        transition: "all 0.15s ease",
        background: active ? "var(--dt-accent-tint-strong)" : "var(--dt-button-bg)",
        border: active
            ? "0.5px solid var(--dt-accent-border-color)"
            : "0.5px solid var(--dt-button-border-color)",
        color: active ? "var(--dt-accent-color)" : "var(--dt-text-tertiary)",
    });

    // -- Dark mode styles (mockup-matched) --

    // Compact setting group label
    const darkGroupLabel: React.CSSProperties = {
        fontFamily: fontStack,
        fontSize: "9px",
        lineHeight: 1,
        letterSpacing: "1.2px",
        textTransform: "uppercase" as const,
        color: "rgba(201,168,76,0.4)",
        marginBottom: "8px",
    };

    // Setting row: label + value side by side
    const darkSettingRow: React.CSSProperties = {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 0",
        borderBottom: "1px solid rgba(201,168,76,0.04)",
    };

    const darkSettingLabel: React.CSSProperties = {
        fontFamily: fontStack,
        fontSize: "12px",
        lineHeight: 1.3,
        color: "var(--strict-text-body, rgba(255,255,255,0.56))",
    };

    const darkSettingValue: React.CSSProperties = {
        fontFamily: fontStack,
        fontSize: "12px",
        lineHeight: 1,
        color: "rgba(200,210,230,0.42)",
    };

    // Small gold pill theme button
    const darkThemePill = (active: boolean): React.CSSProperties => ({
        padding: "4px 10px",
        minHeight: "44px",
        borderRadius: "5px",
        fontFamily: fontStack,
        fontSize: "10px",
        lineHeight: 1,
        border: active ? "1px solid rgba(201,168,76,0.15)" : "1px solid transparent",
        background: active ? "rgba(201,168,76,0.08)" : "transparent",
        color: active ? "rgba(201,168,76,0.7)" : "rgba(200,210,230,0.35)",
        cursor: "pointer",
        transition: "all 0.12s",
    });

    // Compact avatar circle
    const darkAvatar: React.CSSProperties = {
        width: "32px",
        height: "32px",
        borderRadius: "8px",
        background: "rgba(201,168,76,0.06)",
        border: "1px solid rgba(201,168,76,0.12)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
    };

    // Small red sign-out button
    const darkSignOutBtn: React.CSSProperties = {
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "6px 12px",
        borderRadius: "6px",
        background: "rgba(239,68,68,0.06)",
        border: "1px solid rgba(239,68,68,0.12)",
        fontFamily: fontStack,
        fontSize: "10px",
        lineHeight: 1,
        color: "#f87171",
        cursor: "pointer",
    };

    // Active badge (green)
    const darkActiveBadge: React.CSSProperties = {
        padding: "3px 8px",
        borderRadius: "4px",
        background: "rgba(34,197,94,0.08)",
        border: "1px solid rgba(34,197,94,0.15)",
        fontFamily: fontStack,
        fontSize: "9px",
        lineHeight: 1,
        color: "#4ade80",
        textTransform: "uppercase" as const,
        letterSpacing: "0.3px",
        marginLeft: "auto",
    };

    // Language select
    const darkSelect: React.CSSProperties = {
        padding: "4px 10px",
        borderRadius: "5px",
        background: "rgba(201,168,76,0.05)",
        border: "1px solid rgba(201,168,76,0.10)",
        fontFamily: fontStack,
        fontSize: "12px",
        color: "rgba(201,168,76,0.7)",
        cursor: "pointer",
        outline: "none",
    };

    // -- Dark mode account section --

    const renderDarkAccount = () => {
        if (userLoading) {
            return (
                <div style={{display: "flex", alignItems: "center", gap: 8, padding: "10px 0"}}>
                    <Loader2 size={14} style={{color: "var(--strict-text-dim)", animation: "spin 1s linear infinite"}}/>
                    <span style={{...darkSettingLabel, fontSize: "12px"}}>{t("settings.loading")}</span>
                </div>
            );
        }

        if (!user) {
            return (
                <div style={{padding: "10px 0", textAlign: "center"}}>
                    <a href="/login" style={{fontFamily: fontStack, fontSize: "12px", color: "rgba(201,168,76,0.7)", textDecoration: "underline"}}>
                        {t("settings.sign_in")}
                    </a>
                </div>
            );
        }

        const isActive = user.subscription_status === "active" || user.subscription_status === "trial";

        return (
            <div style={{display: "flex", flexDirection: "column", gap: 0}}>
                {/* Avatar + name + email + active badge row */}
                <div style={{display: "flex", alignItems: "center", gap: "10px", padding: "8px 0 10px"}}>
                    {user.avatar_url ? (
                        <img
                            src={user.avatar_url}
                            alt={user.name || user.email}
                            style={{...darkAvatar, borderRadius: "8px", objectFit: "cover"}}
                        />
                    ) : (
                        <div style={darkAvatar}>
                            <User size={14} style={{color: "rgba(201,168,76,0.7)"}}/>
                        </div>
                    )}
                    <div>
                        <div style={{fontFamily: fontStack, fontSize: "13px", lineHeight: 1.2, color: "rgba(230,235,245,0.88)"}}>
                            {user.name || user.email}
                        </div>
                        <div style={{fontFamily: fontStack, fontSize: "10px", lineHeight: 1.2, color: "rgba(200,210,230,0.30)"}}>
                            {user.email}
                        </div>
                    </div>
                    <div style={darkActiveBadge}>
                        {isActive ? "Active" : user.subscription_status}
                    </div>
                </div>

                {/* Plan row */}
                <div style={darkSettingRow}>
                    <span style={darkSettingLabel}>{t("settings.plan")}</span>
                    <span style={{...darkSettingValue, fontFamily: fontStack, color: "rgba(201,168,76,0.7)"}}>{user.subscription_status}</span>
                </div>

                {/* Sign out */}
                <div style={{paddingTop: "10px"}}>
                    <button
                        onClick={handleLogout}
                        disabled={loggingOut}
                        style={{...darkSignOutBtn, opacity: loggingOut ? 0.5 : 1, cursor: loggingOut ? "default" : "pointer"}}
                    >
                        <LogOut size={10}/>
                        {loggingOut ? t("settings.signing_out") : t("settings.sign_out")}
                    </button>
                </div>
            </div>
        );
    };

    // -- Dark mode delete section --

    const renderDarkDelete = () => {
        if (!user) return null;

        if (!showDeleteConfirm) {
            return (
                <div style={{textAlign: "center", paddingTop: "8px"}}>
                    <button
                        onClick={() => setShowDeleteConfirm(true)}
                        style={{
                            background: "none",
                            border: "none",
                            padding: "4px 8px",
                            fontFamily: fontStack,
                            fontSize: "10px",
                            lineHeight: 1,
                            color: "var(--strict-text-ghost, rgba(255,255,255,0.16))",
                            cursor: "pointer",
                            transition: "color 0.15s",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--strict-text-dim)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--strict-text-ghost, rgba(255,255,255,0.16))"; }}
                    >
                        {t("settings.delete_account")} ▾
                    </button>
                </div>
            );
        }

        return (
            <div
                style={{
                    border: "1px solid rgba(201,168,76,0.06)",
                    borderRadius: "8px",
                    padding: "10px 12px",
                    background: "rgba(248,113,113,0.03)",
                }}
            >
                <p style={{fontFamily: fontStack, fontSize: "10px", lineHeight: 1.5, color: "var(--strict-text-dim, rgba(200,210,230,0.22))", margin: "0 0 10px"}}>
                    {t("settings.delete_irreversible")}
                </p>
                <label style={{fontFamily: fontStack, fontSize: "10px", color: "var(--strict-text-dim, rgba(200,210,230,0.22))", display: "block", marginBottom: "5px"}}>
                    {t("settings.delete_type_email")}
                </label>
                <input
                    type="email"
                    value={deleteConfirmEmail}
                    onChange={(e) => {
                        setDeleteConfirmEmail(e.target.value);
                        setDeleteError(null);
                    }}
                    placeholder={user.email}
                    autoComplete="off"
                    style={{
                        width: "100%",
                        padding: "5px 8px",
                        borderRadius: "5px",
                        fontFamily: fontStack,
                        fontSize: "10px",
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(201,168,76,0.08)",
                        color: "var(--strict-text-primary)",
                        outline: "none",
                        boxSizing: "border-box",
                        marginBottom: "8px",
                        transition: "border-color 0.15s ease",
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = "rgba(201,168,76,0.25)"; }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = "rgba(201,168,76,0.08)"; }}
                />
                {deleteError && (
                    <p style={{fontFamily: fontStack, fontSize: "10px", color: "#f87171", margin: "0 0 8px"}}>
                        {deleteError}
                    </p>
                )}
                <div style={{display: "flex", gap: "8px", alignItems: "center"}}>
                    <button
                        onClick={handleDeleteAccount}
                        disabled={!deleteEmailMatches || deleting}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "5px 10px",
                            borderRadius: "5px",
                            fontFamily: fontStack,
                            fontSize: "10px",
                            background: deleteEmailMatches ? "rgba(248,113,113,0.10)" : "rgba(255,255,255,0.02)",
                            border: deleteEmailMatches ? "1px solid rgba(248,113,113,0.25)" : "1px solid rgba(201,168,76,0.06)",
                            color: deleteEmailMatches ? "#f87171" : "var(--strict-text-dim)",
                            cursor: deleteEmailMatches && !deleting ? "pointer" : "not-allowed",
                            opacity: deleting ? 0.5 : 1,
                            transition: "all 0.15s",
                        }}
                    >
                        {deleting ? <Loader2 size={10} style={{animation: "spin 1s linear infinite"}}/> : null}
                        {deleting ? t("settings.deleting") : t("settings.delete_permanently")}
                    </button>
                    <button
                        onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmEmail(""); setDeleteError(null); }}
                        disabled={deleting}
                        style={{
                            background: "none",
                            border: "none",
                            padding: "4px 8px",
                            fontFamily: fontStack,
                            fontSize: "10px",
                            color: "var(--strict-text-dim, rgba(200,210,230,0.22))",
                            cursor: deleting ? "not-allowed" : "pointer",
                        }}
                    >
                        {t("settings.cancel")}
                    </button>
                </div>
            </div>
        );
    };

    // -- Main render --

    return (
        <div
            style={{
                ...(isDark ? {
                    display: "flex",
                    flexDirection: "column" as const,
                    height: "100%",
                    overflow: "hidden",
                } : {
                    padding: "24px 16px 120px",
                    maxWidth: "640px",
                    margin: "0 auto",
                }),
            }}
        >
            {/* Page header */}
            {isDark ? (
                <div style={{
                    height: 44,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    padding: "0 20px",
                    borderBottom: "1px solid rgba(201,168,76, 0.06)",
                    background: "linear-gradient(180deg, rgba(255,255,255,0.015) 0%, transparent 100%)",
                }}>
                    <h1 style={{
                        fontFamily: fontStack,
                        fontSize: 14,
                        fontWeight: "normal",
                        color: "var(--strict-text-primary)",
                        margin: 0,
                    }}>
                        {t("settings.title")}
                    </h1>
                </div>
            ) : (
                <div style={{marginBottom: "24px"}}>
                    <h1 style={{fontFamily: fontStack, fontSize: "1.5rem", fontWeight: 700, color: "var(--dt-text-primary)", margin: 0}}>
                        {t("settings.title")}
                    </h1>
                    <p style={{color: "var(--dt-text-tertiary)", fontSize: "13px", fontFamily: fontStack, marginTop: "4px"}}>
                        {t("settings.subtitle")}
                    </p>
                </div>
            )}

            {/* Scrollable content */}
            <div style={{
                ...(isDark ? {
                    flex: 1,
                    overflowY: "auto" as const,
                    padding: "20px 28px",
                    maxWidth: 600,
                    width: "100%",
                    marginLeft: "auto",
                    marginRight: "auto",
                } : {}),
            }}>

                {/* ── DARK MODE ── */}
                {isDark && (
                    <motion.div
                        variants={V3_LIST_VARIANT}
                        initial="hidden"
                        animate="visible"
                        style={{display: "flex", flexDirection: "column", gap: "0px"}}
                    >
                        {/* Account group */}
                        <motion.div variants={V3_ITEM_VARIANT}>
                            <div>
                                <div style={darkGroupLabel}>{t("settings.account")}</div>
                                {renderDarkAccount()}
                            </div>
                        </motion.div>

                        {/* Gold separator */}
                        <div style={{height: "1px", background: "linear-gradient(90deg, rgba(201,168,76,0.12), rgba(201,168,76,0.03))", margin: "24px 0"}} />

                        {/* Appearance group */}
                        <motion.div variants={V3_ITEM_VARIANT}>
                            <div>
                                <div style={darkGroupLabel}>{t("settings.appearance")}</div>

                                {/* Theme row */}
                                <div style={darkSettingRow}>
                                    <span style={darkSettingLabel}>{t("settings.theme")}</span>
                                    <div style={{display: "flex", gap: "4px"}}>
                                        {themeOptions.map((opt) => (
                                            <button
                                                key={opt.value}
                                                onClick={() => setMode(opt.value)}
                                                aria-pressed={mode === opt.value}
                                                style={darkThemePill(mode === opt.value)}
                                                onMouseEnter={(e) => {
                                                    if (mode !== opt.value) {
                                                        e.currentTarget.style.borderColor = "rgba(201,168,76,0.08)";
                                                        e.currentTarget.style.background = "rgba(201,168,76,0.03)";
                                                    }
                                                }}
                                                onMouseLeave={(e) => {
                                                    if (mode !== opt.value) {
                                                        e.currentTarget.style.borderColor = "transparent";
                                                        e.currentTarget.style.background = "transparent";
                                                    }
                                                }}
                                            >
                                                {t(opt.labelKey)}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Language row */}
                                <div style={{...darkSettingRow, borderBottom: "none"}}>
                                    <span style={darkSettingLabel}>{t("settings.language")}</span>
                                    <select
                                        style={darkSelect}
                                        value={locale}
                                        onChange={(e) => setLocale(e.target.value as Locale)}
                                    >
                                        {LOCALES.map((l) => (
                                            <option key={l.code} value={l.code}>
                                                {l.flag} {l.label}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </motion.div>

                        {/* Gold separator */}
                        <div style={{height: "1px", background: "linear-gradient(90deg, rgba(201,168,76,0.12), rgba(201,168,76,0.03))", margin: "24px 0"}} />

                        {/* Delete account (ghost link at bottom) */}
                        <motion.div variants={V3_ITEM_VARIANT}>
                            {renderDarkDelete()}
                        </motion.div>
                    </motion.div>
                )}

                {/* ── LIGHT MODE ── */}
                {!isDark && (
                    <div style={{display: "flex", flexDirection: "column", gap: "20px"}}>
                        {/* Account card */}
                        <div style={glassCardLight}>
                            <div style={cardHeaderLight}>
                                <h2 style={cardHeadingLight}>{t("settings.account")}</h2>
                            </div>
                            <div style={cardBodyLight}>
                                {userLoading ? (
                                    <div style={{display: "flex", alignItems: "center", gap: 8}}>
                                        <Loader2 size={16} style={{color: "var(--dt-text-tertiary)", animation: "spin 1s linear infinite"}}/>
                                        <span style={{fontSize: 13, color: "var(--dt-text-tertiary)", fontFamily: fontStack}}>{t("settings.loading")}</span>
                                    </div>
                                ) : user ? (
                                    <div style={{display: "flex", flexDirection: "column", gap: 16}}>
                                        <div style={{display: "flex", alignItems: "center", gap: 14}}>
                                            {user.avatar_url ? (
                                                <img src={user.avatar_url} alt={user.name || user.email} style={{width: 44, height: 44, borderRadius: 12, border: "0.5px solid var(--dt-glass-border)"}}/>
                                            ) : (
                                                <div style={{width: 44, height: 44, borderRadius: 12, background: "var(--dt-accent-tint)", border: "0.5px solid var(--dt-accent-border-color)", display: "flex", alignItems: "center", justifyContent: "center"}}>
                                                    <User size={20} style={{color: "var(--dt-accent-color)"}}/>
                                                </div>
                                            )}
                                            <div>
                                                <p style={{fontSize: 15, fontWeight: 600, color: "var(--dt-text-primary)", fontFamily: fontStack, margin: 0}}>{user.name || user.email}</p>
                                                <p style={{fontSize: 12, color: "var(--dt-text-quaternary)", fontFamily: fontStack, margin: "2px 0 0"}}>{user.email}</p>
                                            </div>
                                        </div>
                                        <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                                            <span style={{fontSize: 12, color: "var(--dt-text-quaternary)", fontFamily: fontStack}}>{t("settings.plan")}</span>
                                            <span style={statusBadgeLight(user.subscription_status)}>{user.subscription_status}</span>
                                        </div>
                                        <button
                                            onClick={handleLogout}
                                            disabled={loggingOut}
                                            style={{display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "9px 16px", borderRadius: 10, fontSize: 13, fontWeight: 500, fontFamily: fontStack, background: "rgba(239,68,68,0.10)", border: "0.5px solid rgba(239,68,68,0.25)", color: "#dc2626", cursor: loggingOut ? "default" : "pointer", opacity: loggingOut ? 0.5 : 1, transition: "opacity 0.15s", alignSelf: "flex-start"}}
                                        >
                                            <LogOut size={14}/>
                                            {loggingOut ? t("settings.signing_out") : t("settings.sign_out")}
                                        </button>
                                    </div>
                                ) : (
                                    <div style={{textAlign: "center", padding: "12px 0"}}>
                                        <p style={{fontSize: 13, color: "var(--dt-text-tertiary)", fontFamily: fontStack, margin: "0 0 12px"}}>{t("settings.not_signed_in")}</p>
                                        <a href="/login" style={{display: "inline-flex", alignItems: "center", gap: 6, padding: "9px 20px", borderRadius: 10, fontSize: 13, fontWeight: 600, fontFamily: fontStack, background: "var(--dt-accent-solid)", color: "#fff8ee", textDecoration: "none", boxShadow: "0 2px 12px var(--dt-accent-glow)"}}>
                                            {t("settings.sign_in")}
                                        </a>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Appearance card */}
                        <div style={glassCardLight}>
                            <div style={cardHeaderLight}>
                                <h2 style={cardHeadingLight}>{t("settings.appearance")}</h2>
                            </div>
                            <div style={cardBodyLight}>
                                <div style={{display: "flex", flexDirection: "column", gap: "20px"}}>
                                    <div>
                                        <span style={{fontSize: "12px", fontWeight: 500, color: "var(--dt-text-tertiary)", fontFamily: fontStack, marginBottom: "6px", display: "block"}}>{t("settings.theme")}</span>
                                        <div style={{display: "flex", gap: "8px", marginTop: "2px"}}>
                                            {themeOptions.map((opt) => (
                                                <button
                                                    key={opt.value}
                                                    onClick={() => setMode(opt.value)}
                                                    aria-pressed={mode === opt.value}
                                                    style={themeButtonLight(mode === opt.value)}
                                                >
                                                    {t(opt.labelKey)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Delete account */}
                        {user && (
                            <div style={{marginTop: SPACE["4"], display: "flex", flexDirection: "column", alignItems: "center"}}>
                                {!showDeleteConfirm ? (
                                    <button
                                        onClick={() => setShowDeleteConfirm(true)}
                                        style={{display: "inline-flex", alignItems: "center", gap: SPACE["1"], background: "none", border: "none", padding: `${SPACE["2"]}px ${SPACE["3"]}px`, fontSize: TYPE_SCALE.xs, fontFamily: fontStack, fontWeight: 400, color: "var(--dt-text-quaternary)", cursor: "pointer", transition: `color ${TIMING.fast}`}}
                                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--dt-text-tertiary)"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--dt-text-quaternary)"; }}
                                    >
                                        {t("settings.delete_account")}
                                        <ChevronDown size={12}/>
                                    </button>
                                ) : (
                                    <div style={{...glassCardLight, width: "100%"}}>
                                        <div style={cardBodyLight}>
                                            <div style={{display: "flex", flexDirection: "column", gap: SPACE["4"]}}>
                                                <p style={{fontSize: TYPE_SCALE.sm, fontWeight: 500, color: "var(--dt-text-tertiary)", fontFamily: fontStack, margin: 0, lineHeight: 1.5}}>
                                                    {t("settings.delete_irreversible")}
                                                </p>
                                                <div>
                                                    <label style={{fontSize: "12px", fontWeight: 500, color: "var(--dt-text-tertiary)", fontFamily: fontStack, marginBottom: "6px", display: "block"}}>
                                                        {t("settings.delete_type_email")}
                                                    </label>
                                                    <input
                                                        type="email"
                                                        value={deleteConfirmEmail}
                                                        onChange={(e) => { setDeleteConfirmEmail(e.target.value); setDeleteError(null); }}
                                                        placeholder={user.email}
                                                        autoComplete="off"
                                                        style={{width: "100%", padding: `${SPACE["3"]}px ${SPACE["4"]}px`, borderRadius: RADIUS.lg, fontSize: TYPE_SCALE.sm, fontFamily: fontStack, background: "var(--dt-glass-bg-subtle)", border: "0.5px solid var(--dt-glass-border-subtle)", color: "var(--dt-text-primary)", outline: "none", boxSizing: "border-box", transition: "border-color 0.15s ease"}}
                                                    />
                                                </div>
                                                {deleteError && (
                                                    <p style={{fontSize: TYPE_SCALE.xs, color: "var(--dt-text-tertiary)", fontFamily: fontStack, margin: 0}}>{deleteError}</p>
                                                )}
                                                <div style={{display: "flex", gap: SPACE["3"], alignSelf: "flex-start"}}>
                                                    <button
                                                        onClick={handleDeleteAccount}
                                                        disabled={!deleteEmailMatches || deleting}
                                                        style={{display: "inline-flex", alignItems: "center", justifyContent: "center", gap: SPACE["2"], padding: `${SPACE["3"]}px ${SPACE["5"]}px`, borderRadius: RADIUS.lg, fontSize: TYPE_SCALE.sm, fontWeight: 600, fontFamily: fontStack, background: deleteEmailMatches ? "var(--dt-glass-bg-hover)" : "var(--dt-glass-bg-subtle)", border: deleteEmailMatches ? "0.5px solid var(--dt-glass-border)" : "0.5px solid var(--dt-glass-border-subtle)", color: deleteEmailMatches ? "var(--dt-text-secondary)" : "var(--dt-text-quaternary)", cursor: deleteEmailMatches && !deleting ? "pointer" : "not-allowed", opacity: deleting ? 0.5 : 1, transition: `all ${TIMING.fast}`}}
                                                    >
                                                        {deleting ? <><Loader2 size={14} style={{animation: "spin 1s linear infinite"}}/>{t("settings.deleting")}</> : t("settings.delete_permanently")}
                                                    </button>
                                                    <button
                                                        onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmEmail(""); setDeleteError(null); }}
                                                        disabled={deleting}
                                                        style={{display: "inline-flex", alignItems: "center", justifyContent: "center", padding: `${SPACE["3"]}px ${SPACE["5"]}px`, borderRadius: RADIUS.lg, fontSize: TYPE_SCALE.sm, fontWeight: 500, fontFamily: fontStack, background: "var(--dt-glass-bg-subtle)", border: "0.5px solid var(--dt-glass-border-subtle)", color: "var(--dt-text-tertiary)", cursor: deleting ? "not-allowed" : "pointer", transition: `opacity ${TIMING.fast}`}}
                                                    >
                                                        {t("settings.cancel")}
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
