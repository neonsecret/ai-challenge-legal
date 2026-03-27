"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { MessageSquare, FileText, Settings, Sun, Moon } from "lucide-react";

const navItems = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function BottomNav() {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";

  const pill = isDark ? {
    background: "rgba(15,22,35,0.80)",
    border: "0.5px solid rgba(255,255,255,0.12)",
    boxShadow: [
      "inset 0 1px 0 rgba(255,255,255,0.08)",
      "0 8px 40px rgba(0,0,0,0.40)",
      "0 2px 6px rgba(0,0,0,0.30)",
    ].join(", "),
  } : {
    background: "rgba(255,250,235,0.22)",
    border: "0.5px solid rgba(255,255,255,0.42)",
    boxShadow: [
      "inset 0 1.5px 0 rgba(255,255,255,0.90)",
      "inset 1px 0 0 rgba(255,255,255,0.35)",
      "inset -1px 0 0 rgba(255,255,255,0.15)",
      "0 4px 20px rgba(100,50,0,0.12)",
      "0 1px 3px rgba(100,50,0,0.06)",
    ].join(", "),
  };

  const activeColor = isDark ? "#C9A84C" : "#5c2e08";
  const inactiveColor = isDark ? "rgba(255,255,255,0.42)" : "rgba(46,31,8,0.48)";
  const activeBg = isDark ? "rgba(201,168,76,0.16)" : "rgba(255,255,255,0.30)";
  const activeBorder = isDark ? "0.5px solid rgba(201,168,76,0.30)" : "0.5px solid rgba(255,255,255,0.50)";

  return (
    <div
      style={{
        position: "fixed",
        bottom: "20px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: "1px",
        padding: "4px 5px",
        backdropFilter: "blur(32px) saturate(180%)",
        WebkitBackdropFilter: "blur(32px) saturate(180%)",
        borderRadius: "22px",
        ...pill,
      }}
    >
      {navItems.map(({ href, label, icon: Icon }) => {
        const isActive = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "3px",
              padding: "7px 14px",
              borderRadius: "16px",
              textDecoration: "none",
              transition: "all 0.14s ease",
              background: isActive ? activeBg : "transparent",
              boxShadow: isActive && !isDark ? "inset 0 1px 0 rgba(255,255,255,0.80), 0 1px 4px rgba(100,50,0,0.10)" : "none",
              border: isActive ? activeBorder : "0.5px solid transparent",
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)";
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.background = "transparent";
            }}
          >
            <Icon size={18} strokeWidth={isActive ? 2 : 1.6} style={{ color: isActive ? activeColor : inactiveColor }} />
            <span style={{
              fontSize: "10px",
              fontWeight: isActive ? 600 : 400,
              color: isActive ? activeColor : inactiveColor,
              fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
              letterSpacing: "0.01em",
            }}>
              {label}
            </span>
          </Link>
        );
      })}

      {/* Separator */}
      <div style={{ width: 1, height: 28, background: isDark ? "rgba(255,255,255,0.10)" : "rgba(46,31,8,0.12)", margin: "0 2px" }} />

      {/* Theme toggle */}
      <button
        onClick={() => setTheme(isDark ? "light" : "dark")}
        title={isDark ? "Switch to light mode" : "Switch to dark mode"}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "3px",
          padding: "8px 14px",
          borderRadius: "16px",
          background: "transparent",
          border: "0.5px solid transparent",
          cursor: "pointer",
          transition: "all 0.14s ease",
          color: isDark ? "rgba(255,255,255,0.42)" : "rgba(46,31,8,0.48)",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
      >
        {isDark
          ? <Sun size={18} strokeWidth={1.6} />
          : <Moon size={18} strokeWidth={1.6} />
        }
        <span style={{ fontSize: "10px", fontWeight: 400, fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif", letterSpacing: "0.01em" }}>
          {isDark ? "Light" : "Dark"}
        </span>
      </button>
    </div>
  );
}
