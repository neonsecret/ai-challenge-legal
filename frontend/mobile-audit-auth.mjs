/**
 * Authenticated mobile audit screenshots using pre-obtained session cookie.
 * Run after mobile-audit.mjs when login via UI fails.
 */

import { chromium } from "playwright";
import { existsSync, mkdirSync, writeFileSync, readFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.join(__dirname, "..", "docs", "mobile-audit-screenshots");

const VIEWPORTS = [
  { name: "iphone-se", width: 375, height: 812 },
  { name: "iphone-14-pro", width: 390, height: 844 },
  { name: "android-mid", width: 360, height: 800 },
];

const AUTHENTICATED_ROUTES = [
  { path: "/chat", label: "chat-empty" },
  { path: "/settings", label: "settings" },
  { path: "/billing", label: "billing" },
  { path: "/documents", label: "documents" },
];

const BASE_URL = "http://localhost:3000";
const SESSION_COOKIE = "iT_WJbdAA16N2grI_U5Y_SG5AMFGHJM5mJTkpBC3-j0";

if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

const findings = [];

function addFinding(route, viewport, severity, issue, extra = {}) {
  findings.push({ route, viewport: viewport.name, severity, issue, authenticated: true, ...extra });
}

async function checkPageIssues(page, route, viewport) {
  const hasHorizontalScroll = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  if (hasHorizontalScroll) {
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    addFinding(route.path, viewport, "P0", `Horizontal scroll: scrollWidth=${scrollWidth}px > clientWidth=${clientWidth}px`);
  }

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
  for (const t of smallTargets) {
    addFinding(route.path, viewport, "P1", `Touch target too small: <${t.tag}> "${t.text}" is ${t.w}×${t.h}px (min 44×44px)`);
  }

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
  for (const inp of smallInputs) {
    addFinding(route.path, viewport, "P0", `Input font-size ${inp.fontSize}px < 16px triggers iOS auto-zoom: <${inp.tag} type="${inp.type}">`);
  }
}

async function main() {
  console.log("=== Authenticated Mobile Audit ===\n");
  const browser = await chromium.launch({ headless: true });

  for (const viewport of VIEWPORTS) {
    const ctx = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      storageState: {
        cookies: [
          {
            name: "vitreon_session",
            value: SESSION_COOKIE,
            domain: "localhost",
            path: "/",
            httpOnly: true,
            secure: false,
            sameSite: "Lax",
          },
        ],
      },
    });

    const page = await ctx.newPage();
    console.log(`\n[${viewport.name} ${viewport.width}×${viewport.height}]`);

    // Verify we're logged in
    await page.goto(BASE_URL + "/chat", { waitUntil: "networkidle", timeout: 15000 });
    await page.waitForTimeout(1000);
    const isOnLogin = page.url().includes("/login");
    console.log(`  Auth check: ${isOnLogin ? "REDIRECTED TO LOGIN (session expired?)" : "AUTHENTICATED ✓"}`);

    for (const route of AUTHENTICATED_ROUTES) {
      const filename = `${route.label}--${viewport.name}--auth.png`;
      const outPath = path.join(OUT_DIR, filename);

      try {
        await page.goto(BASE_URL + route.path, { waitUntil: "networkidle", timeout: 15000 });
        await page.waitForTimeout(1500);
        await checkPageIssues(page, route, viewport);
        await page.screenshot({ path: outPath, fullPage: true });
        console.log(`  ✓ ${route.path} → ${filename} (url=${page.url()})`);
      } catch (err) {
        console.error(`  ✗ ${route.path}: ${err.message}`);
        addFinding(route.path, viewport, "P0", `Screenshot failed: ${err.message}`, { authenticated: true });
      }
    }

    await ctx.close();
  }

  await browser.close();

  const p0 = findings.filter((f) => f.severity === "P0");
  const p1 = findings.filter((f) => f.severity === "P1");
  console.log(`\nAuthenticated findings: P0=${p0.length} P1=${p1.length}`);

  // Merge with existing findings
  let existing = [];
  const findingsPath = path.join(OUT_DIR, "findings.json");
  if (existsSync(findingsPath)) {
    existing = JSON.parse(readFileSync(findingsPath, "utf8"));
    // Remove old unauthenticated findings for auth routes
    existing = existing.filter((f) => !["/chat", "/settings", "/billing", "/documents"].includes(f.route));
  }

  const merged = [...existing, ...findings];
  writeFileSync(findingsPath, JSON.stringify(merged, null, 2));
  console.log(`Total findings after merge: ${merged.length}`);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
