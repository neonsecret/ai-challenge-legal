#!/usr/bin/env bash
# serve.sh — Start the full NeoLex stack and expose it via Tailscale Funnel.
#
# What this script does:
#   1. Starts uvicorn (NeoLex API) on port 8000
#   2. Starts Next.js dev server on port 3000
#   3. Runs `tailscale funnel 3000` to expose the frontend worldwide
#   4. Traps SIGINT (Ctrl-C) and SIGTERM to shut down all child processes cleanly
#
# Prerequisites:
#   - Python env with neolex installed (or run from project root)
#   - Node.js + npm installed
#   - Tailscale installed and authenticated (`tailscale status` should show connected)
#   - .env file in project root with LLM credentials
#
# Usage:
#   cd /path/to/ai-challenge-legal
#   ./scripts/serve.sh
#
# Environment variables:
#   NEOLEX_PORT     API port (default: 8000)
#   FRONTEND_PORT   Next.js port (default: 3000)
#   LOG_FORMAT      "json" | "human" (default: human when TTY)
#   LOG_LEVEL       Python log level (default: INFO)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NEOLEX_PORT="${NEOLEX_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_reset="\033[0m"
_green="\033[32m"
_yellow="\033[33m"
_red="\033[31m"
_cyan="\033[36m"

info()    { echo -e "${_green}[serve]${_reset} $*"; }
warn()    { echo -e "${_yellow}[serve]${_reset} $*"; }
error()   { echo -e "${_red}[serve]${_reset} $*" >&2; }
section() { echo -e "\n${_cyan}=== $* ===${_reset}"; }

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

section "Checking prerequisites"

if ! command -v tailscale &>/dev/null; then
    error "tailscale not found. Install from https://tailscale.com/download"
    exit 1
fi

if ! tailscale status &>/dev/null; then
    error "Tailscale is not connected. Run: tailscale up"
    exit 1
fi

if ! command -v node &>/dev/null; then
    warn "node not found — skipping Next.js frontend startup"
    SKIP_FRONTEND=1
else
    SKIP_FRONTEND=0
fi

if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
    warn ".env not found at ${PROJECT_ROOT}/.env — LLM calls may fail"
fi

# ---------------------------------------------------------------------------
# Process tracking
# ---------------------------------------------------------------------------

PIDS=()

cleanup() {
    section "Shutting down"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            info "Stopping PID $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done
    # Stop Tailscale Funnel (idempotent)
    tailscale funnel --bg reset 2>/dev/null || true
    info "All processes stopped."
}

trap cleanup SIGINT SIGTERM EXIT

# ---------------------------------------------------------------------------
# 1. Start uvicorn (NeoLex API)
# ---------------------------------------------------------------------------

section "Starting NeoLex API (port ${NEOLEX_PORT})"

cd "${PROJECT_ROOT}"
uvicorn neolex.main:app \
    --host 0.0.0.0 \
    --port "${NEOLEX_PORT}" \
    --log-level info \
    --no-access-log \
    &
NEOLEX_PID=$!
PIDS+=("$NEOLEX_PID")
info "uvicorn started (PID ${NEOLEX_PID})"

# Wait for API to be ready before starting frontend (avoids client connection errors on load).
info "Waiting for API to be ready..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${NEOLEX_PORT}/health/live" &>/dev/null; then
        info "API is live"
        break
    fi
    if [[ $i -eq 30 ]]; then
        warn "API did not become ready in 30s — continuing anyway"
    fi
    sleep 1
done

# ---------------------------------------------------------------------------
# 2. Start Next.js frontend
# ---------------------------------------------------------------------------

if [[ "${SKIP_FRONTEND}" -eq 0 ]] && [[ -d "${FRONTEND_DIR}" ]]; then
    section "Starting Next.js frontend (port ${FRONTEND_PORT})"
    cd "${FRONTEND_DIR}"
    NEXT_PUBLIC_API_URL="http://localhost:${NEOLEX_PORT}" \
    npm run dev -- --port "${FRONTEND_PORT}" &
    FRONTEND_PID=$!
    PIDS+=("$FRONTEND_PID")
    info "Next.js started (PID ${FRONTEND_PID})"
    cd "${PROJECT_ROOT}"
else
    warn "Skipping frontend (not found or node missing)"
    FRONTEND_PID=""
fi

# ---------------------------------------------------------------------------
# 3. Start Tailscale Funnel on the frontend port
#    If the frontend isn't running, funnel the API directly.
# ---------------------------------------------------------------------------

section "Starting Tailscale Funnel"

if [[ -n "${FRONTEND_PID}" ]]; then
    FUNNEL_PORT="${FRONTEND_PORT}"
    info "Funnelling frontend (port ${FUNNEL_PORT}) worldwide"
else
    FUNNEL_PORT="${NEOLEX_PORT}"
    info "No frontend — funnelling API directly (port ${FUNNEL_PORT})"
fi

tailscale funnel --bg "${FUNNEL_PORT}"
FUNNEL_URL=$(tailscale funnel status 2>/dev/null | grep -oE 'https://[^ ]+' | head -1 || echo "unknown")
info "Tailscale Funnel URL: ${FUNNEL_URL}"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

section "NeoLex stack is running"
echo ""
echo "  API (local):   http://localhost:${NEOLEX_PORT}"
echo "  Health:        http://localhost:${NEOLEX_PORT}/health"
echo "  Health live:   http://localhost:${NEOLEX_PORT}/health/live"
echo "  Health ready:  http://localhost:${NEOLEX_PORT}/health/ready"
if [[ -n "${FRONTEND_PID}" ]]; then
    echo "  Frontend:      http://localhost:${FRONTEND_PORT}"
fi
echo "  Public URL:    ${FUNNEL_URL}"
echo ""
echo "  Press Ctrl-C to stop all processes."
echo ""

# ---------------------------------------------------------------------------
# Wait for any child to exit
# ---------------------------------------------------------------------------

wait "${NEOLEX_PID}"
