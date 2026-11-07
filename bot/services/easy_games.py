"""Dice and polls. Deadline hooks commit state and dispatch I/O without waiting for sends."""

from datetime import timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.db.repo.games import Award, GameBusy
from bot.games import dice_duel, quiz, wyr
from bot.services.sender import Priority
from bot.utils.time import utc_now


def duel_buttons(game):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=emoji, callback_data=f"dg:{game.id}:{i}")
                for i, emoji in enumerate(dice_duel.EMOJIS)
            ],
            [InlineKeyboardButton(text=texts.DUEL_ACCEPT, callback_data=f"da:{game.id}")],
        ]
    )


class EasyGames:
    def __init__(self, hub, content, sessions):
        self.hub, self.repo, self.cache = hub, hub.repo, hub.cache
        self.bot, self.sender, self.content, self.sessions = hub.bot, hub.sender, content, sessions
        self.early_answers = {}
        self.sending_polls = set()

    async def start(self, message, kind):
        user = message.from_user
        if user is None or user.is_bot:
            return texts.GAME_JOIN_FIRST
        now = utc_now()
        state = {"phase": "sending", "names": {str(user.id): user.first_name}, "scores": {}}
        target = getattr(message.reply_to_message, "from_user", None)
        if kind == "duel":
            if target and (
                target.is_bot
                or target.id == user.id
                or not self.hub.participants.contains(message.chat.id, target.id)
            ):
                return texts.DUEL_INVALID_TARGET
            state.update(
                phase="lobby",
                emoji="🎲",
                target=target.id if target else None,
                opponent=None,
                round=1,
            )
            if target:
                state["names"][str(target.id)] = target.first_name
        try:
            game = await self.repo.start(
                message.chat.id,
                user.id,
                kind,
                state,
                now + timedelta(seconds=90),
                status="lobby" if kind == "duel" else "running",
            )
        except GameBusy:
            return texts.GAME_BUSY
        if game is None:
            return texts.GAME_JOIN_FIRST
        if kind == "duel":
            sent = await self.hub.board(game, texts.duel_lobby(game), duel_buttons(game))
            await self.hub.attach_board(game, sent)
        else:
            sent = await self.hub.board(
                game, texts.QUIZ_START if kind == "quiz" else texts.WYR_START
            )
            game = await self.hub.attach_board(game, sent)
            if game:
                await self.send_poll(game)
        return None

    async def callback(self, query):
        pieces = (query.data or "").split(":")
        try:
            game = self.cache.get(int(pieces[1]))
        except (ValueError, IndexError):
            return texts.GAME_BUTTON_EXPIRED
        if game is None or query.message is None or game.chat_id != query.message.chat.id:
            return texts.GAME_BUTTON_EXPIRED
        user = query.from_user
        if not self.hub.participants.contains(game.chat_id, user.id):
            return texts.GAME_JOIN_FIRST
        operation = pieces[0]

        def change(row):
            state = row.state
            if (
                state["phase"] != "lobby"
                or row.phase_deadline_at <= utc_now()
                or not self.hub.participants.contains(row.chat_id, user.id)
            ):
                return False
            if operation == "dg":
                if (
                    user.id != row.started_by
                    or len(pieces) != 3
                    or pieces[2] not in {"0", "1", "2"}
                ):
                    return False
                state["emoji"] = dice_duel.EMOJIS[int(pieces[2])]
            elif operation == "da":
                if user.id == row.started_by or state["target"] not in {None, user.id}:
                    return False
                state.update(opponent=user.id, phase="rolling")
                state["names"][str(user.id)] = user.first_name
                row.status, row.phase_deadline_at = "running", utc_now() + timedelta(seconds=90)
            else:
                return False

        updated = await self.repo.transition(game.chat_id, game.id, change)
        if updated is None:
            return texts.GAME_BUTTON_EXPIRED
        if operation == "da":
            self.hub.effects.start(self.roll(updated))
        else:
            self.hub.effects.start(
                self.hub.board(updated, texts.duel_lobby(updated), duel_buttons(updated))
            )
        return None

    async def roll(self, game):
        await self.hub.board(game, texts.duel_rolling(game))
        values = []
        for _ in range(2):

            async def operation():
                current = self.cache.get(game.id)
                if current is None or current.state.get("rev") != game.state["rev"]:
                    return None
                return await self.bot.send_dice(game.chat_id, emoji=game.state["emoji"])

            sent = await self.sender.send(game.chat_id, operation, priority=Priority.GAME)
            if sent is None or sent.dice is None:
                await self.hub.cancel(game, defer=True)
                return
            values.append(sent.dice.value)
        dice_duel.winner(game.state["emoji"], [game.started_by, game.state["opponent"]], values)

        def save(row):
            row.state.update(values=values, phase="animation")
            row.phase_deadline_at = utc_now() + timedelta(seconds=4)

        await self.repo.transition(game.chat_id, game.id, save, expected_rev=game.state["rev"])

    async def send_poll(self, game):
        bank = "quiz_questions" if game.game == "quiz" else "would_you_rather"
        async with self.repo.locks.hold(game.chat_id) as chat_id:
            item = await self.content.draw(self.sessions, chat_id, bank, utc_now())
        if item is None:
            await self.hub.cancel(game, texts.GAME_NO_CONTENT, defer=True)
            return
        if game.game == "wyr":
            wyr.options(item)

        async def operation():
            current = self.cache.get(game.id)
            if current is None or current.state.get("rev") != game.state["rev"]:
                return None
            kwargs = (
                {
                    "type": "quiz",
                    "correct_option_ids": [item["correct_option_id"]],
                    "allows_revoting": False,
                }
                if game.game == "quiz"
                else {"type": "regular"}
            )
            return await self.bot.send_poll(
                game.chat_id,
                item["question"],
                item["options"],
                is_anonymous=False,
                open_period=30 if game.game == "quiz" else 60,
                **kwargs,
            )

        self.sending_polls.add(game.id)
        try:
            sent = await self.sender.send(game.chat_id, operation, priority=Priority.GAME)
        finally:
            self.sending_polls.discard(game.id)
        if sent is None or sent.poll is None:
            await self.hub.cancel(game, defer=True)
            return

        def save(row):
            row.state.update(
                phase="question",
                poll_id=sent.poll.id,
                poll_message_id=sent.message_id,
                question_index=row.state.get("question_index", 0),
                answered={},
                correct=item.get("correct_option_id"),
                first_correct=None,
            )
            row.phase_deadline_at = sent.date + timedelta(seconds=30 if game.game == "quiz" else 60)

        updated = await self.repo.transition(
            game.chat_id, game.id, save, expected_rev=game.state["rev"]
        )
        if updated is None:
            await self.stop_poll(game.chat_id, sent.message_id)
        else:
            for answer in self.early_answers.pop(sent.poll.id, {}).values():
                await self.answer(answer)
            if game.game == "quiz":
                await self.hub.board(updated, texts.quiz_board(updated))
        if not self.sending_polls:
            self.early_answers.clear()

    async def answer(self, event):
        game_id = self.cache.by_poll.get(event.poll_id)
        game = self.cache.get(game_id) if game_id else None
        if game is None:
            # Only retain early replies while a quiz send is outstanding, bounded in memory.
            if self.sending_polls:
                if len(self.early_answers) < 500:
                    pending = self.early_answers.setdefault(event.poll_id, {})
                    if len(pending) < 1000 and event.user:
                        pending.setdefault(event.user.id, event)
            return
        if game.game != "quiz" or event.user is None:
            return
        user = event.user

        def score(row):
            if (
                row.state.get("poll_id") != event.poll_id
                or row.state.get("phase") != "question"
                or row.phase_deadline_at < utc_now()
                or not self.hub.participants.contains(row.chat_id, user.id)
                or str(user.id) in row.state.get("answered", {})
            ):
                return False
            row.state, delta = quiz.answer(row.state, user.id, user.first_name, event.option_ids)
            return (
                [Award(user.id, delta, "quiz", f"game:{row.id}:q:{row.state['question_index']}")]
                if delta
                else []
            )

        await self.repo.transition(game.chat_id, game.id, score)

    async def advance(self, game, now):
        phase = game.state.get("phase")
        if game.game == "duel" and phase == "animation":
            result = dice_duel.winner(
                game.state["emoji"], [game.started_by, game.state["opponent"]], game.state["values"]
            )

            def resolve(row):
                if result is None:
                    row.state.update(phase="rolling", round=row.state["round"] + 1)
                    row.phase_deadline_at = now + timedelta(seconds=90)
                else:
                    winner = result
                    row.state.update(phase="done", winner=winner)
                    row.status, row.phase_deadline_at = "finished", None
                    return [Award(winner, 2, "duel", f"game:{row.id}")]

            updated = await self.repo.transition(
                game.chat_id, game.id, resolve, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(
                    self.roll(updated)
                    if result is None
                    else self.hub.finish(updated, texts.duel_result(updated))
                )
        elif game.game in {"quiz", "wyr"} and phase == "question":
            final = game.game == "wyr" or game.state.get("question_index", 0) == 4

            def next_question(row):
                row.state.update(
                    phase="done" if final else "sending",
                    poll_id=None,
                    question_index=row.state.get("question_index", 0) + 1,
                )
                row.status = "finished" if final else "running"
                row.phase_deadline_at = None if final else now + timedelta(seconds=90)

            updated = await self.repo.transition(
                game.chat_id, game.id, next_question, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.after_poll(game, updated, final))
        else:
            await self.hub.cancel(game, texts.GAME_TIMEOUT, defer=True)

    async def after_poll(self, previous, updated, final):
        await self.cleanup(previous)
        if final:
            await self.hub.board(
                updated,
                texts.quiz_board(updated, final=True)
                if updated.game == "quiz"
                else texts.WYR_FINISHED,
            )
            await self.hub.result_card(updated)
        else:
            await self.send_poll(updated)

    async def stop_poll(self, chat_id, message_id):
        if message_id:
            await self.sender.send(
                chat_id, lambda: self.bot.stop_poll(chat_id, message_id), priority=Priority.GAME
            )

    async def cleanup(self, game):
        if game.game in {"quiz", "wyr"}:
            await self.stop_poll(game.chat_id, game.state.get("poll_message_id"))

    async def recover(self, game):
        if game.state.get("phase") in {"sending", "rolling"}:
            await self.hub.cancel(game, texts.GAME_RESTARTED, defer=True)

    async def observe(self, game, message):
        return None
