"""Vitreon Legal admin CLI — user management and audit log.

Usage:
    python -m neolex.admin show-log [--table queries|events] [--limit N]
    python -m neolex.admin list-users

Reads DATABASE_URL from .env (PostgreSQL on RTX 3070).
Does NOT require the FastAPI server to be running.
"""
from dotenv import load_dotenv as _load_dotenv

_load_dotenv(override=False)

import argparse
import asyncio

from neolex.db.audit import get_audit_db


async def cmd_list_users(args: argparse.Namespace) -> None:
    from sqlalchemy import select

    from neolex.db.models import User
    from neolex.db.postgres import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()

    if not users:
        print("No users found.")
        return

    fmt = "{:<38} {:<30} {:<10} {:<12} {}"
    print(fmt.format("ID", "Email", "Status", "Verified", "Created"))
    print("-" * 110)
    for u in users:
        print(fmt.format(
            str(u.id)[:37],
            (u.email or "")[:29],
            u.subscription_status,
            "YES" if u.email_verified else "NO",
            str(u.created_at)[:19] if u.created_at else "",
        ))


async def cmd_show_log(args: argparse.Namespace) -> None:
    async with get_audit_db() as db:
        if args.table == "queries":
            rows = await db.get_queries(limit=args.limit)
        else:
            rows = await db.get_events(limit=args.limit)

    if not rows:
        print(f"No entries in {args.table} table.")
        return

    print(f"\n--- {args.table} (last {len(rows)}) ---\n")
    for r in rows:
        ts = r.get("ts", "")
        if args.table == "queries":
            print(f"[{ts}] latency={r.get('latency_ms')}ms | "
                  f"model={r.get('model_name', '')} | "
                  f"q={r.get('question', '')[:60]}")
        else:
            detail = r.get("detail_json", "{}")
            print(f"[{ts}] type={r.get('event_type', '')} | "
                  f"ip={r.get('ip', '')} | "
                  f"detail={detail[:80]}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m neolex.admin",
        description="Vitreon Legal admin CLI — manage users and view audit log.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    sub.add_parser("list-users", help="List all registered users")

    p_log = sub.add_parser("show-log", help="Display recent audit log entries")
    p_log.add_argument("--table", choices=["queries", "events"], default="queries",
                       help="Which log table to show (default: queries)")
    p_log.add_argument("--limit", type=int, default=20,
                       help="Number of recent entries to show (default: 20)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "list-users": cmd_list_users,
        "show-log": cmd_show_log,
    }

    handler = dispatch[args.command]
    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
