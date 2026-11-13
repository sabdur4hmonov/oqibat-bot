"""One target, private authorization, and linked challenge lifecycle for dares."""

import random
from datetime import timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot import texts
from bot.db.models import Challenge, User
from bot.db.repo.games import Award, GameBusy
from bot.games.truth_dare import can_answer
from bot.services.challenges import message_kind
from bot.utils.time import utc_now


def buttons(game, choice=False):
    rows = []
    if choice:
        rows.append(
            [
                InlineKeyboardButton(text=texts.HYJ_TRUTH, callback_data=f"ht:{game.id}"),
                InlineKeyboardButton(text=texts.HYJ_DARE, callback_data=f"hd:{game.id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text=texts.HYJ_REFUSE, callback_data=f"hr:{game.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


class TruthDare:
    def __init__(self, hub, content, sessions, challenges):
        self.hub, self.repo, self.cache = hub, hub.repo, hub.cache
        self.content, self.sessions, self.challenges = content, sessions, challenges
        self.early_messages = {}

    async def start(self, message):
        if message.from_user is None or message.from_user.is_bot:
            return texts.GAME_JOIN_FIRST
        members = self.hub.participants.for_chat(message.chat.id)
        target = getattr(message.reply_to_message, "from_user", None)
        if target and (target.is_bot or target.id not in members):
            return texts.HYJ_INVALID_TARGET
        target_id = target.id if target else (random.choice(members) if members else None)
        if target_id is None:
            return texts.GAME_JOIN_FIRST
        async with self.sessions() as session:
            user = await session.get(User, target_id)
        state = {
            "phase": "choice",
            "target": target_id,
            "name": user.first_name,
            "answer_after_id": message.message_id,
        }
        try:
            game = await self.repo.start(
                message.chat.id,
                message.from_user.id,
                "hyj",
                state,
                utc_now() + timedelta(seconds=90),
            )
        except GameBusy:
            return texts.GAME_BUSY
        if game is None:
            return texts.GAME_JOIN_FIRST
        sent = await self.hub.board(game, texts.hyj_choice(game), buttons(game, True))
        await self.hub.attach_board(game, sent)
        return None

    async def callback(self, query):
        try:
            operation, value = (query.data or "").split(":")
            game = self.cache.get(int(value))
        except ValueError:
            return texts.GAME_BUTTON_EXPIRED
        if (
            game is None
            or game.game != "hyj"
            or query.message is None
            or game.chat_id != query.message.chat.id
            or game.state["target"] != query.from_user.id
            or not self.hub.participants.contains(game.chat_id, query.from_user.id)
        ):
            return texts.HYJ_TARGET_ONLY
        if operation == "hr":
            updated = await self.repo.refuse_hyj(game.chat_id, game.id, query.from_user.id)
            if updated:
                self.hub.effects.start(self.hub.finish(updated, texts.hyj_result(updated)))
                return None
            return texts.GAME_BUTTON_EXPIRED
        if operation not in {"ht", "hd"}:
            return texts.GAME_BUTTON_EXPIRED
        if operation == "hd" and self.challenges.pending.for_chat(game.chat_id):
            return texts.PENDING_CHALLENGE

        def choose(row):
            if (
                row.state.get("phase") != "choice"
                or row.phase_deadline_at <= utc_now()
                or not self.hub.participants.contains(row.chat_id, query.from_user.id)
            ):
                return False
            row.state.update(phase="preparing", mode="truth" if operation == "ht" else "dare")
            row.phase_deadline_at = utc_now() + timedelta(seconds=90)

        updated = await self.repo.transition(game.chat_id, game.id, choose)
        if updated is None:
            return texts.GAME_BUTTON_EXPIRED
        self.hub.effects.start(
            self.prepare_truth(updated) if operation == "ht" else self.prepare_dare(updated)
        )
        return None

    async def prepare_truth(self, game):
        async with self.repo.locks.hold(game.chat_id) as chat_id:
            item = await self.content.draw(self.sessions, chat_id, "truth_questions", utc_now())
        if item is None:
            await self.hub.cancel(game, texts.GAME_NO_CONTENT, defer=True)
            return

        def sending(row):
            row.state.update(phase="truth_sending", question=item["text"])

        game = await self.repo.transition(
            game.chat_id, game.id, sending, expected_rev=game.state["rev"]
        )
        if game is None:
            return
        sent = await self.hub.board(game, texts.hyj_truth(game), buttons(game))
        if sent is None:
            await self.hub.cancel(game, defer=True)
            return

        def ready(row):
            now = utc_now().replace(microsecond=0)
            row.phase_deadline_at = now + timedelta(minutes=30)
            row.state.update(
                phase="truth",
                answer_from=now.isoformat(),
                answer_until=row.phase_deadline_at.isoformat(),
            )

        updated = await self.repo.transition(
            game.chat_id, game.id, ready, expected_rev=game.state["rev"]
        )
        early = self.early_messages.pop(game.id, None)
        if updated:
            self.hub.effects.start(
                self.hub.board(updated, texts.hyj_truth(updated), buttons(updated))
            )
        if updated and early:
            await self.observe(updated, early)

    async def prepare_dare(self, game):
        error = await self.challenges.assign(
            game.chat_id, force=True, target=game.state["target"], hours=1, game_id=game.id
        )
        current = self.cache.get(game.id)
        if current is None:
            return
        if error:

            def reset(row):
                row.state["phase"] = "choice"
                row.phase_deadline_at = utc_now() + timedelta(seconds=90)

            current = await self.repo.transition(game.chat_id, game.id, reset)
            if current:
                await self.hub.board(
                    current, error + "\n\n" + texts.hyj_choice(current), buttons(current, True)
                )
        else:
            await self.hub.board(current, texts.hyj_dare(current), buttons(current))

    async def observe(self, game, message):
        if message.from_user is None or message.from_user.is_bot:
            return
        user = message.from_user.id
        kind = message_kind(message)
        if (
            game.state.get("phase") == "truth_sending"
            and user == game.state["target"]
            and kind in {"text", "voice"}
        ):
            self.early_messages.setdefault(game.id, message)
            return
        if not can_answer(game.state, user, kind, message.date, message.message_id):
            return

        def complete(row):
            if not self.hub.participants.contains(row.chat_id, user) or not can_answer(
                row.state, user, kind, message.date, message.message_id
            ):
                return False
            row.status, row.phase_deadline_at = "finished", None
            row.state.update(phase="done", result="truth_done")
            return [Award(user, 5, "hyj_truth", f"game:{row.id}")]

        updated = await self.repo.transition(game.chat_id, game.id, complete)
        if updated:
            await self.hub.finish(updated, texts.hyj_result(updated))

    async def advance(self, game, now):
        if game.state.get("phase") == "dare":
            async with self.sessions() as session:
                challenge = await session.get(Challenge, game.state["challenge_id"])
            if challenge and challenge.status == "pending":
                await self.challenges.expire(challenge, now)
                return

        def expired(row):
            row.status, row.phase_deadline_at = "finished", None
            row.state.update(phase="done", result="timeout")

        updated = await self.repo.transition(
            game.chat_id, game.id, expired, expected_rev=game.state["rev"]
        )
        if updated:
            self.hub.effects.start(self.hub.finish(updated, texts.hyj_result(updated)))

    def challenge_resolved(self, game):
        self.hub.effects.start(self.hub.finish(game, texts.hyj_result(game)))

    async def cleanup(self, game):
        self.early_messages.pop(game.id, None)
        async with self.sessions() as session:
            challenge_id = await session.scalar(
                select(Challenge.id)
                .where(Challenge.game_session_id == game.id, Challenge.status == "pending")
                .limit(1)
            )
        if challenge_id is not None:
            await self.challenges.repo.resolve(game.chat_id, challenge_id, "cancelled")

    async def recover(self, game):
        if game.state.get("phase") in {"preparing", "truth_sending"}:
            await self.hub.cancel(game, texts.GAME_RESTARTED, defer=True)
