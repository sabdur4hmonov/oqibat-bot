"""Number hunt and arithmetic use existing locked sessions and deferred GAME effects."""

import random
from datetime import timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.db.repo.games import Award, GameBusy
from bot.games import number_hunt, quick_math
from bot.services.points import MATH_CORRECT, NUMBER_WIN
from bot.utils.time import utc_now


def math_keyboard(game):
    item = game.state["questions"][game.state["round"] - 1]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(option), callback_data=f"qm:{game.id}:{game.state['round']}:{index}"
                )
                for index, option in enumerate(item["options"])
            ]
        ]
    )


class QuickGames:
    def __init__(self, hub):
        self.hub, self.repo, self.cache = hub, hub.repo, hub.cache
        self.rng = random.SystemRandom()

    async def start(self, message, kind):
        user = message.from_user
        if user is None or user.is_bot:
            return texts.GAME_JOIN_FIRST
        state = (
            number_hunt.initial(self.rng.randint(1, 100))
            if kind == "number"
            else quick_math.initial(quick_math.questions(self.rng))
        )
        try:
            game = await self.repo.start(
                message.chat.id, user.id, kind, state, utc_now() + timedelta(seconds=90)
            )
        except GameBusy:
            return texts.GAME_BUSY
        if game is None:
            return texts.GAME_JOIN_FIRST
        await self.publish(game)
        return None

    async def publish(self, game):
        sent = await self.hub.board(
            game, texts.quick_board(game), math_keyboard(game) if game.game == "math" else None
        )
        if sent is None:
            await self.hub.cancel(game, defer=True)
            return

        def ready(row):
            if row.state["phase"] != "preparing":
                return False
            row.state.update(phase="playing", board_id=sent.message_id)
            if row.game == "number":
                row.state["last_message_id"] = sent.message_id
            row.phase_deadline_at = utc_now() + timedelta(
                seconds=180 if row.game == "number" else 20
            )

        updated = await self.repo.transition(
            game.chat_id, game.id, ready, expected_rev=game.state["rev"]
        )
        if updated:
            self.hub.effects.start(
                self.hub.board(
                    updated,
                    texts.quick_board(updated),
                    math_keyboard(updated) if updated.game == "math" else None,
                )
            )

    async def display(self, game):
        if game.status == "finished":
            await self.hub.finish(game, texts.quick_board(game))
        elif game.state["phase"] == "preparing":
            await self.publish(game)
        else:
            await self.hub.board(game, texts.quick_board(game))

    async def observe(self, game, message):
        if game.game != "number":
            return
        user = message.from_user
        reply = message.reply_to_message
        value = number_hunt.parse_guess(message.text)
        now = utc_now()
        if (
            user is None
            or user.is_bot
            or reply is None
            or message.forward_origin is not None
            or reply.message_id != game.state.get("board_id")
            or value is None
            or not self.hub.participants.contains(game.chat_id, user.id)
            or game.phase_deadline_at is None
            or game.phase_deadline_at <= now
            or not number_hunt.guess(
                game.state, user.id, user.first_name, value, message.message_id, now.timestamp()
            )
        ):
            return

        def change(row):
            if (
                row.phase_deadline_at is None
                or row.phase_deadline_at <= utc_now()
                or not self.hub.participants.contains(row.chat_id, user.id)
                or reply.message_id != row.state.get("board_id")
            ):
                return False
            state = number_hunt.guess(
                row.state,
                user.id,
                user.first_name,
                value,
                message.message_id,
                utc_now().timestamp(),
            )
            if state is None:
                return False
            row.state = state
            if state["phase"] == "done":
                row.status, row.phase_deadline_at = "finished", None
                if state.get("winner"):
                    return [Award(user.id, NUMBER_WIN, "number", f"game:{row.id}")]

        updated = await self.repo.transition(game.chat_id, game.id, change)
        if updated:
            self.hub.effects.start(self.display(updated))

    async def callback(self, query):
        parts = (query.data or "").split(":")
        if (
            len(parts) != 4
            or parts[0] != "qm"
            or not parts[1].isascii()
            or not parts[1].isdecimal()
            or len(parts[1]) > 19
            or parts[3] not in {"0", "1", "2", "3"}
        ):
            return texts.GAME_BUTTON_EXPIRED
        game = self.cache.get(int(parts[1]))
        user = query.from_user
        if (
            game is None
            or game.game != "math"
            or user.is_bot
            or query.message is None
            or query.message.chat.id != game.chat_id
            or query.message.message_id != game.state.get("board_id")
            or parts[2] != str(game.state["round"])
            or game.state["phase"] != "playing"
            or game.phase_deadline_at is None
            or game.phase_deadline_at <= utc_now()
        ):
            return texts.GAME_BUTTON_EXPIRED
        if not self.hub.participants.contains(game.chat_id, user.id):
            return texts.GAME_JOIN_FIRST
        if not quick_math.answer(
            game.state, user.id, user.first_name, int(parts[3]), game.state["round"]
        ):
            return texts.MATH_ALREADY_TRIED
        was_correct = False

        def choose(row):
            nonlocal was_correct
            if (
                row.phase_deadline_at is None
                or row.phase_deadline_at <= utc_now()
                or parts[2] != str(row.state["round"])
                or not self.hub.participants.contains(row.chat_id, user.id)
            ):
                return False
            result = quick_math.answer(
                row.state, user.id, user.first_name, int(parts[3]), row.state["round"]
            )
            if result is None:
                return False
            row.state, was_correct = result
            if was_correct:
                row.status = "finished" if row.state["phase"] == "done" else "running"
                row.phase_deadline_at = (
                    None if row.status == "finished" else utc_now() + timedelta(seconds=90)
                )
                return [Award(user.id, MATH_CORRECT, "math", f"game:{row.id}:r:{parts[2]}")]

        updated = await self.repo.transition(game.chat_id, game.id, choose)
        if updated is None:
            return texts.GAME_BUTTON_EXPIRED
        if was_correct:
            self.hub.effects.start(self.display(updated))
        return texts.MATH_CORRECT if was_correct else texts.MATH_WRONG

    async def advance(self, game, now):
        def expire(row):
            if row.phase_deadline_at is None or row.phase_deadline_at > now:
                return False
            if row.state["phase"] == "preparing":
                row.status, row.phase_deadline_at = "cancelled", None
                row.state["phase"] = "done"
                return
            row.state = (
                number_hunt.expire(row.state)
                if row.game == "number"
                else quick_math.next_round(row.state)
            )
            row.status = "finished" if row.state["phase"] == "done" else "running"
            row.phase_deadline_at = (
                None if row.status == "finished" else now + timedelta(seconds=90)
            )

        updated = await self.repo.transition(
            game.chat_id, game.id, expire, expected_rev=game.state["rev"]
        )
        if updated:
            self.hub.effects.start(
                self.hub.finish(updated, texts.QUICK_RESET)
                if updated.status == "cancelled"
                else self.display(updated)
            )

    async def recover(self, game):
        await self.hub.cancel(game, texts.QUICK_RESET, defer=True)

    def membership_resolved(self, game):
        self.hub.effects.start(self.hub.finish(game, texts.QUICK_STARTER_LEFT))

    async def cleanup(self, game):
        return None
