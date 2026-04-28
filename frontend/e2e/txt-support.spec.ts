/**
 * E2E tests for TXT corpus support — NEO-2095 (NEO-2091-A)
 *
 * Covers:
 *   TXT-1  Upload zone accepts .txt files — file input has correct accept attr and backend is called
 *   TXT-2  Upload zone rejects unsupported file type with local validation error
 *   TXT-3  Source viewer for TXT source does not request the PDF endpoint (source_type path)
 *   TXT-4  Citation strip shows L.N label for TXT sources, not p.N (source_type path)
 *
 * Run: npx playwright test e2e/txt-support.spec.ts
 */
import { test, expect, type Page, type BrowserContext, type Route, type Browser } from "playwright/test";
import * as path from "path";
import * as os from "os";
import * as fs from "fs";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FRONTEND = `http://localhost:${process.env.CI_PORT ?? "3000"}`;

const SEED_UID = "e2e-user-id";
const SEED_SESSION_ID = "e2e-session-00000001";

const MOCK_USER = {
  id: "e2e-user-id",
  email: "testuser@vitreon.app",
  name: "E2E Tester",
  avatar_url: null,
  plan: "pro",
  subscription_status: "active",
  monthly_queries_used: 0,
  max_corpora: 5,
};

/** Valid UUID — must pass the UUID guard in use-query-stream.ts */
const TXT_DOC_UUID = "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e";

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------

function sseBody(events: Array<{ event: string; data: object }>): string {
  return events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
}

/** SSE response with a TXT source using source_type="txt" — matches real backend output.
 *  The source text is populated so TextSourceViewer can render it without a chunk API call. */
const SSE_WITH_TXT_SOURCE = sseBody([
  {
    event: "answer",
    data: {
      answer: "The legislation is referenced in section 42 [DOC-1] of the statute.",
      sources: [
        {
          doc_id: TXT_DOC_UUID,
          title: "Custom TXT Statute",
          page_numbers: [42],
          text: "Section 42. Every person shall comply with the applicable regulations.",
          source_type: "txt",
        },
      ],
      confidence: 0.9,
    },
  },
  { event: "done", data: {} },
]);

/** SSE response with a document_generated event for a TXT file.
 *  template_name ends in ".txt" so DocumentViewer's isTxt detection triggers.
 *  Used by TXT-5 to verify the correct /api/v1/documents/{id}/txt endpoint is called. */
const SSE_WITH_TXT_DOC_GENERATED = sseBody([
  { event: "answer", data: { answer: "The statute document has been generated.", sources: [], confidence: 0.9 } },
  {
    event: "document_generated",
    data: {
      doc_id: TXT_DOC_UUID,
      template_slug: "txt_statute",
      template_name: "statute.txt",
      version: 1,
      fields: { section: "42" },
    },
  },
  { event: "done", data: {} },
]);

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function buildStorageState() {
  const session = {
    id: SEED_SESSION_ID,
    title: "E2E TXT Setup",
    messages: [
      { id: "u-setup", role: "user", content: "Setup." },
      {
        id: "a-setup",
        role: "assistant",
        content: "Setup answer.",
        sources: [],
        confidence: null,
      },
    ],
    createdAt: Date.now() - 120_000,
    lastMessageAt: Date.now() - 60_000,
    corpora: ["difc"],
  };
  return {
    cookies: [] as Array<{
      name: string; value: string; domain: string; path: string;
      expires: number; httpOnly: boolean; secure: boolean; sameSite: "Lax" | "None" | "Strict";
    }>,
    origins: [
      {
        origin: FRONTEND,
        localStorage: [
          { name: "neolex_uid", value: SEED_UID },
          { name: `neolex_chat_sessions_${SEED_UID}`, value: JSON.stringify([session]) },
          { name: `neolex_current_session_${SEED_UID}`, value: SEED_SESSION_ID },
          { name: "neolex_jurisdiction", value: "difc" },
        ],
      },
    ],
  };
}

async function createSeededPage(browser: Browser): Promise<[Page, BrowserContext]> {
  const context = await browser.newContext({ storageState: buildStorageState() });
  const page = await context.newPage();
  return [page, context];
}

async function mockBaseRoutes(page: Page) {
  await page.route("**/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_USER) })
  );
  // Health endpoint — consumed by IndexInfoPanel on all app pages
  await page.route("**/health", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ pipeline_ready: true, status: "ok" }) })
  );
  // Corpora listing — called by chat page when custom jurisdiction is selected
  await page.route("**/api/v1/corpora", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ corpora: [] }) })
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

async function mockDocumentsPage(page: Page) {
  await page.route("**/api/v1/documents", (route: Route) => {
    if (route.request().method() === "GET") {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ documents: [] }) });
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
// TXT-1 — Upload zone accepts .txt files
// ---------------------------------------------------------------------------
test("TXT-1: upload zone accepts a .txt file and calls the backend upload endpoint", async ({ browser }) => {
  // The upload zone's file input must accept text/plain and the backend must be called
  // when a valid .txt file is selected. This proves end-to-end: accept attr → validation → POST.
  const [page, context] = await createSeededPage(browser);
  let uploadCalled = false;

  try {
    await mockBaseRoutes(page);
    await mockDocumentsPage(page);

    // Mock the document upload endpoint (POST /api/v1/documents) — return a minimal success response.
    // Note: the upload route is registered AFTER mockDocumentsPage so it takes precedence (Playwright LIFO).
    // We check the method to let GETs fall through to the mockDocumentsPage handler.
    await page.route("**/api/v1/documents", (route: Route) => {
      if (route.request().method() === "POST") {
        uploadCalled = true;
        route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            doc_id: TXT_DOC_UUID,
            filename: "statute.txt",
            size_bytes: 42,
            upload_ts: new Date().toISOString(),
            indexed: false,
            collection: "My Documents",
            media_type: "text/plain",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.goto(`${FRONTEND}/documents`);

    // Write a temporary .txt file on disk so setInputFiles has a real path
    const tmpFile = path.join(os.tmpdir(), "e2e-statute.txt");
    fs.writeFileSync(tmpFile, "Section 1. This is a test statute.\n");

    // The hidden file input — upload zone renders one with accept attr
    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached({ timeout: 10_000 });

    // Verify accept attribute includes .txt and text/plain
    const acceptAttr = await fileInput.getAttribute("accept");
    expect(acceptAttr).toContain(".txt");
    expect(acceptAttr).toContain("text/plain");

    // Upload the .txt file via setInputFiles — triggers the onChange handler
    await fileInput.setInputFiles(tmpFile);

    // Backend upload endpoint must be called — confirms the file passed local validation
    // and the upload request was sent. Use a polling assertion to give the async fetch time.
    await expect(async () => {
      expect(uploadCalled).toBe(true);
    }).toPass({ timeout: 10_000 });

    // Cleanup temp file
    fs.unlinkSync(tmpFile);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// TXT-2 — Upload zone rejects unsupported file types with validation error
// ---------------------------------------------------------------------------
test("TXT-2: upload zone rejects an unsupported file type and shows a validation error", async ({ browser }) => {
  // Uploading a .docx file (not PDF/TXT/ZIP) must trigger the local validation error
  // immediately, without hitting the backend. The error message must appear in the UI.
  const [page, context] = await createSeededPage(browser);

  try {
    await mockBaseRoutes(page);
    await mockDocumentsPage(page);

    await page.goto(`${FRONTEND}/documents`);

    // Write a temporary .docx file
    const tmpFile = path.join(os.tmpdir(), "e2e-unsupported.docx");
    fs.writeFileSync(tmpFile, "PK\x03\x04fake docx content");

    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached({ timeout: 10_000 });

    // Trigger setInputFiles with an unsupported MIME — the browser will pass it,
    // but the local validate() guard will reject it based on extension + MIME type.
    await fileInput.setInputFiles({
      name: "unsupported.docx",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: Buffer.from("fake docx content"),
    });

    // The validation error must appear — upload-zone sets validationError state
    // when !isPdf && !isTxt && !isZip. The error renders as an overlay inside the drop zone.
    const errorEl = page.locator("text=/only|PDF|TXT|ZIP/i").first();
    await expect(errorEl).toBeVisible({ timeout: 5_000 });

    fs.unlinkSync(tmpFile);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// TXT-3 — Source viewer for TXT source does not request the PDF endpoint
// ---------------------------------------------------------------------------
test("TXT-3: TXT source in grounding view does not trigger a PDF endpoint request", async ({ browser }) => {
  // For TXT sources (source_type="txt"), TextSourceViewer must skip PdfViewerWithFallback.
  // The PDF endpoint for the TXT doc_id must never be called — even if the chunk-context API
  // returns pdf_available=true. This test verifies the isTxtSource() gate via source_type path.
  const [page, context] = await createSeededPage(browser);
  const pdfRequests: string[] = [];

  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_TXT_SOURCE })
    );

    // Capture any PDF requests — there must be none for the TXT document
    await page.route("**/api/v1/documents/*/pdf", (route: Route) => {
      pdfRequests.push(route.request().url());
      // Fulfill normally so the test doesn't hang if an unexpected PDF request fires
      route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.0" });
    });

    // Mock chunk-context to simulate pdf_available=true — this lets us verify the TXT gate
    // blocks the PDF viewer even when the API claims a PDF exists.
    await page.route("**/api/v1/documents/chunk-context/**", (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          pdf_available: true,
          chunks: [
            {
              chunk_id: "chunk-001",
              text: "Section 42. Every person shall comply with the applicable regulations.",
              page: 42,
              is_target: true,
            },
          ],
        }),
      })
    );

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for the answer with a citation marker
    const sup = page.locator("sup").first();
    await expect(sup).toBeVisible({ timeout: 15_000 });
    await sup.click();

    // Wait briefly to allow any potential PDF requests to fire
    await page.waitForTimeout(2_000);

    // No PDF request should have been made for the TXT document
    const txtPdfRequests = pdfRequests.filter(url => url.includes(TXT_DOC_UUID));
    expect(txtPdfRequests).toHaveLength(0);
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// TXT-4 — Citation strip shows L.N label for TXT sources
// ---------------------------------------------------------------------------
test("TXT-4: citation pill for a TXT source shows L.N label instead of p.N", async ({ browser }) => {
  // SourceCitationCard renders `L.{page}` instead of `p.{page}` when isTxtSource() is true.
  // With source_type="txt" and page_numbers=[42], the pill must read "L.42".
  const [page, context] = await createSeededPage(browser);

  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_TXT_SOURCE })
    );
    // Block PDF requests so the viewer doesn't stall
    await page.route("**/api/v1/documents/*/pdf", (route: Route) =>
      route.fulfill({ status: 404 })
    );

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for the citation <sup> to appear — confirms sources were received
    const sup = page.locator("sup").first();
    await expect(sup).toBeVisible({ timeout: 15_000 });
    await sup.click();

    // After opening the grounding panel, the sources strip renders citation pills.
    // For a TXT source with page_numbers=[42], the pill text must be "L.42", not "p.42".
    const lineLabel = page.locator("text=L.42").first();
    await expect(lineLabel).toBeVisible({ timeout: 8_000 });

    // Confirm the old PDF-style label is absent
    const pageLabel = page.locator("text=p.42").first();
    await expect(pageLabel).not.toBeVisible({ timeout: 2_000 });
  } finally {
    await context.close();
  }
});

// ---------------------------------------------------------------------------
// TXT-5 — DocumentViewer fetches TXT via /api/v1/documents/{id}/txt (not conversations path)
// ---------------------------------------------------------------------------
test("TXT-5: DocumentViewer for a TXT document fetches from /api/v1/documents/{id}/txt, not the conversations path", async ({ browser }) => {
  // Regression guard for NEO-2149: DocumentViewer.tsx previously built txtUrl as
  //   /api/v1/conversations/{chatId}/documents/{docId}/txt  (404 — endpoint does not exist)
  // The correct endpoint is:
  //   /api/v1/documents/{docId}/txt
  // This test opens the viewer for a .txt-named document and asserts the correct URL is hit.
  const [page, context] = await createSeededPage(browser);
  const txtRequests: string[] = [];

  try {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/query/stream", (route: Route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_WITH_TXT_DOC_GENERATED })
    );

    // Intercept TXT fetch — correct endpoint is /api/v1/documents/*/txt (no "conversations" segment)
    await page.route("**/api/v1/documents/*/txt", (route: Route) => {
      txtRequests.push(route.request().url());
      route.fulfill({ status: 200, contentType: "text/plain", body: "Section 42. Every person shall comply with the applicable regulations." });
    });

    // Intercept the wrong conversations path — must never be called after the fix
    const wrongPathRequests: string[] = [];
    await page.route("**/api/v1/conversations/*/documents/*/txt", (route: Route) => {
      wrongPathRequests.push(route.request().url());
      route.fulfill({ status: 404, body: "Not Found" });
    });

    await page.goto(`${FRONTEND}/chat`);
    await clickFollowUp(page);

    // Wait for document card to enter isReady=true state (v1 badge appears when fields are set)
    await expect(page.locator("text=v1").first()).toBeVisible({ timeout: 15_000 });

    // Click Preview to open DocumentViewer
    const previewBtn = page.locator('button[aria-label="Preview"]').first();
    await expect(previewBtn).toBeVisible({ timeout: 5_000 });
    await previewBtn.click();

    // Viewer must open (close button confirms the dialog is mounted)
    await expect(page.locator('button[aria-label="Close document viewer"]')).toBeVisible({ timeout: 5_000 });

    // Wait for the TXT fetch to fire — DocumentViewer's useEffect triggers on open+isTxt
    await expect(async () => {
      expect(txtRequests.length).toBeGreaterThan(0);
    }).toPass({ timeout: 10_000 });

    // The correct endpoint must be called
    expect(txtRequests[0]).toContain(`/api/v1/documents/${TXT_DOC_UUID}/txt`);
    expect(txtRequests[0]).not.toContain("conversations");

    // The wrong conversations path must never have been called
    expect(wrongPathRequests).toHaveLength(0);
  } finally {
    await context.close();
  }
});
