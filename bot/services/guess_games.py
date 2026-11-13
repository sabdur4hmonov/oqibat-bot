"""Anonymous private answers with timed, context-bound group guessing."""

import random
from datetime import datetime, timedelta

from bot import texts
from bot.db.repo.games import Award
from bot.games.private_input import LOBBY_LIMITS, guess_rewards, safe_submission
from bot.keyboards import private_games as keyboards
from bot.services.sender import Priority
from bot.utils.time import utc_now


class GuessGames:
    def __init__(self, foundation):
        self.base = foundation
        self.hub, self.repo, self.cache = foundation.hub, foundation.repo, foundation.cache

    async def cleanup(self, game):
        await self.base.cleanup(game)

    async def recover(self, game):
        await self.base.recover(game)

    async def observe(self, game, message):
        pass

    def next_round(self, row, now):
        state = row.state
        if state["round"] >= len(state["order"]):
            row.status, row.phase_deadline_at = "finished", None
            state["phase"] = "done"
        else:
            state["item"] = state["order"][state["round"]]
            state["round"] += 1
            state.update(phase="answer_sending", votes={})
            row.phase_deadline_at = now + timedelta(seconds=90)

    def collection_done(self, row, now):
        order = list(row.state["items"])
        random.shuffle(order)
        row.state["order"] = order
        self.next_round(row, now)

    async def advance(self, game, now):
        phase = game.state["phase"]
        if phase == "lobby":
            if len(game.state["players"]) < LOBBY_LIMITS[game.game][0]:
                await self.hub.cancel(game, texts.PRIVATE_GAME_NOT_ENOUGH, defer=True)
                return

            def prepare(row):
                row.status = "running"
                row.state["phase"] = "preparing"
                row.phase_deadline_at = now + timedelta(seconds=90)

            updated = await self.repo.transition(
                game.chat_id, game.id, prepare, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.prepare(updated))
        elif phase == "collect":
            if not game.state["items"]:
                await self.hub.cancel(game, texts.PRIVATE_GAME_NO_ANSWERS, defer=True)
                return

            def collected(row):
                self.collection_done(row, now)

            updated = await self.repo.transition(
                game.chat_id, game.id, collected, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.send_answer(updated))
        elif phase == "guess":

            def resolve(row):
                state = row.state
                item = state["items"][state["item"]]
                if item.get("resolved"):
                    return False
                author = str(item["user_id"])
                rewards = guess_rewards(author, state["votes"], item.get("hidden", False), row.game)
                item["resolved"] = True
                item["author_points"] = rewards.get(author, 0)
                for user, points in rewards.items():
                    state["scores"][user] = state["scores"].get(user, 0) + points
                state["phase"] = "reveal_sending"
                row.phase_deadline_at = now + timedelta(seconds=90)
                return [
                    Award(
                        int(user),
                        points,
                        "private_author" if user == author else f"{row.game}_correct",
                        f"game:{row.id}:{state['item']}",
                    )
                    for user, points in rewards.items()
                ]

            updated = await self.repo.transition(
                game.chat_id, game.id, resolve, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.reveal(updated))
        else:
            await self.hub.cancel(game, defer=True)

    async def prepare(self, game):
        question = {"text": ""}
        if game.game == "kim":
            async with self.repo.locks.hold(game.chat_id) as chat_id:
                question = await self.base.content.draw(
                    self.repo.sessions, chat_id, "kim_aytdi_questions", utc_now()
                )
        elif not await self.base.can_delete(game.chat_id):
            await self.hub.cancel(game, texts.PRIVATE_GAME_NEED_DELETE, defer=True)
            return
        if question is None:
            await self.hub.cancel(game, texts.GAME_NO_CONTENT, defer=True)
            return

        def prompting(row):
            if row.state["phase"] != "preparing":
                return False
            row.state.update(
                phase="prompting", input_from=utc_now().isoformat(), question=question["text"]
            )

        game = await self.repo.transition(
            game.chat_id, game.id, prompting, expected_rev=game.state["rev"]
        )
        if not game:
            return
        for user in game.state["players"]:
            if not await self.base.dm(
                game,
                user,
                texts.KIM_QUESTION.format(question=texts.escape(question["text"]))
                if game.game == "kim"
                else texts.MEMORY_PROMPT,
            ):
                current = self.cache.get(game.id)
                if current:
                    await self.hub.cancel(current, defer=True)
                return

        def ready(row):
            if row.state["phase"] != "prompting":
                return False
            row.state["phase"] = "collect"
            row.phase_deadline_at = utc_now() + timedelta(minutes=5)
            if len(row.state["items"]) == len(row.state["players"]):
                self.collection_done(row, utc_now())

        updated = await self.repo.transition(game.chat_id, game.id, ready)
        if updated:
            if updated.state["phase"] == "answer_sending":
                await self.send_answer(updated)
            else:
                await self.base.render(game.id)

    async def private_input(self, game, message):
        user = message.from_user
        if (
            not user
            or user.is_bot
            or message.chat.type != "private"
            or message.chat.id != user.id
            or not safe_submission(message)
        ):
            return texts.PRIVATE_GAME_INVALID
        if game.game == "memory":
            if not message.photo or not message.photo[-1].file_id or message.voice or message.text:
                return texts.PRIVATE_GAME_INVALID
            item = {
                "kind": "photo",
                "file_id": message.photo[-1].file_id,
                "caption": (message.caption or "").strip(),
            }
        else:
            if not message.text or not message.text.strip() or message.photo or message.voice:
                return texts.PRIVATE_GAME_INVALID
            item = {"kind": "text", "text": message.text.strip()}
        if game.state["phase"] not in {"collect", "prompting"}:
            return texts.PRIVATE_GAME_INPUT_WAIT
        key = str(user.id)

        def submit(row):
            state, now = row.state, utc_now()
            if (
                state["phase"] not in {"collect", "prompting"}
                or row.phase_deadline_at <= now
                or key not in state["players"]
                or key in state["items"]
                or int(message.date.timestamp())
                < int(datetime.fromisoformat(state["input_from"]).timestamp())
                or not self.hub.participants.contains(row.chat_id, user.id)
            ):
                return False
            state["items"][key] = {
                **item,
                "user_id": user.id,
                "author_points": 0,
                "input_message_id": message.message_id,
            }
            if state["phase"] == "collect" and len(state["items"]) == len(state["players"]):
                self.collection_done(row, now)

        updated = await self.repo.transition(game.chat_id, game.id, submit)
        if not updated:
            return texts.PRIVATE_GAME_INPUT_WAIT
        if updated.state["phase"] == "answer_sending":
            self.hub.effects.start(self.send_answer(updated))
        return texts.PRIVATE_GAME_SAVED

    async def send_answer(self, game):
        item_id = game.state["item"]

        async def send():
            current = self.cache.get(game.id)
            if (
                not current
                or current.state["phase"] != "answer_sending"
                or current.state["round"] != game.state["round"]
            ):
                return None
            if current.game == "memory":
                if not await self.base.can_delete(game.chat_id):
                    return None
                return await self.hub.bot.send_photo(
                    game.chat_id,
                    current.state["items"][item_id]["file_id"],
                    caption=texts.private_answer(current),
                    has_spoiler=True,
                    reply_markup=keyboards.guesses(current, item_id),
                )
            return await self.hub.bot.send_message(
                game.chat_id,
                texts.private_answer(current),
                reply_markup=keyboards.guesses(current, item_id),
            )

        sent = await self.hub.sender.send(game.chat_id, send, priority=Priority.GAME)
        if not sent:
            current = self.cache.get(game.id)
            if current:
                await self.hub.cancel(current, texts.PRIVATE_GAME_DELIVERY_FAILED, defer=True)
            return

        def delivered(row):
            if row.state["phase"] != "answer_sending" or row.state["round"] != game.state["round"]:
                return False
            row.state["items"][item_id]["message_id"] = sent.message_id
            row.state["items"][item_id]["origin_chat_id"] = row.chat_id
            row.state["phase"] = "guess"
            row.phase_deadline_at = utc_now() + timedelta(seconds=30)

        updated = await self.repo.transition(game.chat_id, game.id, delivered)
        if updated:
            await self.base.render(updated.id)

    async def callback(self, query):
        try:
            prefix, number, round_number, action, target = query.data.split(":")
            game = self.cache.get(int(number))
            round_number = int(round_number)
        except (ValueError, AttributeError):
            return texts.PRIVATE_GAME_CLOSED
        user = str(query.from_user.id)
        if (
            not game
            or game.game not in {"kim", "memory"}
            or prefix != "pg"
            or action != "v"
            or query.from_user.is_bot
            or not query.message
            or query.message.chat.id != game.chat_id
            or game.state["phase"] != "guess"
            or game.state["round"] != round_number
        ):
            return texts.PRIVATE_GAME_CLOSED
        item = game.state["items"][game.state["item"]]
        if (
            query.message.message_id != item.get("message_id")
            or user == str(item["user_id"])
            or user not in game.state["players"]
            or target not in game.state["players"]
            or item.get("hidden")
        ):
            return texts.PRIVATE_GUESS_DENIED

        def vote(row):
            state = row.state
            if (
                state["phase"] != "guess"
                or state["round"] != round_number
                or row.phase_deadline_at <= utc_now()
                or user in state["votes"]
                or state["items"][state["item"]].get("hidden")
                or not self.hub.participants.contains(row.chat_id, int(user))
            ):
                return False
            state["votes"][user] = target

        updated = await self.repo.transition(game.chat_id, game.id, vote)
        return texts.PRIVATE_GUESS_SAVED if updated else texts.PRIVATE_GAME_CLOSED

    async def reveal(self, game):
        item_id = game.state["item"]

        async def edit():
            current = self.cache.get(game.id)
            if (
                not current
                or current.state["phase"] != "reveal_sending"
                or current.state["round"] != game.state["round"]
            ):
                return None
            item = current.state["items"][item_id]
            if item.get("hidden"):
                return True
            if current.game == "memory":
                return await self.hub.bot.edit_message_caption(
                    chat_id=game.chat_id,
                    message_id=item["message_id"],
                    caption=texts.private_answer(current, reveal=True),
                    reply_markup=keyboards.hide(game.id, item_id),
                )
            return await self.hub.bot.edit_message_text(
                texts.private_answer(current, reveal=True),
                chat_id=game.chat_id,
                message_id=item["message_id"],
                reply_markup=keyboards.hide(game.id, item_id),
            )

        async with self.hub.board_locks.for_chat(game.id):
            sent = await self.hub.sender.send(game.chat_id, edit, priority=Priority.GAME)
        if not sent:
            current = self.cache.get(game.id)
            if current:
                await self.hub.cancel(current, defer=True)
            return

        def advance(row):
            if row.state["phase"] != "reveal_sending" or row.state["round"] != game.state["round"]:
                return False
            self.next_round(row, utc_now())

        updated = await self.repo.transition(game.chat_id, game.id, advance)
        if updated:
            if updated.status == "finished":
                await self.hub.finish(updated, texts.private_game_board(updated))
            else:
                await self.send_answer(updated)
