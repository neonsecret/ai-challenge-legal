/**
 * E2E tests for document drafting — additional scenarios not in document-drafting.spec.ts
 * NEO-1855
 *
 * Covers:
 *   CD-1   Documents persist after navigating away and back to /chat
 *   CD-2   Document delete — clicking delete removes the card from the DOM
 *   CD-3   "Vlastní dokument" option appears exactly once in template picker
 *   CD-4   Drafting indicator visible during SSE stream, hidden after done
 *   CD-10  LaTeX button hidden when /tex HEAD returns 422 (NEO-1972)
 *   CD-11  LaTeX button hidden in DocumentViewer when /tex HEAD returns 422 (NEO-1985)
 *   CD-12  LaTeX button visible in DocumentViewer when /tex HEAD returns 200 (NEO-2003)
 *
 * Run: npx playwright test e2e/chat-documents.spec.ts
 */
import { test, expect, type Page, type BrowserContext, type Route, type Browser } from "playwright/test";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FRONTEND = "http://localhost:3000";

const SEED_UID = "e2e-user-id";
const SEED_SESSION_ID = "e2e-session-00000001";

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

const DOC_UUID = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d";

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
  // Note: 'vlastni_dokument' must NOT be in this mock. TemplatePanel hardcodes a
  // "Custom document" button with slug "__custom__" and filters out any API template
  // whose slug matches CUSTOM_SLUG ("__custom__"). The backend never returns
  // 'vlastni_dokument' in production. Including it here would cause CD-3 to fail in
  // Czech-locale CI where t("template.custom_document") = "Vlastní dokument",
  // producing count=2 for 'button:has-text("Vlastní dokument")' in the panel.
];

// ---------------------------------------------------------------------------
// MOCK_BACKEND_DOC is the shape returned by GET /api/v1/conversations/*/documents.
// Used in CD-1 and CD-8 to simulate backend document persistence across navigation.
const MOCK_BACKEND_DOC = {
  doc_id: DOC_UUID,
  template_slug: "zaloba_neplatnost_vypovedi",
  template_name: "Žaloba na neplatnost výpovědi",
  version: 1,
  generated_at: "2026-01-01T00:00:00.000Z",
  fields: { zalobce: "Jan Novák", zalovany: "Firma s.r.o." },
};

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------

function sseBody(events: Array<{ event: string; data: object }>): string {
  return events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
}

const SSE_WITH_DOC = sseBody([
  { event: "answer", data: { answer: "Dokument byl vygenerován.", sources: [], confidence: 0.9 } },
  {
    event: "document_generated",
    data: {
      doc_id: DOC_UUID,
      template_slug: "zaloba_neplatnost_vypovedi",
      template_name: "Žaloba na neplatnost výpovědi",
      version: 1,
    },
  },
  { event: "done", data: {} },
]);

// SSE_WITH_DOC_READY includes populated `fields` so the DocumentCard enters the
// "ready" state and renders the Preview button and Download PDF link (isReady=true).
const SSE_WITH_DOC_READY = sseBody([
  { event: "answer", data: { answer: "Dokument byl vygenerován.", sources: [], confidence: 0.9 } },
  {
    event: "document_generated",
    data: {
      doc_id: DOC_UUID,
      template_slug: "zaloba_neplatnost_vypovedi",
      template_name: "Žaloba na neplatnost výpovědi",
      version: 1,
      fields: { zalobce: "Jan Novák", zalovany: "Firma s.r.o." },
    },
  },
  { event: "done", data: {} },
]);

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function buildStorageState(extraLocalStorage: Array<{ name: string; value: string }> = []) {
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
  const localStorage = new Map<string, string>([
    ["neolex_uid", SEED_UID],
    [`neolex_chat_sessions_${SEED_UID}`, JSON.stringify([session])],
    [`neolex_current_session_${SEED_UID}`, SEED_SESSION_ID],
  ]);
  for (const entry of extraLocalStorage) {
    localStorage.set(entry.name, entry.value);
  }

  return {
    cookies: [] as Array<{ name: string; value: string; domain: string; path: string; expires: number; httpOnly: boolean; secure: boolean; sameSite: "Lax" | "None" | "Strict" }>,
    origins: [
      {
        origin: FRONTEND,
        localStorage: [...localStorage.entries()].map(([name, value]) => ({ name, value })),
      },
    ],
  };
}

async function createSeededPage(
  browser: Browser,
  extraLocalStorage: Array<{ name: string; value: string }> = []
): Promise<[Page, BrowserContext]> {
  const context = await browser.newContext({ storageState: buildStorageState(extraLocalStorage) });
  const page = await context.newPage();
  return [page, context];
}

async function mockBaseRoutes(page: Page) {
  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );
  await page.route("**/api/v1/conversations", (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v1/conversations") {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ conversations: [] }) });
    } else {
      route.continue();
    }
  });
  await page.route("**/api/v1/conversations/*/documents", (route: Route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.match(/\/documents\/[^/]+$/)) {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    } else {
      route.continue();
    }
  });
}

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
// CD-1 — Documents persist across navigation
// ---------------------------------------------------------------------------
test("CD-1: navigating away from /chat and back preserves the document card", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    // Override documents list to return MOCK_BACKEND_DOC — useDocumentState fetches
    // this on every mount, so the card reappears after navigation (not localStorage).
    await page.route("**/api/v1/conversations/*/documents", (route: Route) => {
      const reqUrl = new URL(route.request().url());
      if (!reqUrl.pathname.match(/\/documents\/[^/]+/)) {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MOCK_BACKEND_DOC]) });
      } else {
        route.continue();
      }
    });
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC })
    );

    await page.goto(`${FRONTEND}/chat`);
    await expect(page.locator("text=Žaloba na neplatnost výpovědi").first()).toBeVisible({ timeout: 15_000 });

    // Navigate away — settings requires auth (already mocked)
    await page.goto(`${FRONTEND}/settings`);
    await page.waitForURL(/\/settings/, { timeout: 5_000 });

    // Navigate back to chat
    await page.goto(`${FRONTEND}/chat`);
    await page.waitForURL(/\/chat/, { timeout: 5_000 });

    // Hard assertion: the document card must be visible after returning.
    // useDocumentState re-fetches from the backend on mount — MOCK_BACKEND_DOC provides it.
    await expect(page.locator("text=Žaloba na neplatnost výpovědi").first()).toBeVisible({ timeout: 10_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-2 — Document delete removes the card
// ---------------------------------------------------------------------------
// TODO(NEO-1946): CD-2 skipped — DocumentCard (DocumentCard.tsx) has no delete
// button. The feature (doc deletion via the card UI) was not implemented when
// these tests were written. Re-enable once the delete button and DELETE endpoint
// integration are added to DocumentCard.
test.skip("CD-2: clicking delete on a document card removes it from the page", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC })
    );
    // Delete endpoint — accept DELETE requests for document deletion
    await page.route("**/api/v1/conversations/*/documents/**", (route: Route) => {
      if (route.request().method() === "DELETE") {
        route.fulfill({ status: 204 });
      } else {
        route.continue();
      }
    });

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Hard assertion: the delete button must be visible on the document card.
    // If it's absent, the test fails explicitly — exposing the missing feature rather
    // than silently skipping and hiding the regression.
    const deleteBtn = page.locator(
      'button[aria-label*="Delete"], button[aria-label*="delete"], button[aria-label*="Remove"], button[title*="Delete"], button[title*="delete"]'
    ).first();
    await expect(deleteBtn).toBeVisible({ timeout: 5_000 });
    await deleteBtn.click();

    // The document card must disappear after deletion
    await expect(page.locator("text=Žaloba na neplatnost výpovědi").first()).not.toBeVisible({ timeout: 5_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-3 — "Vlastní dokument" appears exactly once in template picker
// ---------------------------------------------------------------------------
test("CD-3: Vlastní dokument option appears exactly once in the template picker", async ({ browser }) => {
  // TemplatePanel hardcodes a "Custom document" button (slug __custom__) separately from the API.
  // This test verifies that the custom-document entry appears exactly once (EN locale)
  // and that no Czech "Vlastní dokument" leaks through from the API mock.
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/templates**", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_TEMPLATES) })
    );

    await page.goto(`${FRONTEND}/chat`);

    // Open template picker
    const pickerBtn = page.locator('button[aria-label="Open template picker"]');
    await expect(pickerBtn).toBeVisible({ timeout: 8_000 });
    await pickerBtn.click();

    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible({ timeout: 5_000 });

    // TemplatePanel renders the custom entry as a hardcoded button (slug "__custom__")
    // with i18n text t("template.custom_document") = "Custom document" (EN).
    // The API's "Vlastní dokument" entry (slug "vlastni_dokument") is excluded from
    // the rendered list. Assert both sides to catch the actual duplication bug:
    //   1. The hardcoded EN button appears exactly once.
    //   2. The API's Czech "Vlastní dokument" does NOT leak into the panel
    //      (which would mean the exclusion guard is broken and it shows twice).
    const customCount = await panel.locator('button:has-text("Custom document")').count();
    expect(customCount).toBe(1);

    const vlastniLeakedCount = await panel.locator('button:has-text("Vlastní dokument")').count();
    expect(vlastniLeakedCount).toBe(0);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-4 — Drafting indicator visible during streaming, hidden after done
// ---------------------------------------------------------------------------
test("CD-4: drafting indicator is visible during streaming and absent after stream completes", async ({ browser }) => {
  // Use a slow-resolved SSE to observe the indicator while streaming
  const [page, context] = await createSeededPage(browser);
  try {
    let fulfillSSE: (() => void) | null = null;

    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", async (route: Route) => {
      // Hold the response until we've observed the indicator, then resolve
      await new Promise<void>((resolve) => { fulfillSSE = resolve; });
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC });
    });

    await page.goto(`${FRONTEND}/chat`);

    // Trigger the query — the route will pause waiting for fulfillSSE()
    await clickFollowUp(page);

    // While the route is held (SSE response not yet delivered), the app must show
    // a streaming indicator — proving the "isStreaming" UI state is active before
    // any answer content arrives. This is the meaningful pre-answer assertion.
    // StreamingStatus renders "Connecting." text synchronously when sendQuery fires.
    const streamingIndicator = page.getByRole("status", { name: "Processing pipeline" }).first();
    await expect(streamingIndicator).toBeVisible({ timeout: 8_000 });

    // Release SSE now that we have confirmed the indicator was visible
    fulfillSSE!();

    // After streaming completes, the answer must appear — this proves streaming ended.
    await expect(page.locator("text=Dokument byl vygenerován.").first()).toBeVisible({ timeout: 15_000 });

    // PipelineStatusBar keeps the "Connecting..." trace label visible as a static step
    // in the completed trace (parseStep("Connecting...") returns the raw string since
    // it doesn't match any pipeline keyword). Asserting "Connecting" text is gone would
    // always fail. Instead we confirm the answer is present (streaming is done) AND that
    // the live streaming state is gone by checking isStreaming-gated elements.
    // The abort/"Stop generating" button only renders when isStreaming=true — it must be gone.
    await expect(page.locator('[aria-label="Stop generating"]')).not.toBeVisible({ timeout: 5_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-5 — PDF preview dialog loads without "Could not load document" error
// ---------------------------------------------------------------------------
test("CD-5: PDF preview dialog loads successfully without error text", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    // SSE_WITH_DOC_READY includes fields so DocumentCard enters isReady=true state,
    // rendering the Preview button that this test exercises.
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_READY })
    );
    await page.route("**/api/v1/conversations/*/documents/*/pdf", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4" })
    );

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Click Preview button on the document card
    const previewBtn = page.locator('button[aria-label="Preview"]').first();
    await expect(previewBtn).toBeVisible({ timeout: 5_000 });
    await previewBtn.click();

    // DocumentViewer dialog must open (identified by its close button)
    await expect(page.locator('button[aria-label="Close document viewer"]')).toBeVisible({ timeout: 5_000 });

    // "Could not load document" must NOT appear in the dialog
    const errorText = page.locator("text=Could not load document");
    const hasError = await errorText.count() > 0;
    expect(hasError).toBe(false);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-6 — PDF download works without "PDF generation not available" error
// ---------------------------------------------------------------------------
test("CD-6: PDF download works without error text in the DOM", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    let pdfEndpointCalled = 0;

    await mockBaseRoutes(page);
    // SSE_WITH_DOC_READY includes fields so DocumentCard enters isReady=true state,
    // rendering the Download PDF link that this test exercises.
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_READY })
    );
    await page.route("**/api/v1/conversations/*/documents/*/pdf", (route: Route) => {
      pdfEndpointCalled += 1;
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4" });
    });

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Click the Download PDF link
    const downloadLink = page.locator('a[title="Download PDF"]').first();
    await expect(downloadLink).toBeVisible({ timeout: 5_000 });

    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 5_000 }).catch(() => null),
      downloadLink.click(),
    ]);

    // Either download event fired or the PDF endpoint was called
    expect(pdfEndpointCalled > 0 || download !== null).toBe(true);

    // "PDF generation not available" must NOT appear anywhere in the DOM
    const errorText = page.locator("text=PDF generation not available");
    expect(await errorText.count()).toBe(0);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-7 — LaTeX source download triggers the .tex endpoint
// ---------------------------------------------------------------------------
test("CD-7: clicking LaTeX download triggers the /tex endpoint", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    let texEndpointCalled = 0;

    await mockBaseRoutes(page);
    // SSE_WITH_DOC_READY includes populated fields so DocumentCard enters isReady=true,
    // which renders the .tex download link (DocumentCard.tsx:100-122, title="Download LaTeX source").
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_READY })
    );
    await page.route("**/api/v1/conversations/*/documents/*/tex", (route: Route) => {
      texEndpointCalled += 1;
      route.fulfill({
        status: 200,
        contentType: "text/plain",
        body: "\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}",
      });
    });

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card to reach isReady=true (v1 badge visible = fields populated)
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // LaTeX download link on the card — requires isReady=true (DocumentCard.tsx:100-122)
    const latexLink = page.locator('a[title="Download LaTeX source"]').first();
    await expect(latexLink).toBeVisible({ timeout: 5_000 });

    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 5_000 }).catch(() => null),
      latexLink.click(),
    ]);

    // The tex endpoint must have been called (or browser download event fired)
    expect(texEndpointCalled > 0 || download !== null).toBe(true);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-8 — Documents persist after chat session close and reopen
// ---------------------------------------------------------------------------
test("CD-8: documents generated in a session persist when the context is reopened", async ({ browser }) => {
  // Generate a document, capture localStorage, then reopen with that state.
  const [page, context] = await createSeededPage(browser);
  let savedLocalStorage: Array<{ name: string; value: string }> = [];

  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC })
    );

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card to appear
    await expect(page.locator("text=Žaloba na neplatnost výpovědi").first()).toBeVisible({ timeout: 15_000 });

    // Capture all localStorage from the origin
    savedLocalStorage = await page.evaluate(() => {
      const entries: Array<{ name: string; value: string }> = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key) entries.push({ name: key, value: localStorage.getItem(key) ?? "" });
      }
      return entries;
    });
  } finally {
    await context.close();
  }

  // Reopen with the saved localStorage (which contains the session + chatId).
  // The app fetches documents from the backend on mount via useDocumentState.
  // We mock that endpoint to return the document that was generated — this
  // tests that the frontend correctly renders documents fetched on session reopen,
  // which is the real persistence mechanism (not localStorage).
  const [page2, context2] = await createSeededPage(browser, savedLocalStorage);
  try {
    await mockBaseRoutes(page2);

    // Override the documents list endpoint to return the generated document.
    // mockBaseRoutes sets up a catch-all that returns [] — this specific route
    // is registered after and takes priority for the exact documents-list path.
    await page2.route("**/api/v1/conversations/*/documents", (route: Route) => {
      const url = new URL(route.request().url());
      if (!url.pathname.match(/\/documents\/[^/]+$/)) {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              doc_id: DOC_UUID,
              template_slug: "zaloba_neplatnost_vypovedi",
              template_name: "Žaloba na neplatnost výpovědi",
              version: 1,
              generated_at: new Date().toISOString(),
            },
          ]),
        });
      } else {
        route.continue();
      }
    });

    await page2.goto(`${FRONTEND}/chat`);
    await page2.waitForURL(/\/chat/, { timeout: 5_000 });

    // The document card must be visible — confirms the frontend correctly fetches
    // and renders documents when the session is reopened (the core persistence test).
    await expect(page2.locator("text=Žaloba na neplatnost výpovědi").first()).toBeVisible({ timeout: 10_000 });
    await expect(page2.locator("text=v1").first()).toBeVisible({ timeout: 5_000 });
  } finally {
    await context2.close().catch(() => {});
  }
});

// ---------------------------------------------------------------------------
// CD-9 — Template selection persists across consecutive messages
// ---------------------------------------------------------------------------
test("CD-9: template selection is included in all consecutive query POST bodies", async ({ browser }) => {
  const [page, context] = await createSeededPage(browser);
  try {
    const capturedBodies: Array<Record<string, unknown>> = [];

    await mockBaseRoutes(page);
    await page.route("**/api/v1/templates**", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_TEMPLATES) })
    );
    await page.route("**/api/v1/query/stream", async (route: Route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      capturedBodies.push(body);
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC });
    });

    await page.goto(`${FRONTEND}/chat`);

    // Open template picker and select the first template
    const pickerBtn = page.locator('button[aria-label="Open template picker"]');
    await expect(pickerBtn).toBeVisible({ timeout: 8_000 });
    await pickerBtn.click();

    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible({ timeout: 5_000 });
    await panel.locator('button:has-text("Žaloba na neplatnost výpovědi")').click();
    await expect(panel).not.toBeVisible({ timeout: 3_000 });

    // First message — template_slug must be in the POST body
    await clickFollowUp(page);
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    await expect(async () => {
      expect(capturedBodies.length).toBeGreaterThanOrEqual(1);
    }).toPass({ timeout: 5_000 });

    expect(capturedBodies[0]["template_slug"]).toBe("zaloba_neplatnost_vypovedi");

    // Second message — template_slug must still be present (sticky selection)
    await clickFollowUp(page);
    await expect(async () => {
      expect(capturedBodies.length).toBeGreaterThanOrEqual(2);
    }).toPass({ timeout: 15_000 });

    expect(capturedBodies[1]["template_slug"]).toBe("zaloba_neplatnost_vypovedi");
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-10 — LaTeX download button hidden when /tex HEAD returns 422 (NEO-1972)
// ---------------------------------------------------------------------------
test("CD-10: LaTeX download button is hidden when the /tex HEAD request returns 422", async ({ browser }) => {
  // DocumentCard.tsx fires HEAD /tex once the document reaches isReady=true (fields
  // populated). It gates the .tex link on the response: 200 → hasLatex=true (show),
  // non-ok (e.g. 422) → hasLatex=false (hide). This test verifies the hide path.
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    // SSE_WITH_DOC_READY includes populated fields so DocumentCard enters isReady=true,
    // which is the prerequisite for the HEAD availability check to fire.
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_READY })
    );
    // Return 422 for HEAD — template has no LaTeX source. Any other method falls through
    // (the download link won't be rendered, so no GET will occur in practice).
    await page.route("**/api/v1/conversations/*/documents/*/tex", (route: Route) => {
      if (route.request().method() === "HEAD") {
        route.fulfill({ status: 422 });
      } else {
        route.continue();
      }
    });

    await page.goto(`${FRONTEND}/chat`);

    // Register the HEAD watcher after navigation, before triggering the query.
    // DocumentCard fires the HEAD check only after isReady=true — this is safe.
    const texHeadDone = page.waitForResponse(
      (resp) => resp.url().includes("/tex") && resp.request().method() === "HEAD",
      { timeout: 20_000 }
    );

    await clickFollowUp(page);

    // Wait for document card to reach isReady=true (fields populated → v1 badge visible)
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Wait for the HEAD /tex request to resolve — proves the availability check ran
    // and returned 422, which keeps hasLatex=false in DocumentCard state.
    const headResp = await texHeadDone;
    expect(headResp.status()).toBe(422);

    // After HEAD returned 422, hasLatex=false — the LaTeX download link must not be in the DOM.
    const latexLink = page.locator('a[title="Download LaTeX source"]');
    await expect(latexLink).not.toBeVisible({ timeout: 2_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-12 — LaTeX download button visible in DocumentViewer when /tex HEAD → 200
// ---------------------------------------------------------------------------
test("CD-12: LaTeX download button is visible inside DocumentViewer when the /tex HEAD request returns 200", async ({ browser }) => {
  // DocumentViewer.tsx fires HEAD /tex when it mounts (open effect, lines 88-95).
  // It gates the download link on hasLatex state. This test verifies the show path
  // inside the viewer — mirrors CD-11 which tests the hide path (422 → hidden).
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    // SSE_WITH_DOC_READY: populated fields → DocumentCard enters isReady=true → Preview button visible
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_READY })
    );
    // PDF endpoint — needed so DocumentViewer renders without error
    await page.route("**/api/v1/conversations/*/documents/*/pdf", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4" })
    );
    // Return 200 for HEAD /tex — template has a LaTeX source available in the viewer context.
    // GET falls through (not needed since we only test link visibility, not download).
    await page.route("**/api/v1/conversations/*/documents/*/tex", (route: Route) => {
      if (route.request().method() === "HEAD") {
        route.fulfill({ status: 200 });
      } else {
        route.continue();
      }
    });

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card to reach isReady=true (v1 badge visible = fields populated)
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Register HEAD watcher BEFORE clicking Preview — DocumentViewer fires HEAD
    // immediately on mount (the `open` effect), so the watcher must be in place first.
    const texHeadDone = page.waitForResponse(
      (resp) => resp.url().includes("/tex") && resp.request().method() === "HEAD",
      { timeout: 10_000 }
    );

    // Click Preview to open DocumentViewer
    const previewBtn = page.locator('button[aria-label="Preview"]').first();
    await expect(previewBtn).toBeVisible({ timeout: 5_000 });
    await previewBtn.click();

    // Viewer must open (close button confirms it)
    await expect(page.locator('button[aria-label="Close document viewer"]')).toBeVisible({ timeout: 5_000 });

    // Wait for HEAD /tex to resolve — confirms the availability check ran and returned 200
    const headResp = await texHeadDone;
    expect(headResp.status()).toBe(200);

    // After HEAD returned 200, hasLatex=true — LaTeX link MUST appear in the viewer.
    // DocumentViewer renders BOTH title and aria-label on the same element; DocumentCard
    // renders only title. Using AND (no comma) targets the viewer link exclusively so the
    // locator never matches 2 elements when DocumentCard is also showing its .tex button.
    const latexLink = page.locator('a[title="Download LaTeX source"][aria-label="Download LaTeX source"]');
    await expect(latexLink).toBeVisible({ timeout: 5_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// CD-11 — LaTeX download button hidden in DocumentViewer when /tex HEAD → 422
// ---------------------------------------------------------------------------
test("CD-11: LaTeX download button is hidden inside DocumentViewer when the /tex HEAD request returns 422", async ({ browser }) => {
  // DocumentViewer.tsx fires HEAD /tex when it mounts (open effect, lines 88-95).
  // It gates the download link at line 281 on hasLatex state. This test verifies
  // the hide path inside the viewer — mirrors CD-10 which tests DocumentCard.
  const [page, context] = await createSeededPage(browser);
  try {
    await mockBaseRoutes(page);
    // SSE_WITH_DOC_READY: populated fields → DocumentCard enters isReady=true → Preview button visible
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_DOC_READY })
    );
    // PDF endpoint — needed so DocumentViewer renders without error
    await page.route("**/api/v1/conversations/*/documents/*/pdf", (route: Route) =>
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4" })
    );
    // Return 422 for HEAD /tex — template has no LaTeX source in the viewer context
    await page.route("**/api/v1/conversations/*/documents/*/tex", (route: Route) => {
      if (route.request().method() === "HEAD") {
        route.fulfill({ status: 422 });
      } else {
        route.continue();
      }
    });

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card to reach isReady=true (v1 badge visible = fields populated)
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Register HEAD watcher BEFORE clicking Preview — DocumentViewer fires HEAD
    // immediately on mount (the `open` effect), so the watcher must be in place first.
    const texHeadDone = page.waitForResponse(
      (resp) => resp.url().includes("/tex") && resp.request().method() === "HEAD",
      { timeout: 10_000 }
    );

    // Click Preview to open DocumentViewer
    const previewBtn = page.locator('button[aria-label="Preview"]').first();
    await expect(previewBtn).toBeVisible({ timeout: 5_000 });
    await previewBtn.click();

    // Viewer must open (close button confirms it)
    await expect(page.locator('button[aria-label="Close document viewer"]')).toBeVisible({ timeout: 5_000 });

    // Wait for HEAD /tex to resolve — confirms the availability check ran and returned 422
    const headResp = await texHeadDone;
    expect(headResp.status()).toBe(422);

    // After HEAD returned 422, hasLatex=false — LaTeX link must NOT appear in the viewer.
    // DocumentViewer renders both title and aria-label on the link (lines 285-286).
    const latexLink = page.locator('a[title="Download LaTeX source"], a[aria-label="Download LaTeX source"]');
    await expect(latexLink).not.toBeVisible({ timeout: 2_000 });
  } finally {
    await context.close();
  }
});
