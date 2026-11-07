"""Persistent aliases, atomic row movement and synchronized runtime cache rekeying."""

import logging

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from sqlalchemy import select

from bot.db.models import Chat
from bot.db.repo.migrations import ChatMigrationRepository

logger = logging.getLogger(__name__)


class ChatIdMiddleware(BaseRequestMiddleware):
    def __init__(self, resolve) -> None:
        self.resolve = resolve

    async def __call__(self, make_request, bot, method):
        chat_id = getattr(method, "chat_id", None)
        canonical = self.resolve(chat_id)
        if canonical != chat_id:
            method = method.model_copy(update={"chat_id": canonical})
        return await make_request(bot, method)


class ChatMigrations:
    def __init__(self, runtime, bot) -> None:
        self.runtime = runtime
        self.repo = ChatMigrationRepository(runtime.sessions, runtime.locks)
        self.aliases: dict[int, int] = {}
        self.times = {}
        if hasattr(bot, "session"):
            bot.session.middleware(ChatIdMiddleware(self.resolve))

    def resolve(self, chat_id):
        seen = set()
        while chat_id in self.aliases:
            if chat_id in seen:
                raise ValueError("Cyclic chat migration aliases")
            seen.add(chat_id)
            chat_id = self.aliases[chat_id]
        return chat_id

    async def load(self) -> None:
        async with self.runtime.sessions() as session:
            rows = (
                await session.execute(
                    select(Chat.id, Chat.migrated_to_chat_id, Chat.updated_at).where(
                        Chat.migrated_to_chat_id.is_not(None)
                    )
                )
            ).all()
        self.aliases = {old: new for old, new, _ in rows}
        for _, target, updated in rows:
            canonical = self.resolve(target)
            self.times[canonical] = max(updated, self.times.get(canonical, updated))

    async def migrate(self, old_id: int, new_id: int) -> None:
        if type(old_id) is not int or type(new_id) is not int or old_id >= 0 or new_id >= 0:
            raise ValueError("Chat migration requires two group IDs")
        source, target = self.resolve(old_id), self.resolve(new_id)
        if source == target:
            return
        runtime = self.runtime
        await runtime.activity.flush()
        await runtime.checkins.flush()
        async with runtime.activity._flush_lock, runtime.checkins._lock:
            result = await self.repo.migrate(source, target)
            self.aliases[source] = target
            self.times[target] = result["migrated_at"]
            self._rekey(source, target, result)
        logger.info("Telegram chat migrated atomically: %s -> %s", source, target)

    def _rekey(self, old_id, new_id, result) -> None:
        runtime = self.runtime
        members = {}
        for (chat, user), seen in runtime.activity.members.items():
            key = (new_id if chat == old_id else chat, user)
            members[key] = max(seen, members.get(key, seen))
        runtime.activity.members = members
        awards = {}
        for (chat, user, day), event in runtime.checkins.pending.items():
            canonical = new_id if chat == old_id else chat
            awards[(canonical, user, day)] = {**event, "chat_id": canonical}
        runtime.checkins.pending = awards
        for chat_id in (old_id, new_id):
            for user in runtime.participants.for_chat(chat_id):
                runtime.participants.set(chat_id, user, False)
        for user in result["participants"]:
            runtime.participants.set(new_id, user, True)
        for challenge_id in (*runtime.pending.for_chat(old_id), *runtime.pending.for_chat(new_id)):
            runtime.pending.remove(challenge_id)
        for challenge in result["pending"]:
            runtime.pending.add(
                challenge.id,
                new_id,
                challenge.user_id,
                challenge.kind,
                challenge.deadline_at,
                challenge.created_at,
            )
            runtime.pending.message_ids[challenge.id] = (
                0 if challenge.origin_chat_id not in {None, new_id} else challenge.message_id
            )
        runtime.admins.invalidate(old_id)
        runtime.admins.invalidate(new_id)
        runtime.daily.posts.pop(old_id, None)
        post = result["post"]
        if post and post.posted_at is not None:
            boundary = 0 if post.origin_chat_id not in {None, new_id} else post.message_id
            runtime.daily.posts[new_id] = (
                post.local_date,
                boundary,
                post.posted_at,
                result["chat"].tz,
            )
        old_checked = runtime.daily.checked.pop(old_id, None)
        current = runtime.daily.checked.get(new_id)
        if old_checked:
            if current is None or old_checked[0] > current[0]:
                runtime.daily.checked[new_id] = old_checked
            elif old_checked[0] == current[0]:
                current[1].update(old_checked[1])
        old_inflight = runtime.daily.in_flight.pop(old_id, None)
        if old_inflight is not None:
            runtime.daily.in_flight.setdefault(new_id, {}).update(old_inflight)
        for chat, user in list(runtime.setting_prompts.pending):
            if chat == old_id:
                runtime.setting_prompts.pending.pop((chat, user))
        cache = getattr(runtime, "game_cache", None)
        if cache is not None:
            for game in list(cache.for_chat(old_id)) + list(cache.for_chat(new_id)):
                from dataclasses import replace

                cache.sync(replace(game, status="cancelled"))
            for game in result["games"]:
                cache.sync(game)
