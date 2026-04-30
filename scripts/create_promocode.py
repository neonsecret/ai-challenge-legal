#!/usr/bin/env python3
"""CLI to create or update promocodes in the database.

Usage:
    uv run python scripts/create_promocode.py HIVITREON --tier starter --days 30
    uv run python scripts/create_promocode.py HIVITREON --tier starter --days 30 --max-redemptions 500
    uv run python scripts/create_promocode.py HIVITREON --disable
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from neolex.config import settings


async def run(args: argparse.Namespace) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Import after engine is set up
    from neolex.db.models import Promocode

    async with Session() as db:
        result = await db.execute(select(Promocode).where(Promocode.code == args.code))
        promo = result.scalar_one_or_none()

        if args.disable:
            if promo is None:
                print(f"Code {args.code!r} not found.")
                sys.exit(1)
            promo.active = False
            await db.commit()
            print(f"Disabled {args.code!r}.")
            return

        valid_until = None
        if args.expires_days:
            valid_until = datetime.now(UTC) + timedelta(days=args.expires_days)

        if promo is None:
            promo = Promocode(
                code=args.code,
                tier=args.tier,
                duration_days=args.days,
                max_redemptions=args.max_redemptions,
                valid_until=valid_until,
                active=True,
                notes=args.notes,
            )
            db.add(promo)
            action = "Created"
        else:
            promo.tier = args.tier
            promo.duration_days = args.days
            promo.max_redemptions = args.max_redemptions
            promo.valid_until = valid_until
            promo.active = True
            if args.notes:
                promo.notes = args.notes
            action = "Updated"

        await db.commit()
        print(
            f"{action} code {args.code!r}: tier={args.tier}, days={args.days}, "
            f"max_redemptions={args.max_redemptions!r}, valid_until={valid_until!r}"
        )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a Vitreon promocode.")
    parser.add_argument("code", help="Promocode string (case-sensitive, e.g. HIVITREON)")
    parser.add_argument("--tier", choices=["starter", "pro", "enterprise"], help="Plan to grant")
    parser.add_argument("--days", type=int, help="Duration in days after redemption")
    parser.add_argument(
        "--max-redemptions",
        type=int,
        default=None,
        help="Max total redemptions (omit = unlimited)",
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="Days until the code itself expires (not per-user duration)",
    )
    parser.add_argument("--notes", default=None, help="Internal notes")
    parser.add_argument("--disable", action="store_true", help="Disable an existing code")
    args = parser.parse_args()

    if not args.disable and (not args.tier or not args.days):
        parser.error("--tier and --days are required unless --disable is used")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
