import Link from "next/link";
import type {Metadata} from "next";

export const metadata: Metadata = {
    title: "Terms of Service — Vitreon Legal",
    description:
        "Terms and conditions governing your use of the Vitreon Legal AI legal research platform.",
};

const LAST_UPDATED = "April 5, 2026";

export default function TermsPage() {
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
                        Terms of Service
                    </h1>
                    <p className="text-sm" style={{color: "rgba(255,255,255,0.38)"}}>
                        Last updated: {LAST_UPDATED}
                    </p>
                </div>

                {/* Intro */}
                <Section>
                    <p style={{color: "rgba(255,255,255,0.62)", lineHeight: 1.75}}>
                        These Terms of Service (&ldquo;Terms&rdquo;) govern your access to and use of the Vitreon Legal
                        AI legal research platform (&ldquo;Service&rdquo;), operated by Vitreon Legal
                        (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;us&rdquo;). By accessing or using the
                        Service you agree to be bound by these Terms. If you do not agree, do not use the
                        Service.
                    </p>
                </Section>

                <Divider/>

                {/* 1. Acceptance */}
                <Section>
                    <SectionTitle index="1">Acceptance of Terms</SectionTitle>
                    <BodyText>
                        By creating an account or otherwise accessing the Service, you
                        represent that you are at least 18 years of age and have the authority to enter into
                        these Terms on behalf of yourself or the organisation you represent.
                    </BodyText>
                    <BodyText>
                        If you are using the Service on behalf of a business or other legal entity, you
                        represent that you have authority to bind that entity to these Terms, and &ldquo;you&rdquo;
                        refers to that entity. These Terms constitute a legally binding agreement between you and
                        Vitreon Legal.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 2. Service Description */}
                <Section>
                    <SectionTitle index="2">Service Description</SectionTitle>
                    <BodyText>
                        Vitreon Legal provides an AI-powered platform for legal research and document analysis. The
                        Service uses large language models (including Anthropic&apos;s Claude) to generate
                        answers to legal queries based on documents you supply.
                    </BodyText>

                    <Callout>
                        <strong style={{color: "rgba(255,255,255,0.9)"}}>Important notice:</strong> Vitreon Legal is
                        a legal research assistance tool, not a law firm. The answers generated by the Service
                        are for informational and research purposes only and do not constitute legal advice.
                        Nothing in the Service creates an attorney-client relationship. You should always consult
                        a qualified legal professional before making decisions based on legal research outputs.
                    </Callout>

                    <BodyText>
                        The Service is provided as a hosted platform at vitreon.app. Access requires creating
                        an account. Usage is subject to the subscription plan and daily query limits associated
                        with your account tier.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 3. Acceptable Use */}
                <Section>
                    <SectionTitle index="3">Acceptable Use</SectionTitle>
                    <BodyText>You agree to use the Service only for lawful purposes. You must not:</BodyText>
                    <BulletList
                        items={[
                            "Upload documents you do not have the right to process or share.",
                            "Use the Service to generate content that facilitates illegal activity, harassment, or discrimination.",
                            "Attempt to reverse-engineer, decompile, or extract source code from the Service.",
                            "Circumvent, disable, or interfere with security features of the Service.",
                            "Use automated means to access the Service at a rate that causes undue server load without prior written consent.",
                            "Resell, sublicense, or offer access to the Service to third parties without an applicable enterprise licence.",
                            "Misrepresent the source or authorship of AI-generated legal content to courts, regulators, or counterparties.",
                        ]}
                    />
                    <BodyText>
                        We reserve the right to suspend or terminate access to the Service for any violation of
                        these acceptable use provisions without prior notice.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 4. Subscription and Billing */}
                <Section>
                    <SectionTitle index="4">Subscription and Billing</SectionTitle>
                    <BodyText>
                        The Service is available under the following plans:
                    </BodyText>
                    <BulletList
                        items={[
                            "Free: $0/month — up to 3 queries per day. No payment information required.",
                            "Starter: $29/month — up to 30 queries per day.",
                            "Pro: $179/month — up to 200 queries per day.",
                            "Enterprise: $499/month — unlimited queries.",
                        ]}
                    />
                    <BodyText>
                        Paid subscriptions renew automatically at the start of each billing cycle. You may
                        cancel your subscription at any time; cancellation takes effect at the end of the
                        current billing period and no pro-rata refund is issued for the remaining days.
                    </BodyText>
                    <BodyText>
                        Plan upgrades take effect immediately after payment is processed. Plan downgrades
                        take effect at the start of the next billing cycle.
                        All payments are processed by{" "}
                        <a href="https://stripe.com" target="_blank" rel="noopener noreferrer" style={{color: "#C9A84C"}} className="hover:underline">
                            Stripe
                        </a>
                        . Any billing disputes should be directed to Stripe or to{" "}
                        <a href="mailto:billing@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                            billing@vitreon.app
                        </a>
                        .
                    </BodyText>
                </Section>

                <Divider/>

                {/* 5. Account Security */}
                <Section>
                    <SectionTitle index="5">Account Security</SectionTitle>
                    <BodyText>
                        Your account is protected by the following measures:
                    </BodyText>
                    <BulletList
                        items={[
                            "Passwords are hashed using bcrypt — we never store your password in plain text.",
                            "Sessions use HttpOnly, SameSite cookies that cannot be accessed by client-side scripts.",
                            "Brute-force protection limits failed login attempts per IP address.",
                        ]}
                    />
                    <BodyText>
                        You are solely responsible for keeping your login credentials confidential and for all
                        activity that occurs under your account. If you suspect your account has been
                        compromised, you should change your password immediately and contact{" "}
                        <a href="mailto:security@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                            security@vitreon.app
                        </a>
                        .
                    </BodyText>
                </Section>

                <Divider/>

                {/* 6. Termination and Suspension */}
                <Section>
                    <SectionTitle index="6">Termination and Suspension</SectionTitle>
                    <BodyText>
                        Either party may terminate your account at any time. You may delete your account from
                        your account settings or by emailing{" "}
                        <a href="mailto:legal@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                            legal@vitreon.app
                        </a>
                        .
                    </BodyText>
                    <BodyText>
                        Upon account deletion, all your personal data, conversations, documents, and sessions
                        are permanently removed in accordance with the retention policy described in our{" "}
                        <a href="/privacy" style={{color: "#C9A84C"}} className="hover:underline">
                            Privacy Policy
                        </a>
                        . Any active paid subscription is automatically cancelled.
                    </BodyText>
                    <BodyText>
                        We may suspend or terminate your access without prior notice if you violate these Terms
                        or the Acceptable Use provisions. In the event of termination for cause, no refund is
                        issued for the current billing period.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 7. Intellectual Property */}
                <Section>
                    <SectionTitle index="7">Intellectual Property</SectionTitle>

                    <SubHeading>Our intellectual property</SubHeading>
                    <BodyText>
                        The Vitreon Legal platform, including its software, design, trade marks, and documentation, is
                        owned by or licensed to Vitreon Legal and is protected by applicable intellectual property laws.
                        These Terms do not grant you any right to use our trade marks, logos, or other brand
                        features.
                    </BodyText>

                    <SubHeading>Your content</SubHeading>
                    <BodyText>
                        You retain full ownership of the documents and queries you submit to the Service. By
                        using the Service you grant Vitreon Legal a limited, non-exclusive, royalty-free licence to
                        process your content solely to the extent necessary to deliver the Service to you.
                    </BodyText>

                    <SubHeading>Output</SubHeading>
                    <BodyText>
                        Subject to applicable law and Anthropic&apos;s terms, the research outputs generated by
                        the Service in response to your queries are owned by you. You are responsible for
                        verifying the accuracy of all outputs and for complying with any applicable rules
                        governing the use of AI-generated content in legal proceedings.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 8. Limitation of Liability */}
                <Section>
                    <SectionTitle index="8">Disclaimer and Limitation of Liability</SectionTitle>

                    <SubHeading>Disclaimer of warranties</SubHeading>
                    <BodyText>
                        The Service is provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo; without
                        warranties of any kind, whether express or implied, including but not limited to
                        warranties of merchantability, fitness for a particular purpose, accuracy, or
                        non-infringement. We do not warrant that the Service will be uninterrupted, error-free,
                        or that any defects will be corrected.
                    </BodyText>

                    <SubHeading>Limitation of liability</SubHeading>
                    <BodyText>
                        To the maximum extent permitted by applicable law, Vitreon Legal and its officers, employees,
                        agents, and licensors shall not be liable for any indirect, incidental, special,
                        consequential, or exemplary damages, including damages for loss of profits, goodwill,
                        data, or other intangible losses arising from your use of or inability to use the
                        Service, even if we have been advised of the possibility of such damages.
                    </BodyText>
                    <BodyText>
                        Our total aggregate liability to you for any claims arising under or related to these
                        Terms shall not exceed the greater of (a) the fees paid by you in the twelve months
                        preceding the claim, or (b) EUR 100.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 9. Enterprise */}
                <Section>
                    <SectionTitle index="9">Enterprise Licences</SectionTitle>
                    <BodyText>
                        Organisations requiring data processing agreements (DPA), extended SLAs, custom
                        retention policies, on-premise deployment, or dedicated support should contact us to
                        discuss enterprise licence terms. Enterprise agreements supersede these Terms to the
                        extent of any conflict.
                    </BodyText>
                    <BodyText>
                        To enquire about enterprise licensing, email{" "}
                        <a href="mailto:enterprise@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                            enterprise@vitreon.app
                        </a>
                        .
                    </BodyText>
                </Section>

                <Divider/>

                {/* 10. Governing Law */}
                <Section>
                    <SectionTitle index="10">Governing Law and Jurisdiction</SectionTitle>
                    <BodyText>
                        These Terms are governed by and construed in accordance with the laws of the{" "}
                        <strong style={{color: "rgba(255,255,255,0.85)"}}>Czech Republic</strong>, without
                        regard to its conflict of law provisions and to the extent not superseded by applicable
                        EU law.
                    </BodyText>
                    <BodyText>
                        Any dispute arising out of or in connection with these Terms shall be subject to the
                        exclusive jurisdiction of the courts of the Czech Republic, unless you are a consumer
                        entitled to bring proceedings in your country of habitual residence under applicable
                        EU consumer protection law.
                    </BodyText>
                    <BodyText>
                        If you are an EU consumer, you may also use the European Commission&apos;s Online Dispute
                        Resolution platform at{" "}
                        <a
                            href="https://ec.europa.eu/consumers/odr"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{color: "#C9A84C"}}
                            className="hover:underline"
                        >
                            ec.europa.eu/consumers/odr
                        </a>
                        .
                    </BodyText>
                </Section>

                <Divider/>

                {/* 11. Changes */}
                <Section>
                    <SectionTitle index="11">Changes to These Terms</SectionTitle>
                    <BodyText>
                        We may update these Terms from time to time. When we make material changes we will
                        update the &ldquo;Last updated&rdquo; date at the top of this page and, where
                        practicable, notify active users via the platform or email. Your continued use of the
                        Service after the effective date of any changes constitutes your acceptance of the
                        revised Terms.
                    </BodyText>
                    <BodyText>
                        If you do not agree to updated Terms, you should stop using the Service before the
                        changes take effect.
                    </BodyText>
                </Section>

                <Divider/>

                {/* 12. Contact */}
                <Section>
                    <SectionTitle index="12">Contact</SectionTitle>
                    <BodyText>
                        For legal enquiries or questions about these Terms, please contact:
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
                            Vitreon Legal — Legal Team
                        </p>
                        <p className="text-sm" style={{color: "rgba(255,255,255,0.55)"}}>
                            Email:{" "}
                            <a href="mailto:legal@vitreon.app" style={{color: "#C9A84C"}} className="hover:underline">
                                legal@vitreon.app
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
                    <span>2026 Vitreon Legal</span>
                    <div className="flex items-center gap-4">
                        <Link href="/privacy" className="hover:text-white/60 transition-colors">
                            Privacy Policy
                        </Link>
                        <span style={{color: "rgba(255,255,255,0.15)"}}>·</span>
                        <Link href="/terms" className="hover:text-white/60 transition-colors"
                              style={{color: "#C9A84C"}}>
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

/* ── Shared layout primitives ── */

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
      <span
          style={{
              color: "rgba(201,168,76,0.7)",
              marginRight: "0.5rem",
              fontFamily: "var(--font-sans), sans-serif",
              fontSize: "0.85em",
              fontWeight: 500,
          }}
      >
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
                    key={item}
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
            className="mt-4 mb-4 rounded-xl px-5 py-4 text-sm leading-6"
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
