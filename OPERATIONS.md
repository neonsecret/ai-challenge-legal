# Vitreon Legal — Operations Guide

## Services (launchd — auto-restart, auto-start on login)

All three processes run as macOS launchd services:

```bash
# Restart a service
launchctl stop app.vitreon.backend && launchctl start app.vitreon.backend
launchctl stop app.vitreon.frontend && launchctl start app.vitreon.frontend
launchctl stop app.vitreon.tunnel && launchctl start app.vitreon.tunnel

# Check status
launchctl list | grep vitreon

# View logs
tail -f /tmp/vitreon-backend.log
tail -f /tmp/vitreon-frontend.log
tail -f /tmp/vitreon-tunnel.log

# Full restart after code changes
launchctl stop app.vitreon.frontend
launchctl stop app.vitreon.backend
cd /Users/viacheslavivannikov/projects/ai-challenge-legal/frontend && npx next build
launchctl start app.vitreon.backend
sleep 12
launchctl start app.vitreon.frontend
```

## Manual Start (if launchd not set up)

```bash
cd /Users/viacheslavivannikov/projects/ai-challenge-legal

# 1. Backend (FastAPI) — must start from project root
python3 -m uvicorn neolex.main:app --host 0.0.0.0 --port 8000 &

# 2. Frontend (Next.js)
cd frontend && npm run start -- -p 3000 &

# 3. Cloudflare Tunnel (public access)
cloudflared tunnel run --token eyJhIjoiODk4M2Y3NjYyMDIzOGIxZTMzODYwOWRiOGJmNmI3NDciLCJ0IjoiZWZiY2YwZTItMzkxNC00MDNkLWE0NDItZGZmN2Q1NmRmMzBkIiwicyI6Ik0yWTBNR0kzWXpndE1qWXhaaTAwWkRNMExXSXpOVGN0WkRsbE5XRTRNelpoTm1WaSJ9 &
```

## URLs

| Service      | Local                        | Public                         |
|--------------|------------------------------|--------------------------------|
| Frontend     | http://localhost:3000        | https://vitreon.app            |
| Backend API  | http://localhost:8000        | https://api.vitreon.app        |
| Health check | http://localhost:8000/health | https://api.vitreon.app/health |
| LAN access   | http://192.168.0.150:3000    | —                              |

## Kill Everything

```bash
pkill -f "uvicorn neolex" 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
pkill -f cloudflared 2>/dev/null
```

## Rebuild Frontend (after code changes)

```bash
cd frontend
npm run build    # must pass with 0 errors
# then restart:
lsof -ti:3000 | xargs kill -9 2>/dev/null
npm run start -- -p 3000 &
```

## Admin CLI

```bash
cd /Users/viacheslavivannikov/projects/ai-challenge-legal

# Create API key
python3 -m neolex.admin keys-create --name "Client Name" --client-slug client-co --scope admin

# List keys
python3 -m neolex.admin keys-list

# Revoke key
python3 -m neolex.admin keys-revoke <prefix>

# View audit log
python3 -m neolex.admin show-log --limit 20
```

## Infrastructure

| Component          | Location                      | Details                          |
|--------------------|-------------------------------|----------------------------------|
| Backend + Frontend | Mac (local)                   | Python 3.13, Node 22             |
| Embedding server   | RTX 3070 (100.98.171.97:8088) | llama-server, Qwen3-8B-Q4_K_M    |
| PostgreSQL         | Mac (local, localhost:5432)   | vitreon_legal DB, local only     |
| Cloudflare Tunnel  | Mac (local)                   | Routes vitreon.app → localhost   |
| Domain             | Cloudflare                    | vitreon.app ($14.20/yr)          |

## Environment (.env)

All config in `.env` at project root. Auto-loaded by backend. Key vars:

```
DATABASE_URL=postgresql+asyncpg://vitreon:...@localhost:5432/vitreon_legal
LLAMA_SERVER_URL=http://100.98.171.97:8088
EMBEDDING_MODEL=llama-server
FAISS_INDEX_PATH=data/faiss_llama-server.bin
ALLOWED_ORIGINS=https://vitreon.app,http://localhost:3000,http://192.168.0.150:3000
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
RESEND_API_KEY=...
JWT_SECRET_KEY=...
```

## Remote Machine (RTX 3070)

```bash
ssh neon@100.98.171.97

# llama-server
~/llama.cpp/build/bin/llama-server \
  -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \
  --embedding --pooling last -ngl 99 -c 16384 --port 8088 &

# PostgreSQL is on local Mac (localhost:5432), not on this machine
```

## FAISS Indexes

| Index | File                        | Vectors | Dim  | Corpus        |
|-------|-----------------------------|---------|------|---------------|
| DIFC  | data/faiss_llama-server.bin | 26,947  | 4096 | 303 DIFC PDFs |
| Czech | data/faiss_czech.bin        | 5,056   | 4096 | 5 Czech codes (section-aware) |

## Troubleshooting

**Backend won't start**: Check you're in project root, not `frontend/`.

**"No module named neolex"**: Wrong working directory. `cd` to project root.

**CORS errors**: Restart backend (loads ALLOWED_ORIGINS from .env on startup).

**Embedding hangs**: llama-server on remote is either down or busy. Check: `curl http://100.98.171.97:8088/health`

**Cloudflare 502**: Tunnel is up but backend is down. Restart backend.

**API key invalid**: Create a new one with `python3 -m neolex.admin keys-create ...`
