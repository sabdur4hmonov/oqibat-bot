from datetime import timedelta
from unittest.mock import AsyncMock

from sqlalchemy import func, insert, select, text

from bot.db.models import Chat
from bot.services.scheduler import Scheduler
from bot.utils.time import utc_now


async def test_tick_processes_only_500_due_and_recomputes(sessions):
    now = utc_now()
    async with sessions.begin() as session:
        await session.execute(
            insert(Chat),
            [
                {
                    "id": -i - 1,
                    "title": "Sinov",
                    "bot_is_admin": True,
                    "next_daily_at": now - timedelta(seconds=1)
                    if i < 501
                    else now + timedelta(days=1),
                }
                for i in range(520)
            ],
        )
    hook = AsyncMock(return_value=True)
    scheduler = Scheduler(sessions, hooks={"daily": hook})
    counts = await scheduler.tick(now)
    assert counts["daily"] == hook.await_count == 500
    assert scheduler.last_tick_duration > 0
    counts = await scheduler.tick(now)
    assert counts["daily"] == 1
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(Chat).where(Chat.next_daily_at <= now)
            )
            == 0
        )


async def test_missing_or_failed_hook_does_not_lose_due_work(sessions):
    now = utc_now()
    due = now - timedelta(seconds=1)
    async with sessions.begin() as session:
        session.add(Chat(id=-1, title="Sinov", bot_is_admin=True, next_daily_at=due))
    assert not any((await Scheduler(sessions).tick(now)).values())
    scheduler = Scheduler(sessions, hooks={"daily": AsyncMock(side_effect=RuntimeError("offline"))})
    assert (await scheduler.tick(now))["daily"] == 0
    async with sessions() as session:
        assert (await session.get(Chat, -1)).next_daily_at == due


async def test_due_query_uses_timestamp_index(sessions):
    async with sessions() as session:
        plan = (
            await session.execute(
                text(
                    "EXPLAIN QUERY PLAN SELECT * FROM chats WHERE next_daily_at <= :now "
                    "ORDER BY next_daily_at, id LIMIT 500"
                ),
                {"now": "2026-11-07"},
            )
        ).all()
    assert "ix_chats_next_daily_at" in str(plan)
    assert "SCAN chats" not in str(plan)
