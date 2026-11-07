"""Private-word callbacks and memory-filtered guessing; all writes use the game repository."""

import random
from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot import texts
from bot.db.models import User
from bot.db.repo.games import Award, GameBusy
from bot.games import krokodil
from bot.utils.time import utc_now


def buttons(game):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.KROK_SEE, callback_data=f"kw:{game.id}"),
                InlineKeyboardButton(text=texts.KROK_SKIP, callback_data=f"ks:{game.id}"),
            ]
        ]
    )


class Krokodil:
    def __init__(self, hub, content, sessions):
        self.hub, self.repo, self.cache = hub, hub.repo, hub.cache
        self.content, self.sessions = content, sessions

    async def start(self, message):
        user = message.from_user
        if user is None or user.is_bot:
            return texts.GAME_JOIN_FIRST
        members = self.hub.participants.for_chat(message.chat.id)
        if len(members) < 2:
            return texts.KROK_NEED_PLAYERS
        async with self.sessions() as session:
            names = dict(
                (
                    await session.execute(
                        select(User.id, User.first_name).where(User.id.in_(members))
                    )
                ).all()
            )
        state = {
            "phase": "preparing",
            "host": user.id,
            "round": 1,
            "generation": 0,
            "word": None,
            "skips": 0,
            "end_at": None,
            "scores": {},
            "names": {str(key): name for key, name in names.items()},
        }
        try:
            game = await self.repo.start(
                message.chat.id, user.id, "krokodil", state, utc_now() + timedelta(seconds=90)
            )
        except GameBusy:
            return texts.GAME_BUSY
        if game is None:
            return texts.GAME_JOIN_FIRST
        sent = await self.hub.board(game, texts.KROK_START)
        game = await self.hub.attach_board(game, sent)
        if game:
            await self.prepare(game)
        return None

    async def prepare(self, game):
        async with self.repo.locks.hold(game.chat_id) as chat_id:
            current = self.cache.get(game.id)
            if current is None or current.state["rev"] != game.state["rev"]:
                return
            item = await self.content.draw(self.sessions, chat_id, "krokodil_words", utc_now())
        if item is None:
            await self.hub.cancel(game, texts.GAME_NO_CONTENT, defer=True)
            return

        def ready(row):
            if not self.hub.participants.contains(row.chat_id, row.state["host"]):
                eligible = self.hub.participants.for_chat(row.chat_id)
                if not eligible:
                    return False
                row.state["host"] = random.choice(eligible)
            end = (
                datetime.fromisoformat(row.state["end_at"])
                if row.state.get("end_at")
                else utc_now() + timedelta(minutes=3)
            )
            row.state.update(
                phase="playing",
                word=item["word"],
                generation=row.state["generation"] + 1,
                end_at=end.isoformat(),
                word_started_at=utc_now().isoformat(),
            )
            row.phase_deadline_at = end

        updated = await self.repo.transition(
            game.chat_id, game.id, ready, expected_rev=game.state["rev"]
        )
        if updated:
            await self.hub.board(updated, texts.krok_board(updated), buttons(updated))

    async def callback(self, query):
        try:
            action, game_id = (query.data or "").split(":")
            game = self.cache.get(int(game_id))
        except ValueError:
            return texts.GAME_BUTTON_EXPIRED
        if (
            game is None
            or game.game != "krokodil"
            or query.message is None
            or query.message.chat.id != game.chat_id
            or game.state.get("phase") != "playing"
            or game.state["host"] != query.from_user.id
            or game.phase_deadline_at <= utc_now()
            or not self.hub.participants.contains(game.chat_id, query.from_user.id)
        ):
            return texts.KROK_HOST_ONLY
        if action == "kw":
            return texts.krok_word(game.state["word"])
        if action != "ks":
            return texts.GAME_BUTTON_EXPIRED

        def change(row):
            if not self.hub.participants.contains(row.chat_id, query.from_user.id):
                return False
            state = krokodil.skip(row.state, query.from_user.id)
            if state is None:
                return False
            row.state = state
            row.phase_deadline_at = utc_now() + timedelta(seconds=90)

        updated = await self.repo.transition(
            game.chat_id, game.id, change, expected_rev=game.state["rev"]
        )
        if updated is None:
            return texts.KROK_NO_SKIPS
        self.hub.effects.start(self.prepare(updated))
        return texts.KROK_SKIPPED

    async def observe(self, game, message):
        user = message.from_user
        if (
            user is None
            or user.is_bot
            or not message.text
            or not self.hub.participants.contains(game.chat_id, user.id)
            or game.phase_deadline_at is None
            or message.date > game.phase_deadline_at
            or not krokodil.guess(game.state, user.id, message.text)
        ):
            return

        def guessed(row):
            if not self.hub.participants.contains(row.chat_id, user.id):
                return False
            if message.message_id <= row.state.get("seen", {}).get(
                str(user.id), 0
            ) or message.date < datetime.fromisoformat(row.state["word_started_at"]).replace(
                microsecond=0
            ):
                return False
            result = krokodil.guess(row.state, user.id, message.text)
            if result is None or message.date > row.phase_deadline_at:
                return False
            state, deltas = result
            state["names"][str(user.id)] = user.first_name
            state.setdefault("seen", {})[str(user.id)] = message.message_id
            generation = row.state["generation"]
            row.state = state
            row.status = "finished" if state["phase"] == "done" else "running"
            row.phase_deadline_at = (
                None if row.status == "finished" else utc_now() + timedelta(seconds=90)
            )
            return [
                Award(who, delta, "krokodil", f"game:{row.id}:word:{generation}")
                for who, delta in deltas
            ]

        updated = await self.repo.transition(
            game.chat_id, game.id, guessed, expected_rev=game.state["rev"]
        )
        if updated:
            if updated.status == "finished":
                await self.hub.finish(updated, texts.krok_board(updated, final=True))
            else:
                await self.prepare(updated)

    async def advance(self, game, now):
        if game.state.get("phase") != "playing":
            await self.hub.cancel(game, texts.GAME_TIMEOUT, defer=True)
            return
        eligible = self.hub.participants.for_chat(game.chat_id)
        if not eligible:
            await self.hub.cancel(game, defer=True)
            return

        def expired(row):
            row.state = krokodil.timeout(row.state, random.choice(eligible))
            row.status = "finished" if row.state["phase"] == "done" else "running"
            row.phase_deadline_at = (
                None if row.status == "finished" else now + timedelta(seconds=90)
            )

        updated = await self.repo.transition(
            game.chat_id, game.id, expired, expected_rev=game.state["rev"]
        )
        if updated:
            self.hub.effects.start(
                self.hub.finish(updated, texts.krok_board(updated, final=True))
                if updated.status == "finished"
                else self.prepare(updated)
            )

    async def recover(self, game):
        if game.state.get("phase") == "preparing":
            self.hub.effects.start(self.prepare(game))

    async def cleanup(self, game):
        return None
