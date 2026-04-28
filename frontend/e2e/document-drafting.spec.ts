/**
 * E2E tests for document drafting feature — NEO-1004 / NEO-845 [2/3]
 *
 * Covers:
 *   T9–T15  Frontend UI tests (template picker, document card, viewer, download)
 *   T16–T20 Integration round-trip tests (full flow with mocked SSE backend)
 *
 * All network routes are mocked via page.route() — no real backend required.
 * The dev server must be running at http://localhost:3000.
 *
 * Strategy: React 19 + Next.js 16 App Router's production build does not process
 * events dispatched via Playwright's CDP layer (fill, press, evaluate dispatchEvent).
 * We bypass the textarea entirely by:
 *   1. Pre-populating localStorage via browser.newContext({ storageState }) before
 *      ANY navigation. This is the only reliable way — addInitScript and
 *      evaluate+reload both execute too late relative to React's useEffect that reads
 *      the store. With storageState, the origin's localStorage already contains
 *      session data when the very first page request is made.
 *   2. Clicking follow-up suggestion buttons which call onSend() directly in the
 *      React component tree, without involving the textarea at all.
 *
 * Run: npx playwright test e2e/document-drafting.spec.ts
 */
import { test, expect, type Page, type BrowserContext, type Route, type Browser } from "playwright/test";
import { gotoWithRetry } from "./helpers";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FRONTEND = `http://localhost:${process.env.CI_PORT ?? "3000"}`;

/** Pre-seeded session IDs written to storageState */
const SEED_UID = "e2e-user-id"; // must match MOCK_USER.id
const SEED_SESSION_ID = "e2e-session-00000001";

/** Minimal /auth/me response — lets any page requiring auth pass the guard */
const MOCK_USER = {
  id: "e2e-user-id",
  email: "testuser@vitreon.app",
  name: "E2E Tester",
  avatar_url: null,
  plan: "free",
  subscription_status: "active",
  monthly_queries_used: 0,
  max_corpora: 1,
};

/** Two CZ templates used throughout the tests */
const MOCK_TEMPLATES = [
  {
    id: "00000001-0000-4000-a000-000000000001",
    slug: "zaloba_neplatnost_vypovedi",
    name: "Žaloba na neplatnost výpovědi",
    jurisdiction: "CZ",
    category: "labor",
    description: "Žaloba na neplatnost výpovědi z pracovního poměru.",
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "00000001-0000-4000-a000-000000000002",
    slug: "navrh_platebni_rozkaz",
    name: "Návrh na platební rozkaz",
    jurisdiction: "CZ",
    category: "civil",
    description: "Návrh na vydání platebního rozkazu.",
    created_at: "2025-01-01T00:00:00Z",
  },
];

/** Valid UUIDs — required by the UUID_RE guard in use-query-stream.ts */
const DOC_UUID_1 = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d";
const DOC_UUID_2 = "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e";
const DOC_UUID_3 = "c3d4e5f6-a7b8-4c5d-a0b1-2c3d4e5f6a7b";

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------

/**
 * Builds a proper SSE body string.
 * Each event MUST use the "event:" line so eventsource-parser routes it to
 * the correct processEvent branch.
 */
function sseBody(events: Array<{ event: string; data: object }>): string {
  return events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
}

/** SSE that generates document v1.
 *  fields must be non-empty so DocumentCard.isReady=true, which renders the
 *  Preview button and Download PDF link (T12, T13, T16). Without fields the
 *  card shows "AI is filling fields…" and the action buttons are hidden. */
const SSE_WITH_DOC_V1 = sseBody([
  { event: "answer", data: { answer: "Na základě zákoníku práce [DOC-1]...", sources: [], confidence: 0.9 } },
  {
    event: "document_generated",
    data: {
      doc_id: DOC_UUID_1,
      template_slug: "zaloba_neplatnost_vypovedi",
      template_name: "Žaloba na neplatnost výpovědi",
      version: 1,
      fields: { zalobce: "Jan Novák", zalovany: "Firma s.r.o." },
    },
  },
  { event: "done", data: {} },
]);

/** SSE that updates the same document to version 2.
 *  fields included so isReady=true in version-update tests (T14, T17). */
const SSE_WITH_DOC_V2 = sseBody([
  { event: "answer", data: { answer: "Dokument byl upraven.", sources: [], confidence: 0.9 } },
  {
    event: "document_generated",
    data: {
      doc_id: DOC_UUID_1,
      template_slug: "zaloba_neplatnost_vypovedi",
      template_name: "Žaloba na neplatnost výpovědi",
      version: 2,
      fields: { zalobce: "Jan Novák", zalovany: "Firma s.r.o." },
    },
  },
  { event: "done", data: {} },
]);

/** SSE returning three distinct documents */
const SSE_WITH_THREE_DOCS = sseBody([
  { event: "answer", data: { answer: "Tři dokumenty vygenerovány.", sources: [], confidence: 0.9 } },
  { event: "document_generated", data: { doc_id: DOC_UUID_1, template_slug: "zaloba_neplatnost_vypovedi", template_name: "Žaloba na neplatnost výpovědi", version: 1 } },
  { event: "document_generated", data: { doc_id: DOC_UUID_2, template_slug: "navrh_platebni_rozkaz", template_name: "Návrh na platební rozkaz", version: 1 } },
  { event: "document_generated", data: { doc_id: DOC_UUID_3, template_slug: "vlastni_dokument", template_name: "Vlastní dokument", version: 1 } },
  { event: "done", data: {} },
]);

/** SSE with Czech text and [DOC-1] citation */
const SSE_WITH_CITATION = sseBody([
  {
    event: "answer",
    data: {
      answer: "Na základě zákoníku práce [DOC-1] §\u00a052 lze výpověď napadnout soudně.",
      sources: [{ doc_id: DOC_UUID_1, title: "Zákoník práce", page_numbers: [52] }],
      confidence: 0.9,
    },
  },
  { event: "done", data: {} },
]);

/** SSE with Czech characters only */
const SSE_WITH_CZECH = sseBody([
  {
    event: "answer",
    data: {
      answer: "Na základě zákoníku práce §\u00a052 lze výpověď napadnout soudně v řízení před příslušným soudem.",
      sources: [],
      confidence: 0.9,
    },
  },
  { event: "done", data: {} },
]);

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

/**
 * Build the storage-state object that pre-seeds localStorage for http://localhost:3000
 * with a completed session. Pass this to browser.newContext({ storageState }).
 *
 * Using browser.newContext({ storageState }) is the ONLY reliable way to inject
 * localStorage before a page loads in Playwright. addInitScript runs after the
 * document is created, and page.evaluate()+reload() executes after React's
 * mount effect has already run — so both arrive too late.
 *
 * The seeded session has one user + one assistant message. This makes:
 *   - currentSessionId truthy → TemplatePicker button visible
 *   - showFollowUps = true → follow-up suggestion buttons rendered
 */
function buildStorageState() {
  const session = {
    id: SEED_SESSION_ID,
    title: "E2E Setup",
    messages: [
      { id: "u-setup", role: "user", content: "Setup." },
      {
        id: "a-setup",
        role: "assistant",
        content: "Simple answer for setup.",
        sources: [],
        confidence: null,
      },
    ],
    createdAt: Date.now() - 120_000,
    lastMessageAt: Date.now() - 60_000,
    corpora: ["difc"],
  };
  return {
    cookies: [] as Array<{ name: string; value: string; domain: string; path: string; expires: number; httpOnly: boolean; secure: boolean; sameSite: "Lax" | "None" | "Strict" }>,
    origins: [
      {
        origin: FRONTEND,
        localStorage: [
          { name: "neolex_uid", value: SEED_UID },
          { name: `neolex_chat_sessions_${SEED_UID}`, value: JSON.stringify([session]) },
          { name: `neolex_current_session_${SEED_UID}`, value: SEED_SESSION_ID },
        ],
      },
    ],
  };
}

/**
 * Create a browser context with the session pre-seeded in localStorage, then
 * return the page. Call context.close() in a finally block after the test.
 */
async function createSeededPage(browser: Browser): Promise<[Page, BrowserContext]> {
  const context = await browser.newContext({ storageState: buildStorageState() });
  const page = await context.newPage();
  return [page, context];
}

/** Install auth + conversations + documents mocks that every test needs */
async function mockBaseRoutes(page: Page) {
  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );
  // Conversations list — return empty so no backend sessions merge in
  await page.route("**/api/v1/conversations", (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v1/conversations") {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ conversations: [] }) });
    } else {
      route.continue();
    }
  });
  // Documents for any conversation — return empty (documents come from SSE only)
  await page.route("**/api/v1/conversations/*/documents", (route: Route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.match(/\/documents\/[^/]+$/)) {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    } else {
      route.continue();
    }
  });
}

/**
 * Click the first follow-up suggestion button to send a query.
 *
 * Follow-up buttons are rendered by the chat page when the last message is
 * an assistant reply. Their onClick directly calls onSend(text), bypassing
 * the textarea and its React event handling entirely.
 */
async function clickFollowUp(page: Page) {
  const followUpBtn = page.locator('button:has-text("Can you cite the specific article?")').first();
  if (await followUpBtn.isVisible({ timeout: 10_000 }).catch(() => false)) {
    await followUpBtn.click();
    return;
  }

  const messageInput = page.getByRole("textbox", { name: "Message input" });
  await expect(messageInput).toBeVisible({ timeout: 10_000 });
  await messageInput.fill("What is the limitation period under DIFC Law No. 5 of 2005?");
  // fill() sets the DOM value but doesn't fire React's synthetic input event — leaving
  // hasText=false and the Send button disabled. Dispatch a native input event so React's
  // onInput handler picks up the value and enables the button.
  await messageInput.dispatchEvent("input");
  await page.getByRole("button", { name: "Send message" }).click();
}

// ---------------------------------------------------------------------------
// T9 — Template picker opens/closes
// ---------------------------------------------------------------------------
test("T9: template picker opens and closes via Escape", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/templates**", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_TEMPLATES) })
    );

    await gotoWithRetry(page, `${FRONTEND}/chat`);

    // chatId is set from localStorage — TemplatePicker is visible immediately
    const pickerBtn = page.locator('button[aria-label="Open template picker"]');
    await expect(pickerBtn).toBeVisible({ timeout: 8_000 });
    await pickerBtn.click();

    // Panel is a dialog
    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible({ timeout: 5_000 });

    // Close via Escape
    await page.keyboard.press("Escape");
    await expect(panel).not.toBeVisible({ timeout: 3_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T10 — Template selection sends metadata in the query request body
// ---------------------------------------------------------------------------
test("T10: selecting a template adds template_slug to the POST /query/stream body", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    let capturedBody: Record<string, unknown> | null = null;

    await mockBaseRoutes(page);
    await page.route("**/api/v1/templates**", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_TEMPLATES) })
    );
    await page.route("**/api/v1/query/stream", async (route: Route) => {
      capturedBody = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_V1 });
    });

    await gotoWithRetry(page, `${FRONTEND}/chat`);

    // Open picker and select the first template
    await page.locator('button[aria-label="Open template picker"]').click();
    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible({ timeout: 5_000 });
    await panel.locator(`button:has-text("Žaloba na neplatnost výpovědi")`).click();
    await expect(panel).not.toBeVisible({ timeout: 3_000 });

    // Send via follow-up button — pendingTemplateSlug is picked up by onSend
    await clickFollowUp(page);

    // Wait for the request to be captured
    await expect(async () => {
      expect(capturedBody).not.toBeNull();
    }).toPass({ timeout: 10_000 });

    expect(capturedBody!["template_slug"]).toBe("zaloba_neplatnost_vypovedi");
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T11 — Document card renders after SSE document_generated event
// ---------------------------------------------------------------------------
test("T11: document card appears with template name and version after SSE document_generated", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_V1 })
    );

    await gotoWithRetry(page, `${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Document card must show the template name
    await expect(page.locator("text=Žaloba na neplatnost výpovědi").first()).toBeVisible({ timeout: 15_000 });

    // Version badge shows "v1"
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 5_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T12 — Document viewer opens on card preview click
// ---------------------------------------------------------------------------
test("T12: clicking Preview on a document card opens the DocumentViewer dialog", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_V1 })
    );
    await page.route("**/api/v1/conversations/*/documents/*/pdf", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.0" })
    );

    await gotoWithRetry(page, `${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Click Preview button
    await page.locator('button[aria-label="Preview"]').first().click();

    // DocumentViewer is identified by its close button aria-label
    await expect(page.locator('button[aria-label="Close document viewer"]')).toBeVisible({ timeout: 5_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T13 — Download link triggers the PDF endpoint
// ---------------------------------------------------------------------------
test("T13: clicking the Download link on a document card requests the PDF endpoint", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_V1 })
    );

    let pdfEndpointCalled = 0;
    await page.route("**/api/v1/conversations/*/documents/*/pdf", (route: Route) => {
      pdfEndpointCalled += 1;
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.0" });
    });

    await gotoWithRetry(page, `${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Click the download anchor
    const downloadLink = page.locator('a[title="Download PDF"]').first();
    await expect(downloadLink).toBeVisible({ timeout: 5_000 });

    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 5_000 }).catch(() => null),
      downloadLink.click(),
    ]);

    // Either download event fires or route was intercepted
    expect(pdfEndpointCalled > 0 || download !== null).toBe(true);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T14 — Version update increments the badge from v1 to v2
// ---------------------------------------------------------------------------
test("T14: sending a follow-up message updates the document card version badge to v2", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    let queryCount = 0;

    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) => {
      queryCount += 1;
      const body = queryCount === 1 ? SSE_WITH_DOC_V1 : SSE_WITH_DOC_V2;
      route.fulfill({ status: 200, contentType: "text/event-stream", body });
    });

    await gotoWithRetry(page, `${FRONTEND}/chat`);

    // First query → doc v1
    await clickFollowUp(page);
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // After streaming ends the follow-up buttons reappear — click for second query
    await clickFollowUp(page);
    await expect(page.locator("text=v2").first()).toBeVisible({ timeout: 15_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T15 — Three SSE document_generated events produce three document cards
// ---------------------------------------------------------------------------
test("T15: three document_generated events render three document cards", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_THREE_DOCS })
    );

    await gotoWithRetry(page, `${FRONTEND}/chat`);
    await clickFollowUp(page);

    // All three version "v1" badges must appear — one per document card
    await expect(page.locator("text=v1")).toHaveCount(3, { timeout: 15_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T16 — Full template → agent → document → PDF round-trip
// ---------------------------------------------------------------------------
test("T16: full round-trip — template selection, SSE doc, preview, and PDF download", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    let pdfHits = 0;

    await mockBaseRoutes(page);
    await page.route("**/api/v1/templates**", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_TEMPLATES) })
    );
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_V1 })
    );
    await page.route("**/api/v1/conversations/*/documents/*/pdf", (route: Route) => {
      pdfHits += 1;
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.0" });
    });

    await gotoWithRetry(page, `${FRONTEND}/chat`);

    // chatId is set from localStorage — TemplatePicker is immediately available
    await page.locator('button[aria-label="Open template picker"]').click();
    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible({ timeout: 5_000 });
    await panel.locator('button:has-text("Žaloba na neplatnost výpovědi")').click();
    await expect(panel).not.toBeVisible({ timeout: 3_000 });

    // Send message via follow-up (includes pendingTemplateSlug)
    await clickFollowUp(page);

    // Verify document card appears
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Open viewer
    await page.locator('button[aria-label="Preview"]').first().click();
    await expect(page.locator('button[aria-label="Close document viewer"]')).toBeVisible({ timeout: 5_000 });

    // Close viewer
    await page.locator('button[aria-label="Close document viewer"]').click();
    await expect(page.locator('button[aria-label="Close document viewer"]')).not.toBeVisible({ timeout: 3_000 });

    // Download PDF via card link
    const downloadLink = page.locator('a[title="Download PDF"]').first();
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 5_000 }).catch(() => null),
      downloadLink.click(),
    ]);
    expect(pdfHits > 0 || download !== null).toBe(true);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T17 — Update round-trip: v1 → v2
// ---------------------------------------------------------------------------
test("T17: update round-trip — document version increments from v1 to v2", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    let queryCount = 0;

    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) => {
      queryCount += 1;
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: queryCount === 1 ? SSE_WITH_DOC_V1 : SSE_WITH_DOC_V2,
      });
    });

    await gotoWithRetry(page, `${FRONTEND}/chat`);

    // First message — doc v1 appears
    await clickFollowUp(page);
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Second message — same doc_id, version bumped to 2
    await clickFollowUp(page);
    await expect(page.locator("text=v2").first()).toBeVisible({ timeout: 15_000 });

    // v1 badge must be gone (replaced in-place, not duplicated)
    await expect(page.locator("text=v1")).toHaveCount(0, { timeout: 3_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T18 — Custom template round-trip (vlastni_dokument)
// ---------------------------------------------------------------------------
test("T18: selecting vlastni_dokument (no required fields) produces a document card without errors", async ({ browser }) => {
  const customTemplate = {
    id: "00000001-0000-4000-a000-000000000099",
    slug: "vlastni_dokument",
    name: "Vlastní dokument",
    jurisdiction: "General",
    category: "General",
    description: "Volná šablona bez povinných polí.",
    created_at: "2025-01-01T00:00:00Z",
  };

  const sseWithCustomDoc = sseBody([
    { event: "answer", data: { answer: "Vlastní dokument byl vygenerován.", sources: [], confidence: 0.9 } },
    { event: "document_generated", data: { doc_id: DOC_UUID_2, template_slug: "vlastni_dokument", template_name: "Vlastní dokument", version: 1 } },
    { event: "done", data: {} },
  ]);

  const [page, context] = await createSeededPage(browser);
  try {
    // Capture console errors (set up before page.goto)
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await mockBaseRoutes(page);
    await page.route("**/api/v1/templates**", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([customTemplate]) })
    );
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: sseWithCustomDoc })
    );

    await gotoWithRetry(page, `${FRONTEND}/chat`);

    // Select custom template
    await page.locator('button[aria-label="Open template picker"]').click();
    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible({ timeout: 5_000 });
    await panel.locator('button:has-text("Vlastní dokument")').click();
    await expect(panel).not.toBeVisible({ timeout: 3_000 });

    // Send message with custom template
    await clickFollowUp(page);

    // Document card appears — no required-field validation errors
    await expect(page.locator("text=Vlastní dokument").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 5_000 });

    // No validation-related console errors
    const validationErrors = consoleErrors.filter((e) =>
      e.toLowerCase().includes("required") || e.toLowerCase().includes("validation")
    );
    expect(validationErrors).toHaveLength(0);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T19 — Corpus grounding: [DOC-1] in answer renders as citation marker
// ---------------------------------------------------------------------------
test("T19: [DOC-1] citation in SSE answer renders as a superscript citation marker", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_CITATION })
    );

    await gotoWithRetry(page, `${FRONTEND}/chat`);
    await clickFollowUp(page);

    // chat-message.tsx replaces [DOC-N] with a <sup> element
    const citationSup = page.locator("sup").first();
    await expect(citationSup).toBeVisible({ timeout: 15_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// T20 — Czech output renders correctly (ž, á, č characters preserved)
// ---------------------------------------------------------------------------
test("T20: SSE stream with Czech text renders Czech characters without corruption", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_CZECH })
    );

    await gotoWithRetry(page, `${FRONTEND}/chat`);
    await clickFollowUp(page);

    // The answer must contain Czech diacritics — if mangled these would fail
    await expect(page.locator("text=zákoníku").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("text=výpověď").first()).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=příslušným").first()).toBeVisible({ timeout: 5_000 });
  } finally {
    await context.close();
  }
});
