import Link from "next/link";
import type {Metadata} from "next";

export const metadata: Metadata = {
    title: "Privacy Policy — Vitreon Legal",
    description:
        "How Vitreon Legal collects, uses, and protects your data when you use our AI-powered legal research platform.",
    alternates: {
        canonical: "https://vitreon.app/privacy",
    },
};

const LAST_UPDATED = "April 5, 2026";

export default function PrivacyPage() {
    return (
        <div
            className="dark min-h-screen"
            style={{background: "#0F1623", color: "rgba(255,255,255,0.88)"}}
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
                            style={{color: "rgba(255,255,255,0.95)"}}
                        >
              Vitreon Legal
            </span>
                    </Link>

                    <Link
                        href="/"
                        className="text-sm transition-colors"
                        style={{color: "rgba(255,255,255,0.38)"}}
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
                        style={{color: "rgba(201,168,76,0.75)"}}
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
                    <p className="text-sm" style={{color: "rgba(255,255,255,0.38)"}}>
                        Last updated: {LAST_UPDATED}
                    </p>
                </div>

                {/* Intro */}
                <Section>
                    <p style={{color: "rgba(255,255,255,0.62)", lineHeight: 1.75}}>
                        Vitreon Legal (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;us&rdquo;) operates the
                        AI-powered legal research platform at{" "}
                        <a href="https://vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                            vitreon.app
                        </a>
                        . This Privacy Policy explains what personal data we collect, why we collect it, how
                        long we keep it, and the rights you have over your information under the General Data
                        Protection Regulation (GDPR) and other applicable privacy laws.
                    </p>
                    <p className="mt-4" style={{color: "rgba(255,255,255,0.62)", lineHeight: 1.75}}>
                        By using the Service you agree to the practices described in this policy. If you do not
                        agree, please discontinue use of the Service.
                    </p>
                </Section>

                <Divider/>

                {/* 1. Who We Are */}
                <Section>
                    <SectionTitle index="1">Who We Are</SectionTitle>
                    <BodyText>
                        Vitreon Legal is an AI-powered legal research platform that helps legal professionals
                        find answers grounded in primary legal sources. We are the data controller for the
                        personal data processed through our Service.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 2. Data We Collect */}
                <Section>
                    <SectionTitle index="2">Data We Collect</SectionTitle>

                    <SubHeading>Account information</SubHeading>
                    <BodyText>
                        When you create an account, we collect your email address, display name, and a
                        cryptographically hashed version of your password. If you sign in with Google, we
                        receive your email, name, and profile picture URL from Google. We never store your
                        password in plain text.
                    </BodyText>

                    <SubHeading>Legal research queries and answers</SubHeading>
                    <BodyText>
                        When you submit a question, we store your query text and the AI-generated answer
                        (including cited sources) in your conversation history. This enables multi-turn
                        conversations and lets you review past research.
                    </BodyText>

                    <SubHeading>Session and security data</SubHeading>
                    <BodyText>
                        We record your IP address and browser user-agent string when you log in or create a
                        session. This data is used exclusively for security purposes — detecting unauthorised
                        access, preventing brute-force attacks, and investigating incidents.
                    </BodyText>

                    <SubHeading>Payment information</SubHeading>
                    <BodyText>
                        Payments are processed entirely by{" "}
                        <a
                            href="https://stripe.com/privacy"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{color: "#C9A84C"}}
                            className="hover:underline"
                        >
                            Stripe
                        </a>
                        . We do not store credit card numbers, CVVs, or full card details on our servers. We
                        only retain your Stripe customer ID and subscription status for billing management.
                    </BodyText>

                    <SubHeading>Documents you upload</SubHeading>
                    <BodyText>
                        Documents you upload for analysis are processed and indexed on our servers. Document
                        content is stored only for the purpose of providing the research service and is subject
                        to the retention periods described below.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 3. Why We Collect It */}
                <Section>
                    <SectionTitle index="3">Why We Collect Your Data</SectionTitle>
                    <BodyText>We process your personal data for the following purposes:</BodyText>
                    <BulletList
                        items={[
                            "Provide the Service: deliver accurate, source-grounded legal research answers and maintain your conversation history.",
                            "Improve answer quality: analyse aggregate usage patterns to improve retrieval accuracy and answer relevance.",
                            "Security and abuse prevention: detect unauthorised access, enforce rate limits, and investigate security incidents.",
                            "Billing: manage subscriptions, process payments through Stripe, and enforce usage limits.",
                            "Legal compliance: meet our obligations under GDPR and other applicable data protection laws.",
                        ]}
                    />

                    <SubHeading>Lawful basis for processing</SubHeading>
                    <BodyText>
                        Under GDPR Article 6, we rely on the following legal bases for processing your
                        personal data:
                    </BodyText>
                    <BulletList
                        items={[
                            "Service delivery (queries, answers, conversation history): contractual necessity — Article 6(1)(b).",
                            "Billing and subscription management: contractual necessity — Article 6(1)(b).",
                            "Security and abuse prevention (rate limiting, brute-force protection, audit logs): legitimate interests — Article 6(1)(f).",
                            "Legal compliance (tax records, regulatory obligations): legal obligation — Article 6(1)(c).",
                        ]}
                    />

                    <Callout>
                        We do <strong>not</strong> use your queries, answers, or uploaded documents to
                        train, fine-tune, or evaluate AI models. Your data is processed solely to generate
                        your research results.
                    </Callout>
                </Section>

                <Divider/>

                {/* 4. Data Retention */}
                <Section>
                    <SectionTitle index="4">Data Retention</SectionTitle>
                    <BodyText>
                        We retain your data only as long as necessary for the purposes described above.
                        Specific retention periods:
                    </BodyText>

                    <div
                        className="mt-4 rounded-xl overflow-hidden"
                        style={{
                            border: "1px solid rgba(255,255,255,0.08)",
                        }}
                    >
                        <table className="w-full text-sm">
                            <thead>
                                <tr style={{background: "rgba(255,255,255,0.04)"}}>
                                    <th className="text-left px-5 py-3 font-semibold" style={{color: "rgba(255,255,255,0.78)"}}>Data type</th>
                                    <th className="text-left px-5 py-3 font-semibold" style={{color: "rgba(255,255,255,0.78)"}}>Retention period</th>
                                </tr>
                            </thead>
                            <tbody>
                                {[
                                    ["Queries and answers (conversation history)", "90 days, then automatically deleted"],
                                    ["Account data (email, name, preferences)", "Until you delete your account"],
                                    ["Sessions (login records)", "30 days"],
                                    ["Audit logs", "90 days"],
                                    ["Payment records", "As required by financial regulations"],
                                ].map(([type, period], i) => (
                                    <tr
                                        key={type}
                                        style={{
                                            borderTop: "1px solid rgba(255,255,255,0.06)",
                                            background: i % 2 === 1 ? "rgba(255,255,255,0.02)" : "transparent",
                                        }}
                                    >
                                        <td className="px-5 py-3" style={{color: "rgba(255,255,255,0.58)"}}>{type}</td>
                                        <td className="px-5 py-3" style={{color: "rgba(255,255,255,0.58)"}}>{period}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <BodyText>
                        <span className="mt-4 block">
                            Automated cleanup processes run hourly to enforce these retention periods. When you
                            delete your account, all associated data (conversations, sessions, documents) is
                            permanently removed.
                        </span>
                    </BodyText>
                </Section>

                <Divider/>

                {/* 5. Your Rights (GDPR Articles 15-22) */}
                <Section>
                    <SectionTitle index="5">Your Rights Under GDPR</SectionTitle>
                    <BodyText>
                        Under the General Data Protection Regulation (Articles 15-22), you have the following
                        rights regarding your personal data:
                    </BodyText>
                    <BulletList
                        items={[
                            "Right to access (Article 15): Request a copy of all personal data we hold about you. You can also export your data directly from the platform.",
                            "Right to rectification (Article 16): Request correction of inaccurate or incomplete personal data.",
                            "Right to erasure (Article 17): Request deletion of your account and all associated data. We will remove all your personal data unless we have a legal obligation to retain it.",
                            "Right to data portability (Article 20): Receive your data in a structured, machine-readable JSON format. Use the data export feature in your account settings or contact us.",
                            "Right to object (Article 21): Object to processing of your personal data based on legitimate interests.",
                            "Right to restrict processing (Article 18): Request that we limit how we process your data in certain circumstances.",
                            "Right to withdraw consent (Article 7): Where processing is based on consent, you may withdraw it at any time without affecting the lawfulness of prior processing.",
                        ]}
                    />

                    <SubHeading>How to exercise your rights</SubHeading>
                    <BodyText>
                        To exercise any of these rights, email{" "}
                        <a href="mailto:privacy@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                            privacy@vitreon.app
                        </a>{" "}
                        with the subject line &ldquo;Data Subject Request&rdquo;. We will respond within 30 days
                        as required by GDPR. For data export, you can also use the self-service export endpoint
                        available in your authenticated account.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 6. Data Security */}
                <Section>
                    <SectionTitle index="6">Data Security</SectionTitle>
                    <BodyText>
                        We implement appropriate technical and organisational measures to protect your data:
                    </BodyText>
                    <BulletList
                        items={[
                            "Encryption in transit: all connections are encrypted using TLS 1.2 or higher.",
                            "Password security: passwords are hashed using bcrypt with automatic salting — we never store plain-text passwords.",
                            "Session security: authentication uses HttpOnly, SameSite cookies that cannot be accessed by JavaScript or sent in cross-site requests.",
                            "CSRF protection: state-mutating requests require a custom header, blocking cross-site request forgery.",
                            "Rate limiting: brute-force protection on authentication endpoints (IP-based throttling).",
                            "Access control: audit logs and user data are restricted by user ID — one user cannot access another's data.",
                        ]}
                    />
                    <BodyText>
                        If you discover a security vulnerability, please disclose it responsibly to{" "}
                        <a href="mailto:security@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                            security@vitreon.app
                        </a>
                        .
                    </BodyText>
                </Section>

                <Divider/>

                {/* 7. Third Parties */}
                <Section>
                    <SectionTitle index="7">Third-Party Services</SectionTitle>
                    <BodyText>
                        We share data with the following third-party services, each for a specific and limited
                        purpose:
                    </BodyText>

                    <SubHeading>Anthropic (via Google Cloud Vertex AI)</SubHeading>
                    <BodyText>
                        Your legal research queries and relevant document excerpts are sent to the Anthropic
                        Claude API (accessed through Google Cloud Vertex AI) to generate answers. Anthropic&apos;s
                        enterprise API does not use customer inputs to train foundation models. See{" "}
                        <a
                            href="https://www.anthropic.com/legal/privacy"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{color: "#C9A84C"}}
                            className="hover:underline"
                        >
                            Anthropic&apos;s Privacy Policy
                        </a>
                        .
                    </BodyText>

                    <SubHeading>Stripe</SubHeading>
                    <BodyText>
                        Payment processing is handled by Stripe. We share your email and subscription details
                        with Stripe to manage billing. Stripe is PCI DSS Level 1 certified. See{" "}
                        <a
                            href="https://stripe.com/privacy"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{color: "#C9A84C"}}
                            className="hover:underline"
                        >
                            Stripe&apos;s Privacy Policy
                        </a>
                        .
                    </BodyText>

                    <SubHeading>Google (OAuth)</SubHeading>
                    <BodyText>
                        If you choose to sign in with Google, we receive your email, name, and profile picture
                        from Google&apos;s OAuth service. We do not access any other Google account data. See{" "}
                        <a
                            href="https://policies.google.com/privacy"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{color: "#C9A84C"}}
                            className="hover:underline"
                        >
                            Google&apos;s Privacy Policy
                        </a>
                        .
                    </BodyText>
                </Section>

                <Divider/>

                {/* 8. Cookies */}
                <Section>
                    <SectionTitle index="8">Cookies</SectionTitle>
                    <BodyText>
                        Vitreon Legal uses a single session cookie (<code style={codeStyle}>vitreon_session</code>)
                        to maintain your authenticated session. This cookie is:
                    </BodyText>
                    <BulletList
                        items={[
                            "HttpOnly: cannot be read by JavaScript, protecting against XSS attacks.",
                            "SameSite=Lax: not sent on cross-site requests, preventing CSRF.",
                            "Secure: transmitted only over HTTPS in production.",
                        ]}
                    />
                    <BodyText>
                        We do not use tracking cookies, advertising cookies, or third-party analytics cookies.
                        We do not use browser <code style={codeStyle}>localStorage</code> to store sensitive data.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 9. International Transfers */}
                <Section>
                    <SectionTitle index="9">International Data Transfers</SectionTitle>
                    <BodyText>
                        When your queries are processed by Anthropic via Google Cloud Vertex AI, your data may
                        be transferred to servers outside your country of residence. These transfers are
                        protected by appropriate safeguards including Google Cloud&apos;s data processing terms
                        and Anthropic&apos;s enterprise data handling agreements.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 10. Changes */}
                <Section>
                    <SectionTitle index="10">Changes to This Policy</SectionTitle>
                    <BodyText>
                        We may update this Privacy Policy from time to time. Material changes will be
                        communicated via email or a prominent notice on the Service. Your continued use of the
                        Service after changes take effect constitutes acceptance of the updated policy.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 11. Contact */}
                <Section>
                    <SectionTitle index="11">Contact Us</SectionTitle>
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
                        <p className="font-heading font-semibold text-base mb-1"
                           style={{color: "rgba(255,255,255,0.9)"}}>
                            Vitreon Legal — Privacy Team
                        </p>
                        <p className="text-sm mb-2" style={{color: "rgba(255,255,255,0.55)"}}>
                            Email:{" "}
                            <a href="mailto:privacy@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                                privacy@vitreon.app
                            </a>
                        </p>
                        <p className="text-sm" style={{color: "rgba(255,255,255,0.55)"}}>
                            Vitreon Legal is currently operated as a sole trader (OSVČ) based in Prague,
                            Czech Republic. The data controller is the platform operator, Viacheslav Ivannikov.
                        </p>
                    </div>
                    <BodyText>
                        <span className="mt-4 block">
                            If you are not satisfied with our response, you have the right to lodge a complaint
                            with your local data protection supervisory authority. For users in the Czech
                            Republic, the supervisory authority is the{" "}
                            <strong style={{color: "rgba(255,255,255,0.78)"}}>
                                Office for Personal Data Protection (Úřad pro ochranu osobních údajů — ÚOOÚ)
                            </strong>{" "}
                            at{" "}
                            <a
                                href="https://uoou.cz"
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{color: "#C9A84C"}}
                                className="hover:underline"
                            >
                                uoou.cz
                            </a>
                            .
                        </span>
                    </BodyText>
                </Section>

                {/* CTA Section */}
                <section
                    className="mt-16 rounded-2xl p-8 text-center"
                    style={{
                        background: "rgba(201,168,76,0.05)",
                        border: "1px solid rgba(201,168,76,0.15)",
                    }}
                >
                    <h2
                        className="font-heading font-bold mb-3"
                        style={{
                            fontSize: "1.25rem",
                            color: "rgba(255,255,255,0.92)",
                        }}
                    >
                        Ready to streamline your legal research?
                    </h2>
                    <p className="text-sm mb-6" style={{color: "rgba(255,255,255,0.55)"}}>
                        Get source-grounded answers with 100% citation coverage. Start free, no credit card.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-3 justify-center">
                        <Link
                            href="/login"
                            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors"
                            style={{
                                background: "#C9A84C",
                                color: "#0F1623",
                            }}
                        >
                            Get Started Free
                        </Link>
                        <Link
                            href="/"
                            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
                            style={{
                                background: "rgba(255,255,255,0.06)",
                                border: "1px solid rgba(255,255,255,0.1)",
                                color: "rgba(255,255,255,0.78)",
                            }}
                        >
                            Learn More
                        </Link>
                    </div>
                </section>

                {/* Footer nav */}
                <div
                    className="mt-12 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs"
                    style={{
                        borderTop: "1px solid rgba(255,255,255,0.06)",
                        color: "rgba(255,255,255,0.28)",
                    }}
                >
                    <span>2026 Vitreon Legal</span>
                    <div className="flex items-center gap-4">
                        <Link href="/privacy" className="hover:text-white/60 transition-colors"
                              style={{color: "#C9A84C"}}>
                            Privacy Policy
                        </Link>
                        <span style={{color: "rgba(255,255,255,0.15)"}}>·</span>
                        <Link href="/terms" className="hover:text-white/60 transition-colors">
                            Terms of Service
                        </Link>
                        <span style={{color: "rgba(255,255,255,0.15)"}}>·</span>
                        <Link href="/" className="hover:text-white/60 transition-colors">
                            Home
                        </Link>
                    </div>
                </div>
            </main>
        </div>
    );
}

/* -- Shared layout primitives -- */

function Section({children}: { children: React.ReactNode }) {
    return <section className="mb-10">{children}</section>;
}

function Divider() {
    return (
        <hr
            className="my-10"
            style={{borderColor: "rgba(255,255,255,0.06)"}}
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
      <span style={{
          color: "rgba(201,168,76,0.7)",
          marginRight: "0.5rem",
          fontFamily: "var(--font-sans), sans-serif",
          fontSize: "0.85em",
          fontWeight: 500
      }}>
        {index}.
      </span>
            {children}
        </h2>
    );
}

function SubHeading({children}: { children: React.ReactNode }) {
    return (
        <h3
            className="font-semibold mb-2 mt-6"
            style={{fontSize: "0.9375rem", color: "rgba(255,255,255,0.78)"}}
        >
            {children}
        </h3>
    );
}

function BodyText({children}: { children: React.ReactNode }) {
    return (
        <p
            className="mb-3 text-sm leading-7"
            style={{color: "rgba(255,255,255,0.58)"}}
        >
            {children}
        </p>
    );
}

function BulletList({items}: { items: string[] }) {
    return (
        <ul className="mb-4 space-y-1.5 pl-1">
            {items.map((item) => (
                <li
                    key={item.slice(0, 40)}
                    className="flex items-start gap-2.5 text-sm leading-6"
                    style={{color: "rgba(255,255,255,0.58)"}}
                >
          <span
              className="mt-2 shrink-0 size-1 rounded-full"
              style={{background: "#C9A84C", opacity: 0.7}}
          />
                    {item}
                </li>
            ))}
        </ul>
    );
}

function Callout({children}: { children: React.ReactNode }) {
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
