"""Shared services and lifecycle for both polling and webhook transports."""

import asyncio
import logging

from aiogram import BaseMiddleware

from bot.db.repo.challenges import ChallengeRepository
from bot.db.repo.games import GameSessionRepository
from bot.db.repo.groups import GroupRepository
from bot.services.achievements import Achievements
from bot.services.activity import ActivityBuffer
from bot.services.admin_cache import AdminCache
from bot.services.challenges import ChallengeService
from bot.services.content import ContentLibrary
from bot.services.daily import DailyService
from bot.services.easy_games import EasyGames
from bot.services.effects import Effects
from bot.services.game_cache import GameCache
from bot.services.game_hub import GameHub
from bot.services.krokodil import Krokodil
from bot.services.locks import ChatLocks
from bot.services.mafia import Mafia
from bot.services.metrics import Metrics
from bot.services.migrations import ChatMigrations
from bot.services.owner import OwnerTools
from bot.services.participation import Participants
from bot.services.penalties import Penalties
from bot.services.pending import PendingChallenges
from bot.services.points import CheckinBuffer, Points
from bot.services.recovery import Recovery
from bot.services.result_cards import ResultCards
from bot.services.scheduler import Scheduler
from bot.services.seasons import Seasons
from bot.services.sender import Sender
from bot.services.settings import SettingPrompts
from bot.services.truth_dare import TruthDare
from bot.services.weekly import Weekly

logger = logging.getLogger(__name__)


class ScaleRuntime:
    def __init__(self, sessions, bot, settings=None) -> None:
        self.activity = ActivityBuffer(sessions)
        self.pending = PendingChallenges()
        self.participants = Participants()
        self.locks = ChatLocks()
        self.checkins = CheckinBuffer(sessions, self.locks)
        self.points = Points(sessions, self.locks)
        self.admins = AdminCache(bot)
        self.metrics = Metrics()
        self.scheduler = Scheduler(sessions)
        self.sender = Sender(sessions, on_forbidden=self.activity.mark_forbidden)
        self.effects = Effects()
        self.game_cache = GameCache()
        self.challenges = ChallengeRepository(sessions, self.pending, self.locks, self.game_cache)
        self.games = GameSessionRepository(sessions, self.locks, self.game_cache, self.pending)
        self.game_hub = GameHub(
            self.games,
            self.game_cache,
            bot,
            self.sender,
            self.admins,
            self.participants,
            self.effects,
        )
        self.groups = GroupRepository(
            sessions, self.locks, self.pending, self.participants, self.game_cache
        )
        self.setting_prompts = SettingPrompts()
        self.content = ContentLibrary()
        self.easy_games = EasyGames(self.game_hub, self.content, sessions)
        self.game_hub.register(("duel", "quiz", "wyr"), self.easy_games)
        self.krokodil_game = Krokodil(self.game_hub, self.content, sessions)
        self.game_hub.register(("krokodil",), self.krokodil_game)
        self.scheduler.hooks["game"] = self.game_hub.advance
        self.daily = DailyService(
            sessions, bot, self.sender, self.content, self.participants, self.checkins, self.locks
        )
        self.scheduler.hooks["daily"] = self.daily.post
        self.weekly = Weekly(sessions, self.locks, bot, self.sender, self.checkins, settings)
        self.scheduler.hooks["weekly"] = self.weekly.post
        self.cards = ResultCards(self.games, bot, self.sender, settings)
        self.game_hub.cards = self.cards
        self.weekly.cards = self.cards
        self.penalties = Penalties(
            bot, self.sender, self.admins, getattr(settings, "owner_id", None)
        )
        self.challenge_service = ChallengeService(
            sessions,
            bot,
            self.sender,
            self.challenges,
            self.pending,
            self.content,
            self.penalties,
            self.effects,
        )
        self.scheduler.hooks["challenge"] = self.challenge_service.scheduled
        self.scheduler.hooks["expire"] = self.challenge_service.expire
        self.truth_dare = TruthDare(self.game_hub, self.content, sessions, self.challenge_service)
        self.game_hub.register(("hyj",), self.truth_dare)
        self.challenges.on_game_resolved = self.truth_dare.challenge_resolved
        self.groups.on_game_resolved = self.truth_dare.challenge_resolved
        self.mafia_game = Mafia(
            self.game_hub, sessions, getattr(settings, "bot_username", "OqibatBot")
        )
        self.game_hub.register(("mafia",), self.mafia_game)
        self.sessions = sessions
        self.recovery = Recovery(self, bot, settings)
        self.owner_tools = OwnerTools(self, getattr(settings, "owner_id", None))
        self.achievements = Achievements(self)
        self.seasons = Seasons(self)
        self.scheduler.hooks["season"] = self.seasons.post
        self.scheduler.maintenance.append(self.achievements.announce)
        self.challenge_service.recovery = self.recovery
        self.scheduler.recovery = self.recovery
        self.stopping = False
        self.tasks = []
        self.migrations = ChatMigrations(self, bot)
        self.locks.resolve = self.migrations.resolve
        self.sender.resolve_chat = self.migrations.resolve
        self.sender.on_migrate = self.migrations.migrate
        self.daily.resolve_chat = self.migrations.resolve

    async def __aenter__(self):
        await self.migrations.load()
        await self.pending.load(self.sessions)
        await self.participants.load(self.sessions)
        await self.daily.load()
        await self.game_cache.load(self.sessions)
        self.mafia_game.load()
        await self.game_hub.recover(list(self.game_cache.records.values()))
        self.tasks = [
            asyncio.create_task(self.activity.run(), name="activity-flush"),
            asyncio.create_task(self.scheduler.run(), name="scheduler-tick"),
            asyncio.create_task(self.scheduler.run_deadlines(), name="deadline-tick"),
            asyncio.create_task(self.checkins.run(), name="checkin-flush"),
            asyncio.create_task(
                self.metrics.run(self.sender, self.scheduler), name="scale-metrics"
            ),
        ]
        return self

    async def __aexit__(self, *args) -> None:
        self.stopping = True
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.effects.close()
        try:
            await self.activity.flush()
            await self.checkins.flush()
        except Exception:
            logger.exception("Shutdown activity flush failed")
        await self.sender.drain(10)
        await self.sender.close()

    def workflow(self) -> dict:
        return {
            "owner_tools": self.owner_tools,
            "achievements": self.achievements,
            "sender": self.sender,
            "activity": self.activity,
            "pending": self.pending,
            "admins": self.admins,
            "chat_locks": self.locks,
            "game_sessions": self.games,
            "challenges": self.challenges,
            "groups": self.groups,
            "setting_prompts": self.setting_prompts,
            "participants": self.participants,
            "checkins": self.checkins,
            "points": self.points,
            "challenge_service": self.challenge_service,
            "migrations": self.migrations,
            "game_hub": self.game_hub,
            "easy_games": self.easy_games,
            "krokodil_game": self.krokodil_game,
            "truth_dare": self.truth_dare,
            "mafia_game": self.mafia_game,
        }


class ScaleMiddleware(BaseMiddleware):
    def __init__(self, runtime: ScaleRuntime) -> None:
        self.runtime = runtime

    async def __call__(self, handler, event, data):
        if self.runtime.stopping:
            return None
        self.runtime.metrics.record_update()
        data.update(self.runtime.workflow())
        membership = event.chat_member or event.my_chat_member
        if membership and self.runtime.migrations.resolve(membership.chat.id) != membership.chat.id:
            return None  # Ignore delayed membership events from the inactive source group.
        if event.message and (
            event.message.migrate_to_chat_id or event.message.migrate_from_chat_id
        ):
            return await handler(event, data)
        for field in ("message", "callback_query"):
            container = getattr(event, field)
            message = (
                container if field == "message" else (container.message if container else None)
            )
            if message is None:
                continue
            canonical = self.runtime.migrations.resolve(message.chat.id)
            if canonical != message.chat.id:
                sender_chat = getattr(message, "sender_chat", None)
                if sender_chat and sender_chat.id == message.chat.id:
                    sender_chat = sender_chat.model_copy(update={"id": canonical})
                elif sender_chat and sender_chat.id == canonical:
                    sender_chat = None
                message = message.model_copy(
                    update={
                        "chat": message.chat.model_copy(update={"id": canonical}),
                        "sender_chat": sender_chat,
                    }
                )
                replacement = (
                    message
                    if field == "message"
                    else container.model_copy(update={"message": message})
                )
                event = event.model_copy(update={field: replacement})
        message = event.message
        query = event.callback_query
        if (
            query
            and query.from_user.id in self.runtime.owner_tools.deleted
            and not (query.data or "").startswith("erase:")
        ):
            from bot import texts

            await self.runtime.sender.answer_callback_query(
                self.runtime.game_hub.bot, query.id, text=texts.ERASE_DONE, show_alert=True
            )
            return None
        answer = event.poll_answer
        if answer and answer.user and answer.user.id in self.runtime.owner_tools.deleted:
            return None
        if (
            message
            and message.from_user
            and message.from_user.id in self.runtime.owner_tools.deleted
        ):
            if (message.text or "").split(" ")[0].split("@")[0] == "/start":
                self.runtime.owner_tools.deleted.discard(message.from_user.id)
            elif (message.text or "").split(" ")[0] not in {
                "/maxfiylik",
                "/help",
                "/malumotlarimni_ochir",
            }:
                return None
            else:
                return await handler(event, data)
        if message and message.from_user and not message.from_user.is_bot:
            user = message.from_user
            self.runtime.activity.observe(message.chat.id, user.id, user.first_name, user.username)
            data["has_pending_challenge"] = self.runtime.pending.contains(message.chat.id, user.id)
            if self.runtime.daily.observe(message):
                # A qualifying award is a scoring action, not ordinary activity.
                # Persist before acknowledging the update; the unique ledger ref deduplicates it.
                try:
                    await self.runtime.checkins.flush()
                except Exception:
                    self.runtime.daily.checked.get(message.chat.id, (None, set()))[1].discard(
                        user.id
                    )
                    raise
        membership = event.chat_member or event.my_chat_member
        if membership:
            try:
                await self.runtime.admins.refresh(membership.chat.id)
            except Exception:
                logger.exception("Admin refresh failed for chat %s", membership.chat.id)
        if (
            event.chat_member
            and event.chat_member.new_chat_member.user.id in self.runtime.owner_tools.deleted
        ):
            return None
        result = await handler(event, data)
        if event.chat_member:
            await self.runtime.mafia_game.membership_changed(
                event.chat_member.chat.id, event.chat_member.new_chat_member.user.id
            )
        if message and message.from_user and not message.from_user.is_bot:
            await self.runtime.challenge_service.complete(message)
            await self.runtime.game_hub.observe(message)
        return result
