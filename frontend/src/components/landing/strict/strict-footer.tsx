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
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-[10px]" style={{ color: "var(--strict-text-dim)" }}>
        <span>&copy; 2026 Vitreon Legal</span>
        <span>&middot;</span>
        <Link href="/about" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>About</Link>
        <span>&middot;</span>
        <Link href="/benchmarks" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>Benchmarks</Link>
        <span>&middot;</span>
        <Link href="/blog" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>Blog</Link>
        <span>&middot;</span>
        <Link href="/faq" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>FAQ</Link>
        <span>&middot;</span>
        <Link href="/privacy" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>
          {t("landing.privacy")}
        </Link>
        <span>&middot;</span>
        <Link href="/terms" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>
          {t("landing.terms")}
        </Link>
      </div>
    </footer>
  );
}
