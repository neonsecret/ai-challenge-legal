"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export function StrictFooter() {
  const { t } = useI18n();

  return (
    <footer
      className="mx-auto max-w-[880px] px-4 sm:px-8 pt-10 pb-6 text-center"
      style={{ borderTop: "1px solid var(--strict-nav-sep)" }}
    >
      <div className="flex flex-wrap justify-center items-center gap-x-3 gap-y-0 text-[10px]" style={{ color: "var(--strict-text-dim)" }}>
        <span className="inline-flex items-center" style={{ minHeight: "44px" }}>&copy; 2026 Vitreon Legal</span>
        <span aria-hidden="true">&middot;</span>
        <Link href="/about" className="hover:underline inline-flex items-center" style={{ color: "var(--strict-text-dim)", minHeight: "44px" }}>About</Link>
        <span aria-hidden="true">&middot;</span>
        <Link href="/benchmarks" className="hover:underline inline-flex items-center" style={{ color: "var(--strict-text-dim)", minHeight: "44px" }}>Benchmarks</Link>
        <span aria-hidden="true">&middot;</span>
        <Link href="/blog" className="hover:underline inline-flex items-center" style={{ color: "var(--strict-text-dim)", minHeight: "44px" }}>Blog</Link>
        <span aria-hidden="true">&middot;</span>
        <Link href="/faq" className="hover:underline inline-flex items-center" style={{ color: "var(--strict-text-dim)", minHeight: "44px" }}>FAQ</Link>
        <span aria-hidden="true">&middot;</span>
        <Link href="/privacy" className="hover:underline inline-flex items-center" style={{ color: "var(--strict-text-dim)", minHeight: "44px" }}>
          {t("landing.privacy")}
        </Link>
        <span aria-hidden="true">&middot;</span>
        <Link href="/terms" className="hover:underline inline-flex items-center" style={{ color: "var(--strict-text-dim)", minHeight: "44px" }}>
          {t("landing.terms")}
        </Link>
      </div>
    </footer>
  );
}
