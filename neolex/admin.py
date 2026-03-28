"""Vitreon Legal admin CLI.

Usage:
    python -m neolex.admin keys-create --name "Al Tamimi POC" --client-slug al-tamimi
    python -m neolex.admin keys-create --name "Admin Key" --client-slug admin --scope admin
    python -m neolex.admin keys-list
    python -m neolex.admin keys-revoke <prefix>
    python -m neolex.admin show-log [--table queries|events] [--limit N]

The CLI reads NEOLEX_DB_PATH (defaults to neolex.db in CWD).
It does NOT require the FastAPI server to be running.
"""
import argparse
import asyncio
import sys

from neolex.auth.keys import generate_key, hash_key, key_prefix as get_prefix
from neolex.config import settings
from neolex.db.audit import get_audit_db


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

async def cmd_keys_create(args: argparse.Namespace) -> None:
    raw_key = generate_key()
    k_hash = hash_key(raw_key)
    k_prefix = get_prefix(raw_key)

    async with get_audit_db() as db:
        await db.init_schema()
        row_id = await db.create_key(
            name=args.name,
            key_hash=k_hash,
            key_prefix=k_prefix,
            client_slug=args.client_slug,
            scope=args.scope,
        )

    print()
    print("=" * 60)
    print("  API KEY CREATED — SAVE THIS KEY, IT WILL NOT BE SHOWN AGAIN")
    print("=" * 60)
    print(f"  Name:        {args.name}")
    print(f"  Client slug: {args.client_slug}")
    print(f"  Scope:       {args.scope}")
    print(f"  Key prefix:  {k_prefix}")
    print(f"  DB row ID:   {row_id}")
    print()
    print(f"  KEY: {raw_key}")
    print()
    print("  Use in requests:  Authorization: Bearer <key>")
    print("=" * 60)
    print()


async def cmd_keys_list(args: argparse.Namespace) -> None:
    async with get_audit_db() as db:
        await db.init_schema()
        rows = await db.list_keys()

    if not rows:
        print("No API keys found.")
        return

    # Header
    col_fmt = "{:<5} {:<25} {:<10} {:<15} {:<8} {:<8} {:<26} {}"
    print(col_fmt.format("ID", "Name", "Prefix", "Client slug", "Scope", "Active", "Created", "Last used"))
    print("-" * 110)
    for row in rows:
        r = dict(row)
        print(col_fmt.format(
            r["id"],
            r["name"][:24],
            r["key_prefix"],
            r["client_slug"][:14],
            r["scope"],
            "YES" if r["active"] else "NO",
            (r["created_at"] or "")[:25],
            (r["last_used"] or "never"),
        ))


async def cmd_keys_revoke(args: argparse.Namespace) -> None:
    async with get_audit_db() as db:
        await db.init_schema()
        n = await db.revoke_key(args.prefix)

    if n == 0:
        print(f"No active keys found with prefix '{args.prefix}'.")
        sys.exit(1)
    else:
        print(f"Revoked {n} key(s) with prefix '{args.prefix}'.")


async def cmd_show_log(args: argparse.Namespace) -> None:
    async with get_audit_db() as db:
        await db.init_schema()
        if args.table == "queries":
            rows = await db.get_queries(limit=args.limit)
        else:
            rows = await db.get_events(limit=args.limit)

    if not rows:
        print(f"No entries in {args.table} table.")
        return

    print(f"\n--- {args.table} (last {len(rows)}) ---\n")
    for row in rows:
        r = dict(row)
        ts = r.get("ts", "")
        if args.table == "queries":
            print(f"[{ts}] key={r.get('key_hash', '')[:12]}... | "
                  f"latency={r.get('latency_ms')}ms | "
                  f"model={r.get('model_name', '')} | "
                  f"q={r.get('question', '')[:60]}")
        else:
            detail = r.get("detail_json", "{}")
            print(f"[{ts}] type={r.get('event_type', '')} | "
                  f"ip={r.get('ip', '')} | "
                  f"detail={detail[:80]}")
    print()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m neolex.admin",
        description="Vitreon Legal admin CLI — manage API keys and view audit log.",
    )
    parser.add_argument(
        "--db",
        help=f"Path to SQLite DB (default: {settings.db_path})",
        default=None,
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # keys-create
    p_create = sub.add_parser("keys-create", help="Create a new API key")
    p_create.add_argument("--name", required=True, help="Human-readable name for this key")
    p_create.add_argument("--client-slug", required=True, dest="client_slug",
                          help="Client namespace slug (e.g. al-tamimi). "
                               "Maps to data/clients/<slug>/")
    p_create.add_argument("--scope", choices=["query", "admin"], default="query",
                          help="Key scope: 'query' (default) or 'admin'")

    # keys-list
    sub.add_parser("keys-list", help="List all API keys")

    # keys-revoke
    p_revoke = sub.add_parser("keys-revoke", help="Revoke a key by its 8-char prefix")
    p_revoke.add_argument("prefix", help="First 8 characters of the key to revoke")

    # show-log
    p_log = sub.add_parser("show-log", help="Display recent audit log entries")
    p_log.add_argument("--table", choices=["queries", "events"], default="queries",
                       help="Which log table to show (default: queries)")
    p_log.add_argument("--limit", type=int, default=20,
                       help="Number of recent entries to show (default: 20)")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Allow --db flag to override settings.db_path for this CLI session
    if args.db:
        settings.db_path = args.db

    dispatch = {
        "keys-create": cmd_keys_create,
        "keys-list": cmd_keys_list,
        "keys-revoke": cmd_keys_revoke,
        "show-log": cmd_show_log,
    }

    handler = dispatch[args.command]
    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
