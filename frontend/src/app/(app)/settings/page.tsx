"use client";

import {useState, useEffect} from "react";
import {Moon, Sun, Monitor, LogOut, User, Loader2, ChevronDown} from "lucide-react";
import {useTheme} from "@/lib/theme";
import {useDesignVersion} from "@/lib/design-version";
import {motion} from "motion/react";
import {V3_LIST_VARIANT, V3_ITEM_VARIANT} from "@/lib/v3-motion";
import {useRouter} from "next/navigation";
import {useI18n} from "@/lib/i18n";
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING} from "@/lib/design-tokens";

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
    const {theme, setTheme, resolvedTheme} = useTheme();
    const {version: designVersion} = useDesignVersion();
    const router = useRouter();
    const {t} = useI18n();
    const [mounted, setMounted] = useState(false);
    const [user, setUser] = useState<UserInfo | null>(null);
    const [userLoading, setUserLoading] = useState(true);
    const [loggingOut, setLoggingOut] = useState(false);
    const [deleteConfirmEmail, setDeleteConfirmEmail] = useState("");
    const [deleting, setDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const isDark = mounted && resolvedTheme === "dark";
    const isV3 = mounted && designVersion === "v3";

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
            // Clear all localStorage and redirect to landing
            localStorage.clear();
            router.push("/");
        } catch {
            setDeleteError("Cannot reach the server. Please try again.");
            setDeleting(false);
        }
    };

    const themeOptions: { value: ThemeOption; labelKey: string; icon: React.ReactNode }[] = [
        {value: "light", labelKey: "settings.light", icon: <Sun size={16}/>},
        {value: "dark", labelKey: "settings.dark", icon: <Moon size={16}/>},
        {value: "system", labelKey: "settings.system", icon: <Monitor size={16}/>},
    ];

    const glassCard: React.CSSProperties = isV3 ? {
        borderRadius: "16px",
        overflow: "clip",
    } : {
        background: isDark
            ? "rgba(255,255,255,0.06)"
            : "rgba(255,250,235,0.22)",
        backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
        border: isDark
            ? "0.5px solid rgba(255,255,255,0.12)"
            : "0.5px solid rgba(255,255,255,0.38)",
        borderRadius: "20px",
        boxShadow: isDark
            ? "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 32px rgba(0,0,0,0.30)"
            : "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
        overflow: "clip",
    };

    const glassCardClass = isV3 ? "v3-glass-elevated" : "";

    const cardHeader: React.CSSProperties = {
        padding: "16px 20px",
        borderBottom: isDark
            ? "0.5px solid rgba(255,255,255,0.12)"
            : "0.5px solid rgba(255,255,255,0.30)",
    };

    const cardHeading: React.CSSProperties = {
        fontSize: "14px",
        fontWeight: 600,
        color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
        fontFamily: fontStack,
        margin: 0,
    };

    const cardBody: React.CSSProperties = {
        padding: "20px",
    };

    const labelStyleDyn: React.CSSProperties = {
        fontSize: "12px",
        fontWeight: 500,
        color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
        fontFamily: fontStack,
        marginBottom: "6px",
        display: "block",
    };

    const themeButton = (active: boolean): React.CSSProperties => ({
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        borderRadius: "10px",
        padding: "8px 16px",
        fontSize: "13px",
        fontWeight: 500,
        fontFamily: fontStack,
        cursor: "pointer",
        transition: "all 0.15s ease",
        background: isDark
            ? (active ? "rgba(201,168,76,0.18)" : "rgba(255,255,255,0.08)")
            : (active ? "rgba(196,124,0,0.18)" : "rgba(255,255,255,0.20)"),
        border: isDark
            ? (active ? "0.5px solid rgba(201,168,76,0.40)" : "0.5px solid rgba(255,255,255,0.14)")
            : (active ? "0.5px solid rgba(196,124,0,0.40)" : "0.5px solid rgba(255,255,255,0.40)"),
        color: isDark
            ? (active ? "#C9A84C" : "rgba(255,255,255,0.55)")
            : (active ? "#5c2e08" : "rgba(46,31,8,0.60)"),
    });

    const statusBadge = (status: string): React.CSSProperties => {
        const isActive = status === "active" || status === "trial";
        return {
            background: isActive
                ? (isDark ? "rgba(34,197,94,0.12)" : "rgba(34,197,94,0.15)")
                : (isDark ? "rgba(239,68,68,0.12)" : "rgba(239,68,68,0.15)"),
            border: isActive
                ? "0.5px solid rgba(34,197,94,0.30)"
                : "0.5px solid rgba(239,68,68,0.30)",
            color: isActive
                ? (isDark ? "#4ade80" : "#16a34a")
                : (isDark ? "#f87171" : "#dc2626"),
            borderRadius: "9999px",
            padding: "2px 10px",
            fontSize: "11px",
            fontWeight: 600,
            textTransform: "capitalize" as const,
        };
    };

    return (
        <div
            style={{
                padding: "24px 16px 120px",
                maxWidth: "640px",
                margin: "0 auto",
            }}
        >
            {/* Page header */}
            <div style={{marginBottom: "24px"}}>
                <h1
                    style={{
                        fontFamily: "var(--font-heading), Georgia, serif",
                        fontSize: "1.5rem",
                        fontWeight: 700,
                        color: isDark ? "rgba(255,255,255,0.90)" : "#1e1208",
                        margin: 0,
                    }}
                >
                    {t("settings.title")}
                </h1>
                <p
                    style={{
                        color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.55)",
                        fontSize: "13px",
                        fontFamily: fontStack,
                        marginTop: "4px",
                    }}
                >
                    {t("settings.subtitle")}
                </p>
            </div>

            {/* Cards container */}
            <motion.div
                variants={isV3 ? V3_LIST_VARIANT : undefined}
                initial={isV3 ? "hidden" : undefined}
                animate={isV3 ? "visible" : undefined}
                style={{display: "flex", flexDirection: "column", gap: "20px"}}
            >
                {/* Account */}
                <motion.div
                    variants={isV3 ? V3_ITEM_VARIANT : undefined}
                    className={glassCardClass}
                    style={glassCard}
                >
                    <div style={cardHeader}>
                        <h2 className={isV3 ? "v3-text-aurora" : ""} style={isV3 ? undefined : cardHeading}>{t("settings.account")}</h2>
                    </div>
                    <div style={cardBody}>
                        {userLoading ? (
                            <div style={{display: "flex", alignItems: "center", gap: 8}}>
                                <Loader2 size={16} style={{
                                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
                                    animation: "spin 1s linear infinite"
                                }}/>
                                <span style={{
                                    fontSize: 13,
                                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
                                    fontFamily: fontStack
                                }}>{t("settings.loading")}</span>
                            </div>
                        ) : user ? (
                            <div style={{display: "flex", flexDirection: "column", gap: 16}}>
                                <div style={{display: "flex", alignItems: "center", gap: 14}}>
                                    {user.avatar_url ? (
                                        <img src={user.avatar_url} alt="" style={{
                                            width: 44,
                                            height: 44,
                                            borderRadius: 12,
                                            border: isDark ? "0.5px solid rgba(255,255,255,0.14)" : "0.5px solid rgba(255,255,255,0.45)"
                                        }}/>
                                    ) : (
                                        <div style={{
                                            width: 44,
                                            height: 44,
                                            borderRadius: 12,
                                            background: isDark ? "rgba(201,168,76,0.15)" : "rgba(196,124,0,0.15)",
                                            border: isDark ? "0.5px solid rgba(201,168,76,0.30)" : "0.5px solid rgba(196,124,0,0.30)",
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center"
                                        }}>
                                            <User size={20} style={{color: isDark ? "#C9A84C" : "#c47c00"}}/>
                                        </div>
                                    )}
                                    <div>
                                        <p style={{
                                            fontSize: 15,
                                            fontWeight: 600,
                                            color: isDark ? "rgba(255,255,255,0.88)" : "#1e1208",
                                            fontFamily: fontStack,
                                            margin: 0
                                        }}>{user.name || user.email}</p>
                                        <p style={{
                                            fontSize: 12,
                                            color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.50)",
                                            fontFamily: fontStack,
                                            margin: "2px 0 0"
                                        }}>{user.email}</p>
                                    </div>
                                </div>
                                <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                                    <span style={{
                                        fontSize: 12,
                                        color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.50)",
                                        fontFamily: fontStack
                                    }}>{t("settings.plan")}</span>
                                    <span
                                        style={statusBadge(user.subscription_status)}>{user.subscription_status}</span>
                                </div>
                                <button
                                    onClick={handleLogout}
                                    disabled={loggingOut}
                                    style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        gap: 6,
                                        padding: "9px 16px",
                                        borderRadius: 10,
                                        fontSize: 13,
                                        fontWeight: 500,
                                        fontFamily: fontStack,
                                        background: isDark ? "rgba(239,68,68,0.10)" : "rgba(239,68,68,0.08)",
                                        border: isDark ? "0.5px solid rgba(239,68,68,0.25)" : "0.5px solid rgba(239,68,68,0.20)",
                                        color: isDark ? "#f87171" : "#dc2626",
                                        cursor: loggingOut ? "default" : "pointer",
                                        opacity: loggingOut ? 0.5 : 1,
                                        transition: "opacity 0.15s",
                                        alignSelf: "flex-start",
                                    }}
                                >
                                    <LogOut size={14}/>
                                    {loggingOut ? t("settings.signing_out") : t("settings.sign_out")}
                                </button>
                            </div>
                        ) : (
                            <div style={{textAlign: "center", padding: "12px 0"}}>
                                <p style={{
                                    fontSize: 13,
                                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.50)",
                                    fontFamily: fontStack,
                                    margin: "0 0 12px"
                                }}>{t("settings.not_signed_in")}</p>
                                <a href="/login" style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: 6,
                                    padding: "9px 20px",
                                    borderRadius: 10,
                                    fontSize: 13,
                                    fontWeight: 600,
                                    fontFamily: fontStack,
                                    background: isDark ? "linear-gradient(135deg, #C9A84C, #e8cc7a)" : "#5c2e08",
                                    color: isDark ? "#0F1623" : "#fff8ee",
                                    textDecoration: "none",
                                    boxShadow: isDark ? "0 2px 12px rgba(201,168,76,0.30)" : "0 2px 12px rgba(92,46,8,0.30)",
                                    border: "none"
                                }}>
                                    {t("settings.sign_in")}
                                </a>
                            </div>
                        )}
                    </div>
                </motion.div>

                {/* Appearance */}
                <motion.div
                    variants={isV3 ? V3_ITEM_VARIANT : undefined}
                    className={glassCardClass}
                    style={glassCard}
                >
                    <div style={cardHeader}>
                        <h2 className={isV3 ? "v3-text-aurora" : ""} style={isV3 ? undefined : cardHeading}>{t("settings.appearance")}</h2>
                    </div>
                    <div style={cardBody}>
                        <div>
                            <span style={labelStyleDyn}>{t("settings.theme")}</span>
                            <div style={{display: "flex", gap: "8px", marginTop: "2px"}}>
                                {themeOptions.map((opt) => (
                                    <button
                                        key={opt.value}
                                        onClick={() => setTheme(opt.value)}
                                        style={themeButton(theme === opt.value)}
                                    >
                                        {opt.icon}
                                        {t(opt.labelKey)}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Delete account — collapsed by default, subtle link */}
                {user && (
                    <div style={{
                        marginTop: SPACE["4"],
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                    }}>
                        {!showDeleteConfirm ? (
                            <button
                                onClick={() => setShowDeleteConfirm(true)}
                                style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: SPACE["1"],
                                    background: "none",
                                    border: "none",
                                    padding: `${SPACE["2"]}px ${SPACE["3"]}px`,
                                    fontSize: TYPE_SCALE.xs,
                                    fontFamily: fontStack,
                                    fontWeight: 400,
                                    color: isDark ? "rgba(255,255,255,0.30)" : "rgba(46,31,8,0.35)",
                                    cursor: "pointer",
                                    transition: `color ${TIMING.fast}`,
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.color = isDark
                                        ? "rgba(255,255,255,0.50)"
                                        : "rgba(46,31,8,0.55)";
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.color = isDark
                                        ? "rgba(255,255,255,0.30)"
                                        : "rgba(46,31,8,0.35)";
                                }}
                            >
                                {t("settings.delete_account")}
                                <ChevronDown size={12}/>
                            </button>
                        ) : (
                            <div
                                className={glassCardClass}
                                style={{...glassCard, width: "100%"}}
                            >
                                <div style={cardBody}>
                                    <div style={{display: "flex", flexDirection: "column", gap: SPACE["4"]}}>
                                        <div>
                                            <p style={{
                                                fontSize: TYPE_SCALE.sm,
                                                fontWeight: 500,
                                                color: isDark ? "rgba(255,255,255,0.60)" : "rgba(46,31,8,0.60)",
                                                fontFamily: fontStack,
                                                margin: 0,
                                                lineHeight: 1.5,
                                            }}>
                                                {t("settings.delete_irreversible")}
                                            </p>
                                        </div>

                                        <div>
                                            <label style={labelStyleDyn}>
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
                                                    padding: `${SPACE["3"]}px ${SPACE["4"]}px`,
                                                    borderRadius: RADIUS.lg,
                                                    fontSize: TYPE_SCALE.sm,
                                                    fontFamily: fontStack,
                                                    background: isDark
                                                        ? "rgba(255,255,255,0.06)"
                                                        : "rgba(255,255,255,0.40)",
                                                    border: isDark
                                                        ? "0.5px solid rgba(255,255,255,0.14)"
                                                        : "0.5px solid rgba(255,255,255,0.40)",
                                                    color: isDark
                                                        ? "rgba(255,255,255,0.88)"
                                                        : "#1e1208",
                                                    outline: "none",
                                                    boxSizing: "border-box",
                                                    transition: "border-color 0.15s ease, box-shadow 0.15s ease",
                                                }}
                                                onFocus={(e) => {
                                                    if (isV3) {
                                                        e.currentTarget.style.borderColor = isDark ? "rgba(157,127,204,0.50)" : "rgba(123,94,167,0.50)";
                                                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(123,94,167,0.12)";
                                                    }
                                                }}
                                                onBlur={(e) => {
                                                    e.currentTarget.style.borderColor = "";
                                                    e.currentTarget.style.boxShadow = "";
                                                }}
                                            />
                                        </div>

                                        {deleteError && (
                                            <p style={{
                                                fontSize: TYPE_SCALE.xs,
                                                color: isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.55)",
                                                fontFamily: fontStack,
                                                margin: 0,
                                            }}>
                                                {deleteError}
                                            </p>
                                        )}

                                        <div style={{
                                            display: "flex",
                                            gap: SPACE["3"],
                                            alignSelf: "flex-start",
                                        }}>
                                            <button
                                                onClick={handleDeleteAccount}
                                                disabled={!deleteEmailMatches || deleting}
                                                style={{
                                                    display: "inline-flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    gap: SPACE["2"],
                                                    padding: `${SPACE["3"]}px ${SPACE["5"]}px`,
                                                    borderRadius: RADIUS.lg,
                                                    fontSize: TYPE_SCALE.sm,
                                                    fontWeight: 600,
                                                    fontFamily: fontStack,
                                                    background: deleteEmailMatches
                                                        ? (isDark
                                                            ? "rgba(255,255,255,0.10)"
                                                            : "rgba(46,31,8,0.08)")
                                                        : (isDark
                                                            ? "rgba(255,255,255,0.04)"
                                                            : "rgba(255,255,255,0.15)"),
                                                    border: deleteEmailMatches
                                                        ? (isDark
                                                            ? "0.5px solid rgba(255,255,255,0.25)"
                                                            : "0.5px solid rgba(46,31,8,0.20)")
                                                        : (isDark
                                                            ? "0.5px solid rgba(255,255,255,0.08)"
                                                            : "0.5px solid rgba(255,255,255,0.25)"),
                                                    color: deleteEmailMatches
                                                        ? (isDark ? "rgba(255,255,255,0.75)" : "rgba(46,31,8,0.70)")
                                                        : (isDark
                                                            ? "rgba(255,255,255,0.20)"
                                                            : "rgba(46,31,8,0.25)"),
                                                    cursor: deleteEmailMatches && !deleting
                                                        ? "pointer"
                                                        : "not-allowed",
                                                    opacity: deleting ? 0.5 : 1,
                                                    transition: `all ${TIMING.fast}`,
                                                }}
                                            >
                                                {deleting ? (
                                                    <>
                                                        <Loader2 size={14} style={{animation: "spin 1s linear infinite"}}/>
                                                        {t("settings.deleting")}
                                                    </>
                                                ) : (
                                                    t("settings.delete_permanently")
                                                )}
                                            </button>
                                            <button
                                                onClick={() => {
                                                    setShowDeleteConfirm(false);
                                                    setDeleteConfirmEmail("");
                                                    setDeleteError(null);
                                                }}
                                                disabled={deleting}
                                                style={{
                                                    display: "inline-flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    padding: `${SPACE["3"]}px ${SPACE["5"]}px`,
                                                    borderRadius: RADIUS.lg,
                                                    fontSize: TYPE_SCALE.sm,
                                                    fontWeight: 500,
                                                    fontFamily: fontStack,
                                                    background: isDark
                                                        ? "rgba(255,255,255,0.06)"
                                                        : "rgba(255,255,255,0.25)",
                                                    border: isDark
                                                        ? "0.5px solid rgba(255,255,255,0.14)"
                                                        : "0.5px solid rgba(255,255,255,0.35)",
                                                    color: isDark
                                                        ? "rgba(255,255,255,0.55)"
                                                        : "rgba(46,31,8,0.60)",
                                                    cursor: deleting ? "not-allowed" : "pointer",
                                                    transition: `opacity ${TIMING.fast}`,
                                                }}
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

            </motion.div>
        </div>
    );
}
