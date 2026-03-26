#!/usr/bin/env bash
# dev.sh — Start NeoLex backend + frontend in development mode (hot-reload).
#
# Unlike serve.sh this does NOT start Tailscale Funnel.
# Suitable for local development.
#
# Usage:
#   ./scripts/dev.sh          (or: make dev)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
NEOLEX_PORT="${NEOLEX_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

_reset="\033[0m"
_green="\033[32m"
_yellow="\033[33m"
_cyan="\033[36m"

info()    { echo -e "${_green}[dev]${_reset} $*"; }
warn()    { echo -e "${_yellow}[dev]${_reset} $*"; }
section() { echo -e "\n${_cyan}=== $* ===${_reset}"; }

PIDS=()
cleanup() {
    section "Shutting down"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    info "All processes stopped."
}
trap cleanup SIGINT SIGTERM EXIT

section "Starting NeoLex backend (dev / hot-reload)"
cd "${PROJECT_ROOT}"
uv run uvicorn neolex.main:app \
    --host 0.0.0.0 \
    --port "${NEOLEX_PORT}" \
    --reload \
    --log-level info &
BACKEND_PID=$!
PIDS+=("$BACKEND_PID")
info "Backend PID ${BACKEND_PID} — http://localhost:${NEOLEX_PORT}"

info "Waiting for backend..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${NEOLEX_PORT}/health/live" &>/dev/null; then
        info "Backend is live"
        break
    fi
    sleep 1
done

section "Starting Next.js frontend (dev)"
cd "${FRONTEND_DIR}"
NEXT_PUBLIC_API_URL="http://localhost:${NEOLEX_PORT}" \
npm run dev -- --port "${FRONTEND_PORT}" &
FRONTEND_PID=$!
PIDS+=("$FRONTEND_PID")
info "Frontend PID ${FRONTEND_PID} — http://localhost:${FRONTEND_PORT}"

section "NeoLex dev stack running"
echo ""
echo "  Backend:   http://localhost:${NEOLEX_PORT}"
echo "  Frontend:  http://localhost:${FRONTEND_PORT}"
echo "  API docs:  http://localhost:${NEOLEX_PORT}/docs"
echo ""
echo "  Press Ctrl-C to stop."
echo ""

wait "${BACKEND_PID}"
