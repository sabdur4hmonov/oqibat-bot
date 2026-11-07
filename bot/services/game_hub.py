"""Shared game routing, permission checks and outbound board operations."""

import logging

from bot import texts
from bot.services.sender import Priority

logger = logging.getLogger(__name__)


class GameHub:
    def __init__(self, repository, cache, bot, sender, admins, participants, effects) -> None:
        self.repo, self.cache, self.bot, self.sender = repository, cache, bot, sender
        self.admins, self.participants = admins, participants
        self.effects = effects
        self.services = {}

    def register(self, kinds, service) -> None:
        for kind in kinds:
            self.services[kind] = service

    async def board(self, game, text: str, markup=None):
        async def operation():
            current = self.cache.get(game.id)
            if game.status in {"lobby", "running"} and (
                current is None or current.state.get("rev") != game.state.get("rev")
            ):
                return None
            message_id = game.state.get("board_id")
            if message_id:
                return await self.bot.edit_message_text(
                    text, chat_id=game.chat_id, message_id=message_id, reply_markup=markup
                )
            return await self.bot.send_message(game.chat_id, text, reply_markup=markup)

        return await self.sender.send(game.chat_id, operation, priority=Priority.GAME)

    async def cancel(self, game, text=None, *, defer=False):
        def transition(row):
            row.status, row.phase_deadline_at = "cancelled", None
            row.state["phase"] = "done"

        stopped = await self.repo.transition(game.chat_id, game.id, transition)
        if stopped:
            if defer:
                self.effects.start(self.finish(stopped, text or texts.GAME_CANCELLED))
            else:
                await self.finish(stopped, text or texts.GAME_CANCELLED)
        return stopped

    async def finish(self, game, text, markup=None):
        service = self.services.get(game.game)
        if service:
            await service.cleanup(game)
        return await self.board(game, text, markup)

    async def stop(
        self, chat_id: int, user_id: int, reply_id=None, *, anonymous_admin=False
    ) -> str | None:
        games = self.cache.for_chat(chat_id)
        if reply_id:
            game = next((game for game in games if game.state.get("board_id") == reply_id), None)
        else:
            game = self.cache.main(chat_id) or next(
                (game for game in games if game.started_by == user_id), games[0] if games else None
            )
        if game is None:
            return texts.NO_ACTIVE_GAME
        if user_id != game.started_by and not anonymous_admin:
            try:
                if user_id not in await self.admins.get(chat_id):
                    return texts.STOP_DENIED
            except Exception:
                return texts.ADMIN_CHECK_FAILED
        await self.cancel(game)
        return None

    async def attach_board(self, game, sent):
        if sent is None:
            await self.cancel(game, defer=True)
            return None

        def save(row):
            if row.state.get("board_id") is not None:
                return False
            row.state["board_id"] = sent.message_id

        return await self.repo.transition(game.chat_id, game.id, save)

    async def advance(self, row, now) -> bool:
        game = self.cache.get(row.id)
        service = self.services.get(row.game)
        if (
            game is None
            or service is None
            or game.phase_deadline_at is None
            or game.phase_deadline_at > now
        ):
            return False
        await service.advance(game, now)
        return True

    async def recover(self, games) -> None:
        for game in games:
            service = self.services.get(game.game)
            if service:
                try:
                    await service.recover(game)
                except Exception:
                    logger.exception("Could not recover game %s", game.id)

    async def observe(self, message) -> None:
        game = self.cache.main(message.chat.id)
        service = self.services.get(game.game) if game else None
        if service:
            await service.observe(game, message)
