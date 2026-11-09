"""Owner aggregates and confirmed self-deletion; ordinary messages stay SQL-free."""

import asyncio
import secrets
import time
from contextlib import AsyncExitStack
from datetime import timedelta

from sqlalchemy import delete, func, select

from bot import texts
from bot.db.models import Challenge, Chat, GameSession, Membership, PointEvent, User
from bot.utils.time import utc_now


def references(value, user):
    if isinstance(value, dict):
        identities = {"target", "host", "winner", "starter", "challenger", "opponent", "user_id"}
        return (
            str(user) in value
            or any(value.get(key) == user for key in identities)
            or any(references(item, user) for item in value.values())
        )
    if isinstance(value, list):
        return any(references(item, user) for item in value)
    return isinstance(value, str) and value == str(user)


class OwnerTools:
    def __init__(self, runtime, owner_id):
        self.runtime, self.owner_id = runtime, owner_id
        self.confirmations = {}
        self.lock = asyncio.Lock()
        self.deleted = set()

    def confirm(self, user):
        now = time.monotonic()
        self.confirmations = {
            key: value for key, value in self.confirmations.items() if value[1] > now
        }
        token = secrets.token_hex(8)
        self.confirmations[user] = (token, now + 300)
        return token

    async def stats(self):
        now = utc_now()
        async with self.runtime.sessions() as session:
            groups = await session.scalar(
                select(func.count()).select_from(Chat).where(Chat.is_active.is_(True), Chat.id < 0)
            )
            opted = await session.scalar(
                select(func.count(func.distinct(Membership.user_id))).where(
                    Membership.opted_in.is_(True), Membership.is_active.is_(True)
                )
            )
            active = await session.scalar(
                select(func.count(func.distinct(Membership.user_id))).where(
                    Membership.last_seen_at >= now - timedelta(hours=24)
                )
            )
            games = (
                await session.execute(
                    select(GameSession.game, func.count())
                    .where(GameSession.created_at >= now - timedelta(days=7))
                    .group_by(GameSession.game)
                )
            ).all()
        buffered = {
            user
            for (_, user), seen in self.runtime.activity.members.items()
            if seen >= now - timedelta(hours=24)
        }
        # Flush before owner stats in the handler, so these aggregates use committed activity.
        return {
            "groups": groups,
            "opted": opted,
            "active": active,
            "games": dict(games),
            "queue": self.runtime.sender.queue_length,
            "tick": self.runtime.scheduler.last_tick_duration,
            "buffered": len(buffered),
        }

    async def erase(self, user, token):
        async with self.lock:
            stored = self.confirmations.pop(user, None)
            if (
                stored is None
                or stored[1] < time.monotonic()
                or not secrets.compare_digest(stored[0], token)
            ):
                return False
            runtime = self.runtime
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(runtime.activity._flush_lock)
                await stack.enter_async_context(runtime.checkins._lock)
                async with runtime.sessions() as session:
                    chats = set(
                        (
                            await session.scalars(
                                select(Membership.chat_id).where(Membership.user_id == user)
                            )
                        ).all()
                    )
                    chats.update(
                        (
                            await session.scalars(
                                select(PointEvent.chat_id).where(PointEvent.user_id == user)
                            )
                        ).all()
                    )
                    chats.update(
                        (
                            await session.scalars(
                                select(GameSession.chat_id).where(GameSession.started_by == user)
                            )
                        ).all()
                    )
                for chat in sorted(chats):
                    await stack.enter_async_context(runtime.locks.hold(chat))
                runtime.sender.discard_chats(chats | {user})
                self.deleted.add(user)
                runtime.activity.users.pop(user, None)
                runtime.activity.names.pop(user, None)
                runtime.activity.members = {
                    key: value for key, value in runtime.activity.members.items() if key[1] != user
                }
                runtime.checkins.pending = {
                    key: value for key, value in runtime.checkins.pending.items() if key[1] != user
                }
                async with runtime.sessions.begin() as session:
                    # Stream rows: privacy commands are rare, but must not load all history at once.
                    query = (
                        select(GameSession)
                        .where(GameSession.chat_id.in_(chats) | (GameSession.started_by == user))
                        .execution_options(yield_per=100)
                    )
                    games = await session.stream_scalars(query)
                    remove_games = []
                    async for game in games:
                        if game.started_by == user or references(game.state, user):
                            remove_games.append(game.id)
                            cached = runtime.game_cache.get(game.id)
                            if cached:
                                from dataclasses import replace

                                runtime.game_cache.sync(replace(cached, status="cancelled"))
                            runtime.mafia_game.last_render = {
                                key: value
                                for key, value in runtime.mafia_game.last_render.items()
                                if key[0] != game.id
                            }
                    if remove_games:
                        if await session.get(User, 0) is None:
                            session.add(User(id=0, first_name=texts.ERASED_NAME))
                            await session.flush()
                        await session.execute(
                            delete(Challenge).where(Challenge.game_session_id.in_(remove_games))
                        )
                        # Keep anonymous IDs so SQLite cannot reuse game refs in others' ledger.
                        from sqlalchemy import update

                        await session.execute(
                            update(GameSession)
                            .where(GameSession.id.in_(remove_games))
                            .values(
                                started_by=0,
                                state={"erased": True},
                                status="cancelled",
                                phase_deadline_at=None,
                            )
                        )
                    await session.execute(delete(Challenge).where(Challenge.user_id == user))
                    await session.execute(delete(PointEvent).where(PointEvent.user_id == user))
                    await session.execute(delete(Membership).where(Membership.user_id == user))
                    await session.execute(delete(User).where(User.id == user))
                for game_id in remove_games:
                    cached = runtime.game_cache.get(game_id)
                    if cached:
                        from dataclasses import replace

                        runtime.game_cache.sync(replace(cached, status="cancelled"))
                for challenge_id, key in tuple(runtime.pending._ids.items()):
                    if key[1] == user or challenge_id not in runtime.pending._details:
                        runtime.pending.remove(challenge_id)
                # Rebuild pending after linked game-task deletion, and remove cached consent.
                await runtime.pending.load(runtime.sessions)
                for chat in chats:
                    runtime.setting_prompts.clear(chat, user)
                    runtime.admins.invalidate(chat)
                    runtime.participants.set(chat, user, False)
                    if chat in runtime.daily.checked:
                        runtime.daily.checked[chat][1].discard(user)
                    runtime.daily.in_flight.get(chat, {}).pop(user, None)
                runtime.challenge_service.early_messages = {
                    key: message
                    for key, message in runtime.challenge_service.early_messages.items()
                    if message.from_user.id != user
                }
                for answers in runtime.easy_games.early_answers.values():
                    answers.pop(user, None)
            return True
