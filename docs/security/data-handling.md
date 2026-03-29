# NeoLex Data Handling

**Version:** 1.0
**Date:** 2026-03-26
**Owner:** Engineering

---

## Overview

This document describes how client data flows through NeoLex, where it is stored, and
what protections are in place. NeoLex processes legal documents and queries on behalf of
law firm clients.

---

## Data Classification

| Data Type              | Classification | Examples                                  |
|------------------------|----------------|-------------------------------------------|
| Client query text      | Confidential   | "What are the damages limits under..."    |
| LLM answer text        | Confidential   | Generated answers referencing client docs |
| Uploaded documents     | Confidential   | Client-uploaded PDFs                      |
| API keys (hash only)   | Restricted     | SHA-256 digest stored in DB               |
| Audit log metadata     | Internal       | IPs, timestamps, key prefixes             |
| Health check responses | Public         | Status strings, no client data            |

---

## Data Flow

```
Client Application
    |
    | HTTPS (Tailscale Funnel or TLS termination)
    v
Next.js Frontend (port 3000)
    |
    | Internal HTTP (localhost)
    v
FastAPI Backend (port 8000)
    |
    |-- Auth: API key validated against SQLite (neolex.db)
    |-- Audit: Query + metadata written to SQLite (neolex.db)
    |
    |-- Document Storage: data/clients/<slug>/docs/<doc_id>.pdf
    |-- Index Storage: data/clients/<slug>/ (FAISS index, BM25 pickle)
    |
    v
arlc/ Pipeline
    |
    | HTTPS (Anthropic API or LiteLLM proxy)
    v
Claude API (claude-sonnet-4-6)
    |
    | Answer text returned
    v
FastAPI → Audit log → Client response
```

---

## Data at Rest

### SQLite Audit Database (`neolex.db`)

- **Location:** Configured via `NEOLEX_DB_PATH` (default: `neolex.db` in working directory)
- **Tables:**
    - `queries`: question, answer_text, sources_json, key_hash, ip, user_agent, timestamps
    - `events`: event_type, detail_json, key_hash, ip, user_agent, timestamps
    - `api_keys`: key_hash (SHA-256), key_prefix (8 chars), client_slug, scope, active
    - `documents`: doc_id, filename, size_bytes, upload_ts, indexed status
    - `reindex_jobs`: job status and progress
- **WAL mode:** Enabled for concurrent read safety
- **Encryption at rest:** Not enabled at v1 — SQLite file is protected by filesystem
  permissions. For production: encrypt the database volume or use SQLCipher.
- **Retention:** Configurable via `AUDIT_LOG_RETENTION_DAYS` (default: 365 days).
  See `neolex/compliance/retention.py`.

### Uploaded Documents

- **Location:** `data/clients/<slug>/docs/<doc_id>.pdf`
- **Access control:** Filesystem path includes client slug; cross-client access prevented
  at API level by slug enforcement in all document endpoints
- **Encryption at rest:** Not enabled at v1. For production: encrypt the `data/` volume.

### FAISS/BM25 Indexes

- **Location:** `data/` (shared corpus) or `data/clients/<slug>/` (per-client indexes)
- **Content:** Embeddings derived from document text — no raw plaintext stored
- **Reconstruction:** Indexes can be rebuilt from source PDFs via the reindex pipeline

---

## Data in Transit

- **Client to backend:** HTTPS via Tailscale Funnel (mutual TLS) in production.
  In development: plain HTTP on localhost (acceptable for non-production).
- **Backend to Claude API:** HTTPS. Anthropic API keys are read from `.env` and never
  committed to source control.
- **LiteLLM proxy:** If using an internal proxy, traffic is HTTPS over Tailscale network.

---

## Data Sent to LLM Provider

The following data is sent to the Claude API (Anthropic) per query:

1. **Retrieved document pages** (text chunks from FAISS/BM25 retrieval)
2. **Client question** (verbatim)
3. **System prompt** (static, contains no client data)

**What is NOT sent to Anthropic:**

- API keys
- Client identity (client_slug, key names)
- Previously logged queries or answers
- Document filenames or metadata

Anthropic's data processing agreement applies. Review the Anthropic API Terms of Service
for data retention and privacy commitments before processing regulated data.

---

## Data Sent to Logging/Monitoring

NeoLex logs to stdout in JSON or human-readable format (configurable via `LOG_FORMAT`).
Log lines include:

- Request method and path
- Response status code and duration
- Request ID (UUID, for correlation)
- Client IP address
- Error messages (no answer text in error logs)

**Answer text is NOT logged to stdout.** Only the `queries` table in the audit DB
contains answer text.

---

## Data Minimization

- API keys are never stored in plaintext — only SHA-256 hashes
- Key prefix (8 chars) is stored for audit attribution — insufficient to reconstruct key
- Log lines contain request IDs, not full answers
- Uploaded documents are stored only in `data/clients/<slug>/docs/` — not echoed
  in log output

---

## Backups and Disaster Recovery

At v1, no automated backup is configured. For production:

1. Add scheduled SQLite backup: `sqlite3 neolex.db ".backup neolex-backup-$(date +%Y%m%d).db"`
2. Back up `data/` directory (documents + indexes)
3. Store backups off-machine (S3, Backblaze, etc.)
4. Test restore procedure quarterly

---

## Data Deletion

- **Per-document deletion:** `DELETE /api/v1/documents/{doc_id}` removes the file from
  `data/clients/<slug>/docs/` and the row from the `documents` table. The associated
  `upload` and `delete` events remain in the audit log (append-only).
- **Audit log entries:** Not deleted in normal operation. Automated purging is available
  via `neolex/compliance/retention.py` (blocked during SOC 2 observation period).
- **API keys:** Never hard-deleted. Revocation sets `active=0`; hash and metadata are
  retained in the audit trail.

---

## Known Gaps (to address before production)

1. SQLite database and document storage are not encrypted at rest
2. No automated backup configured
3. No data loss prevention (DLP) scanning on uploaded documents
4. Anthropic DPA / sub-processor agreement not yet formalized
5. No geographic data residency controls (data processed where server runs)
