# Local Product-Branch Enforcement

GitHub Pro branch protection is not available for private repos on the Free plan.
This setup replicates the same safety guarantee — blocking broken pushes to `product` — via a client-side git hook.

## What it does

- **`pre-commit`** — runs `ruff` (lint + format) and `bandit` (security scan) on every commit via the [pre-commit framework](https://pre-commit.com). Same checks as before; this hook just moves them into the version-controlled `.githooks/` directory.
- **`pre-push`** — on any push to `refs/heads/product`, runs the full `@smoke` Playwright suite against the already-running server on `:3000`. Push is blocked if any test fails. Feature-branch pushes are unaffected (hook exits in < 50 ms).

## Installation

Run once after cloning (or re-run at any time — idempotent):

```bash
bash scripts/install-git-hooks.sh
```

This sets `core.hooksPath = .githooks` and `chmod +x`s the hooks.

## Telegram alerts

When a push to `product` is blocked, the hook sends a Telegram message if both variables are present in `.env`:

```
TELEGRAM_BOT_TOKEN=<bot token>
TELEGRAM_CHAT_ID=<your chat id>
```

If either variable is absent the hook still blocks the push — it just doesn't alert. The alert is non-fatal: a network failure cannot allow a bad push through.

## Bypassing in an emergency

```bash
git push --no-verify
```

Use only when smoke failures are a known flake and you have verified correctness by other means.

## Uninstalling

```bash
git config --unset core.hooksPath
```

This restores git to using `.git/hooks/` (the default). The `.githooks/` files remain in the repo.
