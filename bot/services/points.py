"""Buffered daily check-in ledger; additional award rules arrive in Phase 3."""

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot.db.models import Challenge, PointEvent, User
from bot.services.locks import ChatLocks

DAILY_CHECKIN = 1
CHALLENGE_DONE = {"video_note": 15, "voice": 10, "photo": 10, "text": 5}
CHALLENGE_MISSED = -5
QUIZ_CORRECT, QUIZ_FIRST_BONUS = 3, 2
DUEL_WIN = 2
RPS_WIN = 2
KROKODIL_GUESSER, KROKODIL_HOST, KROKODIL_REVEAL = 5, 3, -3
TRUTH_ANSWERED, DARE_REFUSED = 5, -2
MAFIA_WIN, MAFIA_SURVIVED = 10, 3
logger = logging.getLogger(__name__)


def challenge_points(kind: str, *, done: bool, penalty_mode: str = "points") -> int:
    return CHALLENGE_DONE[kind] if done else (0 if penalty_mode == "off" else CHALLENGE_MISSED)


async def record_event(
    session, chat_id: int, user_id: int, delta: int, reason: str, ref_id: str
) -> bool:
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    statement = insert(PointEvent).values(
        chat_id=chat_id, user_id=user_id, delta=delta, reason=reason, ref_id=ref_id
    )
    result = await session.execute(
        statement.on_conflict_do_nothing(
            index_elements=[
                PointEvent.chat_id,
                PointEvent.user_id,
                PointEvent.reason,
                PointEvent.ref_id,
            ]
        )
    )
    if result.rowcount == 1:
        from bot.services.achievements import on_event

        await on_event(session, chat_id, user_id, delta, reason, ref_id)
        return True
    return False


class Points:
    def __init__(self, sessions, locks=None) -> None:
        self.sessions = sessions
        self.locks = locks or ChatLocks()

    async def award(self, chat_id, user_id, delta, reason, ref_id) -> bool:
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                return await record_event(session, chat_id, user_id, delta, reason, ref_id)

    async def stats(self, chat_id: int, user_id: int) -> tuple[int, int, int]:
        chat_id = self.locks.resolve(chat_id)
        async with self.sessions() as session:
            points = await session.scalar(
                select(func.coalesce(func.sum(PointEvent.delta), 0)).where(
                    PointEvent.chat_id == chat_id,
                    PointEvent.user_id == user_id,
                )
            )
            counts = dict(
                (
                    await session.execute(
                        select(Challenge.status, func.count())
                        .where(
                            Challenge.chat_id == chat_id,
                            Challenge.user_id == user_id,
                        )
                        .group_by(Challenge.status)
                    )
                ).all()
            )
            return points, counts.get("done", 0), counts.get("missed", 0)

    async def top(self, chat_id: int, since=None, until=None):
        chat_id = self.locks.resolve(chat_id)
        query = (
            select(User.id, User.first_name, func.sum(PointEvent.delta).label("points"))
            .join(PointEvent, PointEvent.user_id == User.id)
            .where(PointEvent.chat_id == chat_id)
        )
        if since is not None:
            query = query.where(PointEvent.created_at >= since)
        if until is not None:
            query = query.where(PointEvent.created_at < until)
        query = (
            query.group_by(User.id, User.first_name)
            .order_by(func.sum(PointEvent.delta).desc(), User.id)
            .limit(10)
        )
        async with self.sessions() as session:
            return (await session.execute(query)).all()


class CheckinBuffer:
    def __init__(self, sessions, locks=None) -> None:
        self.sessions = sessions
        self.locks = locks or ChatLocks()
        self.pending: dict[tuple, dict] = {}
        self._lock = asyncio.Lock()

    def add(self, chat_id: int, user_id: int, local_date) -> None:
        key = (chat_id, user_id, local_date)
        self.pending[key] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "delta": DAILY_CHECKIN,
            "reason": "daily_checkin",
            "ref_id": f"daily:{local_date.isoformat()}",
        }

    async def flush(self) -> None:
        async with self._lock:
            pending, self.pending = self.pending, {}
            if not pending:
                return
            try:
                grouped = {}
                for row in pending.values():
                    grouped.setdefault(row["chat_id"], []).append(row)
                for source, rows in grouped.items():
                    async with self.locks.hold(source) as chat_id:
                        async with self.sessions.begin() as session:
                            insert = (
                                pg_insert
                                if session.bind.dialect.name == "postgresql"
                                else sqlite_insert
                            )
                            rows = [{**row, "chat_id": chat_id} for row in rows]
                            for start in range(0, len(rows), 100):
                                statement = insert(PointEvent).values(rows[start : start + 100])
                                result = await session.execute(
                                    statement.on_conflict_do_nothing(
                                        index_elements=[
                                            PointEvent.chat_id,
                                            PointEvent.user_id,
                                            PointEvent.reason,
                                            PointEvent.ref_id,
                                        ]
                                    ).returning(
                                        PointEvent.chat_id, PointEvent.user_id, PointEvent.ref_id
                                    )
                                )
                                from bot.services.achievements import checkin_milestones

                                for row in result.all():
                                    await checkin_milestones(
                                        session, row.chat_id, row.user_id, row.ref_id
                                    )
            except BaseException:
                self.pending = pending | self.pending
                raise

    async def run(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self.flush()
            except Exception:
                logger.exception("Check-in flush failed; awards retained for retry")
