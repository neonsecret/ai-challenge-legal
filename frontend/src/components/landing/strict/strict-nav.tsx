"use client";

import { useState } from "react";
import Link from "next/link";

const NAV_LINKS = [
  { href: "#features", label: "Features" },
  { href: "#pricing", label: "Pricing" },
] as const;

export function StrictNav() {
  const [hoveredLink, setHoveredLink] = useState<string | null>(null);
  const [signInHovered, setSignInHovered] = useState(false);

  return (
    <nav
      className="flex items-center mx-auto px-4 py-4 sm:px-8 sm:py-5"
      style={{
        maxWidth: "880px",
        borderBottom: "1px solid var(--strict-nav-sep)",
      }}
    >
      <Link
        href="/"
        className="text-[13px] tracking-[2px] font-normal no-underline"
        style={{ color: "var(--strict-nav-signin)" }}
      >
        VITREON
      </Link>

      {/* Desktop nav links */}
      <div className="ml-auto flex items-center gap-4 sm:gap-5">
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
            {link.label}
          </a>
        ))}

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
          Sign In
        </Link>
      </div>
    </nav>
  );
}
