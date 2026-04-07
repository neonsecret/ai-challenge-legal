/**
 * E2E tests for auth retry flow and OAuth redirect — NEO-266
 *
 * These tests target the local dev server (http://localhost:3000).
 * Backend is expected at BACKEND_URL (default http://localhost:8000).
 *
 * Test credentials come from environment variables:
 *   E2E_TEST_EMAIL    (default: testuser@vitreon.app)
 *   E2E_TEST_PASSWORD (default: <unset — skip credential tests>)
 *
 * Run: npm run test:e2e
 */
import { test, expect, type Page, type Route } from "playwright/test";

const FRONTEND = "http://localhost:3000";
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const TEST_EMAIL = process.env.E2E_TEST_EMAIL ?? "testuser@vitreon.app";
const TEST_PASSWORD = process.env.E2E_TEST_PASSWORD ?? "";

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

/**
 * Helper: log in via the real backend API (email/password).
 * Returns false if TEST_PASSWORD is not set (callers should skip).
 */
async function apiLogin(page: Page): Promise<boolean> {
  if (!TEST_PASSWORD) return false;

  const res = await page.request.post(`${BACKEND}/auth/login`, {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
  });
  return res.ok();
}

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
  page.on("pageerror", (err) => { pageErrors.push(err); });

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
  const hasGoogleBtn = await googleBtn.count() > 0;

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
  if (!TEST_PASSWORD) {
    test.skip(true, "E2E_TEST_PASSWORD not set — skipping credential test");
    return;
  }

  const loggedIn = await apiLogin(page);
  if (!loggedIn) {
    test.skip(true, "Backend login failed — check E2E_TEST_EMAIL / E2E_TEST_PASSWORD");
    return;
  }

  // Navigate to /chat — should be authenticated
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });
  expect(page.url()).toContain("/chat");

  // Navigate to /settings
  await page.goto(`${FRONTEND}/settings`);
  await page.waitForURL(/\/settings/, { timeout: 5_000 });
  // Settings page is only reachable when authenticated
  expect(page.url()).toContain("/settings");

  // Navigate back to /chat
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });

  // Should still be on /chat — not redirected to /
  expect(page.url()).toContain("/chat");
});

// ---------------------------------------------------------------------------
// Scenario 5 — Logout flow
// ---------------------------------------------------------------------------
test("Scenario 5: logout clears session and redirects away from /chat", async ({ page }) => {
  if (!TEST_PASSWORD) {
    test.skip(true, "E2E_TEST_PASSWORD not set — skipping credential test");
    return;
  }

  const loggedIn = await apiLogin(page);
  if (!loggedIn) {
    test.skip(true, "Backend login failed — check E2E_TEST_EMAIL / E2E_TEST_PASSWORD");
    return;
  }

  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });
  expect(page.url()).toContain("/chat");

  // The sidebar logout button has aria-label="Sign out" (app-sidebar.tsx:258)
  const signOutBtn = page.getByRole("button", { name: "Sign out" });
  await expect(signOutBtn).toBeVisible({ timeout: 5_000 });
  await signOutBtn.click();

  // After logout the sidebar navigates to "/" (app-sidebar.tsx:101: router.push("/"))
  await page.waitForURL(/^\/(login|$)/, { timeout: 5_000 }).catch(() => {
    // Some builds redirect to /login, some to /
  });

  // Should not still be on /chat
  expect(page.url()).not.toContain("/chat");

  // Session cookie must be absent or cleared after logout
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((c) => c.name === "session");
  expect(sessionCookie === undefined || sessionCookie.value === "").toBe(true);

  // Attempting to navigate to /chat should redirect away (no session)
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForLoadState("networkidle");
  expect(page.url()).not.toContain("/chat");
});
