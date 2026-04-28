#!/usr/bin/env bash
# setup-github-runner.sh
# One-time setup: downloads, configures, and installs the GitHub Actions
# self-hosted runner as a persistent launchd service on macOS.
#
# Usage:
#   GITHUB_TOKEN=<registration-token> bash scripts/setup-github-runner.sh
#
# The registration token is a short-lived token from:
#   GitHub → neonsecret/vitreon-legal → Settings → Actions → Runners → New self-hosted runner
# It looks like: AXXXXXXXXXXXXXXXXXXXXXXXXXX  (starts with 'A', expires in 1h)
#
# Required GitHub Secrets (set in repo Settings → Secrets → Actions):
#   TELEGRAM_BOT_TOKEN  — Telegram bot token from @BotFather
#   TELEGRAM_CHAT_ID    — Chat/user ID to receive alerts (get via @userinfobot)
#
# After running this script, set branch protection:
#   gh api repos/neonsecret/vitreon-legal/branches/product/protection \
#     -X PUT \
#     -f required_status_checks[strict]=true \
#     -f "required_status_checks[contexts][]=E2E Full Suite" \
#     -f enforce_admins=false \
#     -f "required_pull_request_reviews=null" \
#     -f "restrictions=null"

set -euo pipefail

RUNNER_DIR="${HOME}/actions-runner"
RUNNER_VERSION="2.322.0"
REPO_URL="https://github.com/neonsecret/vitreon-legal"
RUNNER_NAME="mac-vitreon"
RUNNER_LABELS="mac-vitreon,self-hosted,macOS"

# Registration token is required
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "ERROR: GITHUB_TOKEN env var must be set to the runner registration token."
  echo "Get it from: ${REPO_URL}/settings/actions/runners/new"
  exit 1
fi

echo "=== Setting up GitHub Actions runner ==="
echo "Runner: ${RUNNER_NAME}  Labels: ${RUNNER_LABELS}"
echo "Target dir: ${RUNNER_DIR}"
echo ""

# ── 1. Download runner ─────────────────────────────────────────────────────
mkdir -p "${RUNNER_DIR}"
cd "${RUNNER_DIR}"

ARCH=$(uname -m)
if [[ "${ARCH}" == "arm64" ]]; then
  RUNNER_PKG="actions-runner-osx-arm64-${RUNNER_VERSION}.tar.gz"
else
  RUNNER_PKG="actions-runner-osx-x64-${RUNNER_VERSION}.tar.gz"
fi

if [[ -f "${RUNNER_DIR}/config.sh" ]]; then
  echo "Runner binary already present — skipping download."
else
  echo "Downloading ${RUNNER_PKG}..."
  curl -sfL \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_PKG}" \
    -o "${RUNNER_PKG}"
  tar -xzf "${RUNNER_PKG}"
  rm "${RUNNER_PKG}"
  echo "Runner extracted to ${RUNNER_DIR}"
fi

# ── 2. Configure runner ────────────────────────────────────────────────────
if [[ -f "${RUNNER_DIR}/.runner" ]]; then
  echo "Runner already configured — skipping config."
else
  echo "Configuring runner..."
  "${RUNNER_DIR}/config.sh" \
    --url "${REPO_URL}" \
    --token "${GITHUB_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --work "_work" \
    --unattended \
    --replace
  echo "Runner configured."
fi

# ── 3. Install as launchd service (survives reboots) ──────────────────────
echo "Installing runner as launchd service..."
cd "${RUNNER_DIR}"
./svc.sh install
./svc.sh start

PLIST_LABEL="actions.runner.neonsecret-vitreon-legal.${RUNNER_NAME}"
echo ""
echo "=== Done ==="
echo "Runner '${RUNNER_NAME}' is running as a launchd service."
echo ""
echo "Manage with:"
echo "  ${RUNNER_DIR}/svc.sh status  — check status"
echo "  ${RUNNER_DIR}/svc.sh stop    — stop runner"
echo "  ${RUNNER_DIR}/svc.sh start   — start runner"
echo "  launchctl list | grep ${PLIST_LABEL}"
echo ""
echo "Logs: ~/Library/Logs/${PLIST_LABEL}.log"
echo ""
echo "=== Next steps ==="
echo "1. Verify runner appears online at: ${REPO_URL}/settings/actions/runners"
echo "2. Set GitHub Secrets (repo Settings → Secrets → Actions):"
echo "     TELEGRAM_BOT_TOKEN=<your-bot-token>"
echo "     TELEGRAM_CHAT_ID=<your-chat-id>"
echo "3. Enable branch protection (requires GITHUB_PAT with repo admin):"
echo "   gh api repos/neonsecret/vitreon-legal/branches/product/protection \\"
echo "     -X PUT \\"
echo "     -f required_status_checks[strict]=true \\"
echo "     --field 'required_status_checks[contexts][]=E2E Full Suite' \\"
echo "     -f enforce_admins=false \\"
echo "     --field 'required_pull_request_reviews=null' \\"
echo "     --field 'restrictions=null'"
echo ""
echo "4. Push a commit to 'product' to trigger the first CI run and verify all steps."
