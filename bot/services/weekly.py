"""Indexed weekly summaries, anchored to their scheduled Sunday and reserved once."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram.types import BufferedInputFile
from sqlalchemy import String, cast, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot import texts
from bot.db.models import Challenge, Chat, PointEvent, ScheduledPost, User
from bot.keyboards.cards import story_keyboard
from bot.keyboards.private import add_to_group_keyboard
from bot.services.sender import Priority
from bot.utils.time import UTC, after_quiet, is_quiet, week_start


def weekly_period(chat, due):
    """Use the previous scheduled Sunday, even after Monday quiet-hour deferral."""
    zone = ZoneInfo(chat.tz)
    local = due.astimezone(zone)
    sunday = local.date() - timedelta(days=(local.weekday() - 6) % 7)
    # Date identity is independent of the hash: a supergroup migration changes
    # chat_id (and future offsets) while a previously scheduled job stays due.
    anchor = datetime.combine(sunday, time(20), zone)
    if anchor.astimezone(UTC) > due:
        anchor -= timedelta(days=7)
    since = week_start(anchor, chat.tz)
    monday = since.astimezone(zone).date()
    until = datetime.combine(monday + timedelta(days=7), time(), zone).astimezone(UTC)
    return monday, since, until


async def summary(session, chat_id, since, until):
    window = (
        PointEvent.chat_id == chat_id,
        PointEvent.created_at >= since,
        PointEvent.created_at < until,
    )
    top = (
        await session.execute(
            select(User.id, User.first_name, func.sum(PointEvent.delta).label("points"))
            .join(PointEvent, User.id == PointEvent.user_id)
            .where(*window)
            .group_by(User.id, User.first_name)
            .order_by(func.sum(PointEvent.delta).desc(), User.id)
            .limit(5)
        )
    ).all()
    reference = func.coalesce(PointEvent.ref_id, literal("event:") + cast(PointEvent.id, String))
    activity = func.count(func.distinct(reference))
    active = (
        await session.execute(
            select(User.id, User.first_name, activity.label("activities"))
            .join(PointEvent, User.id == PointEvent.user_id)
            .where(*window, PointEvent.delta > 0)
            .group_by(User.id, User.first_name)
            .order_by(activity.desc(), func.sum(PointEvent.delta).desc(), User.id)
            .limit(1)
        )
    ).first()
    resolved = dict(
        (
            await session.execute(
                select(Challenge.status, func.count())
                .where(
                    Challenge.chat_id == chat_id,
                    Challenge.resolved_at >= since,
                    Challenge.resolved_at < until,
                )
                .group_by(Challenge.status)
            )
        ).all()
    )
    pending = await session.scalar(
        select(func.count())
        .select_from(Challenge)
        .where(Challenge.chat_id == chat_id, Challenge.status == "pending")
    )
    return {
        "top": list(top),
        "active": active,
        "done": resolved.get("done", 0),
        "missed": resolved.get("missed", 0),
        "pending": pending or 0,
    }


class Weekly:
    def __init__(self, sessions, locks, bot, sender, checkins, settings):
        self.sessions, self.locks, self.bot, self.sender = sessions, locks, bot, sender
        self.checkins = checkins
        self.username = getattr(settings, "bot_username", "OqibatBot")
        self.instagram = getattr(settings, "instagram_handle", "oqibat")
        self.cards = None

    async def post(self, chat, now):
        generation = self.sender.generations.get(chat.id, 0)
        await self.checkins.flush()
        async with self.locks.hold(chat.id) as chat_id:
            async with self.sessions.begin() as session:
                current = await session.get(Chat, chat_id)
                if current is None or not current.is_active or not current.bot_is_admin:
                    return True
                if current.next_weekly_at is None or current.next_weekly_at > now:
                    return True
                if is_quiet(now, current.tz, current.quiet_start, current.quiet_end):
                    return after_quiet(now, current.tz, current.quiet_start, current.quiet_end)
                week, since, until = weekly_period(current, current.next_weekly_at or now)
                insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
                result = await session.execute(
                    insert(ScheduledPost)
                    .values(
                        chat_id=chat_id,
                        origin_chat_id=chat_id,
                        kind="weekly",
                        local_date=week,
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
                data = await summary(
                    session, chat_id, since, min(until, now + timedelta(microseconds=1))
                )
        payload = await self.cards.weekly(week, data) if self.cards else None
        if generation != self.sender.generations.get(chat.id, 0):
            return True
        if payload is not None:
            sent = await self.sender.send(
                chat_id,
                lambda: self.bot.send_photo(
                    chat_id,
                    BufferedInputFile(payload, filename="oqibat-weekly.png"),
                    caption=texts.weekly_summary(week, data, self.instagram, compact=True),
                    reply_markup=story_keyboard(f"w:{chat_id}:{week}",
                                                add_to_group_keyboard(self.username)),
                ),
                priority=Priority.BULK,
            )
        else:
            sent = await self.sender.send(
                chat_id,
                lambda: self.bot.send_message(
                    chat_id,
                    texts.weekly_summary(week, data, self.instagram),
                    reply_markup=add_to_group_keyboard(self.username),
                ),
                priority=Priority.BULK,
            )
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                await session.execute(
                    update(ScheduledPost)
                    .where(
                        ScheduledPost.chat_id == chat_id,
                        ScheduledPost.kind == "weekly",
                        ScheduledPost.local_date == week,
                    )
                    .values(
                        status="sent" if sent is not None else "failed",
                        sent_at=sent.date if sent is not None else None,
                        retry_at=None if sent is not None else now + timedelta(minutes=10),
                        posted_at=sent.date if sent is not None else None,
                        message_id=sent.message_id if sent is not None else None,
                        origin_chat_id=getattr(getattr(sent, "chat", None), "id", chat_id),
                    )
                )
        return sent is not None
