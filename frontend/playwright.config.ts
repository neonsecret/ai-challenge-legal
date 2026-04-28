import { defineConfig, devices } from "playwright/test";

/**
 * Playwright E2E configuration for Vitreon Legal frontend.
 * Targets local dev server (http://localhost:3000) by default.
 * Uses Chromium only per NEO-266 spec.
 *
 * CI_PORT env var lets CI use a dedicated port (e.g. 3002) so it does not
 * collide with the launchd-managed production server on 3000.
 */
const PORT = Number(process.env.CI_PORT ?? 3000);
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  /* Run tests sequentially — avoids port conflicts with the live dev server */
  fullyParallel: false,
  /* Fail the build on CI if tests are accidentally left as .only */
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }], ["json", { outputFile: "playwright-results.json" }]],
  use: {
    baseURL: BASE_URL,
    /* Always include credentials (cookies) */
    extraHTTPHeaders: {
      "X-Requested-With": "XMLHttpRequest",
    },
    /* Capture trace on first retry for debugging */
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  /* Dev server is assumed to be already running (managed by the launchctl plist). */
  /* Set webServer only when TEST_START_SERVER=1 to keep CI flexible.            */
  ...(process.env.TEST_START_SERVER
    ? {
        webServer: {
          command: `npm run build && npm run start -- --hostname 127.0.0.1 --port ${PORT}`,
          url: BASE_URL,
          reuseExistingServer: PORT === 3000,
          timeout: 300_000,
        },
      }
    : {}),
});
