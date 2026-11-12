"""Locked game transitions; Telegram effects run after state/points commit."""

from datetime import timedelta

from bot import texts
from bot.db.repo.games import Award, GameBusy
from bot.games import rps
from bot.keyboards.rps import game_keyboard
from bot.services.points import RPS_WIN
from bot.utils.time import utc_now


class RockPaperScissors:
    def __init__(self, hub):
        self.hub, self.repo, self.cache = hub, hub.repo, hub.cache

    async def start(self, message):
        user = message.from_user
        if user is None or user.is_bot:
            return texts.GAME_JOIN_FIRST
        target = getattr(message.reply_to_message, "from_user", None)
        if target and (
            target.is_bot
            or target.id == user.id
            or not self.hub.participants.contains(message.chat.id, target.id)
        ):
            return texts.DUEL_INVALID_TARGET
        state = {
            "phase": "lobby",
            "round": 1,
            "players": [user.id],
            "target": target.id if target else None,
            "names": {str(user.id): user.first_name},
            "choices": {},
        }
        if target:
            state["names"][str(target.id)] = target.first_name
        try:
            game = await self.repo.start(
                message.chat.id,
                user.id,
                "rps",
                state,
                utc_now() + timedelta(seconds=90),
                status="lobby",
            )
        except GameBusy:
            return texts.GAME_BUSY
        if game is None:
            return texts.GAME_JOIN_FIRST
        sent = await self.hub.board(game, texts.rps_board(game), game_keyboard(game))
        await self.hub.attach_board(game, sent)
        return None

    async def callback(self, query):
        pieces = (query.data or "").split(":")
        if (
            len(pieces) != 4
            or pieces[0] != "rp"
            or not pieces[1].isascii()
            or not pieces[1].isdecimal()
            or len(pieces[1]) > 19
            or pieces[3] not in {"a", *rps.MOVES}
        ):
            return texts.GAME_BUTTON_EXPIRED
        game = self.cache.get(int(pieces[1]))
        user = query.from_user
        if (
            game is None
            or game.game != "rps"
            or query.message is None
            or query.message.chat.id != game.chat_id
            or query.message.message_id != game.state.get("board_id")
            or pieces[2] != str(game.state.get("round"))
            or user.is_bot
        ):
            return texts.GAME_BUTTON_EXPIRED
        if not self.hub.participants.contains(game.chat_id, user.id):
            return texts.GAME_JOIN_FIRST

        def change(row):
            if (
                row.game != "rps"
                or row.phase_deadline_at is None
                or row.phase_deadline_at <= utc_now()
                or pieces[2] != str(row.state.get("round"))
                or not all(
                    self.hub.participants.contains(row.chat_id, player)
                    for player in {*row.state["players"], user.id}
                )
            ):
                return False
            try:
                if pieces[3] == "a":
                    row.state = rps.accept(row.state, user.id, user.first_name)
                    row.status = "running"
                    row.phase_deadline_at = utc_now() + timedelta(seconds=60)
                else:
                    row.state = rps.choose(row.state, user.id, pieces[3])
                    if row.state["phase"] == "done":
                        row.status, row.phase_deadline_at = "finished", None
                        winner = row.state["winner"]
                        return [Award(winner, RPS_WIN, "rps", f"game:{row.id}")] if winner else []
            except ValueError:
                return False

        updated = await self.repo.transition(game.chat_id, game.id, change)
        if updated is None:
            return texts.GAME_BUTTON_EXPIRED
        self.hub.effects.start(self.display(updated))
        return texts.RPS_ACCEPTED if pieces[3] == "a" else texts.RPS_CHOICE_LOCKED

    async def display(self, game):
        if game.status == "finished":
            await self.hub.finish(game, texts.rps_board(game))
        else:
            await self.hub.board(game, texts.rps_board(game), game_keyboard(game))

    async def advance(self, game, now):
        def expire(row):
            if row.phase_deadline_at is None or row.phase_deadline_at > now:
                return False
            row.status, row.phase_deadline_at = "cancelled", None
            row.state.update(phase="done", result="timeout")

        updated = await self.repo.transition(
            game.chat_id, game.id, expire, expected_rev=game.state["rev"]
        )
        if updated:
            self.hub.effects.start(self.hub.finish(updated, texts.RPS_TIMEOUT))

    def membership_resolved(self, game):
        self.hub.effects.start(self.hub.finish(game, texts.RPS_LEFT))

    async def recover(self, game):
        await self.hub.cancel(game, texts.RPS_RESET, defer=True)

    async def cleanup(self, game):
        return None

    async def observe(self, game, message):
        return None
