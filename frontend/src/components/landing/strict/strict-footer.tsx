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
      <p className="text-[10px]" style={{ color: "var(--strict-text-dim)" }}>
        &copy; 2026 Vitreon Legal &middot;{" "}
        <Link href="/privacy" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>
          {t("landing.privacy")}
        </Link>
        {" "}&middot;{" "}
        <Link href="/terms" className="hover:underline" style={{ color: "var(--strict-text-dim)" }}>
          {t("landing.terms")}
        </Link>
      </p>
    </footer>
  );
}
