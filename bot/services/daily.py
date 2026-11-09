"""Reserved-once daily delivery and memory-only incoming check-in detection."""

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot import texts
from bot.db.models import Challenge, Chat, ContentUsage, ScheduledPost, User
from bot.services.content import choose_content
from bot.services.locks import ChatLocks
from bot.services.sender import Priority
from bot.utils.time import after_quiet, is_quiet, utc_now

logger = logging.getLogger(__name__)


class DailyService:
    def __init__(self, sessions, bot, sender, content, participants, checkins, locks=None) -> None:
        self.sessions, self.bot, self.sender, self.content = sessions, bot, sender, content
        self.participants, self.checkins = participants, checkins
        self.locks = locks or ChatLocks()
        self.resolve_chat = lambda chat_id: self.locks.resolve(chat_id)
        self.posts: dict[int, tuple] = {}
        self.checked: dict[int, tuple] = {}
        self.in_flight: dict[int, dict] = {}

    async def load(self) -> None:
        async with self.sessions() as session:
            posts = (
                await session.execute(
                    select(ScheduledPost, Chat.tz)
                    .join(Chat)
                    .where(
                        ScheduledPost.kind == "daily",
                        ScheduledPost.status == "sent",
                        ScheduledPost.posted_at >= utc_now() - timedelta(days=2),
                    )
                    .order_by(ScheduledPost.posted_at)
                )
            ).all()
        for post, tz in posts:
            boundary = 0 if post.origin_chat_id not in {None, post.chat_id} else post.message_id
            self.posts[post.chat_id] = (post.local_date, boundary, post.posted_at, tz)

    async def _reserve(self, chat, now):
        async with self.locks.hold(chat.id) as chat_id:
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if (
                    chat is None
                    or not chat.is_active
                    or not chat.bot_is_admin
                    or not chat.daily_enabled
                ):
                    return True
                if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end):
                    return after_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end)
                date = now.astimezone(ZoneInfo(chat.tz)).date()
                insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
                used = dict(
                    (
                        await session.execute(
                            select(ContentUsage.content_key, ContentUsage.used_at).where(
                                ContentUsage.chat_id == chat_id
                            )
                        )
                    ).all()
                )
                content = choose_content(self.content.banks["daily_messages"], used)
                if content is None:
                    logger.warning("Daily content bank empty; chat %s skipped", chat_id)
                    return True
                statement = insert(ScheduledPost).values(
                    chat_id=chat_id,
                    origin_chat_id=chat_id,
                    kind="daily",
                    local_date=date,
                    content_key=content["key"],
                    status="reserved",
                    claimed_at=now,
                )
                result = await session.execute(
                    statement.on_conflict_do_nothing(
                        index_elements=[
                            ScheduledPost.chat_id,
                            ScheduledPost.kind,
                            ScheduledPost.local_date,
                        ]
                    )
                )
                if result.rowcount == 0:
                    return True
                usage = insert(ContentUsage).values(
                    chat_id=chat_id, content_key=content["key"], used_at=now
                )
                await session.execute(
                    usage.on_conflict_do_update(
                        index_elements=[ContentUsage.chat_id, ContentUsage.content_key],
                        set_={"used_at": now},
                    )
                )
                debtors = (
                    await session.execute(
                        select(Challenge.id, Challenge.user_id, User.first_name)
                        .join(User, User.id == Challenge.user_id)
                        .where(
                            Challenge.chat_id == chat_id,
                            Challenge.status == "missed",
                            Challenge.miss_announced_at.is_(None),
                        )
                        .order_by(Challenge.resolved_at, Challenge.id)
                        .limit(5)
                    )
                ).all()
            return chat, date, content, debtors

    async def post(self, chat, now):
        reservation = await self._reserve(chat, now)
        if not isinstance(reservation, tuple):
            return reservation
        chat, date, content, debtors = reservation
        chat_id = chat.id
        self.in_flight[chat_id] = {}
        try:
            sent = await self.sender.send(
                chat_id,
                lambda: self.bot.send_message(
                    self.resolve_chat(chat_id),
                    texts.daily_post(content["text"], chat.title)
                    + texts.debtors_suffix([(row.user_id, row.first_name) for row in debtors]),
                ),
                priority=Priority.BULK,
            )
        finally:
            recent = self.in_flight.pop(chat_id, {})
            canonical = self.resolve_chat(chat_id)
            if canonical != chat_id:
                recent.update(self.in_flight.pop(canonical, {}))
        posted_at = (
            getattr(sent, "date", utc_now()).replace(microsecond=0) if sent is not None else None
        )
        origin = getattr(getattr(sent, "chat", None), "id", self.resolve_chat(chat_id))
        if sent is not None:
            canonical = self.resolve_chat(chat_id)
            boundary = sent.message_id if origin == canonical else 0
            self.posts[canonical] = (date, boundary, posted_at, chat.tz)
            for message in recent.values():
                self.observe(message)
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                await session.execute(
                    update(ScheduledPost)
                    .where(
                        ScheduledPost.chat_id == chat_id,
                        ScheduledPost.kind == "daily",
                        ScheduledPost.local_date == date,
                    )
                    .values(
                        status="sent" if sent is not None else "failed",
                        sent_at=posted_at,
                        retry_at=None if sent is not None else now + timedelta(minutes=10),
                        posted_at=posted_at,
                        origin_chat_id=origin,
                        message_id=sent.message_id if sent is not None else None,
                    )
                )
                if sent is not None and debtors:
                    await session.execute(
                        update(Challenge)
                        .where(Challenge.id.in_(row.id for row in debtors))
                        .values(miss_announced_at=posted_at)
                    )
            if sent is not None:
                boundary = sent.message_id if origin == chat_id else 0
                self.posts[chat_id] = (date, boundary, posted_at, chat.tz)
        return sent is not None

    def observe(self, message) -> None:
        chat_id = self.resolve_chat(message.chat.id)
        if message.from_user is None or not self.participants.contains(
            chat_id, message.from_user.id
        ):
            return
        post = self.posts.get(chat_id)
        if chat_id in self.in_flight:
            recent = self.in_flight[chat_id]
            if len(recent) < 1000 or message.from_user.id in recent:
                recent[message.from_user.id] = message
        if (
            post is None
            or post[1] is None
            or message.message_id <= post[1]
            or message.date < post[2]
        ):
            return
        if message.date.astimezone(ZoneInfo(post[3])).date() != post[0]:
            return
        day, users = self.checked.setdefault(chat_id, (post[0], set()))
        if day != post[0]:
            users = set()
            self.checked[chat_id] = (post[0], users)
        if message.from_user.id not in users:
            users.add(message.from_user.id)
            self.checkins.add(chat_id, message.from_user.id, post[0])
            return True
        return False
