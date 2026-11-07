"""Coalesced incoming activity. No SQL is issued by observe/mark_private."""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime

from sqlalchemy import BigInteger, case, literal, select, union_all
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot.db.models import Chat, Membership, User, UTCDateTime
from bot.utils.time import utc_now

logger = logging.getLogger(__name__)
CHUNK_SIZE = 100  # Below SQLite compound-select and bind-parameter limits.


class ActivityBuffer:
    def __init__(self, sessions) -> None:
        self.sessions = sessions
        self.users: dict[int, dict] = {}
        self.members: dict[tuple[int, int], datetime] = {}
        self.names: OrderedDict[int, tuple[str, str | None]] = OrderedDict()
        self._flush_lock = asyncio.Lock()

    def observe(
        self,
        chat_id: int,
        user_id: int,
        first_name: str,
        username: str | None,
        seen_at: datetime | None = None,
    ) -> None:
        name = (first_name, username)
        if self.names.get(user_id) != name:
            old = self.users.get(user_id, {})
            self.users[user_id] = {
                "id": user_id,
                "first_name": first_name,
                "username": username,
                "private": old.get("private"),
            }
            self.names[user_id] = name
        self.names.move_to_end(user_id)
        if len(self.names) > 100_000:
            self.names.popitem(last=False)
        if chat_id < 0:
            key = (chat_id, user_id)
            seen = seen_at or utc_now()
            self.members[key] = max(seen, self.members.get(key, seen))

    def mark_private(self, user_id: int, first_name: str, username: str | None) -> None:
        self.observe(user_id, user_id, first_name, username)
        self.users.setdefault(
            user_id, {"id": user_id, "first_name": first_name, "username": username}
        )["private"] = True

    async def mark_forbidden(self, chat_id: int) -> None:
        # Finish an in-flight flush before the sender persists the forbidden flag.
        async with self._flush_lock:
            if chat_id > 0 and chat_id in self.names:
                first_name, username = self.names[chat_id]
                self.users[chat_id] = {
                    "id": chat_id,
                    "first_name": first_name,
                    "username": username,
                    "private": False,
                }

    async def flush(self) -> None:
        async with self._flush_lock:
            users, members = self.users, self.members
            self.users, self.members = {}, {}
            if not users and not members:
                return
            try:
                async with self.sessions.begin() as session:
                    insert = (
                        pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
                    )
                    user_rows = list(users.values())
                    for start in range(0, len(user_rows), CHUNK_SIZE):
                        chunk = user_rows[start : start + CHUNK_SIZE]
                        statement = insert(User).values(
                            [
                                {
                                    "id": row["id"],
                                    "first_name": row["first_name"],
                                    "username": row["username"],
                                    "started_private": bool(row.get("private")),
                                }
                                for row in chunk
                            ]
                        )
                        private_ids = [row["id"] for row in chunk if row.get("private") is not None]
                        statement = statement.on_conflict_do_update(
                            index_elements=[User.id],
                            set_={
                                "first_name": statement.excluded.first_name,
                                "username": statement.excluded.username,
                                "started_private": case(
                                    (User.id.in_(private_ids), statement.excluded.started_private),
                                    else_=User.started_private,
                                ),
                                "updated_at": utc_now(),
                            },
                        )
                        await session.execute(statement)
                    member_rows = list(members.items())
                    for start in range(0, len(member_rows), CHUNK_SIZE):
                        chunk = member_rows[start : start + CHUNK_SIZE]
                        incoming = union_all(
                            *[
                                select(
                                    literal(chat, BigInteger).label("chat_id"),
                                    literal(user, BigInteger).label("user_id"),
                                    literal(seen, UTCDateTime()).label("last_seen_at"),
                                )
                                for (chat, user), seen in chunk
                            ]
                        ).subquery()
                        source = (
                            select(incoming)
                            .join(Chat, Chat.id == incoming.c.chat_id)
                            .where(Chat.is_active.is_(True))
                        )
                        statement = insert(Membership).from_select(
                            ["chat_id", "user_id", "last_seen_at"], source
                        )
                        statement = statement.on_conflict_do_update(
                            index_elements=[Membership.chat_id, Membership.user_id],
                            set_={"last_seen_at": statement.excluded.last_seen_at},
                        )
                        await session.execute(statement)
            except BaseException:
                # Newer observations win if more messages arrived during an unsuccessful flush.
                for user_id, row in users.items():
                    current = self.users.setdefault(user_id, row)
                    if current.get("private") is None:
                        current["private"] = row.get("private")
                for key, seen in members.items():
                    self.members[key] = max(self.members.get(key, seen), seen)
                raise

    async def run(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self.flush()
            except Exception:
                logger.exception("Activity flush failed; buffered rows retained for retry")
