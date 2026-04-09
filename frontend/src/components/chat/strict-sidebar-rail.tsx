"use client";

/**
 * Strict design sidebar rail — the narrow left column with logo circle and
 * icon placeholders. Shared between StrictLayout (chat) and StrictPreview
 * (landing page). Desktop-only; callers are responsible for hiding on mobile.
 */
export function StrictSidebarRail() {
  return (
    <div
      style={{
        width: 44,
        flexShrink: 0,
        background: "var(--strict-glass-recessed)",
        borderRight: "1px solid var(--strict-gold-border)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        paddingTop: 14,
        gap: 10,
      }}
    >
      {/* Logo circle */}
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          border: "1px solid var(--strict-gold-border-active)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 8,
          color: "var(--strict-gold-text)",
          flexShrink: 0,
        }}
      >
        V
      </div>

      {/* Icon placeholders */}
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: 16,
            height: 16,
            borderRadius: 4,
            background: "var(--strict-glass-bg)",
            flexShrink: 0,
          }}
        />
      ))}
    </div>
  );
}
