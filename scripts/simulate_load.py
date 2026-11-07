"""Isolated scheduler benchmark. Never reads/writes the configured application DB."""

import argparse
import asyncio
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import func, insert, select  # noqa: E402

from bot.db.models import Chat  # noqa: E402
from bot.db.session import create_engine, create_session_factory  # noqa: E402
from bot.services.scheduler import Scheduler  # noqa: E402
from bot.utils.time import utc_now  # noqa: E402


async def simulate(url: str, count: int, ticks: int) -> None:
    engine = create_engine(url)
    sessions = create_session_factory(engine)
    now = utc_now()
    try:
        async with sessions.begin() as session:
            for start in range(0, count, 500):
                await session.execute(
                    insert(Chat),
                    [
                        {
                            "id": -1000000000000 - i,
                            "title": f"Simulation {i}",
                            "bot_is_admin": True,
                            "next_daily_at": now - timedelta(seconds=1),
                            "next_challenge_at": now - timedelta(seconds=1),
                            "next_weekly_at": now - timedelta(seconds=1),
                        }
                        for i in range(start, min(start + 500, count))
                    ],
                )

        async def simulated_work(chat, tick_now):
            return True  # Benchmark scheduling/DB work; deliberately no Telegram I/O.

        scheduler = Scheduler(
            sessions, hooks={kind: simulated_work for kind in ("daily", "challenge", "weekly")}
        )
        total = 0
        print(f"fake_chats={count} database=temporary_sqlite telegram_requests=0")
        for number in range(1, ticks + 1):
            counts = await scheduler.tick(now)
            processed = sum(counts.values())
            total += processed
            print(
                f"tick={number} duration_ms={scheduler.last_tick_duration * 1000:.3f} "
                f"due_items_processed={processed} daily={counts['daily']} "
                f"challenge={counts['challenge']} weekly={counts['weekly']}"
            )
        async with sessions() as session:
            remaining = await session.scalar(
                select(func.count()).select_from(Chat).where(Chat.next_daily_at <= now)
            )
        print(f"total_due_items_processed={total} remaining_due_daily={remaining}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chats", type=int, default=5000)
    parser.add_argument("--ticks", type=int, default=1)
    args = parser.parse_args()
    if args.chats <= 0 or args.ticks <= 0:
        parser.error("--chats and --ticks must be positive")
    with tempfile.TemporaryDirectory(prefix="oqibat-load-") as folder:
        url = f"sqlite+aiosqlite:///{(Path(folder) / 'load.db').as_posix()}"
        old_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        try:
            command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
            asyncio.run(simulate(url, args.chats, args.ticks))
        finally:
            if old_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old_url


if __name__ == "__main__":
    main()
