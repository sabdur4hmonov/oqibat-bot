"""Read-only opt-in Stories. Source rows and recipient consent are checked again at upload."""

import time
from collections import OrderedDict
from datetime import date, datetime, timedelta
from datetime import time as local_time
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BufferedInputFile

from bot import texts
from bot.db.models import Chat, GameSession, ScheduledPost
from bot.services.game_catalog import trusted_button
from bot.services.seasons import month_bounds
from bot.services.sender import Priority
from bot.services.weekly import summary
from bot.utils.admin import member_is_active


class Stories:
    def __init__(self, runtime, bot):
        self.runtime, self.bot = runtime, bot
        self.recent = OrderedDict()

    async def source(self, query):
        runtime = self.runtime
        if (
            not trusted_button(query, self.bot)
            or query.message.chat.id >= 0
            or query.from_user.id in runtime.owner_tools.deleted
        ):
            return None
        chat_id, message_id = query.message.chat.id, query.message.message_id
        parts = query.data.split(":")
        async with runtime.sessions() as session:
            chat = await session.get(Chat, chat_id)
            if not chat or not chat.is_active or not chat.bot_is_admin:
                return None
            try:
                if len(parts) == 3 and parts[1] == "g":
                    game = await session.get(GameSession, int(parts[2]))
                    if (
                        not game
                        or game.chat_id != chat_id
                        or game.state.get("erased")
                        or game.state.get("result_card_origin_chat_id") != chat_id
                        or game.state.get("result_card_message_id") != message_id
                    ):
                        return None
                    data = texts.game_card_data(game)
                    if data:
                        return (data["title"], data["entries"], None, game.game)
                elif len(parts) == 4 and parts[1] in {"w", "s"}:
                    if int(parts[2]) != chat_id:
                        return None
                    day = date.fromisoformat(parts[3])
                    kind = "weekly" if parts[1] == "w" else "season"
                    post = await session.get(ScheduledPost, (chat_id, kind, day))
                    if (
                        not post
                        or not post.sent_at
                        or post.origin_chat_id != chat_id
                        or post.message_id != message_id
                    ):
                        return None
                    since = datetime.combine(day, local_time(), ZoneInfo(chat.tz))
                    if kind == "season":
                        since, until = month_bounds(since, chat.tz)
                        entries = await runtime.points.top(chat_id, since, until)
                        return (texts.SEASON_TITLE, entries[:5], texts.season_month(day), kind)
                    data = await summary(session, chat_id, since, since + timedelta(days=7))
                    return (texts.CARD_WEEKLY_TITLE, data["top"][:5], texts.card_week(day), kind)
            except (ValueError, OverflowError):
                return None
        return None

    async def callback(self, query):
        runtime, sender = self.runtime, self.runtime.sender
        source = await self.source(query)
        if source and runtime.cards.enabled:
            try:
                source_allowed = member_is_active(
                    await self.bot.get_chat_member(query.message.chat.id, query.from_user.id)
                )
            except TelegramRetryAfter as error:
                sender.limiter.pause(None, sender.clock.now() + error.retry_after)
                sender._wake.set()
                source_allowed = False
            except Exception:
                source_allowed = False
        else:
            source_allowed = False
        if not source_allowed:
            await sender.answer_callback_query(
                self.bot, query.id, text=texts.STORY_FAILED, show_alert=True
            )
            return
        await sender.answer_callback_query(self.bot, query.id, text=texts.STORY_WAIT)
        key = (query.from_user.id, query.data, query.message.chat.id)
        now = time.monotonic()
        if self.recent.get(key, 0) > now:
            return
        self.recent[key] = now + 10
        self.recent.move_to_end(key)
        if len(self.recent) > 20_000:
            self.recent.popitem(last=False)
        runtime.effects.start(self.send(query, source))

    async def send(self, query, source):
        title, entries, subtitle, kind = source
        runtime = self.runtime
        payload = await runtime.cards.ranked(
            title, entries, subtitle, kind=kind, story=True, chat_id=query.message.chat.id
        )
        if not payload:
            return

        async def upload():
            if await self.source(query) != source:
                return None
            return await self.bot.send_photo(
                query.from_user.id,
                BufferedInputFile(payload, filename="oqibat-story.png"),
                caption=texts.card_watermark(runtime.cards.instagram),
            )

        await runtime.sender.send(query.from_user.id, upload, priority=Priority.GAME)
