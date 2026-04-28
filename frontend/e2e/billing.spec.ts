/**
 * E2E tests for billing and upgrade flows — NEO-2830
 *
 * All API calls are mocked — no real Stripe credentials or live backend needed.
 *
 * Covers:
 *   BL-1  Billing upgrade CTA click triggers a Stripe Checkout redirect
 *
 * Run: npx playwright test e2e/billing.spec.ts
 */
import { test, expect, type Route } from "playwright/test";

const FRONTEND = `http://localhost:${process.env.CI_PORT ?? "3000"}`;
const TEST_EMAIL = process.env.E2E_TEST_EMAIL ?? "testuser@vitreon.app";

/** Minimal authenticated /auth/me response */
const MOCK_USER = {
  id: "e2e-user-id",
  email: TEST_EMAIL,
  name: "E2E Tester",
  avatar_url: null,
  plan: "free",
  subscription_status: "active",
  monthly_queries_used: 0,
  max_corpora: 1,
};

/** Free-plan billing status — shows upgrade CTAs */
const MOCK_BILLING_FREE = {
  plan: "free",
  subscription_status: "active",
  monthly_queries_used: 0,
  monthly_queries_limit: 90,
  daily_queries_used: 0,
  daily_queries_limit: 3,
  is_monthly_limit: false,
  corpora_used: 0,
  corpora_limit: 1,
  has_stripe_customer: false,
  cancel_at_period_end: false,
  current_period_end: null,
};

/** Fake Stripe Checkout URL — intercepted by the route handler so we never leave localhost */
const MOCK_STRIPE_URL = "https://checkout.stripe.com/c/pay/cs_test_mock_e2e";

// ---------------------------------------------------------------------------
// BL-1 — Billing upgrade CTA click triggers a Stripe Checkout redirect
//
// The billing page calls POST /stripe/create-checkout-session → gets {url: ...}
// → does window.location.href = url. This test verifies that clicking the
// upgrade button initiates navigation toward checkout.stripe.com.
// ---------------------------------------------------------------------------
test("BL-1: clicking the upgrade CTA redirects to Stripe Checkout", { tag: ["@smoke"] }, async ({ page }) => {
  // Mock /auth/me so the app considers the user authenticated.
  // billing-client.tsx redirects to /login on a 401 from /stripe/billing-status,
  // but does not separately call /auth/me — mocking it here prevents auth guards
  // in shared layout components from redirecting before the page loads.
  await page.route(`**/auth/me`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    });
  });

  // Mock the billing status endpoint — free plan exposes upgrade CTAs
  await page.route(`**/stripe/billing-status`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_BILLING_FREE),
    });
  });

  // Mock the checkout session creation to return a fake Stripe URL
  await page.route(`**/stripe/create-checkout-session`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ url: MOCK_STRIPE_URL }),
    });
  });

  // Intercept the Stripe navigation so the test does not actually leave localhost.
  // Fulfill with minimal HTML so the navigation resolves cleanly and we can
  // assert the final URL without a network round-trip to Stripe.
  await page.route("https://checkout.stripe.com/**", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><html><body>Stripe Checkout (mocked)</body></html>",
    });
  });

  // Navigate to the billing page
  await page.goto(`${FRONTEND}/billing`);

  // Wait for the billing page to load (billing-status mock resolves)
  // The upgrade button text is "Upgrade to Starter" (t("billing.upgrade") + " " + t("billing.to") + " Starter")
  const upgradeBtn = page
    .locator("button")
    .filter({ hasText: /upgrade/i })
    .first();

  await expect(upgradeBtn).toBeVisible({ timeout: 10_000 });

  // Click the upgrade button and wait for the Stripe redirect
  await Promise.all([
    page.waitForURL((url) => url.href.includes("checkout.stripe.com"), { timeout: 10_000 }),
    upgradeBtn.click(),
  ]);

  // Assert that the navigation landed on the Stripe Checkout URL
  expect(page.url()).toContain("checkout.stripe.com");
});
