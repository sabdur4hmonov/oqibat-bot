"""Six-hour recovery of announcements on business rows; never changes points."""

import asyncio
import logging
from datetime import timedelta

from aiogram.types import BufferedInputFile
from sqlalchemy import or_, select

from bot import texts
from bot.db.models import Challenge, Chat, ScheduledPost, User
from bot.keyboards.private import add_to_group_keyboard
from bot.services.locks import ChatLocks
from bot.services.points import challenge_points
from bot.services.sender import Priority
from bot.services.weekly import summary
from bot.utils.time import after_quiet, is_quiet, utc_now

logger = logging.getLogger(__name__)
WINDOW = timedelta(hours=6)


def fresh(event_at, now):
    return event_at is not None and now - WINDOW <= event_at <= now


class Recovery:
    def __init__(self, runtime, bot, settings):
        self.runtime, self.bot = runtime, bot
        self.sessions, self.sender = runtime.sessions, runtime.sender
        self.username = getattr(settings, "bot_username", "OqibatBot")
        self.instagram = getattr(settings, "instagram_handle", "oqibat")
        self.lock = asyncio.Lock()
        self.announcements = ChatLocks()

    async def challenge(self, challenge_id, *, result=False, now=None):
        now = now or utc_now()
        field = "result_announced_at" if result else "assigned_announced_at"
        skipped = "result_skipped_at" if result else "assigned_skipped_at"
        async with self.announcements.for_chat(challenge_id * 2 + int(result)):
            async with self.sessions() as session:
                row = await session.get(Challenge, challenge_id)
                generation = self.sender.generations.get(row.chat_id, 0) if row else 0
                if row is None or getattr(row, field) or getattr(row, skipped):
                    return None
                chat = await session.get(Chat, self.runtime.locks.resolve(row.chat_id))
                user = await session.get(User, row.user_id)
            event_at = row.resolved_at if result else row.created_at
            valid = (
                row.status in {"done", "missed"}
                if result
                else row.status == "pending" and row.deadline_at > now
            )
            if (
                not valid
                or not fresh(event_at, now)
                or not chat
                or not user
                or not chat.is_active
                or not chat.bot_is_admin
            ):
                async with self.sessions.begin() as session:
                    current = await session.get(Challenge, challenge_id)
                    if current:
                        setattr(current, skipped, now)
                if not result and row.status == "pending":
                    await self.runtime.challenges.resolve(row.chat_id, row.id, "cancelled")
                return None
            if result:
                message = (
                    texts.challenge_done(
                        user.id, user.first_name, challenge_points(row.kind, done=True)
                    )
                    if row.status == "done"
                    else texts.challenge_missed(user.id, chat.penalty_mode)
                )
            else:
                item = next(
                    (
                        item
                        for item in self.runtime.content.banks["challenges"]
                        if item["key"] == row.prompt_key
                    ),
                    None,
                )
                if item is None:
                    logger.warning("Recovery content unavailable for challenge %s", row.id)
                    async with self.sessions.begin() as session:
                        current = await session.get(Challenge, row.id)
                        if current:
                            current.assigned_skipped_at = now
                    await self.runtime.challenges.resolve(row.chat_id, row.id, "cancelled")
                    return None
                message = texts.challenge_post(
                    user.id, user.first_name, item["text"], row.deadline_at, chat.tz
                )
            if generation != self.sender.generations.get(row.chat_id, 0):
                return None
            sent = await self.sender.send(
                row.chat_id,
                lambda: self.bot.send_message(self.runtime.locks.resolve(row.chat_id), message),
                priority=Priority.CHALLENGE,
            )
            if sent is not None:
                if not result:
                    await self.runtime.challenges.set_message(
                        row.chat_id, row.id, sent.message_id, sent.chat.id
                    )
                async with self.runtime.locks.hold(row.chat_id):
                    async with self.sessions.begin() as session:
                        current = await session.get(Challenge, row.id)
                        if current:
                            setattr(current, field, now)
                            current.announce_retry_at = None
            else:
                async with self.sessions.begin() as session:
                    current = await session.get(Challenge, row.id)
                    if current:
                        current.announce_retry_at = now + timedelta(minutes=10)
            return sent

    async def post(self, row, now):
        if row.kind == "season":
            await self.runtime.seasons.recover(row, now)
            return
        generation = self.sender.generations.get(row.chat_id, 0)
        key = (self.runtime.locks.resolve(row.chat_id), row.kind, row.local_date)
        async with self.sessions() as session:
            chat = await session.get(Chat, key[0])
        if (
            not fresh(row.claimed_at, now)
            or not chat
            or not chat.is_active
            or not chat.bot_is_admin
        ):
            async with self.sessions.begin() as session:
                stored = await session.get(ScheduledPost, key)
                if stored and stored.sent_at is None:
                    stored.status = "skipped"
            return
        markup = None
        if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end):
            async with self.sessions.begin() as session:
                stored = await session.get(ScheduledPost, key)
                if stored:
                    stored.retry_at = min(
                        after_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end),
                        row.claimed_at + WINDOW + timedelta(microseconds=1),
                    )
            return
        payload = None
        if row.kind == "daily":
            item = next(
                (
                    item
                    for item in self.runtime.content.banks["daily_messages"]
                    if item["key"] == row.content_key
                ),
                None,
            )
            if item is None:
                async with self.sessions.begin() as session:
                    stored = await session.get(ScheduledPost, key)
                    if stored:
                        stored.status = "skipped"
                return
            message = texts.daily_post(item["text"], chat.title)
        else:
            from datetime import datetime, time
            from zoneinfo import ZoneInfo

            since = datetime.combine(row.local_date, time(), ZoneInfo(chat.tz))
            until = min(since + timedelta(days=7), now)
            async with self.sessions() as session:
                data = await summary(session, chat.id, since, until)
            payload = await self.runtime.cards.weekly(row.local_date, data)
            message = texts.weekly_summary(
                row.local_date, data, self.instagram, compact=payload is not None
            )
            markup = add_to_group_keyboard(self.username)
        target = self.runtime.locks.resolve(row.chat_id)
        if generation != self.sender.generations.get(row.chat_id, 0):
            return
        if payload is None:

            def operation():
                return self.bot.send_message(target, message, reply_markup=markup)
        else:

            def operation():
                return self.bot.send_photo(
                    target,
                    BufferedInputFile(payload, filename="oqibat-weekly.png"),
                    caption=message,
                    reply_markup=markup,
                )

        sent = await self.sender.send(target, operation, priority=Priority.BULK)
        if sent is not None:
            async with self.runtime.locks.hold(target):
                async with self.sessions.begin() as session:
                    stored = await session.get(ScheduledPost, (target, row.kind, row.local_date))
                    if stored:
                        stored.sent_at = stored.posted_at = sent.date
                        stored.status, stored.message_id, stored.origin_chat_id = (
                            "sent",
                            sent.message_id,
                            sent.chat.id,
                        )
            if row.kind == "daily":
                self.runtime.daily.posts[target] = (
                    row.local_date,
                    sent.message_id,
                    sent.date,
                    chat.tz,
                )
        else:
            async with self.sessions.begin() as session:
                stored = await session.get(ScheduledPost, key)
                if stored:
                    stored.retry_at = now + timedelta(minutes=10)

    async def tick(self, now=None):
        now = now or utc_now()
        async with self.lock:
            for result in (False, True):
                field = Challenge.result_announced_at if result else Challenge.assigned_announced_at
                skip = Challenge.result_skipped_at if result else Challenge.assigned_skipped_at
                async with self.sessions() as session:
                    state = (
                        Challenge.status.in_(["done", "missed", "cancelled"]) if result else True
                    )
                    ids = (
                        await session.scalars(
                            select(Challenge.id)
                            .where(
                                field.is_(None),
                                skip.is_(None),
                                state,
                                or_(
                                    Challenge.announce_retry_at.is_(None),
                                    Challenge.announce_retry_at <= now,
                                ),
                            )
                            .order_by(Challenge.id)
                            .limit(500)
                        )
                    ).all()
                for key in ids:
                    try:
                        await self.challenge(key, result=result, now=now)
                    except Exception:
                        logger.exception("Challenge announcement recovery failed for %s", key)
            async with self.sessions() as session:
                rows = (
                    await session.scalars(
                        select(ScheduledPost)
                        .where(
                            ScheduledPost.sent_at.is_(None),
                            ScheduledPost.status.in_(["reserved", "failed"]),
                            or_(ScheduledPost.retry_at.is_(None), ScheduledPost.retry_at <= now),
                        )
                        .order_by(ScheduledPost.claimed_at)
                        .limit(500)
                    )
                ).all()
            for row in rows:
                try:
                    await self.post(row, now)
                except Exception:
                    logger.exception("Post recovery failed for chat %s", row.chat_id)
