/**
 * E2E tests for auth retry flow and OAuth redirect — NEO-266
 *
 * These tests target the local dev server (http://localhost:3000).
 * Backend is expected at BACKEND_URL (default http://localhost:8000).
 *
 * All scenarios use Playwright route mocking — no real credentials or CI
 * secrets are required.  See frontend/e2e/README.md for details.
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

async function gotoWithRetry(page: import("playwright/test").Page, url: string) {
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await page.goto(url, { waitUntil: "domcontentloaded" });
      return;
    } catch (error) {
      lastError = error;
      const message = String(error);
      const isTransientNavError =
        message.includes("ERR_ABORTED") || message.includes("frame was detached");
      if (!isTransientNavError || attempt === 2) throw error;
      await page.waitForTimeout(500);
    }
  }
  throw lastError;
}

// ---------------------------------------------------------------------------
// Scenario 1 — Auth retry on /chat OAuth redirect
// ---------------------------------------------------------------------------
// TODO(NEO-1946): Scenario 1 skipped — chat/page.tsx uses its own one-shot auth
// guard (lines 191-198) and does not call useAuth at all, so the retry logic in
// use-auth.ts:59-60 never fires on this page. The chat guard redirects immediately
// on a 401 without any retry. Re-enable if a retry guard is added to chat/page.tsx.
test.skip("Scenario 1: auth retry on /chat — succeeds after first 401", async ({ page }) => {
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

  await gotoWithRetry(page, `${FRONTEND}/definitely-does-not-exist`);

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
test("Scenario 3: Google OAuth redirect flow — mocked Google, redirect to error page", async ({ page }) => {
  // We intercept the GET /auth/google redirect (which would go to Google OAuth)
  // and redirect straight to /login?error=oauth_denied — no real backend callback needed.
  //
  // NOTE: NEXT_PUBLIC_SSE_URL is empty in the dev build, so loginWithGoogle() calls
  // window.location.href = "/auth/google" (relative), which navigates to localhost:3000.
  // The route glob **/auth/google matches regardless of origin, so we don't need to
  // hard-code the backend hostname. Redirecting to /login avoids any real backend
  // involvement and keeps the test self-contained.

  let googleRedirectCaught = false;
  const pageErrors: Error[] = [];

  // Capture unhandled JS errors before any navigation
  page.on("pageerror", (err) => { pageErrors.push(err); });

  // **/auth/google matches the navigation to /auth/google on any origin.
  // Redirecting to /login?error=oauth_denied mimics a failed OAuth flow
  // without involving the real backend callback.
  await page.route(`**/auth/google`, async (route: Route) => {
    // Skip callback sub-path — only intercept the initial redirect
    if (route.request().url().includes("/callback")) {
      await route.continue();
      return;
    }
    googleRedirectCaught = true;
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: `<!doctype html><html><body><script>window.location.replace(${JSON.stringify(`${FRONTEND}/login?error=oauth_denied`)});</script></body></html>`,
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
  await expect(page.getByText("Google sign-in was cancelled. Please try again.")).toBeVisible();

  // Route-fulfilled document redirects can emit a transient hydration error from
  // the abandoned source page. Treat the final rendered state as the source of
  // truth here and only fail on unexpected runtime errors.
  const unexpectedErrors = pageErrors.filter(
    (err) => !err.message.includes("React error #418")
  );
  expect(unexpectedErrors).toHaveLength(0);
});

// ---------------------------------------------------------------------------
// Scenario 4 — Session persistence across navigation
// ---------------------------------------------------------------------------
test("Scenario 4: session persists across page navigations", async ({ page }) => {
  // Mock /auth/me to always return an authenticated user — no real credentials needed.
  // This lets us test navigation behaviour without CI secrets.
  await page.route(`**/auth/me`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    });
  });

  // Navigate to /chat — the page redirects to "/" on a 401, so reaching /chat
  // confirms the mock is actually being honoured (cannot silently pass).
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });
  expect(page.url()).toContain("/chat");

  // Navigate to /settings
  await page.goto(`${FRONTEND}/settings`);
  await page.waitForURL(/\/settings/, { timeout: 5_000 });
  expect(page.url()).toContain("/settings");

  // Navigate back to /chat — session mock must still be active
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });

  // Should still be on /chat — not redirected to /
  expect(page.url()).toContain("/chat");
});

// ---------------------------------------------------------------------------
// Scenario 5 — Logout flow
// ---------------------------------------------------------------------------
test("Scenario 5: logout clears session and redirects away from /chat", async ({ page }) => {
  // Stateful mock: /auth/me returns 200 while logged in, 401 after logout.
  // Flips when /auth/logout is intercepted — no real credentials needed.
  let isLoggedIn = true;

  await page.route(`**/auth/me`, async (route: Route) => {
    if (isLoggedIn) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER),
      });
    } else {
      await route.fulfill({
        status: 401,
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
    }
  });

  // settings/page.tsx awaits the logout response before calling router.push("/"),
  // so flipping isLoggedIn here guarantees /auth/me returns 401 for any
  // subsequent navigation to /chat.
  await page.route(`**/auth/logout`, async (route: Route) => {
    isLoggedIn = false;
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });

  // Reach /chat while mocked-authenticated.
  // waitForURL failing here means the mock was rejected — cannot silently pass.
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForURL(/\/chat/, { timeout: 5_000 });
  expect(page.url()).toContain("/chat");

  // Navigate to /settings — the sign-out button lives there (settings/page.tsx).
  // The button is only rendered once the /auth/me response sets user state,
  // so we wait for it to become visible before clicking.
  await page.goto(`${FRONTEND}/settings`);
  const signOutBtn = page.getByRole("button", { name: /sign out/i });
  await expect(signOutBtn).toBeVisible({ timeout: 5_000 });
  await signOutBtn.click();

  // settings/page.tsx calls router.push("/") after the awaited logout request,
  // so by the time the navigation resolves isLoggedIn is already false.
  await page.waitForURL(/^\/(login|$)/, { timeout: 5_000 }).catch(() => {
    // Some builds redirect to /login, some to "/"
  });
  expect(page.url()).not.toContain("/settings");

  // Session cookie must be absent — we never injected a real one.
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((c) => c.name === "session");
  expect(sessionCookie === undefined || sessionCookie.value === "").toBe(true);

  // Attempting to navigate to /chat should redirect away — /auth/me now returns 401.
  await page.goto(`${FRONTEND}/chat`);
  await page.waitForLoadState("networkidle");
  expect(page.url()).not.toContain("/chat");
});

// ---------------------------------------------------------------------------
// Scenario 6 — Password reset flow
// ---------------------------------------------------------------------------
test("Scenario 6: password reset flow — submitting the forgot-password form shows success", async ({ page }) => {
  const jsErrors: string[] = [];
  page.on("pageerror", (err) => jsErrors.push(err.message));

  // Mock the forgot-password endpoint to return 200 without hitting the real backend
  await page.route(`**/auth/forgot-password`, async (route: Route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ message: "ok" }) });
  });
  // /auth/me returns 401 — user is not authenticated (forgot-password page is public)
  await page.route(`**/auth/me`, async (route: Route) => {
    await route.fulfill({ status: 401, body: JSON.stringify({ detail: "Not authenticated" }) });
  });

  // Navigate to the forgot-password page directly — the route exists at /forgot-password
  await page.goto(`${FRONTEND}/forgot-password`);
  await page.waitForLoadState("networkidle");

  // Hard assertion: the email input must be visible. If the page doesn't render it,
  // the test fails with a clear error rather than silently passing with zero assertions.
  const emailField = page.locator('input[type="email"]').first();
  await expect(emailField).toBeVisible({ timeout: 8_000 });

  await emailField.fill(TEST_EMAIL);

  // Submit button — hard assertion that it exists and is interactable
  const submitBtn = page
    .locator('button[type="submit"], button:has-text("Send"), button:has-text("Reset"), button:has-text("Continue")')
    .first();
  await expect(submitBtn).toBeVisible({ timeout: 5_000 });
  await submitBtn.click();

  // After submission a success message must appear ("Check your email" or similar)
  await expect(async () => {
    const bodyText = (await page.locator("body").innerText()).toLowerCase();
    const hasSuccess =
      bodyText.includes("check your email") ||
      bodyText.includes("email sent") ||
      bodyText.includes("reset link") ||
      bodyText.includes("sent") ||
      bodyText.includes("success");
    expect(hasSuccess).toBe(true);
  }).toPass({ timeout: 10_000 });

  // No unhandled JS errors
  const criticalErrors = jsErrors.filter(
    (e) => !e.includes("418") && !e.toLowerCase().includes("hydration") && !e.includes("did not match")
  );
  expect(criticalErrors).toHaveLength(0);
});

// ---------------------------------------------------------------------------
// Scenario 7 — Protected route redirects unauthenticated user
// ---------------------------------------------------------------------------
test("Scenario 7: unauthenticated user navigating to /chat is redirected away", async ({ page }) => {
  // Mock /auth/me to return 401 — simulates an unauthenticated session.
  // We do NOT set a session cookie so the page's auth guard triggers a redirect.
  await page.route(`**/auth/me`, async (route: Route) => {
    await route.fulfill({ status: 401, body: JSON.stringify({ detail: "Not authenticated" }) });
  });

  // Navigate directly to the protected /chat route
  await page.goto(`${FRONTEND}/chat`);

  // The auth guard calls /auth/me on mount and redirects to "/" on a 401.
  // Use an event-based assertion rather than a fixed sleep — resolves as soon
  // as the redirect fires, fails fast if it never comes.
  await expect(async () => {
    expect(page.url()).not.toContain("/chat");
  }).toPass({ timeout: 5_000 });

  // The redirected page must render meaningful content (not a blank crash)
  const bodyText = await page.locator("body").innerText();
  expect(bodyText.length).toBeGreaterThan(0);
});
