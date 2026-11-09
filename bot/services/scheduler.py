"""Indexed, bounded scheduler infrastructure. Product hooks arrive in later phases."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy import bindparam, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.models import Challenge, Chat, GameSession
from bot.services.schedule_times import next_for_chat
from bot.utils.time import utc_now

logger = logging.getLogger(__name__)
BATCH_SIZE = 500
CHAT_JOBS = {
    "daily": Chat.next_daily_at,
    "challenge": Chat.next_challenge_at,
    "weekly": Chat.next_weekly_at,
    "season": Chat.next_season_at,
}


def due_chats_query(kind: str, now: datetime):
    column = CHAT_JOBS[kind]
    return select(Chat).where(column <= now).order_by(column, Chat.id).limit(BATCH_SIZE)


class Scheduler:
    def __init__(
        self,
        sessions: async_sessionmaker,
        *,
        hooks: dict[str, Callable[..., Awaitable[bool]]] | None = None,
    ) -> None:
        self.sessions = sessions
        self.hooks = hooks or {}
        self.last_tick_duration = 0.0
        self.recovery = None
        self.maintenance = []
        self._lock = asyncio.Lock()
        self._deadline_lock = asyncio.Lock()
        self.last_deadline_tick_duration = 0.0
        self._workers = {kind: asyncio.Semaphore(25) for kind in (*CHAT_JOBS, "expire", "game")}

    async def _process(self, kind: str, row, now: datetime) -> bool | datetime:
        try:
            async with self._workers[kind]:
                return await self.hooks[kind](row, now)
        except Exception:
            logger.exception("Scheduled %s failed for id %s", kind, row.id)
            return False

    async def _chat_batch(self, kind: str, now: datetime) -> int:
        column = CHAT_JOBS[kind]
        async with self.sessions() as session:
            chats = (await session.scalars(due_chats_query(kind, now))).all()

        async def process(chat):
            try:
                next_time = next_for_chat(kind, chat, now)
                outcome = True if next_time is None else await self._process(kind, chat, now)
                if outcome:
                    if isinstance(outcome, datetime):
                        next_time = outcome
                    return {
                        "chat_key": chat.id,
                        "expected": getattr(chat, column.key),
                        "next_value": next_time,
                    }
            except Exception:
                logger.exception("Could not reschedule %s for chat %s", kind, chat.id)
            retry_at = now + timedelta(minutes=10)
            logger.warning(
                "Scheduled %s failed for chat %s; backing off until %s", kind, chat.id, retry_at
            )
            return {
                "chat_key": chat.id,
                "expected": getattr(chat, column.key),
                "next_value": retry_at,
            }

        changes = [
            change
            for change in await asyncio.gather(*[process(chat) for chat in chats])
            if change is not None
        ]
        if changes:
            table = Chat.__table__
            statement = (
                table.update()
                .where(
                    table.c.id == bindparam("chat_key"),
                    table.c[column.key] == bindparam("expected"),
                )
                .values({column.key: bindparam("next_value")})
            )
            async with self.sessions.begin() as session:
                await session.execute(statement, changes)
        return len(changes)

    async def _deadline_batch(self, kind: str, now: datetime) -> int:
        model, deadline, statuses = (
            (Challenge, Challenge.deadline_at, ["pending"])
            if kind == "expire"
            else (GameSession, GameSession.phase_deadline_at, ["lobby", "running"])
        )
        query = (
            select(model)
            .where(model.status.in_(statuses), deadline <= now)
            .order_by(deadline, model.id)
            .limit(BATCH_SIZE)
        )
        async with self.sessions() as session:
            rows = (await session.scalars(query)).all()
        return sum(await asyncio.gather(*[self._process(kind, row, now) for row in rows]))

    async def tick(self, now: datetime | None = None) -> dict[str, int]:
        async with self._lock:
            started = time.perf_counter()
            now = now or utc_now()
            counts = {kind: 0 for kind in (*CHAT_JOBS, "expire", "game")}
            try:
                tasks = {}
                # Bulk work has its own loop/lock, entirely separate from deadline progression.
                async with asyncio.TaskGroup() as group:
                    for kind in ("challenge", "daily", "weekly", "season"):
                        if kind in self.hooks:
                            operation = (
                                self._chat_batch if kind in CHAT_JOBS else self._deadline_batch
                            )
                            tasks[kind] = group.create_task(operation(kind, now))
                counts.update({kind: task.result() for kind, task in tasks.items()})
                if self.recovery:
                    await self.recovery.tick(now)
                for operation in self.maintenance:
                    await operation(now)
                return counts
            finally:
                self.last_tick_duration = time.perf_counter() - started

    async def deadline_tick(self, now: datetime | None = None) -> dict[str, int]:
        async with self._deadline_lock:
            started = time.perf_counter()
            now = now or utc_now()
            try:
                tasks = {}
                async with asyncio.TaskGroup() as group:
                    for kind in ("game", "expire"):
                        if kind in self.hooks:
                            tasks[kind] = group.create_task(self._deadline_batch(kind, now))
                return {kind: task.result() for kind, task in tasks.items()}
            finally:
                self.last_deadline_tick_duration = time.perf_counter() - started

    async def run_deadlines(self) -> None:
        while True:
            try:
                await self.deadline_tick()
            except Exception:
                logger.exception("Deadline tick failed; will retry")
            await asyncio.sleep(1)

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("Scheduler tick failed; will retry")
            await asyncio.sleep(30)


def initialize_schedule(chat: Chat, now: datetime) -> None:
    """Onboarding/settings call this while persisting that one chat; never scan chats."""
    for kind, column in CHAT_JOBS.items():
        setattr(chat, column.key, next_for_chat(kind, chat, now))
