"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { LanguageToggle } from "@/components/language-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { useI18n } from "@/lib/i18n";

const NAV_LINKS = [
  { href: "#features", labelKey: "strict.nav_features" },
  { href: "#pricing", labelKey: "strict.pricing_label" },
  { href: "/benchmarks", labelKey: "strict.nav_benchmarks" },
  { href: "/blog", labelKey: "strict.nav_blog" },
] as const;

export function StrictNav() {
  const { t } = useI18n();
  const [hoveredLink, setHoveredLink] = useState<string | null>(null);
  const [signInHovered, setSignInHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      <nav
        className="flex items-center mx-auto px-4 py-4 sm:px-8 sm:py-5"
        style={{
          maxWidth: "880px",
          borderBottom: menuOpen ? "none" : "1px solid var(--strict-nav-sep)",
        }}
      >
        <Link
          href="/"
          className="text-[13px] tracking-[2px] font-normal no-underline inline-flex items-center"
          style={{ color: "var(--strict-nav-signin)", minHeight: "44px" }}
        >
          VITREON
        </Link>

        <div className="ml-auto flex items-center gap-4 sm:gap-5">
          {/* Desktop nav links */}
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="hidden sm:block text-[11px] no-underline transition-colors duration-150"
              style={{
                color: hoveredLink === link.href
                  ? "var(--strict-nav-link-hover)"
                  : "var(--strict-nav-link)",
              }}
              onMouseEnter={() => setHoveredLink(link.href)}
              onMouseLeave={() => setHoveredLink(null)}
            >
              {t(link.labelKey)}
            </a>
          ))}

          <div className="hidden sm:flex items-center">
            <LanguageToggle />
          </div>

          <div className="hidden sm:flex items-center">
            <ThemeToggle />
          </div>

          <Link
            href="/login"
            className="text-[11px] no-underline pb-px transition-all duration-150"
            style={{
              color: signInHovered ? "var(--strict-nav-signin-hover)" : "var(--strict-nav-signin)",
              borderBottom: `1px solid ${signInHovered ? "var(--strict-gold-underbar-hover)" : "var(--strict-gold-underbar)"}`,
              display: "inline-flex",
              alignItems: "center",
              minHeight: "44px",
            }}
            onMouseEnter={() => setSignInHovered(true)}
            onMouseLeave={() => setSignInHovered(false)}
          >
            {t("landing.sign_in")}
          </Link>

          {/* Theme toggle — mobile nav bar (sm:hidden so desktop uses the one above) */}
          <div className="sm:hidden flex items-center">
            <ThemeToggle />
          </div>

          {/* Hamburger — mobile only */}
          <button
            className="sm:hidden"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            style={{
              display: "inline-flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              gap: "5px",
              width: "44px",
              height: "44px",
              background: "none",
              border: "none",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            <span
              style={{
                display: "block",
                width: "16px",
                height: "1px",
                background: "var(--strict-nav-signin)",
                transition: "transform 0.2s ease",
                transform: menuOpen ? "translateY(6px) rotate(45deg)" : "none",
              }}
            />
            <span
              style={{
                display: "block",
                width: "16px",
                height: "1px",
                background: "var(--strict-nav-signin)",
                transition: "opacity 0.2s ease",
                opacity: menuOpen ? 0 : 1,
              }}
            />
            <span
              style={{
                display: "block",
                width: "16px",
                height: "1px",
                background: "var(--strict-nav-signin)",
                transition: "transform 0.2s ease",
                transform: menuOpen ? "translateY(-6px) rotate(-45deg)" : "none",
              }}
            />
          </button>
        </div>
      </nav>

      {/* Mobile dropdown menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            className="sm:hidden mx-auto"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            style={{
              maxWidth: "880px",
              overflow: "hidden",
              borderBottom: "1px solid var(--strict-nav-sep)",
            }}
          >
            <div className="flex flex-col px-4 pb-3">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="text-[11px] no-underline"
                  style={{
                    color: "var(--strict-nav-link)",
                    display: "flex",
                    alignItems: "center",
                    minHeight: "44px",
                  }}
                  onClick={() => setMenuOpen(false)}
                >
                  {t(link.labelKey)}
                </a>
              ))}

              <div
                style={{
                  height: "1px",
                  background: "var(--strict-nav-sep)",
                  margin: "4px 0",
                }}
              />

              <div
                className="flex items-center justify-between"
                style={{ minHeight: "44px" }}
              >
                <span
                  className="text-[11px]"
                  style={{ color: "var(--strict-text-dim)" }}
                >
                  {t("settings.language")}
                </span>
                <LanguageToggle />
              </div>

              <div
                className="flex items-center justify-between"
                style={{ minHeight: "44px" }}
              >
                <span
                  className="text-[11px]"
                  style={{ color: "var(--strict-text-dim)" }}
                >
                  {t("settings.theme")}
                </span>
                <ThemeToggle />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
