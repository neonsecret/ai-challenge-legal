"use client";

/* ─── Palette: "Arrakis / Dune"
   Source: schemecolor.com/dune.php + Dune 2021 poster palette
   Sand · Spice Gold · Camel · Warm Brown · Fremen Dusty Blue (success)
   No reds. All warm. Low contrast but fully readable. ─── */

const C = {
  spiceGold:  "#c9a230",   // rich spice gold — primary accent chips
  camel:      "#b29254",   // camel sand — source badge numbers, secondary
  cta:        "#5c2e08",   // espresso toned — warm dark coffee, slightly lifted
  caramel:    "#c47c00",   // caramel — source badges
  fremenBlue: "#3576ae",   // Fremen blue (Dune official) — clearly blue, still warm-adjacent
  text:       "#2e1f08",   // deep warm brown — body text
  muted:      "#7a5a20",   // warm mid-brown — labels, placeholder
  darkText:   "#1e1208",   // deepest — headings, strong
};

// Semantic chips
const success = { bg: "rgba(53,118,174,0.14)", border: "rgba(53,118,174,0.32)", text: "#1a3f6e" };
const warn    = { bg: "rgba(178,146,84,0.20)", border: "rgba(160,120,50,0.35)", text: "#5a3a08" };
const danger  = { bg: "rgba(139,53,32,0.14)",  border: "rgba(120,40,20,0.28)", text: "#5a1808" };

const glass = {
  background: "rgba(255,240,215,0.15)",   /* warm tint, less white */
  backdropFilter: "blur(36px) saturate(140%)",
  WebkitBackdropFilter: "blur(36px) saturate(140%)",
  border: "1px solid rgba(255,255,255,0.50)",
  borderRadius: "20px",
  boxShadow: "0 12px 40px rgba(100,50,0,0.28), inset 0 1.5px 0 rgba(255,255,255,0.60)",
} satisfies React.CSSProperties;

const glassSubtle = {
  background: "rgba(255,240,215,0.12)",
  backdropFilter: "blur(20px) saturate(130%)",
  WebkitBackdropFilter: "blur(20px) saturate(130%)",
  border: "1px solid rgba(255,255,255,0.38)",
  borderRadius: "12px",
} satisfies React.CSSProperties;

export default function ShowcasePage() {
  return (
    <div style={{
      minHeight: "100vh",
      position: "relative",
      background: "linear-gradient(145deg, #dfc090 0%, #e8d4b8 45%, #dbb870 100%)",
      fontFamily: "Inter, -apple-system, sans-serif",
      overflow: "hidden",
    }}>

      {/* Background shapes — give backdrop-filter colour to blur */}
      <div style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none" }}>
        <div style={{ position: "absolute", width: 580, height: 580, top: -80, left: "8%",
          background: "radial-gradient(circle, rgba(190,110,30,0.45) 0%, rgba(190,110,30,0.15) 45%, transparent 70%)" }} />
        <div style={{ position: "absolute", width: 460, height: 460, top: 180, right: "4%",
          background: "radial-gradient(circle, rgba(200,80,20,0.38) 0%, rgba(200,80,20,0.12) 45%, transparent 70%)" }} />
        <div style={{ position: "absolute", width: 380, height: 380, bottom: 30, left: "28%",
          background: "radial-gradient(circle, rgba(175,130,20,0.35) 0%, rgba(175,130,20,0.10) 45%, transparent 70%)" }} />
      </div>

      <div style={{ maxWidth: "900px", margin: "0 auto", padding: "40px 24px 60px", display: "flex", flexDirection: "column", gap: "20px", position: "relative", zIndex: 1 }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "8px" }}>
          <span style={{ display: "inline-block", padding: "3px 12px", borderRadius: "9999px", fontSize: "11px", fontWeight: 600, background: "rgba(255,255,255,0.35)", border: "1px solid rgba(255,255,255,0.55)", color: "#5a3e08", marginBottom: "14px", letterSpacing: "0.04em" }}>
            NeoLex v2.0 Preview
          </span>
          <h1 style={{ fontSize: "clamp(1.8rem,3vw,2.4rem)", fontWeight: 700, letterSpacing: "-0.03em", margin: "0 0 6px", color: "#2a1a06" }}>
            AI Legal Counsel
          </h1>
          <p style={{ color: "rgba(42,26,6,0.50)", fontSize: "14px", margin: 0 }}>
            Warm orange · white frost · gold accent
          </p>
        </div>

        {/* ── Chat card ── */}
        <div style={glass}>

          {/* Header */}
          <div style={{ padding: "18px 22px", borderBottom: "1px solid rgba(255,255,255,0.30)", display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{ width: 34, height: 34, borderRadius: 10, background: "rgba(201,168,76,0.30)", border: "1px solid rgba(201,168,76,0.50)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z" stroke="#7a5010" strokeWidth="1.3" strokeLinejoin="round" fill="rgba(201,168,76,0.30)" />
              </svg>
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ fontWeight: 700, fontSize: "14px", margin: 0, color: "#2a1a06" }}>NeoLex</p>
              <p style={{ color: "rgba(42,26,6,0.50)", fontSize: "11px", margin: 0 }}>AI Legal Counsel</p>
            </div>
            <Chip bg={success.bg} border={success.border} color={success.text}>Online</Chip>
            <Chip bg="rgba(233,196,106,0.28)" border="rgba(200,160,50,0.45)" color="#6b4200">DIFC</Chip>
          </div>

          {/* Messages */}
          <div style={{ padding: "22px", display: "flex", flexDirection: "column", gap: "18px", minHeight: "260px" }}>

            {/* User bubble */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <div style={{ maxWidth: "66%", background: "rgba(180,120,10,0.22)", border: "1px solid rgba(160,100,5,0.38)", borderRadius: "16px 16px 4px 16px", padding: "10px 14px", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)" }}>
                <p style={{ fontSize: "13px", margin: 0, lineHeight: 1.55, color: "#2a1806", fontWeight: 500 }}>
                  What are notice periods under DIFC Employment Law?
                </p>
              </div>
            </div>

            {/* Sources */}
            <div>
              <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.16em", color: C.muted, margin: "0 0 8px 0" }}>Sources</p>
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                {["DIFC Employment Law · Art.62 · p.18", "Labour Law 2022 · p.4", "DIFC Courts Circular · p.2"].map((label, i) => (
                  <div key={i} style={{ display: "inline-flex", alignItems: "center", gap: "6px", padding: "5px 12px 5px 6px", borderRadius: "9999px", background: "rgba(233,196,106,0.24)", border: `1px solid rgba(233,196,106,0.50)`, cursor: "pointer" }}>
                    <span style={{ width: 18, height: 18, borderRadius: 5, background: C.caramel, color: "#fff", fontSize: "10px", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{i + 1}</span>
                    <span style={{ fontSize: "11px", color: C.darkText, fontFamily: "monospace", fontWeight: 500 }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Answer */}
            <div>
              <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.16em", color: C.muted, margin: "0 0 8px 0" }}>Answer</p>
              <div style={{ background: "rgba(255,240,210,0.18)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(255,255,255,0.38)", borderRadius: "14px", padding: "14px 16px", marginBottom: "12px" }}>
                <p style={{ fontSize: "14px", lineHeight: 1.7, margin: 0, color: C.text }}>
                  Under <strong style={{ color: "#2a1806" }}>Article 62</strong> of DIFC Employment Law, the minimum notice period is{" "}
                  <strong style={{ color: "#2a1806" }}>30 days</strong> for employees with over 1 year of service, rising to{" "}
                  <strong style={{ color: "#2a1806" }}>90 days</strong> after 5 years.
                </p>
              </div>
              <Chip bg={success.bg} border={success.border} color={success.text}>High confidence</Chip>
            </div>
          </div>

          {/* Input */}
          <div style={{ padding: "14px 22px", borderTop: "1px solid rgba(255,255,255,0.28)", display: "flex", gap: "10px", alignItems: "center" }}>
            <input placeholder="Ask a legal question…" style={{ flex: 1, padding: "10px 14px", fontSize: "14px", borderRadius: "12px", background: "rgba(255,255,255,0.40)", border: "1px solid rgba(255,255,255,0.55)", color: C.text, outline: "none", backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)" }}
              onFocus={e => { e.currentTarget.style.borderColor = "rgba(160,100,5,0.55)"; }}
              onBlur={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.55)"; }}
            />
            <button style={{ padding: "10px 20px", borderRadius: "12px", fontSize: "13px", fontWeight: 700, background: C.cta, border: "none", color: "#fff", cursor: "pointer", boxShadow: "0 3px 14px rgba(201,168,76,0.35)" }}>Send</button>
          </div>
        </div>

        {/* ── Components ── */}
        <div style={glass}>
          <div style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: "14px" }}>
            <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.16em", color: C.muted, margin: 0 }}>Components</p>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
              <button style={{ padding: "8px 16px", borderRadius: "10px", fontSize: "13px", fontWeight: 700, background: C.cta, border: "none", color: "#fff", cursor: "pointer", boxShadow: `0 2px 10px rgba(201,168,76,0.30)` }}>Primary</button>
              <button style={{ ...glassSubtle, padding: "8px 16px", fontSize: "13px", fontWeight: 600, color: C.text, cursor: "pointer", border: `1px solid rgba(233,196,106,0.45)` }}>Secondary</button>
              <button style={{ padding: "8px 16px", fontSize: "13px", fontWeight: 500, background: "transparent", color: C.muted, border: `1px solid rgba(233,196,106,0.30)`, borderRadius: "10px", cursor: "pointer" }}>Ghost</button>
              <Chip bg="rgba(233,196,106,0.28)" border="rgba(200,160,50,0.45)" color="#6b4200">Gold</Chip>
              <Chip bg={success.bg} border={success.border} color={success.text}>Success</Chip>
              <Chip bg={warn.bg} border={warn.border} color={warn.text}>Warning</Chip>
              <Chip bg={danger.bg} border={danger.border} color={danger.text}>Danger</Chip>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              {["Search legal documents…", "API key"].map((ph, i) => (
                <input key={i} placeholder={ph} type={i === 1 ? "password" : "text"} style={{ flex: 1, padding: "10px 14px", fontSize: "14px", borderRadius: "12px", background: "rgba(255,255,255,0.40)", border: "1px solid rgba(255,255,255,0.55)", color: C.text, outline: "none" }} />
              ))}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

function Chip({ bg, border, color, children }: { bg: string; border: string; color: string; children: React.ReactNode }) {
  return (
    <span style={{ padding: "3px 10px", borderRadius: "9999px", fontSize: "11px", fontWeight: 600, background: bg, border: `1px solid ${border}`, color }}>
      {children}
    </span>
  );
}
