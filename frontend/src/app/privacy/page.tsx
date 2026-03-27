import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — NeoLex",
  description:
    "How NeoLex collects, uses, and protects your data when you use our AI-powered legal research platform.",
};

const LAST_UPDATED = "March 27, 2026";

export default function PrivacyPage() {
  return (
    <div
      className="dark min-h-screen"
      style={{ background: "#0F1623", color: "rgba(255,255,255,0.88)" }}
    >
      {/* Nav */}
      <nav
        className="sticky top-0 z-50 w-full"
        style={{
          background: "rgba(15,22,35,0.90)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div
              className="flex items-center justify-center size-7 rounded-lg"
              style={{
                background: "rgba(201,168,76,0.12)",
                border: "1px solid rgba(201,168,76,0.25)",
              }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M7 1L2 4v3c0 3 2.2 5.4 5 6 2.8-.6 5-3 5-6V4L7 1z"
                  stroke="#C9A84C"
                  strokeWidth="1.2"
                  strokeLinejoin="round"
                  fill="rgba(201,168,76,0.15)"
                />
              </svg>
            </div>
            <span
              className="font-heading text-lg font-bold tracking-tight group-hover:opacity-80 transition-opacity"
              style={{ color: "rgba(255,255,255,0.95)" }}
            >
              NeoLex
            </span>
          </Link>

          <Link
            href="/"
            className="text-sm transition-colors"
            style={{ color: "rgba(255,255,255,0.38)" }}
          >
            &larr; Back to home
          </Link>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-16">
        {/* Header */}
        <div className="mb-12">
          <p
            className="text-[11px] uppercase tracking-[0.2em] font-semibold mb-4"
            style={{ color: "rgba(201,168,76,0.75)" }}
          >
            Legal
          </p>
          <h1
            className="font-heading font-bold mb-4"
            style={{
              fontSize: "clamp(2rem, 4vw, 3rem)",
              letterSpacing: "-0.025em",
              lineHeight: 1.15,
              color: "rgba(255,255,255,0.95)",
            }}
          >
            Privacy Policy
          </h1>
          <p className="text-sm" style={{ color: "rgba(255,255,255,0.38)" }}>
            Last updated: {LAST_UPDATED}
          </p>
        </div>

        {/* Intro */}
        <Section>
          <p style={{ color: "rgba(255,255,255,0.62)", lineHeight: 1.75 }}>
            NeoLex (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;us&rdquo;) is committed to
            protecting the privacy of our users. This Privacy Policy explains what data we collect,
            why we collect it, how we use it, and the rights you have over your information when you
            use the NeoLex AI legal research platform (&ldquo;Service&rdquo;).
          </p>
          <p className="mt-4" style={{ color: "rgba(255,255,255,0.62)", lineHeight: 1.75 }}>
            By using the Service you agree to the practices described in this policy. If you do not
            agree, please discontinue use of the Service.
          </p>
        </Section>

        <Divider />

        {/* 1. Data Collection */}
        <Section>
          <SectionTitle index="1">Data Collection</SectionTitle>

          <SubHeading>Information you provide</SubHeading>
          <BodyText>
            When you configure NeoLex, you provide your Anthropic API key to authenticate requests
            to the Claude API. This key is stored exclusively in your browser&apos;s
            <code style={codeStyle}>localStorage</code> and is never transmitted to NeoLex servers.
          </BodyText>

          <SubHeading>Documents you upload</SubHeading>
          <BodyText>
            Documents you upload for analysis are processed in memory on the server instance you
            connect to (typically running on your own infrastructure). We do not copy, cache, or
            retain the raw text of your documents beyond the duration of a single analysis session.
            Documents are stored locally on client-controlled infrastructure and are not transferred
            to NeoLex or any third-party storage service.
          </BodyText>

          <SubHeading>Usage and audit logs</SubHeading>
          <BodyText>
            We retain structured audit logs — including query timestamps, document identifiers, and
            session metadata — for up to <strong style={{ color: "rgba(255,255,255,0.85)" }}>365 days</strong> by
            default. These logs support SOC 2 compliance, incident investigation, and billing
            integrity. Log retention periods may be adjusted under enterprise agreements.
          </BodyText>

          <SubHeading>Technical data</SubHeading>
          <BodyText>
            Standard web server logs (IP address, browser user-agent, request path, response code)
            may be recorded to support operational monitoring and security incident response. These
            logs are not linked to individual user identities.
          </BodyText>
        </Section>

        <Divider />

        {/* 2. How We Use Data */}
        <Section>
          <SectionTitle index="2">How We Use Your Data</SectionTitle>
          <BodyText>We use the information described above to:</BodyText>
          <BulletList
            items={[
              "Deliver accurate, source-grounded answers from your legal documents.",
              "Forward your queries and document content to the Anthropic Claude API on your behalf, using the API key you supply.",
              "Maintain audit trails required by SOC 2 Type II controls and enterprise data governance policies.",
              "Detect and investigate security incidents, abuse, or service integrity issues.",
              "Improve the reliability, performance, and accuracy of the Service through anonymised aggregate telemetry.",
            ]}
          />

          <Callout>
            We do <strong>not</strong> use your documents, queries, or any content you submit to
            train, fine-tune, or evaluate AI models — including the models provided by Anthropic.
            Your data is processed to generate your response and nothing else.
          </Callout>
        </Section>

        <Divider />

        {/* 3. Anthropic API & Data Handling */}
        <Section>
          <SectionTitle index="3">Anthropic API and Data Handling</SectionTitle>
          <BodyText>
            NeoLex uses the Anthropic Claude API to generate legal research answers. When you submit
            a query, the relevant document excerpts and your question are sent to Anthropic&apos;s
            infrastructure for inference. This data handling is governed by{" "}
            <a
              href="https://www.anthropic.com/legal/privacy"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "#C9A84C" }}
              className="hover:underline"
            >
              Anthropic&apos;s Privacy Policy
            </a>{" "}
            and their{" "}
            <a
              href="https://www.anthropic.com/legal/aup"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "#C9A84C" }}
              className="hover:underline"
            >
              Usage Policies
            </a>
            .
          </BodyText>
          <BodyText>
            Anthropic&apos;s enterprise API does not use customer inputs to train foundation models
            by default. We recommend reviewing their data handling documentation if you have
            enterprise data residency or processing requirements.
          </BodyText>
        </Section>

        <Divider />

        {/* 4. Data Retention */}
        <Section>
          <SectionTitle index="4">Data Retention</SectionTitle>
          <BulletList
            items={[
              "API keys: stored only in your browser localStorage; purged when you clear site data or log out.",
              "Document content: not persisted beyond the active session.",
              "Audit logs: retained for 365 days by default; configurable under enterprise agreements.",
              "Anonymised aggregate telemetry: retained indefinitely for service improvement.",
            ]}
          />
          <BodyText>
            You may request deletion of audit log entries associated with your organisation by
            contacting{" "}
            <a href="mailto:privacy@neolex.ai" style={{ color: "#C9A84C" }} className="hover:underline">
              privacy@neolex.ai
            </a>
            . Deletion requests are processed within 30 days subject to applicable legal retention
            obligations.
          </BodyText>
        </Section>

        <Divider />

        {/* 5. Your Rights */}
        <Section>
          <SectionTitle index="5">Your Rights</SectionTitle>
          <BodyText>
            Depending on your jurisdiction, you may have the following rights regarding your personal
            data:
          </BodyText>
          <BulletList
            items={[
              "Access: request a copy of the personal data we hold about you.",
              "Rectification: request correction of inaccurate data.",
              "Erasure: request deletion of your personal data where no overriding legal obligation exists.",
              "Portability: receive your data in a structured, machine-readable format.",
              "Objection: object to processing based on legitimate interests.",
              "Restriction: request that we restrict processing of your data in certain circumstances.",
            ]}
          />
          <BodyText>
            To exercise any of these rights, email{" "}
            <a href="mailto:privacy@neolex.ai" style={{ color: "#C9A84C" }} className="hover:underline">
              privacy@neolex.ai
            </a>{" "}
            with the subject line &ldquo;Data Subject Request&rdquo;. We will respond within 30 days.
          </BodyText>
        </Section>

        <Divider />

        {/* 6. Security */}
        <Section>
          <SectionTitle index="6">Security</SectionTitle>
          <BodyText>
            NeoLex is designed with security-first principles:
          </BodyText>
          <BulletList
            items={[
              "SOC 2 Type II controls govern access, change management, and incident response.",
              "All data in transit is encrypted using TLS 1.2 or higher.",
              "API keys are never stored server-side; they remain in your browser only.",
              "Document processing occurs on client-controlled infrastructure by default.",
              "Access to audit logs is restricted to authorised personnel with a documented need.",
            ]}
          />
          <BodyText>
            If you discover a security vulnerability, please disclose it responsibly to{" "}
            <a href="mailto:security@neolex.ai" style={{ color: "#C9A84C" }} className="hover:underline">
              security@neolex.ai
            </a>
            .
          </BodyText>
        </Section>

        <Divider />

        {/* 7. Cookies */}
        <Section>
          <SectionTitle index="7">Cookies and Local Storage</SectionTitle>
          <BodyText>
            NeoLex does not use tracking cookies or third-party analytics cookies. We use
            browser <code style={codeStyle}>localStorage</code> solely to persist your API key and
            application preferences (such as backend URL) between sessions. No data stored in
            localStorage is transmitted to any third party.
          </BodyText>
        </Section>

        <Divider />

        {/* 8. Contact */}
        <Section>
          <SectionTitle index="8">Contact Us</SectionTitle>
          <BodyText>
            For questions, complaints, or data subject requests related to this Privacy Policy,
            please contact:
          </BodyText>
          <div
            className="mt-4 rounded-xl p-5"
            style={{
              background: "rgba(201,168,76,0.05)",
              border: "1px solid rgba(201,168,76,0.15)",
            }}
          >
            <p className="font-heading font-semibold text-base mb-1" style={{ color: "rgba(255,255,255,0.9)" }}>
              NeoLex — Privacy Team
            </p>
            <p className="text-sm" style={{ color: "rgba(255,255,255,0.55)" }}>
              Email:{" "}
              <a href="mailto:privacy@neolex.ai" style={{ color: "#C9A84C" }} className="hover:underline">
                privacy@neolex.ai
              </a>
            </p>
          </div>
        </Section>

        {/* Footer nav */}
        <div
          className="mt-16 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs"
          style={{
            borderTop: "1px solid rgba(255,255,255,0.06)",
            color: "rgba(255,255,255,0.28)",
          }}
        >
          <span>2026 NeoLex</span>
          <div className="flex items-center gap-4">
            <Link href="/privacy" className="hover:text-white/60 transition-colors" style={{ color: "#C9A84C" }}>
              Privacy Policy
            </Link>
            <span style={{ color: "rgba(255,255,255,0.15)" }}>·</span>
            <Link href="/terms" className="hover:text-white/60 transition-colors">
              Terms of Service
            </Link>
            <span style={{ color: "rgba(255,255,255,0.15)" }}>·</span>
            <Link href="/" className="hover:text-white/60 transition-colors">
              Home
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ── Shared layout primitives ── */

function Section({ children }: { children: React.ReactNode }) {
  return <section className="mb-10">{children}</section>;
}

function Divider() {
  return (
    <hr
      className="my-10"
      style={{ borderColor: "rgba(255,255,255,0.06)" }}
    />
  );
}

function SectionTitle({
  index,
  children,
}: {
  index: string;
  children: React.ReactNode;
}) {
  return (
    <h2
      className="font-heading font-bold mb-4"
      style={{
        fontSize: "1.25rem",
        color: "rgba(255,255,255,0.92)",
        letterSpacing: "-0.01em",
      }}
    >
      <span style={{ color: "rgba(201,168,76,0.7)", marginRight: "0.5rem", fontFamily: "var(--font-sans), sans-serif", fontSize: "0.85em", fontWeight: 500 }}>
        {index}.
      </span>
      {children}
    </h2>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="font-semibold mb-2 mt-6"
      style={{ fontSize: "0.9375rem", color: "rgba(255,255,255,0.78)" }}
    >
      {children}
    </h3>
  );
}

function BodyText({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="mb-3 text-sm leading-7"
      style={{ color: "rgba(255,255,255,0.58)" }}
    >
      {children}
    </p>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="mb-4 space-y-1.5 pl-1">
      {items.map((item) => (
        <li
          key={item}
          className="flex items-start gap-2.5 text-sm leading-6"
          style={{ color: "rgba(255,255,255,0.58)" }}
        >
          <span
            className="mt-2 shrink-0 size-1 rounded-full"
            style={{ background: "#C9A84C", opacity: 0.7 }}
          />
          {item}
        </li>
      ))}
    </ul>
  );
}

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="mt-4 rounded-xl px-5 py-4 text-sm leading-6"
      style={{
        background: "rgba(201,168,76,0.07)",
        border: "1px solid rgba(201,168,76,0.18)",
        color: "rgba(255,255,255,0.72)",
      }}
    >
      {children}
    </div>
  );
}

const codeStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  fontSize: "0.8125em",
  background: "rgba(255,255,255,0.07)",
  borderRadius: "4px",
  padding: "1px 5px",
  color: "rgba(201,168,76,0.9)",
};
