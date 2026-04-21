/**
 * Mobile audit screenshot sweep for Vitreon Legal.
 * Captures all routes at 3 mobile viewports and checks for common mobile issues.
 *
 * Output: docs/mobile-audit-screenshots/*.png
 *
 * Usage: node mobile-audit.mjs
 */

import { chromium } from "playwright";
import { existsSync, mkdirSync, writeFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.join(__dirname, "..", "docs", "mobile-audit-screenshots");

const VIEWPORTS = [
  { name: "iphone-se", width: 375, height: 812 },
  { name: "iphone-14-pro", width: 390, height: 844 },
  { name: "android-mid", width: 360, height: 800 },
];

const PUBLIC_ROUTES = [
  { path: "/", label: "landing" },
  { path: "/blog", label: "blog-index" },
  { path: "/blog/czech-legal-ai-sota", label: "blog-slug" },
  { path: "/login", label: "login" },
  { path: "/forgot-password", label: "forgot-password" },
  { path: "/pricing", label: "pricing" },
  { path: "/about", label: "about" },
  { path: "/faq", label: "faq" },
  { path: "/privacy", label: "privacy" },
  { path: "/terms", label: "terms" },
  { path: "/benchmarks", label: "benchmarks" },
];

const AUTHENTICATED_ROUTES = [
  { path: "/chat", label: "chat-empty" },
  { path: "/settings", label: "settings" },
  { path: "/billing", label: "billing" },
  { path: "/documents", label: "documents" },
];

const BASE_URL = "http://localhost:3000";
const ADMIN_EMAIL = "admin@vitreon.app";
const ADMIN_PASSWORD = "bQiuavDQsAkVHufxbfnIld&t";

if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

const findings = [];

function addFinding(route, viewport, severity, issue, extra = {}) {
  findings.push({ route, viewport: viewport.name, severity, issue, ...extra });
}

async function checkPageIssues(page, route, viewport) {
  const url = BASE_URL + route.path;

  // Check horizontal overflow
  const hasHorizontalScroll = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  if (hasHorizontalScroll) {
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    addFinding(route.path, viewport, "P0", `Horizontal scroll: scrollWidth=${scrollWidth}px > clientWidth=${clientWidth}px`);
  }

  // Check touch targets < 44x44px
  const smallTargets = await page.evaluate(() => {
    const interactives = document.querySelectorAll("a, button, input, select, textarea, [role=button], [tabindex]");
    const small = [];
    for (const el of interactives) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44)) {
        small.push({
          tag: el.tagName,
          text: (el.textContent || "").trim().slice(0, 40),
          w: Math.round(rect.width),
          h: Math.round(rect.height),
        });
      }
    }
    return small.slice(0, 10);
  });
  if (smallTargets.length > 0) {
    for (const t of smallTargets) {
      addFinding(route.path, viewport, "P1", `Touch target too small: <${t.tag}> "${t.text}" is ${t.w}×${t.h}px (min 44×44px)`);
    }
  }

  // Check input font size < 16px (iOS zoom trigger)
  const smallInputs = await page.evaluate(() => {
    const inputs = document.querySelectorAll("input, textarea, select");
    const small = [];
    for (const el of inputs) {
      const style = window.getComputedStyle(el);
      const fontSize = parseFloat(style.fontSize);
      if (fontSize < 16) {
        small.push({ tag: el.tagName, type: el.type || "", fontSize });
      }
    }
    return small;
  });
  if (smallInputs.length > 0) {
    for (const inp of smallInputs) {
      addFinding(route.path, viewport, "P0", `Input font-size ${inp.fontSize}px < 16px will trigger iOS auto-zoom: <${inp.tag} type="${inp.type}">`);
    }
  }

  // Check for tiny text <= 11px
  const tinyText = await page.evaluate(() => {
    const allEls = document.querySelectorAll("p, span, div, h1, h2, h3, h4, h5, h6, li, a, button, label");
    const tiny = [];
    for (const el of allEls) {
      if (el.children.length > 0) continue; // skip containers
      const style = window.getComputedStyle(el);
      const fontSize = parseFloat(style.fontSize);
      if (fontSize <= 11 && el.textContent && el.textContent.trim().length > 0) {
        tiny.push({ tag: el.tagName, text: el.textContent.trim().slice(0, 40), fontSize });
        if (tiny.length >= 5) break;
      }
    }
    return tiny;
  });
  if (tinyText.length > 0) {
    for (const t of tinyText) {
      addFinding(route.path, viewport, "P1", `Text too small: ${t.fontSize}px ≤ 11px — "${t.text}" in <${t.tag}>`);
    }
  }
}

async function screenshotRoute(page, route, viewport) {
  const filename = `${route.label}--${viewport.name}.png`;
  const outPath = path.join(OUT_DIR, filename);

  try {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    const response = await page.goto(BASE_URL + route.path, {
      waitUntil: "networkidle",
      timeout: 15000,
    });
    await page.waitForTimeout(800);

    const status = response?.status() ?? 0;
    if (status >= 400) {
      addFinding(route.path, viewport, "P0", `HTTP ${status} — page not found or errored`);
    }

    await checkPageIssues(page, route, viewport);
    await page.screenshot({ path: outPath, fullPage: true });
    console.log(`  ✓ ${route.path} @ ${viewport.name} → ${filename}`);
    return { ok: true, filename };
  } catch (err) {
    console.error(`  ✗ ${route.path} @ ${viewport.name}: ${err.message}`);
    addFinding(route.path, viewport, "P0", `Screenshot failed: ${err.message}`);
    return { ok: false, filename: null };
  }
}

async function login(page) {
  await page.goto(BASE_URL + "/login", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(500);

  // Fill login form
  await page.fill('input[type="email"], input[name="email"], input[placeholder*="email" i]', ADMIN_EMAIL);
  await page.fill('input[type="password"], input[name="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);

  const currentUrl = page.url();
  const loggedIn = !currentUrl.includes("/login") && !currentUrl.includes("/signup");
  console.log(`  Login attempt → ${currentUrl} — ${loggedIn ? "SUCCESS" : "FAILED"}`);
  return loggedIn;
}

async function main() {
  console.log("=== Vitreon Legal Mobile Audit ===\n");

  const browser = await chromium.launch({ headless: true });

  // --- Public routes ---
  console.log("--- Public routes ---");
  for (const viewport of VIEWPORTS) {
    const ctx = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
    const page = await ctx.newPage();
    console.log(`\n[${viewport.name} ${viewport.width}×${viewport.height}]`);
    for (const route of PUBLIC_ROUTES) {
      await screenshotRoute(page, route, viewport);
    }
    await ctx.close();
  }

  // --- Authenticated routes ---
  console.log("\n--- Authenticated routes ---");
  for (const viewport of VIEWPORTS) {
    const ctx = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
    const page = await ctx.newPage();
    console.log(`\n[${viewport.name} ${viewport.width}×${viewport.height}]`);

    const loggedIn = await login(page);
    if (!loggedIn) {
      console.warn("  Login failed — capturing redirect state for auth routes");
    }

    for (const route of AUTHENTICATED_ROUTES) {
      await screenshotRoute(page, route, viewport);
    }
    await ctx.close();
  }

  await browser.close();

  // Summary
  const p0 = findings.filter((f) => f.severity === "P0");
  const p1 = findings.filter((f) => f.severity === "P1");
  const p2 = findings.filter((f) => f.severity === "P2");
  console.log(`\n=== Findings: P0=${p0.length} P1=${p1.length} P2=${p2.length} ===`);

  // Write findings JSON for report generation
  writeFileSync(path.join(OUT_DIR, "findings.json"), JSON.stringify(findings, null, 2));
  console.log("Findings saved to docs/mobile-audit-screenshots/findings.json");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
