"use client";

import { useState, useEffect } from "react";
import {useColorMode} from "@/lib/color-mode";
import {motion} from "motion/react";
import {V3_LIST_VARIANT, V3_ITEM_VARIANT} from "@/lib/v3-motion";
import { useI18n } from "@/lib/i18n";
import {
  Crown,
  AlertTriangle,
  Zap,
  Loader2,
  CreditCard,
  Database,
  MessageSquare,
  Building2,
  Sparkles,
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

  // -- Light mode styles (unchanged) --

  const glassCardLight: React.CSSProperties = {
    background: "rgba(255,250,235,0.22)",
    backdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    WebkitBackdropFilter: "blur(32px) saturate(180%) brightness(106%)",
    border: "0.5px solid rgba(255,255,255,0.38)",
    borderRadius: "20px",
    boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.12)",
    overflow: "clip",
  };

  const goldGlassCardLight: React.CSSProperties = {
    ...glassCardLight,
    border: "1px solid rgba(92,46,8,0.25)",
    boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.88), 0 8px 32px rgba(100,50,0,0.16), 0 0 0 0.5px rgba(92,46,8,0.15)",
  };

  const cardHeaderLight: React.CSSProperties = {
    padding: "16px 20px",
    borderBottom: "0.5px solid rgba(255,255,255,0.30)",
  };

  const cardBodyLight: React.CSSProperties = { padding: "20px" };

  const mutedTextLight: React.CSSProperties = {
    fontSize: "12px",
    color: "rgba(46,31,8,0.55)",
    fontFamily: fontStack,
  };

  const primaryButtonLight = (isLoading: boolean): React.CSSProperties => ({
    background: "#5c2e08",
    color: "#fff8ee",
    borderRadius: "10px",
    padding: "10px 22px",
    fontSize: "13px",
    fontWeight: 600,
    fontFamily: fontStack,
    boxShadow: "0 2px 12px rgba(92,46,8,0.30)",
    border: "none",
    cursor: isLoading ? "wait" : "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    transition: "opacity 0.15s ease",
    opacity: isLoading ? 0.7 : 1,
    justifyContent: "center",
    width: "100%",
  });

  const secondaryButtonLight = (isLoading: boolean): React.CSSProperties => ({
    background: "rgba(255,255,255,0.35)",
    border: "0.5px solid rgba(255,255,255,0.50)",
    borderRadius: "10px",
    padding: "10px 22px",
    fontSize: "13px",
    fontWeight: 500,
    fontFamily: fontStack,
    color: "#2e1f08",
    cursor: isLoading ? "wait" : "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    transition: "opacity 0.15s ease",
    opacity: isLoading ? 0.7 : 1,
    justifyContent: "center",
  });

  // -- Dark mode (strict-pricing matched) styles --
  // All card/button styles inlined in render functions to match landing page spec exactly

  // -- Plan configs --

  const featureIconStyle: React.CSSProperties = {
    color: isDark ? "#C9A84C" : "#5c2e08",
    flexShrink: 0,
  };

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
      icon: <MessageSquare size={18} style={featureIconStyle} />,
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
      icon: <Zap size={18} style={featureIconStyle} />,
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
      icon: <Sparkles size={18} style={featureIconStyle} />,
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
      icon: <Building2 size={18} style={featureIconStyle} />,
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

  const usageCounts = () => {
    if (!billing) return "";
    if (billing.is_monthly_limit) {
      return `${billing.monthly_queries_used}/${billing.monthly_queries_limit}`;
    }
    if (billing.daily_queries_limit === -1) {
      return `${billing.daily_queries_used}`;
    }
    return `${billing.daily_queries_used}/${billing.daily_queries_limit}`;
  };

  const isExhausted = billing?.is_monthly_limit
    ? billing.monthly_queries_used >= billing.monthly_queries_limit
    : false;

  // -- Dark mode rendering --

  const renderDarkUsageStats = () => {
    if (!billing) return null;

    const planNames: Record<string, string> = {
      free: t("billing.plan_name_free"),
      starter: t("billing.plan_name_starter"),
      pro: t("billing.plan_name_pro"),
      enterprise: t("billing.plan_name_enterprise"),
    };

    const percent = usagePercent();
    const isFull = percent >= 100;
    const isWarning = percent >= 80;

    const barFillColor = isFull
      ? "#f87171"
      : isWarning
        ? "#fbbf24"
        : "linear-gradient(90deg, rgba(201,168,76,0.4), rgba(201,168,76,0.2))";

    const usageLabel = billing.is_monthly_limit
      ? t("billing.queries_this_month")
      : t("billing.todays_queries");

    return (
      <div style={{ maxWidth: 600, margin: "0 auto", width: "100%" }}>
        {/* Section label */}
        <div style={{
          fontFamily: "system-ui, sans-serif",
          fontSize: "9px",
          textTransform: "uppercase",
          letterSpacing: "1.2px",
          color: "rgba(201,168,76,0.4)",
          marginBottom: "14px",
        }}>
          {planNames[billing.plan] ?? billing.plan}
        </div>

        {/* Usage row — queries */}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
          <span style={{
            fontFamily: "system-ui, sans-serif",
            fontSize: "10px",
            color: "rgba(200,210,230,0.35)",
          }}>
            {usageLabel}
          </span>
          <span style={{
            fontFamily: "system-ui, sans-serif",
            fontVariantNumeric: "tabular-nums",
            fontSize: "10px",
            color: "rgba(200,210,230,0.42)",
          }}>
            {usageCounts()}
          </span>
        </div>

        {/* Usage bar */}
        {(billing.is_monthly_limit
          ? billing.monthly_queries_limit > 0
          : billing.daily_queries_limit > 0) && (
          <div style={{
            height: "3px",
            borderRadius: "2px",
            background: "rgba(201,168,76,0.08)",
            overflow: "hidden",
            marginBottom: "16px",
          }}>
            <div style={{
              height: "100%",
              borderRadius: "2px",
              width: `${percent}%`,
              background: barFillColor,
              transition: "width 0.4s ease",
            }} />
          </div>
        )}

        {/* Usage row — corpus */}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
          <span style={{
            fontFamily: "system-ui, sans-serif",
            fontSize: "10px",
            color: "rgba(200,210,230,0.35)",
          }}>
            {t("billing.corpus_uploads_label")}
          </span>
          <span style={{
            fontFamily: "system-ui, sans-serif",
            fontVariantNumeric: "tabular-nums",
            fontSize: "10px",
            color: "rgba(200,210,230,0.42)",
          }}>
            {billing.corpora_used}/{billing.corpora_limit}
          </span>
        </div>

        {/* Exhausted warning */}
        {isExhausted && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            marginTop: "10px",
            padding: "6px 8px",
            borderRadius: "5px",
            background: "rgba(248,113,113,0.08)",
            border: "1px solid rgba(248,113,113,0.20)",
          }}>
            <AlertTriangle size={11} style={{ color: "#f87171", flexShrink: 0 }} />
            <span style={{
              fontFamily: "system-ui, sans-serif",
              fontSize: "10px",
              color: "#f87171",
            }}>
              {t("billing.queries_exhausted")}
            </span>
          </div>
        )}

        {/* Gold separator */}
        <div style={{
          height: "1px",
          background: "linear-gradient(90deg, rgba(201,168,76,0.12), rgba(201,168,76,0.03))",
          margin: "28px auto",
        }} />
      </div>
    );
  };

  const renderDarkPlanCard = (plan: PlanConfig) => {
    const isCurrent = billing?.plan === plan.tier;
    const isFeatured = plan.highlighted ?? false;
    const price = interval === "monthly" ? plan.monthlyPrice : plan.biweeklyPrice;
    const priceLabel = price === 0 ? t("billing.price_free") : `$${price}`;
    const suffix = price === 0 ? null : `/${interval === "monthly" ? t("billing.interval_mo") : t("billing.interval_2wk")}`;

    return (
      <div
        key={plan.tier}
        style={{
          flex: "1 1 180px",
          minWidth: 180,
          background: "var(--strict-glass-bg)",
          backdropFilter: "var(--strict-glass-blur)",
          border: `1px solid ${isCurrent ? "rgba(201,168,76,0.2)" : isFeatured ? "rgba(201,168,76,0.15)" : "rgba(255,255,255,0.04)"}`,
          borderRadius: "14px",
          padding: "20px",
          display: "flex",
          flexDirection: "column" as const,
          gap: "12px",
          transition: "border-color 0.2s ease, box-shadow 0.2s ease",
        }}
        onMouseEnter={(e) => {
          if (!isCurrent) {
            e.currentTarget.style.borderColor = isFeatured ? "rgba(201,168,76,0.25)" : "rgba(201,168,76,0.10)";
            e.currentTarget.style.boxShadow = isFeatured
              ? "0 0 20px rgba(201,168,76,0.08)"
              : "0 8px 24px rgba(0,0,0,0.2)";
          }
        }}
        onMouseLeave={(e) => {
          if (!isCurrent) {
            e.currentTarget.style.borderColor = isFeatured ? "rgba(201,168,76,0.15)" : "rgba(255,255,255,0.04)";
            e.currentTarget.style.boxShadow = isFeatured ? "0 0 20px rgba(201,168,76,0.03)" : "none";
          }
        }}
      >
        {/* Plan name */}
        <p style={{
          fontFamily: "system-ui, sans-serif",
          fontSize: "11px",
          textTransform: "uppercase" as const,
          letterSpacing: "0.5px",
          color: "var(--strict-text-primary)",
          opacity: 0.6,
          margin: 0,
        }}>
          {plan.name}
        </p>

        {/* Price */}
        <div style={{ display: "flex", alignItems: "baseline", gap: "2px" }}>
          <span style={{
            fontFamily: "Georgia, 'Times New Roman', serif",
            fontSize: "20px",
            color: "var(--strict-text-primary)",
            opacity: 0.8,
          }}>
            {priceLabel}
          </span>
          {suffix && (
            <span style={{
              fontFamily: "system-ui, sans-serif",
              fontSize: "12px",
              color: "var(--strict-text-secondary)",
              opacity: 0.5,
            }}>
              {suffix}
            </span>
          )}
        </div>

        {/* Sub label */}
        <p style={{
          fontFamily: "system-ui, sans-serif",
          fontSize: "9px",
          color: "var(--strict-text-dim)",
          margin: 0,
        }}>
          {plan.dailyQueries}
        </p>

        {/* Feature list */}
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column" as const }}>
          {plan.features.map((feature) => (
            <li key={feature} style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "4px",
              fontFamily: "system-ui, sans-serif",
              fontSize: "9.5px",
              color: "var(--strict-text-secondary)",
              opacity: 0.35,
              lineHeight: 1.8,
            }}>
              <span style={{
                color: "var(--strict-gold-text)",
                opacity: 1,
                flexShrink: 0,
              }}>·</span>
              {feature}
            </li>
          ))}
        </ul>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* CTA button */}
        {isCurrent ? (
          <div style={{
            fontFamily: "system-ui, sans-serif",
            fontSize: "10px",
            background: "rgba(255,255,255,0.025)",
            backdropFilter: "blur(12px)",
            border: "1px solid rgba(255,255,255,0.04)",
            borderBottom: "1px solid var(--strict-gold-underbar)",
            borderRadius: "8px",
            padding: "10px 16px",
            color: "var(--strict-text-primary)",
            opacity: 0.4,
            textAlign: "center" as const,
            minHeight: "36px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "default",
          }}>
            {t("billing.current_plan")}
          </div>
        ) : price > 0 ? (
          <button
            onClick={() => handleUpgrade(plan.tier)}
            disabled={actionLoading !== null}
            style={{
              fontFamily: "system-ui, sans-serif",
              fontSize: "10px",
              background: "rgba(255,255,255,0.025)",
              backdropFilter: "blur(12px)",
              border: "1px solid rgba(255,255,255,0.04)",
              borderBottom: "1px solid var(--strict-gold-underbar)",
              borderRadius: "8px",
              padding: "10px 16px",
              color: "var(--strict-text-primary)",
              opacity: isFeatured ? 0.8 : 0.7,
              textAlign: "center" as const,
              minHeight: "36px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: actionLoading ? "wait" : "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = "1";
              e.currentTarget.style.transform = "translateY(-1px)";
              e.currentTarget.style.boxShadow = "0 2px 8px rgba(201,168,76,0.08)";
              e.currentTarget.style.borderBottomColor = "rgba(201,168,76,0.5)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = isFeatured ? "0.8" : "0.7";
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "none";
              e.currentTarget.style.borderBottomColor = "rgba(201,168,76,0.3)";
            }}
          >
            {actionLoading === plan.tier && <Loader2 size={12} className="animate-spin" style={{ marginRight: "6px" }} />}
            {plan.tier === "enterprise" ? t("billing.contact_us") : `${billing?.plan === "free" ? t("billing.upgrade") : t("billing.switch")} ${t("billing.to")} ${plan.name}`}
          </button>
        ) : null}
      </div>
    );
  };

  const renderDarkIntervalToggle = () => (
    <div style={{ display: "flex", justifyContent: "center", marginBottom: "20px" }}>
      <div style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
        <div style={{
          display: "inline-flex",
          borderRadius: "6px",
          padding: "2px",
          background: "rgba(255,255,255,0.02)",
          border: "1px solid rgba(201,168,76,0.08)",
        }}>
          {(["monthly", "biweekly"] as BillingInterval[]).map((opt) => (
            <button
              key={opt}
              onClick={() => setInterval_(opt)}
              style={{
                padding: "4px 10px",
                borderRadius: "5px",
                fontFamily: "system-ui, sans-serif",
                fontSize: "10px",
                lineHeight: 1,
                border: interval === opt ? "1px solid rgba(201,168,76,0.15)" : "1px solid transparent",
                background: interval === opt ? "rgba(201,168,76,0.08)" : "transparent",
                color: interval === opt ? "rgba(201,168,76,0.7)" : "var(--strict-text-dim)",
                cursor: "pointer",
                transition: "all 0.15s",
              }}
            >
              {opt === "monthly" ? t("billing.monthly") : t("billing.biweekly")}
            </button>
          ))}
        </div>
        {interval === "biweekly" && (
          <span style={{
            fontFamily: "system-ui, sans-serif",
            fontSize: "9px",
            fontWeight: 700,
            color: "#4ade80",
            background: "rgba(74,222,128,0.12)",
            border: "0.5px solid rgba(74,222,128,0.25)",
            borderRadius: "5px",
            padding: "4px 10px",
            whiteSpace: "nowrap",
          }}>
            {t("billing.save_percent")}
          </span>
        )}
      </div>
    </div>
  );

  const renderDarkSubscriptionActions = () => {
    if (!billing || billing.plan === "free") return null;
    if (!billing.has_stripe_customer) return null;

    return (
      <div style={{ textAlign: "center" as const, marginTop: "20px" }}>
        {/* Inline action links */}
        <div style={{ display: "inline-flex", gap: "16px", alignItems: "center" }}>
          <button
            onClick={handleManage}
            disabled={actionLoading !== null}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              cursor: actionLoading === "manage" ? "wait" : "pointer",
              fontFamily: "system-ui, sans-serif",
              fontSize: "10px",
              color: "rgba(200,210,230,0.45)",
              transition: "color 0.15s ease",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "rgba(200,210,230,0.35)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(255,255,255,0.16)"; }}
          >
            {actionLoading === "manage" && <Loader2 size={10} className="animate-spin" />}
            {t("billing.manage_subscription")}
          </button>

          {!billing.cancel_at_period_end && !showCancelConfirm && (
            <>
              <span style={{ color: "rgba(255,255,255,0.08)", fontSize: "10px" }}>·</span>
              <button
                onClick={() => setShowCancelConfirm(true)}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  fontFamily: "system-ui, sans-serif",
                  fontSize: "10px",
                  color: "rgba(200,210,230,0.45)",
                  transition: "color 0.15s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "rgba(200,210,230,0.35)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(255,255,255,0.16)"; }}
              >
                {t("billing.cancel_subscription")}
              </button>
            </>
          )}
        </div>

        {/* Cancel confirmation dialog */}
        {showCancelConfirm && !billing.cancel_at_period_end && (
          <div style={{
            maxWidth: 400,
            margin: "12px auto 0",
            padding: "8px 10px",
            borderRadius: "6px",
            background: "rgba(248,113,113,0.06)",
            border: "0.5px solid rgba(248,113,113,0.15)",
            textAlign: "left" as const,
          }}>
            <p style={{
              fontFamily: "system-ui, sans-serif",
              fontSize: "10px",
              color: "var(--strict-text-primary)",
              margin: "0 0 6px",
            }}>
              {t("billing.cancel_confirm_title")}
            </p>
            <p style={{
              fontFamily: "system-ui, sans-serif",
              fontSize: "10px",
              color: "var(--strict-text-dim)",
              margin: "0 0 8px",
              lineHeight: 1.4,
            }}>
              {t("billing.cancel_confirm_body").replace(
                "{date}",
                formatPeriodEnd(billing.current_period_end)
              )}
            </p>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <button
                onClick={handleCancelSubscription}
                disabled={actionLoading !== null}
                style={{
                  padding: "5px 10px",
                  borderRadius: "5px",
                  background: "rgba(248,113,113,0.10)",
                  border: "0.5px solid rgba(248,113,113,0.25)",
                  borderBottom: "1px solid rgba(248,113,113,0.35)",
                  fontFamily: "system-ui, sans-serif",
                  fontSize: "10px",
                  color: "#f87171",
                  cursor: actionLoading === "cancel" ? "wait" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                {actionLoading === "cancel" && <Loader2 size={10} className="animate-spin" />}
                {t("billing.cancel_confirm_yes")}
              </button>
              <button
                onClick={() => setShowCancelConfirm(false)}
                disabled={actionLoading !== null}
                style={{
                  background: "none",
                  border: "none",
                  padding: "5px 8px",
                  fontFamily: "system-ui, sans-serif",
                  fontSize: "10px",
                  color: "var(--strict-text-dim)",
                  cursor: "pointer",
                }}
              >
                {t("billing.cancel_confirm_no")}
              </button>
            </div>
          </div>
        )}

        {/* Cancel pending notice */}
        {billing.cancel_at_period_end && (
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            marginTop: "12px",
            padding: "5px 7px",
            borderRadius: "4px",
            background: "rgba(251,191,36,0.06)",
            border: "0.5px solid rgba(251,191,36,0.15)",
          }}>
            <AlertTriangle size={10} style={{ color: "#fbbf24", flexShrink: 0 }} />
            <span style={{
              fontFamily: "system-ui, sans-serif",
              fontSize: "10px",
              color: "#fbbf24",
            }}>
              {t("billing.cancel_pending").replace(
                "{date}",
                formatPeriodEnd(billing.current_period_end)
              )}
            </span>
          </div>
        )}
      </div>
    );
  };

  // -- Light mode rendering (unchanged structure) --

  const renderLightContent = () => {
    if (!billing) return null;

    const planNames: Record<string, string> = {
      free: t("billing.plan_name_free"),
      starter: t("billing.plan_name_starter"),
      pro: t("billing.plan_name_pro"),
      enterprise: t("billing.plan_name_enterprise"),
    };

    const percent = usagePercent();
    const isFull = percent >= 100;
    const isWarning = percent >= 80;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        {/* Current plan card */}
        <div style={glassCardLight}>
          <div style={cardHeaderLight}>
            <h2 style={{ fontSize: "14px", fontWeight: 600, color: "#1e1208", fontFamily: fontStack, margin: 0 }}>
              {t("billing.current_plan")}
            </h2>
          </div>
          <div style={cardBodyLight}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Crown size={20} style={{ color: "#5c2e08" }} />
                <span style={{ fontSize: "16px", fontWeight: 700, color: "#1e1208", fontFamily: fontStack }}>
                  {planNames[billing.plan] ?? billing.plan}
                </span>
              </div>
            </div>

            <div style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "8px" }}>
                <span style={mutedTextLight}>
                  {billing.is_monthly_limit ? t("billing.queries_this_month") : t("billing.todays_queries")}
                </span>
                <span style={{ fontSize: "13px", fontWeight: 600, color: isFull ? "#dc2626" : "#1e1208", fontFamily: fontStack }}>
                  {usageCounts()}
                </span>
              </div>
              {(billing.is_monthly_limit ? billing.monthly_queries_limit > 0 : billing.daily_queries_limit > 0) && (
                <div style={{ height: "8px", borderRadius: "9999px", background: "rgba(0,0,0,0.06)", overflow: "hidden" }}>
                  <div style={{
                    height: "100%",
                    borderRadius: "9999px",
                    width: `${percent}%`,
                    background: isFull ? "#dc2626" : isWarning ? "#d97706" : "linear-gradient(90deg, #5c2e08, #8b5e34)",
                    transition: "width 0.4s ease",
                  }} />
                </div>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Database size={14} style={{ color: "#5c2e08" }} />
                <span style={mutedTextLight}>{t("billing.corpus_uploads_label")}</span>
              </div>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#1e1208", fontFamily: fontStack }}>
                {billing.corpora_used}/{billing.corpora_limit}
              </span>
            </div>

            {isExhausted && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px", padding: "10px 14px", borderRadius: "12px", background: "rgba(220,38,38,0.06)", border: "0.5px solid rgba(220,38,38,0.15)" }}>
                <AlertTriangle size={16} style={{ color: "#dc2626", flexShrink: 0 }} />
                <span style={{ fontSize: "13px", color: "#dc2626", fontFamily: fontStack }}>{t("billing.queries_exhausted")}</span>
              </div>
            )}

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              {billing.plan === "free" && isExhausted && (
                <button onClick={() => handleUpgrade("starter")} disabled={actionLoading !== null} style={primaryButtonLight(actionLoading === "starter")}>
                  {actionLoading === "starter" ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
                  {t("billing.upgrade_now")}
                </button>
              )}
              {billing.plan !== "free" && billing.has_stripe_customer && (
                <button onClick={handleManage} disabled={actionLoading !== null} style={secondaryButtonLight(actionLoading === "manage")}>
                  {actionLoading === "manage" ? <Loader2 size={15} className="animate-spin" /> : <CreditCard size={15} />}
                  {t("billing.manage_subscription")}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Plan cards */}
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
            <h2 style={{ fontFamily: "var(--font-heading), Georgia, serif", fontSize: "1.1rem", fontWeight: 700, color: "#1e1208", margin: 0 }}>
              {t("billing.choose_plan")}
            </h2>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
              <div style={{ display: "inline-flex", borderRadius: "9999px", padding: "3px", background: "rgba(255,250,235,0.22)", backdropFilter: "blur(24px)", border: "0.5px solid rgba(255,255,255,0.38)" }}>
                {(["monthly", "biweekly"] as BillingInterval[]).map((opt) => (
                  <button key={opt} onClick={() => setInterval_(opt)} style={{ borderRadius: "9999px", padding: "7px 18px", fontSize: "13px", fontWeight: 600, fontFamily: fontStack, border: "none", cursor: "pointer", transition: "all 0.2s ease", background: interval === opt ? "rgba(255,255,255,0.60)" : "transparent", color: interval === opt ? "#1e1208" : "rgba(46,31,8,0.50)" }}>
                    {opt === "monthly" ? t("billing.monthly") : t("billing.biweekly")}
                  </button>
                ))}
              </div>
              {interval === "biweekly" && (
                <span style={{ fontSize: "10px", fontWeight: 700, color: "#15803d", background: "rgba(22,163,74,0.08)", border: "0.5px solid rgba(22,163,74,0.20)", borderRadius: "9999px", padding: "3px 10px", fontFamily: fontStack }}>
                  {t("billing.save_percent")}
                </span>
              )}
            </div>
          </div>

          <div style={{ display: "flex", gap: "14px", flexWrap: "wrap" }}>
            {plans.map((plan) => {
              const isCurrent = billing.plan === plan.tier;
              const price = interval === "monthly" ? plan.monthlyPrice : plan.biweeklyPrice;
              const card = plan.tier === "enterprise" ? goldGlassCardLight : glassCardLight;
              return (
                <div key={plan.tier} style={{ ...card, ...(isCurrent ? { border: "1px solid rgba(92,46,8,0.25)" } : {}), flex: "1 1 0", minWidth: "220px", display: "flex", flexDirection: "column", position: "relative" }}>
                  <div style={{ ...cardBodyLight, flex: 1, display: "flex", flexDirection: "column" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                      {plan.icon}
                      <span style={{ fontSize: "15px", fontWeight: 700, color: "#1e1208", fontFamily: fontStack }}>{plan.name}</span>
                    </div>
                    <span style={{ ...mutedTextLight, marginBottom: "16px", display: "block" }}>{plan.tagline}</span>
                    <div style={{ marginBottom: "16px" }}>
                      {plan.monthlyPrice === 0 ? (
                        <span style={{ fontSize: "28px", fontWeight: 700, color: "#1e1208", fontFamily: fontStack }}>{t("billing.price_free")}</span>
                      ) : (
                        <div style={{ display: "flex", alignItems: "baseline", gap: "2px" }}>
                          <span style={{ fontSize: "28px", fontWeight: 700, color: "#5c2e08", fontFamily: fontStack }}>${price}</span>
                          <span style={{ fontSize: "12px", color: "rgba(46,31,8,0.55)", fontFamily: fontStack }}>/{interval === "monthly" ? t("billing.interval_mo") : t("billing.interval_2wk")}</span>
                        </div>
                      )}
                    </div>
                    <div style={{ flex: 1 }} />
                    <div style={{ marginTop: "20px" }}>
                      {isCurrent ? (
                        <div style={{ textAlign: "center", padding: "10px 22px", borderRadius: "10px", fontSize: "13px", fontWeight: 600, fontFamily: fontStack, color: "rgba(46,31,8,0.50)", background: "rgba(0,0,0,0.03)", border: "0.5px solid rgba(0,0,0,0.06)" }}>
                          {t("billing.current_plan")}
                        </div>
                      ) : plan.monthlyPrice === 0 ? null : (
                        <button onClick={() => handleUpgrade(plan.tier)} disabled={actionLoading !== null} style={plan.highlighted || plan.tier === "enterprise" ? primaryButtonLight(actionLoading === plan.tier) : { ...secondaryButtonLight(actionLoading === plan.tier), width: "100%" }}>
                          {actionLoading === plan.tier ? <Loader2 size={15} className="animate-spin" /> : null}
                          {billing.plan === "free" ? t("billing.upgrade") : t("billing.switch")} {t("billing.to")} {plan.name}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Notes */}
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "8px" }}>
          {[t("billing.note_cancel"), t("billing.note_downgrade")].map((note, i) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: "8px", padding: "10px 14px", borderRadius: "12px", background: "rgba(0,0,0,0.02)", border: "0.5px solid rgba(0,0,0,0.04)" }}>
              <Info size={14} style={{ color: "rgba(46,31,8,0.40)", flexShrink: 0, marginTop: "1px" }} />
              <span style={{ fontSize: "12px", color: "rgba(46,31,8,0.55)", fontFamily: fontStack, lineHeight: 1.4 }}>{note}</span>
            </div>
          ))}
          <div style={{ textAlign: "center", marginTop: "4px" }}>
            <span style={{ fontSize: "12px", color: "rgba(46,31,8,0.45)", fontFamily: fontStack }}>
              {t("billing.need_more")}{" "}
              <a href="mailto:hello@vitreon.app" style={{ color: "#5c2e08", textDecoration: "underline", textUnderlineOffset: "2px", fontWeight: 600 }}>
                {t("billing.contact_us")}
              </a>{" "}
              {t("billing.for_custom_plans")}
            </span>
          </div>
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
          maxWidth: "1100px",
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
            {t("billing.title")}
          </h1>
        </div>
      ) : (
        <div style={{ marginBottom: "24px" }}>
          <h1 style={{ fontFamily: "var(--font-heading), Georgia, serif", fontSize: "1.5rem", fontWeight: 700, color: "#1e1208", margin: 0 }}>
            {t("billing.title")}
          </h1>
          <p style={{ color: "rgba(46,31,8,0.55)", fontSize: "13px", fontFamily: fontStack, marginTop: "4px" }}>
            {t("billing.subtitle")}
          </p>
        </div>
      )}

      {/* Scrollable content */}
      <div style={{
        ...(isDark ? {
          flex: 1,
          overflowY: "auto" as const,
          padding: "28px 32px",
          maxWidth: 960,
          width: "100%",
          marginLeft: "auto",
          marginRight: "auto",
        } : {}),
      }}>
        {/* Loading */}
        {loading && (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: "60px 0" }}>
            <Loader2 size={24} className="animate-spin" style={{ color: isDark ? "#C9A84C" : "#5c2e08" }} />
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 14px", borderRadius: "8px", background: isDark ? "rgba(248,113,113,0.08)" : "rgba(220,38,38,0.06)", border: isDark ? "1px solid rgba(248,113,113,0.20)" : "0.5px solid rgba(220,38,38,0.15)", marginBottom: "16px" }}>
            <AlertTriangle size={16} style={{ color: isDark ? "#f87171" : "#dc2626", flexShrink: 0 }} />
            <span style={{ fontSize: "13px", color: isDark ? "#f87171" : "#dc2626", fontFamily: fontStack }}>{error}</span>
          </div>
        )}

        {/* Dark mode content */}
        {isDark && !loading && billing && (
          <motion.div
            variants={isV3 ? V3_LIST_VARIANT : undefined}
            initial={isV3 ? "hidden" : undefined}
            animate={isV3 ? "visible" : undefined}
            style={{ display: "flex", flexDirection: "column" }}
          >
            {/* Usage stats */}
            <motion.div variants={isV3 ? V3_ITEM_VARIANT : undefined}>
              {renderDarkUsageStats()}
            </motion.div>

            {/* Interval toggle */}
            <motion.div variants={isV3 ? V3_ITEM_VARIANT : undefined}>
              {renderDarkIntervalToggle()}
            </motion.div>

            {/* Plan cards row */}
            <motion.div variants={isV3 ? V3_ITEM_VARIANT : undefined}>
              <div style={{
                maxWidth: 880,
                margin: "0 auto",
                width: "100%",
                display: "flex",
                flexWrap: "wrap",
                gap: "14px",
              }}>
                {plans.map((plan) => renderDarkPlanCard(plan))}
              </div>
            </motion.div>

            {/* Subscription actions (manage / cancel) */}
            <motion.div variants={isV3 ? V3_ITEM_VARIANT : undefined}>
              {renderDarkSubscriptionActions()}
            </motion.div>

            {/* Notes */}
            <motion.div variants={isV3 ? V3_ITEM_VARIANT : undefined}>
              <div style={{ maxWidth: 880, margin: "20px auto 0", width: "100%", paddingTop: "8px", borderTop: "1px solid rgba(201,168,76,0.04)" }}>
                {[t("billing.note_cancel"), t("billing.note_downgrade")].map((note, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: "6px", padding: "5px 0" }}>
                    <Info size={10} style={{ color: "rgba(201,168,76,0.35)", flexShrink: 0, marginTop: "1px" }} />
                    <span style={{ fontFamily: fontStack, fontSize: "11px", lineHeight: 1.5, color: "var(--strict-text-dim)" }}>{note}</span>
                  </div>
                ))}
                <div style={{ textAlign: "center", marginTop: "8px" }}>
                  <span style={{ fontFamily: fontStack, fontSize: "10px", color: "var(--strict-text-dim)" }}>
                    {t("billing.need_more")}{" "}
                    <a href="mailto:hello@vitreon.app" style={{ color: "rgba(201,168,76,0.6)", textDecoration: "underline", textUnderlineOffset: "2px" }}>
                      {t("billing.contact_us")}
                    </a>{" "}
                    {t("billing.for_custom_plans")}
                  </span>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* Light mode content */}
        {!isDark && !loading && billing && renderLightContent()}
      </div>
    </div>
  );
}
