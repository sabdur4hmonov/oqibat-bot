"""Bounded off-thread rendering and once-reserved winner card delivery."""

import asyncio
import logging

from aiogram.types import BufferedInputFile

from bot import texts
from bot.keyboards.cards import story_keyboard
from bot.services.avatars import Avatars
from bot.services.cards import render_card
from bot.services.sender import Priority

logger = logging.getLogger(__name__)


class ResultCards:
    def __init__(self, repository, bot, sender, settings):
        self.repo, self.bot, self.sender = repository, bot, sender
        self.enabled = getattr(settings, "result_cards_enabled", False)
        self.instagram = getattr(settings, "instagram_handle", "oqibat")
        self.workers = asyncio.Semaphore(2)
        self.avatars = Avatars(bot, sender)

    async def render(self, title, rows, subtitle=None, **options):
        if not self.enabled:
            return None
        try:
            async with self.workers:
                return await asyncio.to_thread(
                    render_card, title, rows, self.instagram, subtitle, **options
                )
        except Exception:
            logger.exception("Result card rendering failed; text result remains available")
            return None

    async def weekly(self, week, data):
        return await self.ranked(
            texts.CARD_WEEKLY_TITLE,
            data["top"],
            texts.card_week(week),
        )

    async def ranked(self, title, entries, subtitle=None, *, kind="weekly", story=False):
        if not self.enabled:
            return None
        try:
            async with self.workers:
                photos = await asyncio.gather(
                    *(self.avatars.get(user) for user, _, _ in entries[:5])
                )
                return await asyncio.to_thread(
                    render_card,
                    title,
                    [(name, score) for _, name, score in entries[:5]],
                    self.instagram,
                    subtitle,
                    kind=kind,
                    story=story,
                    avatars=photos,
                )
        except Exception:
            logger.exception("Ranked card unavailable; keep text result")
            return None

    async def game(self, game):
        if not self.enabled:
            return
        data = texts.game_card_data(game)
        if data is None:
            return
        if not await self.repo.claim_result_card(game.chat_id, game.id):
            return
        chat_id = self.repo.locks.resolve(game.chat_id)
        payload = await self.ranked(data["title"], data["entries"], kind=game.game)
        if payload is None:
            await self.repo.record_result_card(chat_id, game.id, None)
            return
        from bot.db.models import GameSession

        async def upload():
            async with self.repo.sessions() as session:
                row = await session.get(GameSession, game.id)
                if row is None or row.state.get("erased"):
                    return None
            return await self.bot.send_photo(
                chat_id,
                BufferedInputFile(payload, filename="oqibat-result.png"),
                caption=texts.game_card_caption(game),
                reply_markup=story_keyboard(f"g:{game.id}"),
            )

        sent = await self.sender.send(
            chat_id,
            upload,
            priority=Priority.GAME,
        )
        await self.repo.record_result_card(chat_id, game.id, sent)
