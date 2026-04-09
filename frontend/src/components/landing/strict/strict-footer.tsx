"use client";

export function StrictFooter() {
  return (
    <footer
      className="mx-auto max-w-[880px] px-8 pt-10 pb-6 text-center"
      style={{ borderTop: "1px solid var(--strict-nav-sep)" }}
    >
      <p className="text-[10px]" style={{ color: "var(--strict-text-dim)" }}>
        &copy; 2026 Vitreon Legal &middot; Privacy &middot; Terms
      </p>
    </footer>
  );
}
