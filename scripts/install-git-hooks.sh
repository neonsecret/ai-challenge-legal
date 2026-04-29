#!/usr/bin/env bash
# install-git-hooks.sh — Wire up the local pre-push enforcement hook.
#
# Run once after cloning, or re-run idempotently at any time.
#
# Usage:
#   bash scripts/install-git-hooks.sh

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="${REPO_ROOT}/.githooks"

if [[ ! -d "$HOOKS_DIR" ]]; then
    echo "Error: .githooks/ directory not found at ${HOOKS_DIR}" >&2
    exit 1
fi

# Point git at the version-controlled hooks directory (idempotent)
git -C "${REPO_ROOT}" config core.hooksPath .githooks

# Ensure all hooks are executable
chmod +x "${HOOKS_DIR}"/*

echo "✅ Git hooks installed from .githooks/"
echo "   pre-commit : ruff + bandit (pre-commit framework)"
echo "   pre-push   : @smoke suite gate on product branch"
echo ""
echo "To bypass in an emergency: git push --no-verify"
echo "To uninstall:              git config --unset core.hooksPath"
