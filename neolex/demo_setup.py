"""Demo setup helper.

Creates a demo API key in neolex.db if one does not already exist.
Prints the plaintext key to stdout (captured by Makefile demo target).

Usage:
    DEMO_MODE=true python -m neolex.demo_setup
"""
import asyncio
import os
import sys

from neolex.auth.keys import generate_key, hash_key, key_prefix as get_prefix
from neolex.db.audit import get_audit_db

DEMO_KEY_NAME = "demo"
DEMO_CLIENT_SLUG = "demo"
DEMO_SCOPE = "admin"


async def ensure_demo_key() -> str | None:
    """Create a demo key if none exists. Returns the plaintext key or None."""
    async with get_audit_db() as db:
        await db.init_schema()
        rows = await db.list_keys()

    # Check if demo key already exists
    for row in rows:
        r = dict(row)
        if r.get("name") == DEMO_KEY_NAME and r.get("active"):
            # Key exists — don't print it again (we don't store plaintext)
            return None

    # Create a fresh demo key
    raw_key = generate_key()
    k_hash = hash_key(raw_key)
    k_prefix = get_prefix(raw_key)

    async with get_audit_db() as db:
        await db.init_schema()
        await db.create_key(
            name=DEMO_KEY_NAME,
            key_hash=k_hash,
            key_prefix=k_prefix,
            client_slug=DEMO_CLIENT_SLUG,
            scope=DEMO_SCOPE,
        )

    return raw_key


async def main() -> None:
    if os.environ.get("DEMO_MODE", "").lower() not in ("1", "true", "yes"):
        print("DEMO_MODE not set — skipping demo key creation.", file=sys.stderr)
        sys.exit(0)

    key = await ensure_demo_key()
    if key:
        # Print ONLY the raw key to stdout so Makefile can capture it
        print(key, end="")
    # If key already existed, print nothing — Makefile handles the message


if __name__ == "__main__":
    asyncio.run(main())
