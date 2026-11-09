"""Calendar-month UTC windows and bounded, claimed-once season champion cards."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram.types import BufferedInputFile
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot import texts
from bot.db.models import Chat, ScheduledPost
from bot.services.locks import ChatLocks
from bot.services.schedule_times import stable_offset
from bot.services.sender import Priority
from bot.utils.time import after_quiet, is_quiet


def month_bounds(at, tz):
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Month boundaries require an aware datetime")
    local = at.astimezone(ZoneInfo(tz))
    start = datetime(local.year, local.month, 1, tzinfo=ZoneInfo(tz))
    year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
    end = datetime(year, month, 1, tzinfo=ZoneInfo(tz))
    return start.astimezone(UTC), end.astimezone(UTC)


def next_season(chat_id, tz, after):
    start, end = month_bounds(after, tz)
    zone = ZoneInfo(tz)
    candidate = datetime.combine(start.astimezone(zone).date(), time(9), zone) + timedelta(
        seconds=stable_offset(chat_id, "season")
    )
    if candidate.astimezone(UTC) <= after:
        candidate = datetime.combine(end.astimezone(zone).date(), time(9), zone) + timedelta(
            seconds=stable_offset(chat_id, "season")
        )
    return candidate.astimezone(UTC)


class Seasons:
    def __init__(self, runtime):
        self.runtime = runtime
        self.delivery_locks = ChatLocks()

    async def post(self, chat, now):
        await self.runtime.checkins.flush()
        async with self.runtime.locks.hold(chat.id) as chat_id:
            async with self.runtime.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if (
                    not chat
                    or not chat.is_active
                    or not chat.bot_is_admin
                    or not chat.next_season_at
                    or chat.next_season_at > now
                ):
                    return True
                if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end):
                    return after_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end)
                since, _ = month_bounds(chat.next_season_at, chat.tz)
                previous, _ = month_bounds(since - timedelta(seconds=1), chat.tz)
                date = previous.astimezone(ZoneInfo(chat.tz)).date()
                insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
                result = await session.execute(
                    insert(ScheduledPost)
                    .values(
                        chat_id=chat_id,
                        kind="season",
                        local_date=date,
                        status="reserved",
                        claimed_at=now,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            ScheduledPost.chat_id,
                            ScheduledPost.kind,
                            ScheduledPost.local_date,
                        ]
                    )
                )
                if result.rowcount == 0:
                    return True
        return await self.recover(SimplePost(chat_id, date), now)

    async def recover(self, post, now):
        runtime = self.runtime
        target = runtime.locks.resolve(post.chat_id)
        key = (target, "season", post.local_date)
        generation = runtime.sender.generations.get(target, 0)
        async with self.delivery_locks.for_chat(target):
            async with runtime.sessions() as session:
                stored = await session.get(ScheduledPost, key)
                chat = await session.get(Chat, target)
            if stored is None or stored.sent_at or stored.status == "skipped":
                return True
            if (
                not chat
                or not chat.is_active
                or not chat.bot_is_admin
                or now - stored.claimed_at > timedelta(hours=6)
            ):
                async with runtime.sessions.begin() as session:
                    row = await session.get(ScheduledPost, key)
                    if row:
                        row.status = "skipped"
                return True
            if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end):
                async with runtime.sessions.begin() as session:
                    row = await session.get(ScheduledPost, key)
                    if row:
                        row.retry_at = min(
                            after_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end),
                            stored.claimed_at + timedelta(hours=6, microseconds=1),
                        )
                return False
            local = datetime.combine(post.local_date, time(), ZoneInfo(chat.tz))
            since, until = month_bounds(local, chat.tz)
            top = await runtime.points.top(target, since, until)
            payload = await runtime.cards.render(
                texts.SEASON_TITLE,
                [(name, points) for _, name, points in top[:5]],
                texts.season_month(post.local_date),
            )
            if generation != runtime.sender.generations.get(target, 0):
                return False
            if payload:

                async def send():
                    return await runtime.game_hub.bot.send_photo(
                        target,
                        BufferedInputFile(payload, filename="oqibat-season.png"),
                        caption=texts.season_result(post.local_date, top),
                    )
            else:

                async def send():
                    return await runtime.game_hub.bot.send_message(
                        target, texts.season_result(post.local_date, top)
                    )

            sent = await runtime.sender.send(target, send, priority=Priority.BULK)
            async with runtime.sessions.begin() as session:
                row = await session.get(ScheduledPost, key)
                if row:
                    row.status = "sent" if sent is not None else "failed"
                    row.sent_at = row.posted_at = sent.date if sent is not None else None
                    row.message_id = sent.message_id if sent is not None else None
                    row.origin_chat_id = sent.chat.id if sent is not None else target
                    row.retry_at = None if sent is not None else now + timedelta(minutes=10)
            return sent is not None


class SimplePost:
    def __init__(self, chat_id, local_date):
        self.chat_id, self.local_date = chat_id, local_date
