"""Explicit owner diagnostics; no game state or scoring is created."""

import asyncio
import time
from collections import OrderedDict

from aiogram.types import BufferedInputFile
from sqlalchemy import select

from bot import texts
from bot.db.models import Chat, GameSession
from bot.services.cards import render_card
from bot.services.sender import Priority


class LiveTools:
    def __init__(self, runtime, bot):
        self.runtime, self.bot, self.active = runtime, bot, set()
        self.pin_targets = OrderedDict()

    def owner(self, message):
        return bool(
            message.from_user
            and not message.from_user.is_bot
            and message.chat.type in {"group", "supergroup"}
            and message.from_user.id == self.runtime.owner_tools.owner_id
        )

    async def fast(self, message, value):
        if not self.owner(message):
            return texts.OWNER_ONLY
        if value not in {"on", "off"}:
            return texts.FAST_USAGE
        enabled = value == "on"
        async with self.runtime.locks.hold(message.chat.id) as chat_id:
            async with self.runtime.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if not chat or not chat.is_active or not chat.bot_is_admin:
                    return texts.NEED_ADMIN
                active = await session.scalar(
                    select(GameSession.id)
                    .where(
                        GameSession.chat_id == chat_id, GameSession.status.in_(["lobby", "running"])
                    )
                    .limit(1)
                )
                if active and chat.fast_mode != enabled:
                    return texts.FAST_BUSY
                chat.fast_mode = enabled
        return texts.FAST_ON if enabled else texts.FAST_OFF

    def start(self, message):
        if not self.owner(message):
            return texts.OWNER_ONLY
        if message.chat.id in self.active:
            return texts.SELFTEST_BUSY
        self.active.add(message.chat.id)
        self.runtime.effects.start(self.run(message.chat.id))
        return None

    async def run(self, chat_id):
        try:
            await self._run(chat_id)
        finally:
            self.active.discard(chat_id)

    def observe_pin(self, message):
        pinned = message.pinned_message
        if not pinned or not message.from_user or message.from_user.id != self.bot.id:
            return
        expires = self.pin_targets.pop((message.chat.id, pinned.message_id), 0)
        if expires and (expires > time.monotonic() or message.chat.id in self.active):
            self.runtime.effects.start(self.remove_pin_notice(message))

    async def remove_pin_notice(self, message):
        await self.runtime.sender.send(
            message.chat.id,
            lambda: self.bot.delete_message(message.chat.id, message.message_id),
            priority=Priority.GAME,
        )

    async def _run(self, chat_id):
        sender, bot = self.runtime.sender, self.bot
        results, messages = [], set()
        cancelled = False

        async def action(key, operation):
            try:
                sent = await sender.send(chat_id, operation, priority=Priority.GAME)
                ok = sent is not None and sent is not False
            except Exception:
                sent, ok = None, False
            results.append((key, ok))
            if getattr(sent, "message_id", None):
                messages.add(sent.message_id)
            return sent

        async def cleanup():
            success = True
            for message_id in tuple(messages):
                try:
                    deleted = await sender.send(
                        chat_id,
                        lambda message_id=message_id: bot.delete_message(chat_id, message_id),
                        priority=Priority.GAME,
                    )
                except Exception:
                    deleted = False
                success = success and deleted is True
            results.append(("cleanup", success))

        try:
            member = await sender.send(
                chat_id, lambda: bot.get_chat_member(chat_id, bot.id), priority=Priority.GAME
            )
            admin = bool(member and member.status in {"creator", "administrator"})
            delete = admin and bool(
                getattr(member, "can_delete_messages", False) or member.status == "creator"
            )
            pin = admin and bool(
                getattr(member, "can_pin_messages", False) or member.status == "creator"
            )
            results.extend([("admin", admin), ("delete_right", delete), ("pin_right", pin)])
            if admin and delete and pin:
                sent = await action("send", lambda: bot.send_message(chat_id, texts.SELFTEST_START))
                if sent:
                    await action(
                        "edit",
                        lambda: bot.edit_message_text(
                            texts.SELFTEST_EDIT, chat_id=chat_id, message_id=sent.message_id
                        ),
                    )
                    removed = await action(
                        "delete", lambda: bot.delete_message(chat_id, sent.message_id)
                    )
                    if removed is True:
                        messages.discard(sent.message_id)
                else:
                    results.extend([("edit", False), ("delete", False)])
                poll = await action(
                    "poll",
                    lambda: bot.send_poll(
                        chat_id,
                        texts.SELFTEST_POLL,
                        list(texts.SELFTEST_OPTIONS),
                        type="regular",
                        is_anonymous=True,
                        open_period=5,
                    ),
                )
                if poll:
                    await action("stop_poll", lambda: bot.stop_poll(chat_id, poll.message_id))
                else:
                    results.append(("stop_poll", False))
                await action(
                    "quiz",
                    lambda: bot.send_poll(
                        chat_id,
                        texts.SELFTEST_QUIZ,
                        list(texts.SELFTEST_OPTIONS),
                        type="quiz",
                        is_anonymous=True,
                        correct_option_ids=[1],
                        open_period=5,
                        allows_revoting=False,
                    ),
                )
                await action(
                    "dice", lambda: bot.send_dice(chat_id, emoji=texts.GAME_EMOJIS["duel"])
                )
                try:
                    payload = await asyncio.to_thread(
                        render_card, texts.SELFTEST_CARD, [], self.runtime.cards.instagram
                    )
                except Exception:
                    payload = None
                if payload:
                    await action(
                        "spoiler",
                        lambda: bot.send_photo(
                            chat_id,
                            BufferedInputFile(payload, filename="oqibat-spoiler-test.png"),
                            has_spoiler=True,
                            caption=texts.SELFTEST_CARD,
                        ),
                    )
                    card = await action(
                        "card",
                        lambda: bot.send_photo(
                            chat_id,
                            BufferedInputFile(payload, filename="oqibat-card-test.png"),
                            caption=texts.SELFTEST_CARD,
                        ),
                    )
                else:
                    results.extend([("spoiler", False), ("card", False)])
                    card = None
                if card:
                    self.pin_targets[(chat_id, card.message_id)] = time.monotonic() + 60
                    if len(self.pin_targets) > 1000:
                        self.pin_targets.popitem(last=False)
                    await action(
                        "pin",
                        lambda: bot.pin_chat_message(
                            chat_id, card.message_id, disable_notification=True
                        ),
                    )
                    if (chat_id, card.message_id) in self.pin_targets:
                        self.pin_targets[(chat_id, card.message_id)] = time.monotonic() + 60
                    await action(
                        "unpin",
                        lambda: bot.unpin_chat_message(chat_id=chat_id, message_id=card.message_id),
                    )
                else:
                    results.extend([("pin", False), ("unpin", False)])
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            if cancelled:
                try:
                    async with asyncio.timeout(3):
                        await cleanup()
                except (TimeoutError, asyncio.CancelledError):
                    pass
            else:
                await cleanup()
        await sender.send(
            chat_id,
            lambda: bot.send_message(chat_id, texts.selftest_report(results)),
            priority=Priority.GAME,
        )
