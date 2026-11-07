"""Bounded off-thread rendering and once-reserved winner card delivery."""

import asyncio
import logging

from aiogram.types import BufferedInputFile

from bot import texts
from bot.services.cards import render_card
from bot.services.sender import Priority

logger = logging.getLogger(__name__)


class ResultCards:
    def __init__(self, repository, bot, sender, settings):
        self.repo, self.bot, self.sender = repository, bot, sender
        self.enabled = getattr(settings, "result_cards_enabled", False)
        self.instagram = getattr(settings, "instagram_handle", "oqibat")
        self.workers = asyncio.Semaphore(2)

    async def render(self, title, rows, subtitle=None):
        if not self.enabled:
            return None
        try:
            async with self.workers:
                return await asyncio.to_thread(render_card, title, rows, self.instagram, subtitle)
        except Exception:
            logger.exception("Result card rendering failed; text result remains available")
            return None

    async def weekly(self, week, data):
        return await self.render(
            texts.CARD_WEEKLY_TITLE,
            [(name, points) for _, name, points in data["top"]],
            texts.card_week(week),
        )

    async def game(self, game):
        if not self.enabled:
            return
        data = texts.game_card_data(game)
        if data is None:
            return
        if not await self.repo.claim_result_card(game.chat_id, game.id):
            return
        chat_id = self.repo.locks.resolve(game.chat_id)
        payload = await self.render(data["title"], data["rows"])
        if payload is None:
            await self.repo.record_result_card(chat_id, game.id, None)
            return
        sent = await self.sender.send(
            chat_id,
            lambda: self.bot.send_photo(
                chat_id,
                BufferedInputFile(payload, filename="oqibat-result.png"),
                caption=texts.game_card_caption(game),
            ),
            priority=Priority.GAME,
        )
        await self.repo.record_result_card(chat_id, game.id, sent)
