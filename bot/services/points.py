"""Buffered daily check-in ledger; additional award rules arrive in Phase 3."""

import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot.db.models import PointEvent

DAILY_CHECKIN = 1
logger = logging.getLogger(__name__)


class CheckinBuffer:
    def __init__(self, sessions) -> None:
        self.sessions = sessions
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
                async with self.sessions.begin() as session:
                    insert = (
                        pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
                    )
                    rows = list(pending.values())
                    for start in range(0, len(rows), 100):
                        statement = insert(PointEvent).values(rows[start : start + 100])
                        await session.execute(
                            statement.on_conflict_do_nothing(
                                index_elements=[
                                    PointEvent.chat_id,
                                    PointEvent.user_id,
                                    PointEvent.reason,
                                    PointEvent.ref_id,
                                ]
                            )
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
