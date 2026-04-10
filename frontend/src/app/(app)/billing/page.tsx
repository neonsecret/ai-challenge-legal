"use client";

import { useState, useEffect } from "react";
import {useColorMode} from "@/lib/color-mode";
import {motion} from "motion/react";
import {V3_CARD_HOVER, V3_LIST_VARIANT, V3_ITEM_VARIANT} from "@/lib/v3-motion";
import { useI18n } from "@/lib/i18n";
import {
  Crown,
  AlertTriangle,
  Check,
  Zap,
  Loader2,
  CreditCard,
  Database,
  MessageSquare,
  Building2,
  Sparkles,
  ArrowRight,
  Info,
} from "lucide-react";

const fontStack =
  "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

const API = process.env.NEXT_PUBLIC_SSE_URL ?? "";

type PlanTier = "free" | "starter" | "pro" | "enterprise";
type BillingInterval = "monthly" | "biweekly";

interface BillingStatus {
  plan: PlanTier;
  subscription_status?: string;
  monthly_queries_used: number;
  monthly_queries_limit: number;
  daily_queries_used: number;
  daily_queries_limit: number;
  is_monthly_limit: boolean;
  corpora_used: number;
  corpora_limit: number;
  has_stripe_customer: boolean;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
}

interface PlanConfig {
  tier: PlanTier;
  name: string;
  tagline: string;
  monthlyPrice: number;
  biweeklyPrice: number;
  dailyQueries: string;
  corpusUploads: string;
  features: string[];
  icon: React.ReactNode;
  highlighted?: boolean;
}

export default function BillingPage() {
  const { isDark } = useColorMode();
  const { t } = useI18n();
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [interval, setInterval_] = useState<BillingInterval>("monthly");
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const isV3 = isDark;

  useEffect(() => {
    async function fetchBilling() {
      try {
        const res = await fetch(`${API}/stripe/billing-status`, {
          credentials: "include",
        });
        if (res.status === 401) {
          window.location.href = "/login";
          return;
        }
        if (!res.ok) throw new Error(t("billing.error_load"));
        const data = await res.json();
        setBilling(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : t("billing.error_load")
        );
      } finally {
        setLoading(false);
      }
    }

    fetchBilling();
  }, []);

  const handleUpgrade = async (plan: PlanTier) => {
    setActionLoading(plan);
    try {
      const res = await fetch(`${API}/stripe/create-checkout-session`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
        body: JSON.stringify({ plan, interval }),
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error(t("billing.error_checkout"));
      const data = await res.json();
      window.location.href = data.url;
    } catch {
      setError(t("billing.error_checkout"));
      setActionLoading(null);
    }
  };

  const handleManage = async () => {
    setActionLoading("manage");
    try {
      const res = await fetch(`${API}/stripe/customer-portal`, {
        credentials: "include",
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error(t("billing.error_portal"));
      const data = await res.json();
      window.location.href = data.url;
    } catch {
      setError(t("billing.error_portal"));
      setActionLoading(null);
    }
  };

  const handleCancelSubscription = async () => {
    setActionLoading("cancel");
    try {
      const res = await fetch(`${API}/stripe/cancel-subscription`, {
        method: "POST",
        credentials: "include",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error(t("billing.cancel_error"));
      const data = await res.json();
      // Update local billing state to reflect pending cancellation
      if (billing) {
        setBilling({
          ...billing,
          cancel_at_period_end: true,
          current_period_end: data.period_end,
        });
      }
      setShowCancelConfirm(false);
    } catch {
      setError(t("billing.cancel_error"));
    } finally {
      setActionLoading(null);
    }
  };

  const formatPeriodEnd = (isoDate: string | null): string => {
    if (!isoDate) return "";
    try {
      return new Date(isoDate).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    } catch {
      return isoDate;
    }
  };

  // -- Styles --

  const glassCard: React.CSSProperties = isDark ? {
    background: "rgba(255,255,255, 0.02)",
    backdropFilter: "blur(24px)",
    WebkitBackdropFilter: "blur(24px)",
    border: "1px solid rgba(201,168,76, 0.06)",
    borderRadius: "14px",
    boxShadow: "0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025)",
    overflow: "clip",
  } : {
    background: "rgba(255,250,235,0.22)",
    backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    border: "0.5px solid rgba(255,255,255,0.38)",
    borderRadius: "20px",
    boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
    overflow: "clip",
  };

  const glassCardClass = "";

  const goldGlassCard: React.CSSProperties = isDark ? {
    background: "rgba(201,168,76, 0.03)",
    backdropFilter: "blur(24px)",
    WebkitBackdropFilter: "blur(24px)",
    border: "1px solid rgba(201,168,76, 0.20)",
    borderRadius: "14px",
    boxShadow: "0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025)",
    overflow: "clip",
  } : {
    ...glassCard,
    border: "1px solid rgba(92,46,8,0.25)",
    boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.16), 0 0 0 0.5px rgba(92,46,8,0.15)",
  };

  const cardHeader: React.CSSProperties = {
    padding: "16px 20px",
    borderBottom: isDark
      ? "0.5px solid rgba(201,168,76, 0.08)"
      : "0.5px solid rgba(255,255,255,0.30)",
  };

  const cardHeading: React.CSSProperties = {
    fontSize: "14px",
    fontWeight: 600,
    color: isDark ? "var(--strict-text-primary, rgba(255,255,255,0.90))" : "#1e1208",
    fontFamily: isDark ? "Georgia, 'Times New Roman', serif" : fontStack,
    margin: 0,
  };

  const cardBody: React.CSSProperties = {
    padding: "20px",
  };

  const mutedText: React.CSSProperties = {
    fontSize: "12px",
    color: isDark ? "var(--strict-text-dim, rgba(255,255,255,0.38))" : "rgba(46,31,8,0.55)",
    fontFamily: fontStack,
  };

  const primaryButton = (
    isLoading: boolean
  ): React.CSSProperties => ({
    background: isDark
      ? "rgba(201,168,76, 0.1)"
      : "#5c2e08",
    color: isDark ? "#C9A84C" : "#fff8ee",
    borderRadius: "10px",
    padding: "10px 22px",
    fontSize: "13px",
    fontWeight: 600,
    fontFamily: fontStack,
    boxShadow: isDark
      ? "0 2px 12px rgba(201,168,76,0.15)"
      : "0 2px 12px rgba(92,46,8,0.30)",
    border: isDark
      ? "1px solid rgba(201,168,76, 0.2)"
      : "none",
    borderBottom: isDark ? "2px solid rgba(201,168,76, 0.5)" : undefined,
    cursor: isLoading ? "wait" : "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    transition: "opacity 0.15s ease",
    opacity: isLoading ? 0.7 : 1,
    justifyContent: "center",
    width: "100%",
  });

  const secondaryButton = (
    isLoading: boolean
  ): React.CSSProperties => ({
    background: isDark
      ? "rgba(255,255,255,0.04)"
      : "rgba(255,255,255,0.35)",
    border: isDark
      ? "1px solid rgba(201,168,76, 0.1)"
      : "0.5px solid rgba(255,255,255,0.50)",
    borderBottom: isDark ? "2px solid rgba(201,168,76, 0.25)" : undefined,
    borderRadius: "10px",
    padding: "10px 22px",
    fontSize: "13px",
    fontWeight: 500,
    fontFamily: fontStack,
    color: isDark ? "var(--strict-text-body, rgba(255,255,255,0.65))" : "#2e1f08",
    cursor: isLoading ? "wait" : "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    transition: "opacity 0.15s ease",
    opacity: isLoading ? 0.7 : 1,
    justifyContent: "center",
  });

  const featureIcon: React.CSSProperties = {
    color: isDark ? "#C9A84C" : "#5c2e08",
    flexShrink: 0,
  };

  const featureText: React.CSSProperties = {
    fontSize: "13px",
    fontWeight: 500,
    color: isDark ? "var(--strict-text-body, rgba(255,255,255,0.65))" : "#2e1f08",
    fontFamily: fontStack,
  };

  const planBadge = (tier: PlanTier): React.CSSProperties => {
    if (tier === "enterprise") {
      return {
        background: isDark
          ? "rgba(201,168,76,0.15)"
          : "rgba(92,46,8,0.10)",
        color: isDark ? "#C9A84C" : "#5c2e08",
        border: isDark
          ? "0.5px solid rgba(201,168,76,0.30)"
          : "0.5px solid rgba(92,46,8,0.20)",
        borderRadius: "9999px",
        padding: "3px 12px",
        fontSize: "11px",
        fontWeight: 600,
        fontFamily: fontStack,
        textTransform: "uppercase" as const,
        letterSpacing: "0.04em",
      };
    }
    if (tier === "pro") {
      return {
        background: isDark
          ? "rgba(201,168,76,0.12)"
          : "rgba(99,102,241,0.10)",
        color: isDark ? "#C9A84C" : "#4f46e5",
        border: isDark
          ? "0.5px solid rgba(201,168,76,0.28)"
          : "0.5px solid rgba(99,102,241,0.25)",
        borderRadius: "9999px",
        padding: "3px 12px",
        fontSize: "11px",
        fontWeight: 600,
        fontFamily: fontStack,
        textTransform: "uppercase" as const,
        letterSpacing: "0.04em",
      };
    }
    if (tier === "starter") {
      return {
        background: isDark
          ? "rgba(74,222,128,0.15)"
          : "rgba(22,163,74,0.10)",
        color: isDark ? "#4ade80" : "#15803d",
        border: isDark
          ? "0.5px solid rgba(74,222,128,0.30)"
          : "0.5px solid rgba(22,163,74,0.25)",
        borderRadius: "9999px",
        padding: "3px 12px",
        fontSize: "11px",
        fontWeight: 600,
        fontFamily: fontStack,
        textTransform: "uppercase" as const,
        letterSpacing: "0.04em",
      };
    }
    // free
    return {
      background: isDark
        ? "rgba(255,255,255,0.08)"
        : "rgba(0,0,0,0.06)",
      color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.55)",
      border: isDark
        ? "0.5px solid rgba(255,255,255,0.12)"
        : "0.5px solid rgba(0,0,0,0.10)",
      borderRadius: "9999px",
      padding: "3px 12px",
      fontSize: "11px",
      fontWeight: 600,
      fontFamily: fontStack,
      textTransform: "uppercase" as const,
      letterSpacing: "0.04em",
    };
  };

  // -- Plan configs --

  const plans: PlanConfig[] = [
    {
      tier: "free",
      name: t("billing.free"),
      tagline: t("billing.plan_free_tagline"),
      monthlyPrice: 0,
      biweeklyPrice: 0,
      dailyQueries: "3/day",
      corpusUploads: "0",
      features: [
        t("billing.feature_free_1"),
        t("billing.feature_free_2"),
        t("billing.feature_free_3"),
      ],
      icon: <MessageSquare size={18} style={featureIcon} />,
    },
    {
      tier: "starter",
      name: t("billing.starter"),
      tagline: t("billing.plan_starter_tagline"),
      monthlyPrice: 29,
      biweeklyPrice: 16,
      dailyQueries: "30/day",
      corpusUploads: "2",
      features: [
        t("billing.feature_starter_1"),
        t("billing.feature_starter_2"),
        t("billing.feature_starter_3"),
        t("billing.feature_starter_4"),
      ],
      icon: <Zap size={18} style={featureIcon} />,
    },
    {
      tier: "pro",
      name: t("billing.pro"),
      tagline: t("billing.plan_pro_tagline"),
      monthlyPrice: 179,
      biweeklyPrice: 99,
      dailyQueries: "200/day",
      corpusUploads: "5",
      features: [
        t("billing.feature_pro_1"),
        t("billing.feature_pro_2"),
        t("billing.feature_pro_3"),
        t("billing.feature_pro_4"),
        t("billing.feature_pro_5"),
      ],
      icon: <Sparkles size={18} style={featureIcon} />,
      highlighted: true,
    },
    {
      tier: "enterprise",
      name: t("billing.enterprise"),
      tagline: t("billing.plan_enterprise_tagline"),
      monthlyPrice: 499,
      biweeklyPrice: 279,
      dailyQueries: "Unlimited",
      corpusUploads: "10",
      features: [
        t("billing.feature_enterprise_1"),
        t("billing.feature_enterprise_2"),
        t("billing.feature_enterprise_3"),
        t("billing.feature_enterprise_4"),
        t("billing.feature_enterprise_5"),
        t("billing.feature_enterprise_6"),
      ],
      icon: <Building2 size={18} style={featureIcon} />,
    },
  ];

  // -- Helpers --

  const usagePercent = () => {
    if (!billing) return 0;
    if (billing.is_monthly_limit) {
      if (billing.monthly_queries_limit === 0) return 0;
      return Math.min(
        100,
        (billing.monthly_queries_used / billing.monthly_queries_limit) * 100
      );
    }
    if (billing.daily_queries_limit <= 0) return 0;
    return Math.min(
      100,
      (billing.daily_queries_used / billing.daily_queries_limit) * 100
    );
  };

  const isExhausted = billing?.is_monthly_limit
    ? billing.monthly_queries_used >= billing.monthly_queries_limit
    : false;

  // -- Usage bar component --

  const renderUsageBar = () => {
    if (!billing) return null;
    const percent = usagePercent();
    const isWarning = percent >= 80;
    const isFull = percent >= 100;

    const barBg: React.CSSProperties = {
      height: "8px",
      borderRadius: "9999px",
      background: isDark
        ? "rgba(255,255,255,0.08)"
        : "rgba(0,0,0,0.06)",
      overflow: "hidden",
      width: "100%",
    };

    const barFill: React.CSSProperties = {
      height: "100%",
      borderRadius: "9999px",
      width: `${percent}%`,
      background: isFull
        ? isDark
          ? "#f87171"
          : "#dc2626"
        : isWarning
          ? isDark
            ? "#fbbf24"
            : "#d97706"
          : isDark
            ? "linear-gradient(90deg, #C9A84C, #e8cc7a)"
            : "linear-gradient(90deg, #5c2e08, #8b5e34)",
      transition: "width 0.4s ease",
    };

    return (
      <div style={{ width: "100%" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: "8px",
          }}
        >
          <span style={mutedText}>
            {billing.is_monthly_limit ? t("billing.queries_this_month") : t("billing.todays_queries")}
          </span>
          <span
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: isFull
                ? isDark
                  ? "#f87171"
                  : "#dc2626"
                : isDark
                  ? "rgba(255,255,255,0.80)"
                  : "#1e1208",
              fontFamily: fontStack,
            }}
          >
            {billing.is_monthly_limit
              ? `${billing.monthly_queries_used}/${billing.monthly_queries_limit}`
              : billing.daily_queries_limit === -1
                ? `${billing.daily_queries_used}`
                : `${billing.daily_queries_used}/${billing.daily_queries_limit}`}
          </span>
        </div>
        {(billing.is_monthly_limit
          ? billing.monthly_queries_limit > 0
          : billing.daily_queries_limit > 0) && (
          <div style={barBg}>
            <div style={barFill} />
          </div>
        )}
      </div>
    );
  };

  // -- Current Plan section --

  const renderCurrentPlan = () => {
    if (!billing) return null;

    const planNames: Record<string, string> = {
      free: t("billing.plan_name_free"),
      starter: t("billing.plan_name_starter"),
      pro: t("billing.plan_name_pro"),
      enterprise: t("billing.plan_name_enterprise"),
    };

    return (
      <motion.div
        className={glassCardClass}
        style={glassCard}
        variants={isV3 ? V3_ITEM_VARIANT : undefined}
        initial={isV3 ? "hidden" : undefined}
        animate={isV3 ? "visible" : undefined}
      >
        <div style={cardHeader}>
          <h2 style={cardHeading}>{t("billing.current_plan")}</h2>
        </div>
        <div style={cardBody}>
          {/* Plan name + badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "20px",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <Crown
                size={20}
                style={{ color: isDark ? "#C9A84C" : "#5c2e08" }}
              />
              <span
                style={{
                  fontSize: "16px",
                  fontWeight: 700,
                  color: isDark ? "var(--strict-text-primary, rgba(255,255,255,0.92))" : "#1e1208",
                  fontFamily: isDark ? "Georgia, 'Times New Roman', serif" : fontStack,
                }}
              >
                {planNames[billing.plan] ?? billing.plan}
              </span>
            </div>
            <span style={planBadge((billing.plan as PlanTier) ?? "free")}>
              {billing.plan ?? "free"}
            </span>
          </div>

          {/* Usage bar */}
          <div style={{ marginBottom: "16px" }}>{renderUsageBar()}</div>

          {/* Corpus usage */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "20px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Database
                size={14}
                style={{ color: isDark ? "#C9A84C" : "#5c2e08" }}
              />
              <span style={mutedText}>{t("billing.corpus_uploads_label")}</span>
            </div>
            <span
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: isDark ? "rgba(255,255,255,0.80)" : "#1e1208",
                fontFamily: fontStack,
              }}
            >
              {billing.corpora_used}/{billing.corpora_limit}
            </span>
          </div>

          {/* Exhausted warning */}
          {isExhausted && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "16px",
                padding: "10px 14px",
                borderRadius: "12px",
                background: isDark
                  ? "rgba(248,113,113,0.08)"
                  : "rgba(220,38,38,0.06)",
                border: isDark
                  ? "0.5px solid rgba(248,113,113,0.20)"
                  : "0.5px solid rgba(220,38,38,0.15)",
              }}
            >
              <AlertTriangle
                size={16}
                style={{
                  color: isDark ? "#f87171" : "#dc2626",
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: "13px",
                  color: isDark ? "#f87171" : "#dc2626",
                  fontFamily: fontStack,
                }}
              >
                {t("billing.queries_exhausted")}
              </span>
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            {billing.plan === "free" && isExhausted && (
              <button
                onClick={() => handleUpgrade("starter")}
                disabled={actionLoading !== null}
                style={primaryButton(actionLoading === "starter")}
              >
                {actionLoading === "starter" ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Zap size={15} />
                )}
                {t("billing.upgrade_now")}
              </button>
            )}
            {billing.plan !== "free" && billing.has_stripe_customer && (
              <button
                onClick={handleManage}
                disabled={actionLoading !== null}
                style={secondaryButton(actionLoading === "manage")}
              >
                {actionLoading === "manage" ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <CreditCard size={15} />
                )}
                {t("billing.manage_subscription")}
              </button>
            )}
          </div>

          {/* Cancel subscription / pending cancellation */}
          {billing.plan !== "free" && billing.has_stripe_customer && (
            <div style={{ marginTop: "16px" }}>
              {billing.cancel_at_period_end ? (
                /* Already scheduled for cancellation */
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 14px",
                    borderRadius: "12px",
                    background: isDark
                      ? "rgba(251,191,36,0.06)"
                      : "rgba(217,119,6,0.05)",
                    border: isDark
                      ? "0.5px solid rgba(251,191,36,0.15)"
                      : "0.5px solid rgba(217,119,6,0.12)",
                  }}
                >
                  <AlertTriangle
                    size={14}
                    style={{
                      color: isDark ? "#fbbf24" : "#d97706",
                      flexShrink: 0,
                    }}
                  />
                  <span
                    style={{
                      fontSize: "12px",
                      color: isDark ? "#fbbf24" : "#d97706",
                      fontFamily: fontStack,
                    }}
                  >
                    {t("billing.cancel_pending").replace(
                      "{date}",
                      formatPeriodEnd(billing.current_period_end)
                    )}
                  </span>
                </div>
              ) : (
                /* Show cancel link or inline confirmation */
                <>
                  {!showCancelConfirm ? (
                    <button
                      onClick={() => setShowCancelConfirm(true)}
                      style={{
                        background: "none",
                        border: "none",
                        padding: 0,
                        cursor: "pointer",
                        fontSize: "12px",
                        fontFamily: fontStack,
                        color: isDark
                          ? "rgba(255,255,255,0.30)"
                          : "rgba(46,31,8,0.40)",
                        textDecoration: "underline",
                        textUnderlineOffset: "2px",
                        transition: "color 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = isDark
                          ? "rgba(255,255,255,0.50)"
                          : "rgba(46,31,8,0.60)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = isDark
                          ? "rgba(255,255,255,0.30)"
                          : "rgba(46,31,8,0.40)";
                      }}
                    >
                      {t("billing.cancel_subscription")}
                    </button>
                  ) : (
                    <div
                      style={{
                        padding: "14px 16px",
                        borderRadius: "12px",
                        background: isDark
                          ? "rgba(248,113,113,0.06)"
                          : "rgba(220,38,38,0.04)",
                        border: isDark
                          ? "0.5px solid rgba(248,113,113,0.15)"
                          : "0.5px solid rgba(220,38,38,0.10)",
                      }}
                    >
                      <p
                        style={{
                          fontSize: "13px",
                          fontWeight: 600,
                          color: isDark
                            ? "rgba(255,255,255,0.80)"
                            : "#1e1208",
                          fontFamily: fontStack,
                          margin: "0 0 6px 0",
                        }}
                      >
                        {t("billing.cancel_confirm_title")}
                      </p>
                      <p
                        style={{
                          fontSize: "12px",
                          color: isDark
                            ? "rgba(255,255,255,0.50)"
                            : "rgba(46,31,8,0.60)",
                          fontFamily: fontStack,
                          margin: "0 0 14px 0",
                          lineHeight: 1.4,
                        }}
                      >
                        {t("billing.cancel_confirm_body").replace(
                          "{date}",
                          formatPeriodEnd(billing.current_period_end)
                        )}
                      </p>
                      <div
                        style={{
                          display: "flex",
                          gap: "8px",
                          alignItems: "center",
                        }}
                      >
                        <button
                          onClick={handleCancelSubscription}
                          disabled={actionLoading !== null}
                          style={{
                            background: isDark
                              ? "rgba(248,113,113,0.12)"
                              : "rgba(220,38,38,0.08)",
                            border: isDark
                              ? "0.5px solid rgba(248,113,113,0.25)"
                              : "0.5px solid rgba(220,38,38,0.18)",
                            borderRadius: "8px",
                            padding: "7px 16px",
                            fontSize: "12px",
                            fontWeight: 600,
                            fontFamily: fontStack,
                            color: isDark ? "#f87171" : "#dc2626",
                            cursor:
                              actionLoading === "cancel"
                                ? "wait"
                                : "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                            opacity:
                              actionLoading === "cancel" ? 0.7 : 1,
                            transition: "opacity 0.15s ease",
                          }}
                        >
                          {actionLoading === "cancel" && (
                            <Loader2
                              size={13}
                              className="animate-spin"
                            />
                          )}
                          {t("billing.cancel_confirm_yes")}
                        </button>
                        <button
                          onClick={() => setShowCancelConfirm(false)}
                          disabled={actionLoading !== null}
                          style={{
                            background: "none",
                            border: "none",
                            padding: "7px 12px",
                            fontSize: "12px",
                            fontWeight: 500,
                            fontFamily: fontStack,
                            color: isDark
                              ? "rgba(255,255,255,0.45)"
                              : "rgba(46,31,8,0.50)",
                            cursor: "pointer",
                          }}
                        >
                          {t("billing.cancel_confirm_no")}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </motion.div>
    );
  };

  // -- Billing interval toggle --

  const renderIntervalToggle = () => {
    const toggleContainer: React.CSSProperties = {
      display: "inline-flex",
      borderRadius: "9999px",
      padding: "3px",
      background: isDark
        ? "rgba(255,255,255,0.03)"
        : "rgba(255,250,235,0.22)",
      backdropFilter: "blur(24px)",
      WebkitBackdropFilter: "blur(24px)",
      border: isDark
        ? "1px solid rgba(201,168,76, 0.08)"
        : "0.5px solid rgba(255,255,255,0.38)",
      boxShadow: isDark
        ? "inset 0 1px 0 rgba(255,255,255,0.025)"
        : "inset 0 1px 0 rgba(255,255,255,0.60)",
    };

    const toggleOption = (
      active: boolean
    ): React.CSSProperties => ({
      borderRadius: "9999px",
      padding: "7px 18px",
      fontSize: "13px",
      fontWeight: 600,
      fontFamily: fontStack,
      border: "none",
      cursor: "pointer",
      transition: "all 0.2s ease",
      background: active
        ? isDark
          ? "rgba(201,168,76, 0.1)"
          : "rgba(255,255,255,0.60)"
        : "transparent",
      color: active
        ? isDark
          ? "#C9A84C"
          : "#1e1208"
        : isDark
          ? "var(--strict-text-dim, rgba(255,255,255,0.38))"
          : "rgba(46,31,8,0.50)",
      boxShadow: active
        ? isDark
          ? "0 2px 8px rgba(0,0,0,0.20)"
          : "0 2px 8px rgba(100,50,0,0.10)"
        : "none",
    });

    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <div style={toggleContainer}>
          <button
            onClick={() => setInterval_("monthly")}
            style={toggleOption(interval === "monthly")}
          >
            {t("billing.monthly")}
          </button>
          <button
            onClick={() => setInterval_("biweekly")}
            style={toggleOption(interval === "biweekly")}
          >
            {t("billing.biweekly")}
          </button>
        </div>
        {interval === "biweekly" && (
          <span
            style={{
              fontSize: "10px",
              fontWeight: 700,
              color: isDark ? "#4ade80" : "#15803d",
              background: isDark
                ? "rgba(74,222,128,0.12)"
                : "rgba(22,163,74,0.08)",
              border: isDark
                ? "0.5px solid rgba(74,222,128,0.25)"
                : "0.5px solid rgba(22,163,74,0.20)",
              borderRadius: "9999px",
              padding: "3px 10px",
              fontFamily: fontStack,
              whiteSpace: "nowrap",
            }}
          >
            {t("billing.save_percent")}
          </span>
        )}
      </div>
    );
  };

  // -- Plan card --

  const renderPlanCard = (plan: PlanConfig) => {
    const isCurrent = billing?.plan === plan.tier;
    const isEnterprise = plan.tier === "enterprise";
    const card = isEnterprise ? goldGlassCard : glassCard;
    const price =
      interval === "monthly" ? plan.monthlyPrice : plan.biweeklyPrice;

    return (
      <motion.div
        key={plan.tier}
        style={{
          ...card,
          ...(isCurrent && isDark ? {
            border: "1px solid rgba(201,168,76, 0.2)",
            boxShadow: "0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(201,168,76,0.05)",
          } : {}),
          flex: "1 1 0",
          minWidth: "220px",
          display: "flex",
          flexDirection: "column",
          position: "relative",
        }}
        variants={isV3 ? V3_ITEM_VARIANT : undefined}
        {...(isV3 ? V3_CARD_HOVER : {})}
      >
        {/* Highlighted badge */}
        {plan.highlighted && !isCurrent && (
          <div
            style={{
              position: "absolute",
              top: "-1px",
              left: "50%",
              transform: "translateX(-50%)",
              background: isDark
                ? "linear-gradient(135deg, #C9A84C, #e8cc7a)"
                : "#5c2e08",
              color: isDark ? "#0F1623" : "#fff8ee",
              fontSize: "10px",
              fontWeight: 700,
              fontFamily: fontStack,
              padding: "3px 14px",
              borderRadius: "0 0 8px 8px",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {t("billing.most_popular")}
          </div>
        )}

        <div style={{ ...cardBody, flex: 1, display: "flex", flexDirection: "column" }}>
          {/* Plan icon + name */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "4px",
            }}
          >
            {plan.icon}
            <span
              style={{
                fontSize: "15px",
                fontWeight: 700,
                color: isDark ? "var(--strict-text-primary, rgba(255,255,255,0.90))" : "#1e1208",
                fontFamily: isDark ? "Georgia, 'Times New Roman', serif" : fontStack,
              }}
            >
              {plan.name}
            </span>
          </div>

          {/* Tagline */}
          <span
            style={{
              ...mutedText,
              marginBottom: "16px",
              display: "block",
            }}
          >
            {plan.tagline}
          </span>

          {/* Price */}
          <div style={{ marginBottom: "16px" }}>
            {plan.monthlyPrice === 0 ? (
              <span
                style={{
                  fontSize: "28px",
                  fontWeight: 700,
                  color: isDark ? "var(--strict-text-secondary, rgba(255,255,255,0.75))" : "#1e1208",
                  fontFamily: isDark ? "Georgia, 'Times New Roman', serif" : fontStack,
                }}
              >
                {t("billing.price_free")}
              </span>
            ) : (
              <div style={{ display: "flex", alignItems: "baseline", gap: "2px" }}>
                <span
                  style={{
                    fontSize: "28px",
                    fontWeight: 700,
                    color: isDark ? "rgba(201,168,76, 0.7)" : "#5c2e08",
                    fontFamily: isDark ? "Georgia, 'Times New Roman', serif" : fontStack,
                  }}
                >
                  ${price}
                </span>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 400,
                    color: isDark
                      ? "var(--strict-text-dim, rgba(255,255,255,0.38))"
                      : "rgba(46,31,8,0.55)",
                    fontFamily: fontStack,
                  }}
                >
                  /{interval === "monthly" ? t("billing.interval_mo") : t("billing.interval_2wk")}
                </span>
              </div>
            )}
          </div>

          {/* Features */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              flex: 1,
            }}
          >
            {plan.features.map((feat, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Check
                  size={14}
                  style={{
                    color: isDark ? "#C9A84C" : "#5c2e08",
                    flexShrink: 0,
                  }}
                />
                <span style={featureText}>{feat}</span>
              </div>
            ))}
          </div>

          {/* Action */}
          <div style={{ marginTop: "20px" }}>
            {isCurrent ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "10px 22px",
                  borderRadius: "10px",
                  fontSize: "13px",
                  fontWeight: 600,
                  fontFamily: fontStack,
                  color: isDark
                    ? "rgba(201,168,76, 0.7)"
                    : "rgba(46,31,8,0.50)",
                  background: isDark
                    ? "rgba(201,168,76, 0.06)"
                    : "rgba(0,0,0,0.03)",
                  border: isDark
                    ? "1px solid rgba(201,168,76, 0.15)"
                    : "0.5px solid rgba(0,0,0,0.06)",
                }}
              >
                {t("billing.current_plan")}
              </div>
            ) : plan.monthlyPrice === 0 ? null : (
              <button
                onClick={() => handleUpgrade(plan.tier)}
                disabled={actionLoading !== null}
                style={
                  plan.highlighted || isEnterprise
                    ? primaryButton(actionLoading === plan.tier)
                    : {
                        ...secondaryButton(actionLoading === plan.tier),
                        width: "100%",
                      }
                }
              >
                {actionLoading === plan.tier ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <ArrowRight size={15} />
                )}
                {billing?.plan === "free" ? t("billing.upgrade") : t("billing.switch")} {t("billing.to")}{" "}
                {plan.name}
              </button>
            )}
          </div>
        </div>
      </motion.div>
    );
  };

  // -- Notes section --

  const renderNotes = () => (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        marginTop: "8px",
      }}
    >
      {[
        t("billing.note_cancel"),
        t("billing.note_downgrade"),
      ].map((note, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "8px",
            padding: "10px 14px",
            borderRadius: "12px",
            background: isDark
              ? "rgba(201,168,76, 0.02)"
              : "rgba(0,0,0,0.02)",
            border: isDark
              ? "0.5px solid rgba(201,168,76, 0.06)"
              : "0.5px solid rgba(0,0,0,0.04)",
          }}
        >
          <Info
            size={14}
            style={{
              color: isDark
                ? "rgba(201,168,76, 0.35)"
                : "rgba(46,31,8,0.40)",
              flexShrink: 0,
              marginTop: "1px",
            }}
          />
          <span
            style={{
              fontSize: "12px",
              color: isDark
                ? "var(--strict-text-dim, rgba(255,255,255,0.38))"
                : "rgba(46,31,8,0.55)",
              fontFamily: fontStack,
              lineHeight: 1.4,
            }}
          >
            {note}
          </span>
        </div>
      ))}

      {/* Business contact link */}
      <div
        style={{
          textAlign: "center",
          marginTop: "4px",
        }}
      >
        <span
          style={{
            fontSize: "12px",
            color: isDark
              ? "rgba(255,255,255,0.35)"
              : "rgba(46,31,8,0.45)",
            fontFamily: fontStack,
          }}
        >
          {t("billing.need_more")}{" "}
          <a
            href="mailto:hello@vitreon.app"
            style={{
              color: isDark ? "#C9A84C" : "#5c2e08",
              textDecoration: "underline",
              textUnderlineOffset: "2px",
              fontWeight: 600,
            }}
          >
            {t("billing.contact_us")}
          </a>{" "}
          {t("billing.for_custom_plans")}
        </span>
      </div>
    </div>
  );

  // -- Main render --

  return (
    <div
      style={{
        padding: "24px 16px 24px",
        maxWidth: "1100px",
        margin: "0 auto",
      }}
    >
      {/* Page header */}
      <div style={{ marginBottom: "24px" }}>
        <h1
          style={{
            fontFamily: "var(--font-heading), Georgia, serif",
            fontSize: "1.5rem",
            fontWeight: 700,
            color: isDark ? "var(--strict-text-primary, rgba(255,255,255,0.92))" : "#1e1208",
            margin: 0,
          }}
        >
          {t("billing.title")}
        </h1>
        <p
          style={{
            color: isDark
              ? "var(--strict-text-secondary, rgba(255,255,255,0.50))"
              : "rgba(46,31,8,0.55)",
            fontSize: "13px",
            fontFamily: fontStack,
            marginTop: "4px",
          }}
        >
          {t("billing.subtitle")}
        </p>
      </div>

      {/* Loading state */}
      {loading && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            padding: "60px 0",
          }}
        >
          <Loader2
            size={24}
            className="animate-spin"
            style={{ color: isDark ? "#C9A84C" : "#5c2e08" }}
          />
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div
          style={{
            ...glassCard,
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              padding: "20px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <AlertTriangle
              size={18}
              style={{
                color: isDark ? "#f87171" : "#dc2626",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: "13px",
                color: isDark ? "#f87171" : "#dc2626",
                fontFamily: fontStack,
              }}
            >
              {error}
            </span>
          </div>
        </div>
      )}

      {/* Content */}
      {!loading && billing && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          {/* 1. Current Plan card */}
          {renderCurrentPlan()}

          {/* 2. Plan comparison section */}
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "16px",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <h2
                style={{
                  fontFamily: "var(--font-heading), Georgia, serif",
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  color: isDark ? "var(--strict-text-primary, rgba(255,255,255,0.90))" : "#1e1208",
                  margin: 0,
                }}
              >
                {t("billing.choose_plan")}
              </h2>
              {renderIntervalToggle()}
            </div>

            {/* Plan cards — horizontal row, stacks on mobile */}
            <motion.div
              variants={isV3 ? V3_LIST_VARIANT : undefined}
              initial={isV3 ? "hidden" : undefined}
              animate={isV3 ? "visible" : undefined}
              style={{
                display: "flex",
                gap: "14px",
                flexWrap: "wrap",
              }}
            >
              {plans.map((plan) => renderPlanCard(plan))}
            </motion.div>
          </div>

          {/* 3. Important notes */}
          {renderNotes()}
        </div>
      )}
    </div>
  );
}
