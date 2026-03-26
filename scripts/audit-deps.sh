#!/usr/bin/env bash
# audit-deps.sh — scan Python dependencies for known vulnerabilities.
#
# Uses pip-audit (PyPI Advisory Database) for Python packages.
# Optionally runs npm audit for frontend dependencies if a frontend/
# package.json is present.
#
# Usage:
#   bash scripts/audit-deps.sh               # full audit
#   bash scripts/audit-deps.sh --python-only # skip npm audit
#   bash scripts/audit-deps.sh --fix         # attempt auto-fix (pip-audit --fix)
#
# Exit codes:
#   0 — no vulnerabilities found
#   1 — vulnerabilities found or audit tool unavailable
#
# Setup (run once):
#   pip install pip-audit
#
# CI integration:
#   Add this script to your CI pipeline as a required check.
#   Consider running weekly even if no code changes (new CVEs are published daily).

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

PYTHON_ONLY=false
AUTO_FIX=false
for arg in "$@"; do
    case "$arg" in
        --python-only) PYTHON_ONLY=true ;;
        --fix) AUTO_FIX=true ;;
    esac
done

OVERALL_EXIT=0

# ---------------------------------------------------------------------------
# Python dependency audit
# ---------------------------------------------------------------------------
echo "========================================"
echo "Python Dependency Audit (pip-audit)"
echo "========================================"
echo ""

if ! command -v pip-audit >/dev/null 2>&1; then
    echo "ERROR: pip-audit is not installed."
    echo "Install it with: pip install pip-audit"
    echo ""
    echo "pip-audit scans installed packages against the PyPI Advisory Database (OSV)."
    echo "It detects known CVEs and provides remediation guidance."
    exit 1
fi

PIP_AUDIT_FLAGS="--desc on --format columns"
if $AUTO_FIX; then
    PIP_AUDIT_FLAGS="$PIP_AUDIT_FLAGS --fix"
fi

echo "Running: pip-audit $PIP_AUDIT_FLAGS"
echo ""

if pip-audit $PIP_AUDIT_FLAGS 2>&1; then
    echo ""
    echo "Python audit: PASS — no vulnerabilities found"
else
    PY_EXIT=$?
    echo ""
    echo "Python audit: FAIL — see findings above (exit code $PY_EXIT)"
    echo ""
    echo "Remediation steps:"
    echo "  1. Review each finding: assess CVSS score and whether the vulnerable code path"
    echo "     is reachable in this application"
    echo "  2. For CVSS >= 7.0 (High/Critical): treat as P2 incident, patch immediately"
    echo "  3. For CVSS < 7.0 (Low/Medium): patch in next sprint"
    echo "  4. To auto-upgrade: bash scripts/audit-deps.sh --fix"
    echo "  5. Run tests after patching: python -m pytest tests/neolex/ -v"
    OVERALL_EXIT=1
fi

# ---------------------------------------------------------------------------
# npm / frontend dependency audit
# ---------------------------------------------------------------------------
if ! $PYTHON_ONLY; then
    echo ""
    echo "========================================"
    echo "Frontend Dependency Audit (npm audit)"
    echo "========================================"
    echo ""

    FRONTEND_DIR="$ROOT/frontend"
    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        echo "No frontend/package.json found — skipping npm audit"
        echo "(This is expected if the frontend has not been initialized)"
    elif ! command -v npm >/dev/null 2>&1; then
        echo "WARNING: npm is not installed — cannot audit frontend dependencies"
        echo "Install Node.js from https://nodejs.org to enable frontend audit"
    else
        echo "Running: npm audit --audit-level=moderate"
        echo ""
        cd "$FRONTEND_DIR"
        if npm audit --audit-level=moderate 2>&1; then
            echo ""
            echo "npm audit: PASS"
        else
            NPM_EXIT=$?
            echo ""
            echo "npm audit: FAIL — see findings above (exit code $NPM_EXIT)"
            echo ""
            echo "Remediation:"
            echo "  npm audit fix            # auto-fix non-breaking updates"
            echo "  npm audit fix --force    # force upgrades (may break things — test first)"
            OVERALL_EXIT=1
        fi
        cd "$ROOT"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
if [ "$OVERALL_EXIT" -eq 0 ]; then
    echo "audit-deps: PASS — all checks clean"
else
    echo "audit-deps: FAIL — review findings above"
    echo ""
    echo "Document known vulnerabilities and their status in:"
    echo "  docs/security/dependency-vulnerabilities.md"
fi
echo "========================================"
exit $OVERALL_EXIT
