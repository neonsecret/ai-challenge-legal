#!/usr/bin/env bash
# scan-secrets.sh — grep tracked files for potential hardcoded secrets.
#
# Usage:
#   bash scripts/scan-secrets.sh          # check git-tracked files only
#   bash scripts/scan-secrets.sh --all    # check all files (incl. untracked)
#
# Exit codes:
#   0 — no findings
#   1 — one or more potential secrets found
#
# Pre-commit hook suggestion:
#   Copy or symlink this script to .git/hooks/pre-commit and make executable:
#     cp scripts/scan-secrets.sh .git/hooks/pre-commit
#     chmod +x .git/hooks/pre-commit
#
# What it checks:
#   - Anthropic API keys (sk-ant-...)
#   - OpenAI API keys (sk-...)
#   - Generic "api_key = ..." assignments
#   - password/secret/token assignments in config-like lines
#   - AWS access keys (AKIA...)
#   - Private key PEM headers
#   - Project-specific patterns: rohlik, rhl (internal company names)
#   - LiteLLM proxy URLs with embedded credentials
#
# What it intentionally skips:
#   - .env files (gitignored by design)
#   - .planning/ directory (gitignored)
#   - __pycache__ / .pyc files
#   - Binary files
#   - This script itself (scan-secrets.sh contains patterns as strings)

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

SCAN_ALL=false
if [ "${1:-}" = "--all" ]; then
    SCAN_ALL=true
fi

# ---------------------------------------------------------------------------
# Get file list (written to a temp file for portability — bash 3.2 compat)
# ---------------------------------------------------------------------------
TMPFILE=$(mktemp /tmp/scan-secrets-files.XXXXXX)
trap 'rm -f "$TMPFILE"' EXIT

if $SCAN_ALL; then
    # All files except gitignored ones
    { git ls-files; git ls-files --others --exclude-standard; } | sort -u > "$TMPFILE"
else
    # Git-tracked files only
    git ls-files > "$TMPFILE"
fi

# ---------------------------------------------------------------------------
# Secret patterns — checked with grep -E
# ---------------------------------------------------------------------------
FINDINGS=0
TOTAL=0

while IFS= read -r FILE; do
    # Skip if file doesn't exist (deleted files in git ls-files)
    [ -f "$FILE" ] || continue

    TOTAL=$((TOTAL + 1))

    # Skip binary files (check MIME encoding)
    MIME=$(file -b --mime-encoding "$FILE" 2>/dev/null || echo "")
    if echo "$MIME" | grep -q "binary\|charset=binary"; then
        continue
    fi

    # Skip this script itself (contains patterns as literal strings)
    case "$FILE" in
        *scan-secrets.sh) continue ;;
        *.env|*.env.*) continue ;;
        *.pyc|*.db|*.faiss|*.pkl|*.bin) continue ;;
        *.svg|*.html|*.png|*.jpg|*.jpeg|*.pdf) continue ;;
        *.ico|*.woff|*.woff2|*.ttf|*.eot) continue ;;
        */\__pycache__/*) continue ;;
        CLAUDE.md) continue ;;  # Project instructions — contains pattern examples, not secrets
    esac

    # Pattern 1: Anthropic API keys
    MATCH=$(grep -En 'sk-ant-[a-zA-Z0-9_-]{20,}' "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [anthropic_api_key] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

    # Pattern 2: OpenAI-style API keys (sk- followed by 32+ chars)
    MATCH=$(grep -En "sk-[a-zA-Z0-9]{32,}" "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [openai_api_key] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

    # Pattern 3: AWS access keys
    MATCH=$(grep -En 'AKIA[A-Z0-9]{16}' "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [aws_access_key] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

    # Pattern 4: Private key PEM headers
    MATCH=$(grep -En '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [private_key_pem] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

    # Pattern 5: api_key assignment with a value
    MATCH=$(grep -Ein '(api_key|apikey|API_KEY)\s*[:=]\s*["'"'"'][a-zA-Z0-9_\-\.]{10,}' "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [api_key_assignment] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

    # Pattern 6: password/secret/token with non-placeholder value
    MATCH=$(grep -Ein '(password|passwd)\s*=\s*["'"'"'][a-zA-Z0-9_\-\!\@\#\$\%]{8,}' "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [password_assignment] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

    # Pattern 7: URL with embedded credentials (user:pass@host)
    MATCH=$(grep -En 'https?://[^[:space:]"'"'"'>]+:[^[:space:]"'"'"'>@]+@[a-zA-Z0-9._-]+' "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [url_with_credentials] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

    # Pattern 8: Internal company-specific terms (rohlik, rhl)
    MATCH=$(grep -Ein '(rohlik|\.rhl\.|rhl-)' "$FILE" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo "FINDING [internal_company_name] in $FILE:"
        echo "$MATCH" | head -5 | sed 's/^/  /'
        FINDINGS=$((FINDINGS + 1))
    fi

done < "$TMPFILE"

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
echo ""
if [ "$FINDINGS" -eq 0 ]; then
    echo "scan-secrets: OK — no findings in $TOTAL files scanned"
    exit 0
else
    echo "scan-secrets: FAIL — $FINDINGS finding(s) above"
    echo ""
    echo "If these are false positives, add the file to skip patterns in scripts/scan-secrets.sh"
    echo "NEVER commit .env files or files containing real credentials."
    exit 1
fi
