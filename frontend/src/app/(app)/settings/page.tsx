"use client";

import {useState, useEffect} from "react";
import {Moon, Sun, Monitor, LogOut, User, Loader2, ChevronDown} from "lucide-react";
import {useColorMode} from "@/lib/color-mode";
import {motion} from "motion/react";
import {V3_LIST_VARIANT, V3_ITEM_VARIANT} from "@/lib/v3-motion";
import {useRouter} from "next/navigation";
import {useI18n} from "@/lib/i18n";
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
    const {t} = useI18n();
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

    const themeOptions: { value: ThemeOption; labelKey: string; icon: React.ReactNode }[] = [
        {value: "light", labelKey: "settings.light", icon: <Sun size={16}/>},
        {value: "dark", labelKey: "settings.dark", icon: <Moon size={16}/>},
        {value: "system", labelKey: "settings.system", icon: <Monitor size={16}/>},
    ];

    const glassCard: React.CSSProperties = isDark ? {
        background: "rgba(255,255,255, 0.02)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        border: "1px solid rgba(201,168,76, 0.06)",
        borderRadius: "14px",
        boxShadow: "0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025)",
        overflow: "clip",
    } : {
        background: "var(--dt-glass-bg)",
        backdropFilter: "var(--dt-glass-blur)",
        WebkitBackdropFilter: "var(--dt-glass-blur)",
        border: "0.5px solid var(--dt-glass-border-subtle)",
        borderRadius: "20px",
        boxShadow: "var(--dt-glass-inner-glow), var(--dt-glass-shadow)",
        overflow: "clip",
    };

    const glassCardClass = "";

    const cardHeader: React.CSSProperties = {
        padding: "16px 20px",
        borderBottom: isDark ? "1px solid rgba(201,168,76, 0.06)" : "0.5px solid var(--dt-glass-border-subtle)",
    };

    const cardHeading: React.CSSProperties = isDark ? {
        fontSize: "14px",
        fontWeight: 600,
        color: "var(--strict-text-primary)",
        fontFamily: "Georgia, serif",
        margin: 0,
    } : {
        fontSize: "14px",
        fontWeight: 600,
        color: "var(--dt-text-primary)",
        fontFamily: fontStack,
        margin: 0,
    };

    const cardBody: React.CSSProperties = {
        padding: "20px",
    };

    const labelStyleDyn: React.CSSProperties = {
        fontSize: "12px",
        fontWeight: 500,
        color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
        fontFamily: fontStack,
        marginBottom: "6px",
        display: "block",
    };

    const themeButton = (active: boolean): React.CSSProperties => isDark ? {
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
        background: active ? "rgba(201,168,76, 0.08)" : "rgba(255,255,255,0.02)",
        border: active
            ? "1px solid rgba(201,168,76, 0.15)"
            : "1px solid rgba(201,168,76, 0.06)",
        color: active ? "var(--strict-gold-text)" : "var(--strict-text-secondary)",
    } : {
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
        background: active ? "var(--dt-accent-tint-strong)" : "var(--dt-button-bg)",
        border: active
            ? "0.5px solid var(--dt-accent-border-color)"
            : "0.5px solid var(--dt-button-border-color)",
        color: active ? "var(--dt-accent-color)" : "var(--dt-text-tertiary)",
    };

    const statusBadge = (status: string): React.CSSProperties => {
        const isActive = status === "active" || status === "trial";
        return {
            background: isActive ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            border: isActive ? "0.5px solid rgba(34,197,94,0.30)" : "0.5px solid rgba(239,68,68,0.30)",
            color: isActive ? (isDark ? "#4ade80" : "#16a34a") : (isDark ? "#f87171" : "#dc2626"),
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
                        fontFamily: "Georgia, serif",
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
                <h1
                    style={{
                        fontFamily: "var(--font-heading), Georgia, serif",
                        fontSize: "1.5rem",
                        fontWeight: 700,
                        color: isDark ? "var(--strict-text-primary)" : "var(--dt-text-primary)",
                        margin: 0,
                    }}
                >
                    {t("settings.title")}
                </h1>
                <p
                    style={{
                        color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
                        fontSize: "13px",
                        fontFamily: fontStack,
                        marginTop: "4px",
                    }}
                >
                    {t("settings.subtitle")}
                </p>
            </div>
            )}

            {/* Cards container — scrollable in dark mode */}
            <div style={{
                ...(isDark ? {
                    flex: 1,
                    overflowY: "auto" as const,
                    padding: "20px 24px",
                    maxWidth: 640,
                    width: "100%",
                    marginLeft: "auto",
                    marginRight: "auto",
                } : {}),
            }}>
            <motion.div
                variants={isDark ? V3_LIST_VARIANT : undefined}
                initial={isDark ? "hidden" : undefined}
                animate={isDark ? "visible" : undefined}
                style={{display: "flex", flexDirection: "column", gap: "20px"}}
            >
                {/* Account */}
                <motion.div
                    variants={isDark ? V3_ITEM_VARIANT : undefined}
                    className={glassCardClass}
                    style={glassCard}
                >
                    <div style={cardHeader}>
                        <h2 style={cardHeading}>{t("settings.account")}</h2>
                    </div>
                    <div style={cardBody}>
                        {userLoading ? (
                            <div style={{display: "flex", alignItems: "center", gap: 8}}>
                                <Loader2 size={16} style={{
                                    color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
                                    animation: "spin 1s linear infinite"
                                }}/>
                                <span style={{
                                    fontSize: 13,
                                    color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
                                    fontFamily: fontStack
                                }}>{t("settings.loading")}</span>
                            </div>
                        ) : user ? (
                            <div style={{display: "flex", flexDirection: "column", gap: 16}}>
                                <div style={{display: "flex", alignItems: "center", gap: 14}}>
                                    {user.avatar_url ? (
                                        <img src={user.avatar_url} alt={user.name || user.email} style={{
                                            width: 44,
                                            height: 44,
                                            borderRadius: 12,
                                            border: isDark ? "1px solid rgba(201,168,76, 0.12)" : "0.5px solid var(--dt-glass-border)"
                                        }}/>
                                    ) : (
                                        <div style={{
                                            width: 44,
                                            height: 44,
                                            borderRadius: 12,
                                            background: isDark ? "rgba(201,168,76, 0.06)" : "var(--dt-accent-tint)",
                                            border: isDark ? "1px solid rgba(201,168,76, 0.12)" : "0.5px solid var(--dt-accent-border-color)",
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center"
                                        }}>
                                            <User size={20} style={{color: isDark ? "var(--strict-gold-text)" : "var(--dt-accent-color)"}}/>
                                        </div>
                                    )}
                                    <div>
                                        <p style={{
                                            fontSize: 15,
                                            fontWeight: 600,
                                            color: isDark ? "var(--strict-text-primary)" : "var(--dt-text-primary)",
                                            fontFamily: fontStack,
                                            margin: 0
                                        }}>{user.name || user.email}</p>
                                        <p style={{
                                            fontSize: 12,
                                            color: isDark ? "var(--strict-text-dim)" : "var(--dt-text-quaternary)",
                                            fontFamily: fontStack,
                                            margin: "2px 0 0"
                                        }}>{user.email}</p>
                                    </div>
                                </div>
                                <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                                    <span style={{
                                        fontSize: 12,
                                        color: isDark ? "var(--strict-text-dim)" : "var(--dt-text-quaternary)",
                                        fontFamily: fontStack
                                    }}>{t("settings.plan")}</span>
                                    <span style={statusBadge(user.subscription_status)}>{user.subscription_status}</span>
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
                                        background: "rgba(239,68,68,0.10)",
                                        border: "0.5px solid rgba(239,68,68,0.25)",
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
                                    color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
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
                                    background: isDark ? "rgba(201,168,76, 0.10)" : "var(--dt-accent-solid)",
                                    color: isDark ? "var(--strict-gold-text)" : "#fff8ee",
                                    textDecoration: "none",
                                    boxShadow: isDark ? "0 2px 12px rgba(201,168,76,0.15)" : "0 2px 12px var(--dt-accent-glow)",
                                    border: isDark ? "1px solid rgba(201,168,76, 0.20)" : "none"
                                }}>
                                    {t("settings.sign_in")}
                                </a>
                            </div>
                        )}
                    </div>
                </motion.div>

                {/* Appearance */}
                <motion.div
                    variants={isDark ? V3_ITEM_VARIANT : undefined}
                    className={glassCardClass}
                    style={glassCard}
                >
                    <div style={cardHeader}>
                        <h2 style={cardHeading}>{t("settings.appearance")}</h2>
                    </div>
                    <div style={cardBody}>
                        <div style={{display: "flex", flexDirection: "column", gap: "20px"}}>
                            <div>
                                <span style={labelStyleDyn}>{t("settings.theme")}</span>
                                <div style={{display: "flex", gap: "8px", marginTop: "2px"}}>
                                    {themeOptions.map((opt) => (
                                        <button
                                            key={opt.value}
                                            onClick={() => setMode(opt.value)}
                                            aria-pressed={mode === opt.value}
                                            style={themeButton(mode === opt.value)}
                                        >
                                            {opt.icon}
                                            {t(opt.labelKey)}
                                        </button>
                                    ))}
                                </div>
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
                                    color: isDark ? "var(--strict-text-ghost)" : "var(--dt-text-quaternary)",
                                    cursor: "pointer",
                                    transition: `color ${TIMING.fast}`,
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.color = isDark ? "var(--strict-text-dim)" : "var(--dt-text-tertiary)";
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.color = isDark ? "var(--strict-text-ghost)" : "var(--dt-text-quaternary)";
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
                                                color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
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
                                                    background: isDark ? "rgba(255,255,255,0.03)" : "var(--dt-glass-bg-subtle)",
                                                    border: isDark ? "1px solid rgba(201,168,76,0.08)" : "0.5px solid var(--dt-glass-border-subtle)",
                                                    color: isDark ? "var(--strict-text-primary)" : "var(--dt-text-primary)",
                                                    outline: "none",
                                                    boxSizing: "border-box",
                                                    transition: "border-color 0.15s ease, box-shadow 0.15s ease",
                                                }}
                                                onFocus={(e) => {
                                                    if (isDark) {
                                                        e.currentTarget.style.borderColor = "rgba(201,168,76,0.25)";
                                                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(201,168,76,0.06)";
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
                                                color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
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
                                                    background: isDark
                                                        ? (deleteEmailMatches ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.02)")
                                                        : (deleteEmailMatches ? "var(--dt-glass-bg-hover)" : "var(--dt-glass-bg-subtle)"),
                                                    border: isDark
                                                        ? (deleteEmailMatches ? "1px solid rgba(201,168,76,0.12)" : "1px solid rgba(201,168,76,0.06)")
                                                        : (deleteEmailMatches ? "0.5px solid var(--dt-glass-border)" : "0.5px solid var(--dt-glass-border-subtle)"),
                                                    color: isDark
                                                        ? (deleteEmailMatches ? "var(--strict-text-primary)" : "var(--strict-text-dim)")
                                                        : (deleteEmailMatches ? "var(--dt-text-secondary)" : "var(--dt-text-quaternary)"),
                                                    cursor: deleteEmailMatches && !deleting ? "pointer" : "not-allowed",
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
                                                    background: isDark ? "rgba(255,255,255,0.02)" : "var(--dt-glass-bg-subtle)",
                                                    border: isDark ? "1px solid rgba(201,168,76,0.06)" : "0.5px solid var(--dt-glass-border-subtle)",
                                                    color: isDark ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)",
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
            </div>{/* end scrollable content wrapper */}
        </div>
    );
}
