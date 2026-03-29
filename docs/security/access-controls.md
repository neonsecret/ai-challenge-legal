# NeoLex Access Controls

**Version:** 1.0
**Date:** 2026-03-26
**Owner:** Engineering

---

## Overview

NeoLex uses API key-based authentication for all data-access endpoints. Every request
must present a valid key via the `Authorization: Bearer <key>` header (or `?api_key=<key>`
query parameter for SSE connections). There is no session-based auth, no cookies, and no
OAuth at v1.

---

## API Key Design

### Key Generation

Keys are generated with `secrets.token_urlsafe(32)` — 43 URL-safe base64 characters
providing approximately 256 bits of entropy. This exceeds NIST SP 800-63B requirements
for machine-generated credentials.

### Storage

- **Database:** Only the SHA-256 hex digest of the key is stored in `api_keys` table.
- **Plaintext:** The plaintext key is displayed **once** on creation and never stored.
- **Comparison:** Key verification uses `hmac.compare_digest` for constant-time
  comparison to prevent timing side-channel attacks.

### Key Prefixes

The first 8 characters of the raw key are stored as `key_prefix` for audit log
attribution. This prefix is insufficient to reconstruct the full key.

---

## Key Scopes

| Scope   | Access                                                                                |
|---------|---------------------------------------------------------------------------------------|
| `query` | `POST /api/v1/query`, `GET /api/v1/query/stream`, `GET/POST/DELETE /api/v1/documents` |
| `admin` | All of the above + `GET /api/v1/admin/audit`                                          |

Admin-scoped keys are created with `python -m neolex.admin keys create --name "..." --scope admin`.

### Scope Enforcement

- `get_api_key()` dependency validates the key exists in the DB and `active=1`.
- `get_admin_key()` chains on `get_api_key()` and additionally checks `scope == 'admin'`.
- Query-scoped key accessing admin endpoint returns HTTP 403.
- Missing or invalid key returns HTTP 401.

---

## Client Isolation (Multi-tenancy)

Each API key maps to a `client_slug`. All data queries, document uploads, and document
listings are scoped to the key's `client_slug`:

- Documents are stored in `data/clients/<slug>/docs/`
- Document list endpoint only returns documents for the authenticated client's slug
- Delete and reindex endpoints enforce slug ownership (404 if cross-client access attempted)
- Queries run against the client's private FAISS/BM25 index (when per-client indexing is enabled)

---

## Rate Limiting

Rate limiting is configurable via the `RATE_LIMIT_RPM` environment variable (default: 60
requests per minute). State is tracked in-process per key hash using a sliding window counter.

**Important:** In-process rate limiting is correct for single-process deployments. If
multiple uvicorn workers are used in a future phase, this must move to a Redis or SQLite
counter to prevent per-process windows undermining the limit.

---

## Unauthenticated Endpoints

The following endpoints are intentionally exempt from API key authentication:

| Endpoint                  | Reason                                                   |
|---------------------------|----------------------------------------------------------|
| `GET /health`             | Liveness check — safe to expose for load balancer probes |
| `GET /health/live`        | Same as above                                            |
| `GET /health/ready`       | Readiness check — no data access                         |
| `GET /api/v1/demo/config` | Demo mode metadata — no sensitive data                   |

---

## Auth Failure Logging

Every authentication failure is appended to the `events` table with:

- `event_type`: `"auth_failure"`
- `detail_json`: `{"reason": "missing_key"}` or `{"reason": "invalid_key", "key_prefix": "..."}`
- `ip`: Client IP address
- `user_agent`: Client user-agent string

Auth failure events are committed **before** the HTTP 401 is raised (the context manager
pattern ensures the DB write is not rolled back by the exception).

---

## Key Lifecycle

```
Admin: python -m neolex.admin keys create --name "Al Tamimi POC"
       -> prints plaintext key once, stores SHA-256 hash in DB

Admin: python -m neolex.admin keys list
       -> shows: id, name, key_prefix, client_slug, scope, active, created_at, last_used

Admin: python -m neolex.admin keys revoke <key_prefix>
       -> sets active=0 in DB; key_hash row is retained for audit history
```

Keys are never hard-deleted. Revoked keys (`active=0`) are rejected by `get_api_key()`
and the rejection is logged as `auth_failure`.

---

## Admin Audit Endpoint

`GET /api/v1/admin/audit` (requires admin scope):

- Returns paginated `queries` or `events` table entries
- Query params: `table` (queries|events), `limit` (1-200), `offset`
- All audit data is immutable — no delete or update methods exposed on log tables

---

## Environment Variables

| Variable          | Default                                       | Description                         |
|-------------------|-----------------------------------------------|-------------------------------------|
| `RATE_LIMIT_RPM`  | `60`                                          | Max requests per minute per API key |
| `NEOLEX_DB_PATH`  | `neolex.db`                                   | SQLite audit DB path                |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8000` | CORS allowed origins                |
| `DEMO_MODE`       | `false`                                       | Enable demo key pre-seeding         |
