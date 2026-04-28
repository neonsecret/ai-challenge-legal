import type { Page } from "playwright/test";

/**
 * Retries page.goto() on transient navigation errors caused by auth redirects
 * racing against Playwright's default waitUntil:"load". Applies waitUntil:
 * "domcontentloaded" which is more tolerant of mid-flight redirects.
 */
export async function gotoWithRetry(page: Page, url: string): Promise<void> {
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
