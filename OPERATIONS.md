# Vitreon Legal — Operations Guide

## Services (launchd)

5 services, all auto-restart + auto-start on login:

```bash
# Check all services
launchctl list | grep vitreon

# Restart a service
launchctl stop app.vitreon.backend && launchctl start app.vitreon.backend

# View logs
tail -f /tmp/vitreon-backend.log
tail -f /tmp/vitreon-frontend.log
tail -f /tmp/vitreon-reranker.log

# Full deploy after code changes
launchctl stop app.vitreon.backend
launchctl stop app.vitreon.frontend
cd frontend && npx next build
launchctl start app.vitreon.backend
sleep 65  # wait for warmup
launchctl start app.vitreon.frontend
```

### Service Ports

| Service | Port | Plist | Log |
|---------|------|-------|-----|
| Backend (FastAPI) | 8000 | app.vitreon.backend | /tmp/vitreon-backend.log |
| Frontend (Next.js) | 3000 | app.vitreon.frontend | /tmp/vitreon-frontend.log |
| Embedding (llama-server) | 8088 | app.vitreon.llama | — |
| Reranker (llama-server) | 8089 | app.vitreon.reranker | /tmp/vitreon-reranker.log |
| Cloudflare Tunnel | — | app.vitreon.tunnel | /tmp/vitreon-tunnel.log |

## URLs

| Service | Local | Public |
|---------|-------|--------|
| Frontend | http://localhost:3000 | https://vitreon.app |
| Backend API | http://localhost:8000 | https://api.vitreon.app |
| Health check | http://localhost:8000/health | https://api.vitreon.app/health |

## Admin CLI

```bash
# List users
python3 -m neolex.admin list-users

# View audit log
python3 -m neolex.admin show-log --limit 20

# Delete user (via Python)
python3 -c "
from dotenv import load_dotenv; load_dotenv()
import asyncio
from sqlalchemy import delete
from neolex.db.postgres import AsyncSessionLocal
from neolex.db.models import User
import uuid
async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.id == uuid.UUID('USER_ID_HERE')))
        await db.commit()
asyncio.run(main())
"
```

## Infrastructure

| Component | Location | Details |
|-----------|----------|---------|
| Backend + Frontend | Mac (local) | Python 3.13, Node 22 |
| Embedding server | Mac:8088 (primary: RTX 3070:8088) | llama-server, Qwen3-8B-Q4_K_M |
| Reranker server | Mac:8089 (primary: RTX 3070:8089) | llama-server, Qwen3-Reranker-0.6B-Q8_0 |
| PostgreSQL | Mac localhost:5432 | vitreon_legal DB |
| Cloudflare Tunnel | Mac | vitreon.app → :3000, api.vitreon.app → :8000 |
| Domain | Cloudflare | vitreon.app ($14.20/yr) |

## RTX 3070 (100.98.171.97, optional)

When online, serves as primary for embedding + reranking (auto-detected every 30s).

```bash
ssh root@100.98.171.97

# Embedding server (already running via nohup usually)
nohup /home/neon/llama.cpp/build/bin/llama-server \
  -m /home/neon/ai-challenge-legal-new/models/Qwen3-Embedding-8B-Q4_K_M.gguf \
  --embedding --pooling last -ngl 99 -c 4096 --port 8088 --host 0.0.0.0 &

# Reranker server
nohup /home/neon/llama.cpp/build/bin/llama-server \
  -m /home/neon/ai-challenge-legal-new/models/qwen3-reranker-0.6b-q8_0.gguf \
  --reranking -ngl 99 -c 4096 -ub 4096 --port 8089 --host 0.0.0.0 &
```

## Environment (.env)

Key variables (all in `.env` at project root):

```
DATABASE_URL=postgresql+asyncpg://vitreon:...@localhost:5432/vitreon_legal
LLAMA_SERVER_URL=http://localhost:8088
LLAMA_SERVER_REMOTE_URL=http://100.98.171.97:8088
RERANKER_SERVER_URL=http://100.98.171.97:8089
RERANKER_LOCAL_URL=http://localhost:8089
EMBEDDING_MODEL=llama-server
LLM_BACKEND=vertex
VERTEX_PROJECT_ID=gcp-rhl-claude-api-3654
VERTEX_LOCATION=us-east5
ALLOWED_ORIGINS=https://vitreon.app,http://localhost:3000,http://192.168.0.150:3000
JWT_SECRET_KEY=...  (REQUIRED — server won't start without it)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
RESEND_API_KEY=...
ADMIN_EMAILS=admin@vitreon.app  (comma-separated, restricts /admin endpoints)
```

## Agent Configuration

All in `arlc/agent/config.py`, overridable via env vars:

| Config | Default | Env Var |
|--------|---------|---------|
| LLM model (answer) | claude-sonnet-4-6 | AGENT_LLM_MODEL |
| LLM model (first round) | claude-haiku-4-5 | AGENT_LLM_MODEL_FAST |
| Max searches/turn | 5 | AGENT_MAX_SEARCHES |
| Max accumulated docs | 10 | AGENT_MAX_DOCS |
| Max history messages | 10 | AGENT_MAX_HISTORY |
| Search results per call | 3 | AGENT_SEARCH_TOP_K |
| Web search enabled | true | AGENT_WEB_SEARCH_ENABLED |
| Web search max results | 3 | AGENT_WEB_SEARCH_MAX |

## Pricing

| Plan | Price | Daily Limit | Corpora |
|------|-------|-------------|---------|
| Free | $0 | 3/day | — |
| Starter | $29/mo | 30/day | 2 |
| Pro | $179/mo | 200/day | 5 |
| Enterprise | $499/mo | unlimited | 20 |

## Czech Corpus (11 laws)

To add a new law: edit `scripts/download_czech_law.py`, add the law ID, run:
```bash
python3 scripts/download_czech_law.py
python3 scripts/chunk_czech_corpus.py
LLAMA_SERVER_URL=http://100.98.171.97:8088 EMBEDDING_MODEL=llama-server \
  python3 -m neolex.embeddings.build_index --corpus data/corpus/czech/ --output data/faiss_czech.bin
```

## Security Checklist

- [x] CSRF: X-Requested-With header on all mutating requests
- [x] Auth: HttpOnly SameSite=Lax cookies, bcrypt hashing
- [x] Session cleanup: hourly expiry of stale sessions/tokens
- [x] Rate limiting: per-user daily query limits + brute-force protection
- [x] Admin: restricted to ADMIN_EMAILS
- [x] Stripe: webhook signature + idempotency (LRU dedup)
- [x] CSP, X-Frame-Options, nosniff, strict Referrer-Policy
- [x] Input validation on all user inputs (regex whitelists)
- [x] Model name masked in API responses
- [x] User-scoped localStorage (no cross-account leaks)
- [x] Logout clears all local session data
- [x] Prompt injection defense in agent system prompt
- [x] Path traversal validation on FAISS corpus loader
- [x] Fire-and-forget tasks log exceptions via done callbacks

## GDPR Compliance

- Privacy Policy: `/privacy` page (full Article 13/14 disclosures)
- Data export: `GET /auth/my-data` (Article 20 — data portability)
- Data retention: conversations 90 days, sessions 30 days (hourly auto-cleanup)
- Right to erasure: user deletion cascades all data
- Third parties: Anthropic (Vertex AI), Stripe, Google OAuth — all disclosed
- Contact: privacy@vitreon.app

## Accuracy Benchmarks (March 2026)

| Corpus | Answer Accuracy | Citation Rate |
|--------|----------------|---------------|
| DIFC | 100% | 100% |
| Czech | 100% | 100% |

Run benchmarks: `python3 scripts/benchmark_accuracy.py`
