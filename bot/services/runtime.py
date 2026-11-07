"""Shared services and lifecycle for both polling and webhook transports."""

import asyncio
import logging

from aiogram import BaseMiddleware

from bot.db.repo.challenges import ChallengeRepository
from bot.db.repo.games import GameSessionRepository
from bot.db.repo.groups import GroupRepository
from bot.services.activity import ActivityBuffer
from bot.services.admin_cache import AdminCache
from bot.services.challenges import ChallengeService
from bot.services.content import ContentLibrary
from bot.services.daily import DailyService
from bot.services.locks import ChatLocks
from bot.services.metrics import Metrics
from bot.services.participation import Participants
from bot.services.penalties import Penalties
from bot.services.pending import PendingChallenges
from bot.services.points import CheckinBuffer, Points
from bot.services.scheduler import Scheduler
from bot.services.sender import Sender
from bot.services.settings import SettingPrompts

logger = logging.getLogger(__name__)


class ScaleRuntime:
    def __init__(self, sessions, bot, settings=None) -> None:
        self.activity = ActivityBuffer(sessions)
        self.pending = PendingChallenges()
        self.participants = Participants()
        self.checkins = CheckinBuffer(sessions)
        self.points = Points(sessions)
        self.locks = ChatLocks()
        self.admins = AdminCache(bot)
        self.metrics = Metrics()
        self.scheduler = Scheduler(sessions)
        self.sender = Sender(sessions, on_forbidden=self.activity.mark_forbidden)
        self.challenges = ChallengeRepository(sessions, self.pending, self.locks)
        self.games = GameSessionRepository(sessions, self.locks)
        self.groups = GroupRepository(sessions, self.locks, self.pending, self.participants)
        self.setting_prompts = SettingPrompts()
        self.content = ContentLibrary()
        self.daily = DailyService(
            sessions, bot, self.sender, self.content, self.participants, self.checkins
        )
        self.scheduler.hooks["daily"] = self.daily.post
        self.penalties = Penalties(
            bot, self.sender, self.admins, getattr(settings, "owner_id", None)
        )
        self.challenge_service = ChallengeService(
            sessions, bot, self.sender, self.challenges, self.pending, self.content, self.penalties
        )
        self.scheduler.hooks["challenge"] = self.challenge_service.scheduled
        self.scheduler.hooks["expire"] = self.challenge_service.expire
        self.sessions = sessions
        self.tasks = []

    async def __aenter__(self):
        await self.pending.load(self.sessions)
        await self.participants.load(self.sessions)
        await self.daily.load()
        self.tasks = [
            asyncio.create_task(self.activity.run(), name="activity-flush"),
            asyncio.create_task(self.scheduler.run(), name="scheduler-tick"),
            asyncio.create_task(self.checkins.run(), name="checkin-flush"),
            asyncio.create_task(
                self.metrics.run(self.sender, self.scheduler), name="scale-metrics"
            ),
        ]
        return self

    async def __aexit__(self, *args) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.sender.close()
        try:
            await self.activity.flush()
            await self.checkins.flush()
        except Exception:
            logger.exception("Shutdown activity flush failed")

    def workflow(self) -> dict:
        return {
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
        }


class ScaleMiddleware(BaseMiddleware):
    def __init__(self, runtime: ScaleRuntime) -> None:
        self.runtime = runtime

    async def __call__(self, handler, event, data):
        self.runtime.metrics.record_update()
        data.update(self.runtime.workflow())
        message = event.message
        if message and message.from_user and not message.from_user.is_bot:
            user = message.from_user
            self.runtime.activity.observe(message.chat.id, user.id, user.first_name, user.username)
            data["has_pending_challenge"] = self.runtime.pending.contains(message.chat.id, user.id)
            self.runtime.daily.observe(message)
        membership = event.chat_member or event.my_chat_member
        if membership:
            try:
                await self.runtime.admins.refresh(membership.chat.id)
            except Exception:
                logger.exception("Admin refresh failed for chat %s", membership.chat.id)
        result = await handler(event, data)
        if message and message.from_user and not message.from_user.is_bot:
            await self.runtime.challenge_service.complete(message)
        return result
