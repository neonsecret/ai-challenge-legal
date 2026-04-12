/**
 * E2E tests for Settings and Billing pages — NEO-1872
 *
 * Covers:
 *   ST-1  Settings page loads and shows authenticated user email + name
 *   ST-2  Sign out button is visible on settings page
 *   ST-3  Language selector is visible on settings page (dark mode)
 *   ST-4  Billing page loads and renders plan content
 *   ST-5  At least one plan label (Free/Starter/Pro/Enterprise) is visible on billing
 *   ST-6  Delete account confirmation: type email enables the delete button
 *
 * Run: npx playwright test e2e/settings.spec.ts
 */
import { test, expect, type Route } from "playwright/test";

const FRONTEND = "http://localhost:3000";

const TEST_EMAIL = "testuser@vitreon.app";

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

const MOCK_BILLING: Record<string, unknown> = {
  plan: "free",
  subscription_status: "active",
  monthly_queries_used: 0,
  monthly_queries_limit: 30,
  daily_queries_used: 0,
  daily_queries_limit: 3,
  is_monthly_limit: false,
  corpora_used: 0,
  corpora_limit: 1,
  has_stripe_customer: false,
  cancel_at_period_end: false,
  current_period_end: null,
};

// ---------------------------------------------------------------------------
// ST-1 — Settings page loads with user email and name
// ---------------------------------------------------------------------------
test("ST-1: settings page loads and displays the authenticated user's email", async ({ page }) => {
  const jsErrors: string[] = [];
  page.on("pageerror", (err) => jsErrors.push(err.message));

  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );

  await page.goto(`${FRONTEND}/settings`);
  await page.waitForURL(/\/settings/, { timeout: 5_000 });

  // After auth resolves the page must show the user's email and name
  await expect(async () => {
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toContain(TEST_EMAIL);
    expect(bodyText).toContain("E2E Tester");
  }).toPass({ timeout: 10_000 });

  // Filter pre-existing React hydration mismatches (#418) — not E2E failures
  const criticalErrors = jsErrors.filter(
    (e) =>
      !e.includes("418") &&
      !e.toLowerCase().includes("hydration") &&
      !e.includes("did not match")
  );
  expect(criticalErrors).toHaveLength(0);
});

// ---------------------------------------------------------------------------
// ST-2 — Sign out button is visible
// ---------------------------------------------------------------------------
test("ST-2: sign out button is visible on the settings page", async ({ page }) => {
  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );

  await page.goto(`${FRONTEND}/settings`);
  await page.waitForURL(/\/settings/, { timeout: 5_000 });

  // Settings page renders a "Sign Out" button (t("settings.sign_out") = "Sign Out")
  const signOutBtn = page.getByRole("button", { name: /sign out/i });
  await expect(signOutBtn).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// ST-3 — Language selector is visible (dark mode)
// ---------------------------------------------------------------------------
test("ST-3: language selector is rendered on the settings page", async ({ page }) => {
  // The language <select> only renders in dark mode (light mode has no language section yet).
  // Force dark mode via localStorage before any page script runs.
  await page.addInitScript(() => {
    localStorage.setItem("vitreon-color-mode", "dark");
  });

  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );

  await page.goto(`${FRONTEND}/settings`);
  await page.waitForURL(/\/settings/, { timeout: 5_000 });

  // Dark mode settings renders a <select> for the language picker
  const langSelect = page.locator("select").first();
  await expect(langSelect).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// ST-4 — Billing page loads and renders plan content
// ---------------------------------------------------------------------------
test("ST-4: billing page renders pricing content", async ({ page }) => {
  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );
  // billing/page.tsx fetches ${NEXT_PUBLIC_SSE_URL}/stripe/billing-status
  await page.route("**/stripe/billing-status", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_BILLING) })
  );

  await page.goto(`${FRONTEND}/billing`);
  await page.waitForURL(/\/billing/, { timeout: 5_000 });

  // Plan cards are rendered unconditionally — assert a plan label appears
  await expect(async () => {
    const bodyText = await page.locator("body").innerText();
    const hasPlanContent =
      bodyText.includes("Free") ||
      bodyText.includes("Starter") ||
      bodyText.includes("Pro") ||
      bodyText.includes("Enterprise");
    expect(hasPlanContent).toBe(true);
  }).toPass({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// ST-5 — Billing plan labels visible
// ---------------------------------------------------------------------------
test("ST-5: at least one billing plan label (Free/Starter/Pro/Enterprise) is visible", async ({ page }) => {
  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );
  await page.route("**/stripe/billing-status", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_BILLING) })
  );

  await page.goto(`${FRONTEND}/billing`);
  await page.waitForURL(/\/billing/, { timeout: 5_000 });

  await expect(async () => {
    const bodyText = await page.locator("body").innerText();
    const hasPlan =
      bodyText.includes("Free") ||
      bodyText.includes("Starter") ||
      bodyText.includes("Pro") ||
      bodyText.includes("Enterprise");
    expect(hasPlan).toBe(true);
  }).toPass({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// ST-6 — Delete account: typing the correct email enables the delete button
// ---------------------------------------------------------------------------
test("ST-6: delete account button becomes enabled after typing the correct email", async ({ page }) => {
  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );
  await page.route("**/auth/delete-account", (route: Route) =>
    route.fulfill({ status: 204 })
  );

  await page.goto(`${FRONTEND}/settings`);
  await page.waitForURL(/\/settings/, { timeout: 5_000 });

  // Wait for user email to appear (confirms auth state resolved)
  await expect(async () => {
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toContain(TEST_EMAIL);
  }).toPass({ timeout: 10_000 });

  // Hole A fix: hard-assert the delete toggle is visible before clicking
  // t("settings.delete_account") = "Delete Account"
  const deleteToggle = page.locator('button:has-text("Delete Account")').first();
  await expect(deleteToggle).toBeVisible({ timeout: 10_000 });
  await deleteToggle.click();

  // Email input must appear after the form expands
  const emailInput = page.locator('input[type="email"]').first();
  await expect(emailInput).toBeVisible({ timeout: 5_000 });

  // Hole B fix: confirm button must be disabled BEFORE typing the correct email
  // t("settings.delete_permanently") = "Delete my account permanently"
  const deleteBtn = page.locator('button:has-text("Delete my account permanently")');
  await expect(deleteBtn).toBeDisabled();

  // Type the correct email — should enable the button
  await emailInput.fill(TEST_EMAIL);

  // After typing the correct email, the delete button must become enabled
  await expect(async () => {
    const isDisabled = await deleteBtn.isDisabled().catch(() => true);
    expect(isDisabled).toBe(false);
  }).toPass({ timeout: 5_000 });
});
