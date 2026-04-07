/**
 * E2E tests for auth retry flow and OAuth redirect — NEO-266
 *
 * These tests target the local dev server (http://localhost:3000).
 * Backend is expected at BACKEND_URL (default http://localhost:8000).
 *
 * All 5 scenarios use network mocks — no real credentials required.
 * Scenarios 4 & 5 mock /auth/me so they always run in CI without
 * E2E_TEST_PASSWORD being set.
 *
 * Run: npm run test:e2e
 */
import { test, expect, type Route } from "playwright/test";

const FRONTEND = "http://localhost:3000";
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const TEST_EMAIL = process.env.E2E_TEST_EMAIL ?? "testuser@vitreon.app";

/** Minimal valid /auth/me response */
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

// ---------------------------------------------------------------------------
// Scenario 1 — Auth retry on /chat OAuth redirect
// ---------------------------------------------------------------------------
test("Scenario 1: auth retry on /chat — succeeds after first 401", async ({ page }) => {
  let callCount = 0;

  // Single handler for all /auth/me requests (direct and via Next.js rewrites).
  // Playwright evaluates routes LIFO — one handler avoids double-count confusion.
  await page.route(`**/auth/me`, async (route: Route) => {
    callCount += 1;
    if (callCount === 1) {
      // First call: simulate session cookie not yet present
      await route.fulfill({ status: 401, body: JSON.stringify({ detail: "Not authenticated" }) });
    } else {
      // Subsequent calls: session cookie has arrived
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER),
      });
    }
  });

  await page.goto(`${FRONTEND}/chat`);

  // Wait for the retry loop to complete (up to 500 + 1000 ms backoff = ~2s).
  // After a successful retry, use-auth sets user state and the chat page renders.
  // We assert that the page does NOT redirect to "/" (which would happen on auth failure).
  await page.waitForTimeout(3_500); // intentional: allows all retry delays to elapse

  expect(page.url()).toContain("/chat");
  expect(callCount).toBeGreaterThanOrEqual(2);
});

// ---------------------------------------------------------------------------
// Scenario 2 — /_not-found does not throw InvariantError
// ---------------------------------------------------------------------------
test("Scenario 2: navigating to non-existent path renders gracefully without InvariantError", async ({ page }) => {
  const consoleErrors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  page.on("pageerror", (err) => {
    consoleErrors.push(err.message);
  });

  await page.goto(`${FRONTEND}/definitely-does-not-exist`);

  // Wait for client-side error handling to settle
  await page.waitForLoadState("networkidle");

  // The page should render a recognisable 404 — not a blank white crash
  const bodyText = await page.locator("body").innerText();
  expect(bodyText.length).toBeGreaterThan(0);
  expect(bodyText.toLowerCase().includes("not found") || bodyText.includes("404")).toBe(true);

  // No InvariantError in console or unhandled errors
  const invariantErrors = consoleErrors.filter((e) =>
    e.toLowerCase().includes("invarianterror") || e.toLowerCase().includes("invariant")
  );
  expect(invariantErrors).toHaveLength(0);
});

// ---------------------------------------------------------------------------
// Scenario 3 — Google OAuth redirect flow (Google side mocked)
// ---------------------------------------------------------------------------
test("Scenario 3: Google OAuth redirect flow — mocked Google, real backend callback", async ({ page }) => {
  // We intercept the GET /auth/google redirect (which would go to accounts.google.com)
  // and simulate the backend OAuth callback directly with a mock code.
  // The backend callback + session creation run for real.
  //
  // NOTE: This test requires the backend to have a Google OAuth app configured.
  // If the backend cannot process the mocked callback it will return an error,
  // which we assert on — the user should land back at /login (not crash).

  let googleRedirectCaught = false;
  const pageErrors: Error[] = [];

  // Capture unhandled JS errors before any navigation
  page.on("pageerror", (err) => {
    pageErrors.push(err);
  });

  await page.route(`${BACKEND}/auth/google`, async (route: Route) => {
    googleRedirectCaught = true;
    // Instead of going to Google, redirect to the backend callback with a
    // mock code. The backend will reject it (not a real Google code) and
    // redirect to /login?error=...
    await route.fulfill({
      status: 302,
      headers: {
        Location: `${BACKEND}/auth/google/callback?code=mock_e2e_code&state=mock_state`,
      },
    });
  });

  await page.goto(`${FRONTEND}/`);

  // Click the Google OAuth button on the login page
  const googleBtn = page.getByRole("button", { name: /continue with google/i });
  const hasGoogleBtn = (await googleBtn.count()) > 0;

  if (!hasGoogleBtn) {
    // If not on the login page yet, navigate there
    await page.goto(`${FRONTEND}/login`);
  }

  await page.getByRole("button", { name: /continue with google/i }).click();

  // Wait for navigation to settle after OAuth redirect chain
  await page.waitForLoadState("networkidle");

  // The test is satisfied if:
  //  a) The Google redirect was intercepted (not a real round-trip to Google), AND
  //  b) The page didn't crash — it must be on /chat (success) or /login (expected callback failure)
  expect(googleRedirectCaught).toBe(true);

  const url = page.url();
  expect(url.includes("/chat") || url.includes("/login")).toBe(true);

  // No unhandled JS errors
  expect(pageErrors).toHaveLength(0);
});

// ---------------------------------------------------------------------------
// Scenario 4 — Session persistence across navigation
// ---------------------------------------------------------------------------
test("Scenario 4: session persists across page navigations", async ({ page }) => {
  // Mock /auth/me to always return MOCK_USER — no real credentials required,
  // so this test always runs in CI.  Both the use-auth hook and the chat page's
  // own auth check call GET /auth/me; the mock covers both.
  await page.route(`**/auth/me`, async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER),
      });
    } else {
      await route.continue();
    }
  });

  // Navigate to /chat — should be authenticated
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });
  expect(page.url()).toContain("/chat");

  // Navigate to /settings (only reachable when authenticated)
  await page.goto(`${FRONTEND}/settings`);
  await page.waitForURL(/\/settings/, { timeout: 5_000 });
  expect(page.url()).toContain("/settings");

  // Navigate back to /chat — session must still be valid
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });

  // Should still be on /chat — not redirected to /
  expect(page.url()).toContain("/chat");
});

// ---------------------------------------------------------------------------
// Scenario 5 — Logout flow
// ---------------------------------------------------------------------------
test("Scenario 5: logout clears session and redirects away from /chat", async ({ page }) => {
  // Stateful flag — toggled when the logout endpoint is called, so the /auth/me
  // mock can switch from 200 → 401 without real credentials.
  let loggedOut = false;

  // Mock /auth/me: returns MOCK_USER while logged in, 401 after logout.
  // Both use-auth and the chat page's own auth check are covered by this.
  await page.route(`**/auth/me`, async (route: Route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    if (loggedOut) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER),
      });
    }
  });

  // Mock POST /auth/logout — set the flag and return success.
  // The sidebar fires this fire-and-forget before calling router.push("/").
  await page.route(`**/auth/logout`, async (route: Route) => {
    loggedOut = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "logged out" }),
    });
  });

  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });
  expect(page.url()).toContain("/chat");

  // The sidebar logout button (app-sidebar.tsx handleLogout)
  const signOutBtn = page.getByRole("button", { name: "Sign out" });
  await expect(signOutBtn).toBeVisible({ timeout: 5_000 });
  await signOutBtn.click();

  // After logout the sidebar calls router.push("/") immediately
  await page.waitForURL(/^\/(login|$)/, { timeout: 5_000 }).catch(() => {
    // Some builds redirect to /login, some to /
  });

  // Should not still be on /chat
  expect(page.url()).not.toContain("/chat");

  // Attempting to navigate to /chat should redirect away — /auth/me now returns 401
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForLoadState("networkidle");
  expect(page.url()).not.toContain("/chat");
});
