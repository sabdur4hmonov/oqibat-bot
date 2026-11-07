"""Reserved-once daily delivery and memory-only incoming check-in detection."""

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot import texts
from bot.db.models import Chat, ContentUsage, ScheduledPost
from bot.services.content import choose_content
from bot.services.sender import Priority
from bot.utils.time import after_quiet, is_quiet, utc_now

logger = logging.getLogger(__name__)


class DailyService:
    def __init__(self, sessions, bot, sender, content, participants, checkins) -> None:
        self.sessions, self.bot, self.sender, self.content = sessions, bot, sender, content
        self.participants, self.checkins = participants, checkins
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
            self.posts[post.chat_id] = (post.local_date, post.message_id, post.posted_at, tz)

    async def post(self, chat, now):
        if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end):
            return after_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end)
        date = now.astimezone(ZoneInfo(chat.tz)).date()
        async with self.sessions.begin() as session:
            insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
            used = dict(
                (
                    await session.execute(
                        select(ContentUsage.content_key, ContentUsage.used_at).where(
                            ContentUsage.chat_id == chat.id
                        )
                    )
                ).all()
            )
            content = choose_content(self.content.banks["daily_messages"], used)
            if content is None:
                logger.warning("Daily content bank empty; chat %s skipped", chat.id)
                return True
            statement = (
                insert(ScheduledPost)
                .values(
                    chat_id=chat.id,
                    kind="daily",
                    local_date=date,
                    content_key=content["key"],
                    status="reserved",
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        ScheduledPost.chat_id,
                        ScheduledPost.kind,
                        ScheduledPost.local_date,
                    ]
                )
            )
            if (await session.execute(statement)).rowcount == 0:
                return True
            usage = insert(ContentUsage).values(
                chat_id=chat.id, content_key=content["key"], used_at=now
            )
            await session.execute(
                usage.on_conflict_do_update(
                    index_elements=[ContentUsage.chat_id, ContentUsage.content_key],
                    set_={"used_at": now},
                )
            )
        self.in_flight[chat.id] = {}
        try:
            sent = await self.sender.send(
                chat.id,
                lambda: self.bot.send_message(
                    chat.id, texts.daily_post(content["text"], chat.title)
                ),
                priority=Priority.BULK,
            )
        finally:
            recent = self.in_flight.pop(chat.id, {})
        posted_at = (
            getattr(sent, "date", utc_now()).replace(microsecond=0) if sent is not None else None
        )
        if sent is not None:
            self.posts[chat.id] = (date, sent.message_id, posted_at, chat.tz)
            for message in recent.values():
                self.observe(message)
        async with self.sessions.begin() as session:
            await session.execute(
                update(ScheduledPost)
                .where(
                    ScheduledPost.chat_id == chat.id,
                    ScheduledPost.kind == "daily",
                    ScheduledPost.local_date == date,
                )
                .values(
                    status="sent" if sent is not None else "failed",
                    posted_at=posted_at,
                    message_id=sent.message_id if sent is not None else None,
                )
            )
        if sent is not None:
            self.posts[chat.id] = (date, sent.message_id, posted_at, chat.tz)
        return True

    def observe(self, message) -> None:
        if message.from_user is None or not self.participants.contains(
            message.chat.id, message.from_user.id
        ):
            return
        post = self.posts.get(message.chat.id)
        if message.chat.id in self.in_flight:
            recent = self.in_flight[message.chat.id]
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
        day, users = self.checked.setdefault(message.chat.id, (post[0], set()))
        if day != post[0]:
            users = set()
            self.checked[message.chat.id] = (post[0], users)
        if message.from_user.id not in users:
            users.add(message.from_user.id)
            self.checkins.add(message.chat.id, message.from_user.id, post[0])
