# E2E Auth Tests — Setup Guide

## Running the tests

```bash
# Start the dev server first (or set TEST_START_SERVER=1 to auto-start)
npm run dev

# In another terminal
npm run test:e2e
```

## Auth strategy

The E2E suite deliberately avoids real login credentials so every scenario
runs in CI without any secrets.

### Scenarios 1–3 (mocked backend)

Routes are intercepted with Playwright's `page.route` — no real backend
session is ever created.

### Scenarios 4 & 5 (mocked session)

These scenarios (session persistence and logout) also use `page.route` to
mock `**/auth/me` and `**/auth/logout`:

- **`/auth/me`** returns `200` with a `MOCK_USER` payload while the
  simulated session is active, and `401` after logout.
- **`/auth/logout`** returns `200` and flips the mock state so that the
  next `/auth/me` call returns `401`.

No `E2E_TEST_PASSWORD` is required. The guard previously present has been
removed.

**Why this is safe:** The chat page (`/chat`) calls `/auth/me` on mount and
redirects to `/` on a `401`. Reaching `/chat` and passing `waitForURL`
therefore confirms the mock is actually being honoured — the test cannot
silently pass if the interceptor is not set up correctly.

## Optional: real-credential smoke test

If you want to run a full round-trip against a live backend (e.g. on a
staging environment), set:

```bash
export E2E_TEST_EMAIL=your@email.com
export E2E_TEST_PASSWORD=yourpassword
```

The `apiLogin` helper in `auth.spec.ts` supports this but is not called by
any currently active scenario. Add new credential-based scenarios there if
needed.
