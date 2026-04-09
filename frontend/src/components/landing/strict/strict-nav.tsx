"use client";

import Link from "next/link";

const NAV_LINKS = [
  { href: "#features", label: "Features" },
  { href: "#pricing", label: "Pricing" },
] as const;

export function StrictNav() {
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
            style={{ color: "var(--strict-nav-link)" }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.color = "var(--strict-nav-link-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.color = "var(--strict-nav-link)")
            }
          >
            {link.label}
          </a>
        ))}

        <Link
          href="/login"
          className="text-[11px] no-underline pb-px transition-all duration-150"
          style={{
            color: "var(--strict-nav-signin)",
            borderBottom: "1px solid var(--strict-gold-underbar)",
            /* Ensure 44px tap target on mobile */
            display: "inline-flex",
            alignItems: "center",
            minHeight: "44px",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "var(--strict-nav-signin-hover)";
            e.currentTarget.style.borderBottomColor =
              "var(--strict-gold-underbar-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--strict-nav-signin)";
            e.currentTarget.style.borderBottomColor =
              "var(--strict-gold-underbar)";
          }}
        >
          Sign In
        </Link>
      </div>
    </nav>
  );
}
