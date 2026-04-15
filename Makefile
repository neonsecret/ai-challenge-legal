.PHONY: setup lint test run index prepare demo dev serve logs

# Install dependencies
setup:
	uv sync

# Lint with ruff
lint:
	uv run ruff check .

# Run tests
test:
	uv run pytest tests/ -v

# Run all tests (backend + frontend unit + frontend E2E)
# Note: E2E tests require dev server running on port 3000
test-all:
	@echo "=== Running Backend Tests ==="
	uv run pytest tests/ -v --tb=short || true
	@echo ""
	@echo "=== Running Frontend Unit Tests ==="
	cd frontend && npm test
	@echo ""
	@echo "=== Running Frontend E2E Tests ==="
	@echo "Note: Ensure dev server is running (npm run dev in frontend/)"
	cd frontend && npx playwright test --reporter=list || true

# Prepare corpus (download + index)
prepare:
	uv run python -m arlc.indexing.prepare_corpus

# Build indexes only (skip download)
index:
	uv run python -m arlc.indexing.builders.case_metadata
	uv run python -m arlc.indexing.builders.law_index
	uv run python -m arlc.indexing.builders.article_index
	uv run python -m arlc.indexing.indexer

# Run the pipeline
run:
	uv run python run.py --workers 5 --output output/run1

# ---------------------------------------------------------------------------
# Vitreon Legal server targets
# ---------------------------------------------------------------------------

# Start backend + frontend for development (hot-reload)
dev:
	@echo "Starting Vitreon Legal in development mode..."
	@./scripts/dev.sh

# Start production stack with Tailscale Funnel
serve:
	@echo "Starting Vitreon Legal production stack..."
	@./scripts/serve.sh

# Tail Vitreon Legal logs
logs:
	@tail -f logs/neolex.log 2>/dev/null || echo "No log file found at logs/neolex.log"

# ---------------------------------------------------------------------------
# Demo target — one command to run the full demo
# ---------------------------------------------------------------------------

# demo: Start the full Vitreon Legal demo in one command.
#   - Installs Python dependencies (uv sync)
#   - Installs frontend dependencies (npm install)
#   - Creates a demo API key if none exists (stored in neolex.db)
#   - Starts backend on port 8000
#   - Starts frontend on port 3000
#   - Opens http://localhost:3000 in the default browser
#
# Prerequisites: uv, node/npm installed. .env with LLM credentials.
demo:
	@echo ""
	@echo "=== Vitreon Legal Demo Setup ==="
	@echo ""
	@echo "[1/5] Installing Python dependencies..."
	@uv sync --quiet
	@echo "[2/5] Installing frontend dependencies..."
	@cd frontend && npm install --silent
	@echo "[3/5] Creating demo API key (if needed)..."
	@DEMO_KEY=$$(DEMO_MODE=true uv run python -m neolex.demo_setup 2>/dev/null); \
	 if [ -n "$$DEMO_KEY" ]; then \
	   echo "      Demo key: $$DEMO_KEY"; \
	   echo "$$DEMO_KEY" > .demo_key; \
	 else \
	   echo "      Demo key already exists or setup skipped."; \
	 fi
	@echo "[4/5] Starting Vitreon Legal backend (port 8000)..."
	@DEMO_MODE=true uv run uvicorn neolex.main:app --host 0.0.0.0 --port 8000 --log-level warning & \
	 BACKEND_PID=$$!; \
	 echo "      Backend PID: $$BACKEND_PID"; \
	 echo "$$BACKEND_PID" > .backend_pid
	@echo "      Waiting for backend to be ready..."
	@for i in $$(seq 1 30); do \
	   if curl -sf http://localhost:8000/health/live >/dev/null 2>&1; then \
	     echo "      Backend is live."; break; \
	   fi; \
	   sleep 1; \
	 done
	@echo "[5/5] Starting Vitreon Legal frontend (port 3000)..."
	@cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 NEXT_PUBLIC_DEMO_MODE=true npm run dev -- --port 3000 & \
	 echo $$! > ../.frontend_pid
	@echo ""
	@echo "=== Vitreon Legal is starting up ==="
	@echo ""
	@echo "  Backend:   http://localhost:8000"
	@echo "  Frontend:  http://localhost:3000"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo ""
	@echo "  Opening browser in 5 seconds..."
	@sleep 5
	@open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || echo "  Open http://localhost:3000 in your browser."
	@echo ""
	@echo "  Press Ctrl-C or run 'make demo-stop' to stop all processes."
	@wait

# Stop demo processes
demo-stop:
	@echo "Stopping Vitreon Legal demo..."
	@if [ -f .backend_pid ]; then \
	   kill $$(cat .backend_pid) 2>/dev/null || true; \
	   rm -f .backend_pid; \
	 fi
	@if [ -f .frontend_pid ]; then \
	   kill $$(cat .frontend_pid) 2>/dev/null || true; \
	   rm -f .frontend_pid; \
	 fi
	@pkill -f "uvicorn neolex.main" 2>/dev/null || true
	@pkill -f "next dev" 2>/dev/null || true
	@echo "Done."
