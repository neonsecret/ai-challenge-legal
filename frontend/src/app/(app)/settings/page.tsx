"use client";

import { useState, useEffect } from "react";
import { Eye, EyeOff, Check, Moon, Sun, Monitor, ExternalLink } from "lucide-react";
import { useTheme } from "next-themes";

const APP_VERSION = "0.1.0";
const DEFAULT_API_URL = "http://localhost:8000";

const fontStack = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif";

type ThemeOption = "light" | "dark" | "system";

export default function SettingsPage() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [backendUrl, setBackendUrl] = useState(DEFAULT_API_URL);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted && resolvedTheme === "dark";

  // Load from localStorage on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      setApiKey(localStorage.getItem("neolex_api_key") ?? "");
      setBackendUrl(
        localStorage.getItem("neolex_backend_url") ?? DEFAULT_API_URL
      );
    }
  }, []);

  const handleSave = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem("neolex_api_key", apiKey.trim());
      localStorage.setItem("neolex_backend_url", backendUrl.trim() || DEFAULT_API_URL);
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const themeOptions: { value: ThemeOption; label: string; icon: React.ReactNode }[] = [
    { value: "light", label: "Light", icon: <Sun size={16} /> },
    { value: "dark", label: "Dark", icon: <Moon size={16} /> },
    { value: "system", label: "System", icon: <Monitor size={16} /> },
  ];

  const glassCard: React.CSSProperties = {
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

  const inputStyleBase: React.CSSProperties = {
    background: isDark
      ? "rgba(255,255,255,0.08)"
      : "rgba(255,255,255,0.35)",
    border: isDark
      ? "0.5px solid rgba(255,255,255,0.14)"
      : "0.5px solid rgba(255,255,255,0.50)",
    borderRadius: "10px",
    padding: "9px 12px",
    fontSize: "13px",
    color: isDark ? "rgba(255,255,255,0.88)" : "#2e1f08",
    caretColor: isDark ? "#C9A84C" : undefined,
    fontFamily: "monospace",
    width: "100%",
    outline: "none",
    boxSizing: "border-box",
  };

  const labelStyleDyn: React.CSSProperties = {
    fontSize: "12px",
    fontWeight: 500,
    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
    fontFamily: fontStack,
    marginBottom: "6px",
    display: "block",
  };

  const mutedTextDyn: React.CSSProperties = {
    fontSize: "12px",
    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
    fontFamily: fontStack,
    marginTop: "4px",
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

  const aboutRow: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 0",
    borderBottom: isDark
      ? "0.5px solid rgba(255,255,255,0.08)"
      : "0.5px solid rgba(255,255,255,0.20)",
  };

  const handleInputFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = isDark
      ? "rgba(201,168,76,0.55)"
      : "rgba(196,124,0,0.55)";
    if (isDark) {
      e.currentTarget.style.boxShadow = "0 0 0 3px rgba(201,168,76,0.10)";
    }
  };

  const handleInputBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = isDark
      ? "rgba(255,255,255,0.14)"
      : "rgba(255,255,255,0.50)";
    e.currentTarget.style.boxShadow = "none";
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
      <div style={{ marginBottom: "24px" }}>
        <h1
          style={{
            fontFamily: "var(--font-heading), Georgia, serif",
            fontSize: "1.5rem",
            fontWeight: 700,
            color: isDark ? "rgba(255,255,255,0.90)" : "#1e1208",
            margin: 0,
          }}
        >
          Settings
        </h1>
        <p
          style={{
            color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.55)",
            fontSize: "13px",
            fontFamily: fontStack,
            marginTop: "4px",
          }}
        >
          Configure your Vitreon Legal connection and preferences
        </p>
      </div>

      {/* Cards container */}
      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {/* API Configuration */}
        <div style={glassCard}>
          <div style={cardHeader}>
            <h2 style={cardHeading}>API Configuration</h2>
          </div>
          <div style={cardBody}>
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* API Key */}
              <div>
                <label htmlFor="api-key" style={labelStyleDyn}>
                  API Key
                </label>
                <div style={{ position: "relative" }}>
                  <input
                    id="api-key"
                    type={showKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter your Vitreon Legal API key"
                    autoComplete="off"
                    style={{
                      ...inputStyleBase,
                      paddingRight: "36px",
                    }}
                    onFocus={handleInputFocus}
                    onBlur={handleInputBlur}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey((v) => !v)}
                    aria-label={showKey ? "Hide API key" : "Show API key"}
                    style={{
                      position: "absolute",
                      right: "10px",
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.45)",
                      padding: "2px",
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                <p style={mutedTextDyn}>
                  Stored in browser localStorage. Never sent to third parties.
                </p>
              </div>

              {/* Save button */}
              <div>
                <button
                  onClick={handleSave}
                  style={{
                    background: isDark
                      ? "linear-gradient(135deg, #C9A84C, #e8cc7a)"
                      : "#5c2e08",
                    color: isDark ? "#0F1623" : "#fff8ee",
                    borderRadius: "10px",
                    padding: "9px 20px",
                    fontSize: "13px",
                    fontWeight: 600,
                    fontFamily: fontStack,
                    boxShadow: isDark
                      ? "0 2px 12px rgba(201,168,76,0.30)"
                      : "0 2px 12px rgba(92,46,8,0.30)",
                    border: "none",
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    transition: "opacity 0.15s ease",
                  }}
                >
                  {saved ? (
                    <>
                      <Check size={15} />
                      Saved
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Appearance */}
        <div style={glassCard}>
          <div style={cardHeader}>
            <h2 style={cardHeading}>Appearance</h2>
          </div>
          <div style={cardBody}>
            <div>
              <span style={labelStyleDyn}>Theme</span>
              <div style={{ display: "flex", gap: "8px", marginTop: "2px" }}>
                {themeOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setTheme(opt.value)}
                    style={themeButton(theme === opt.value)}
                  >
                    {opt.icon}
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* About */}
        <div style={glassCard}>
          <div style={cardHeader}>
            <h2 style={cardHeading}>About</h2>
          </div>
          <div style={cardBody}>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div style={aboutRow}>
                <span
                  style={{
                    fontSize: "13px",
                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
                    fontFamily: fontStack,
                  }}
                >
                  Application
                </span>
                <span
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: isDark ? "rgba(255,255,255,0.65)" : "#2e1f08",
                    fontFamily: fontStack,
                  }}
                >
                  Vitreon Legal
                </span>
              </div>
              <div style={aboutRow}>
                <span
                  style={{
                    fontSize: "13px",
                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
                    fontFamily: fontStack,
                  }}
                >
                  Version
                </span>
                <span
                  style={{
                    background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)",
                    border: isDark ? "0.5px solid rgba(255,255,255,0.14)" : "0.5px solid rgba(255,255,255,0.45)",
                    color: isDark ? "rgba(255,255,255,0.65)" : "#5c2e08",
                    borderRadius: "9999px",
                    padding: "2px 10px",
                    fontSize: "11px",
                    fontFamily: "monospace",
                  }}
                >
                  v{APP_VERSION}
                </span>
              </div>
              <div style={aboutRow}>
                <span
                  style={{
                    fontSize: "13px",
                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
                    fontFamily: fontStack,
                  }}
                >
                  Backend
                </span>
                <a
                  href={`${backendUrl || DEFAULT_API_URL}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    fontSize: "13px",
                    color: isDark ? "#C9A84C" : "#5c2e08",
                    fontFamily: fontStack,
                    fontWeight: 500,
                    textDecoration: "none",
                  }}
                >
                  API Docs
                  <ExternalLink size={12} />
                </a>
              </div>
              <div
                style={{
                  ...aboutRow,
                  borderBottom: "none",
                }}
              >
                <span
                  style={{
                    fontSize: "13px",
                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
                    fontFamily: fontStack,
                  }}
                >
                  Tagline
                </span>
                <span
                  style={{
                    fontSize: "13px",
                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.55)",
                    fontStyle: "italic",
                    fontFamily: fontStack,
                  }}
                >
                  Your AI Legal Counsel
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
