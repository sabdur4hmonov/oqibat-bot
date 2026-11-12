"""A bounded DM voice chain; media stays on Telegram and group reveal is opt-in."""

from datetime import datetime, timedelta

from bot import texts
from bot.db.repo.games import Award
from bot.games import telephone as engine
from bot.games.private_input import safe_submission
from bot.keyboards import private_games as keyboards
from bot.services.sender import Priority
from bot.utils.time import utc_now


class Telephone:
    def __init__(self, foundation):
        self.base = foundation
        self.hub, self.repo, self.cache = foundation.hub, foundation.repo, foundation.cache

    async def cleanup(self, game):
        await self.base.cleanup(game)

    async def recover(self, game):
        await self.base.recover(game)

    async def observe(self, game, message):
        pass

    async def callback(self, query):
        return texts.PRIVATE_GAME_CLOSED

    def stage(self, row, now):
        state = row.state
        if state["turn"] >= len(state["order"]):
            if not state["items"]:
                row.status, row.phase_deadline_at = "cancelled", None
                state["phase"] = "done"
                return
            state.update(phase="chain_reveal", reveal_step=0)
        else:
            state.update(phase="turn_sending", round=state["turn"] + 1, input_from=now.isoformat())
        row.phase_deadline_at = now + timedelta(seconds=90)

    def schedule(self, game):
        if game.status == "cancelled":
            self.hub.effects.start(self.hub.finish(game, texts.PRIVATE_GAME_NO_ANSWERS))
        elif game.state["phase"] == "chain_reveal":
            self.hub.effects.start(self.reveal(game))
        else:
            self.hub.effects.start(self.send_turn(game))

    async def advance(self, game, now):
        phase = game.state["phase"]
        if phase == "lobby":
            if len(game.state["players"]) < 4:
                await self.hub.cancel(game, texts.PRIVATE_GAME_NOT_ENOUGH, defer=True)
                return

            def prepare(row):
                row.status, row.state["phase"] = "running", "preparing"
                row.phase_deadline_at = now + timedelta(seconds=90)

            updated = await self.repo.transition(
                game.chat_id, game.id, prepare, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.prepare(updated))
        elif phase in {"turn", "turn_sending"}:
            await self.skip(game, now)
        else:
            await self.hub.cancel(game, defer=True)

    async def prepare(self, game):
        if not await self.base.can_delete(game.chat_id):
            await self.hub.cancel(game, texts.PRIVATE_GAME_NEED_DELETE, defer=True)
            return
        async with self.repo.locks.hold(game.chat_id) as chat_id:
            phrase = await self.base.content.draw(
                self.repo.sessions, chat_id, "telephone_phrases", utc_now()
            )
        if not phrase:
            await self.hub.cancel(game, texts.GAME_NO_CONTENT, defer=True)
            return
        order = engine.player_order(game.state["players"])

        def ready(row):
            row.state.update(order=order, turn=0, phrase=phrase["text"], last_voice=None)
            self.stage(row, utc_now())

        updated = await self.repo.transition(
            game.chat_id, game.id, ready, expected_rev=game.state["rev"]
        )
        if updated:
            await self.send_turn(updated)

    async def skip(self, game, now):
        def skip(row):
            if (
                row.state["phase"] not in {"turn", "turn_sending"}
                or row.state["turn"] != game.state["turn"]
            ):
                return False
            row.state.setdefault("skipped", []).append(row.state["order"][row.state["turn"]])
            row.state["turn"] += 1
            self.stage(row, now)

        updated = await self.repo.transition(
            game.chat_id, game.id, skip, expected_rev=game.state["rev"]
        )
        if updated:
            self.schedule(updated)

    async def send_turn(self, game):
        state = game.state
        user = state["order"][state["turn"]]
        last = state["turn"] == len(state["order"]) - 1
        if last and not state["last_voice"]:
            await self.skip(game, utc_now())
            return

        async def send():
            current = self.cache.get(game.id)
            if (
                not current
                or current.state.get("turn") != state["turn"]
                or current.state["phase"] != "turn_sending"
                or not self.hub.participants.contains(game.chat_id, int(user))
            ):
                return None
            if state["last_voice"]:
                return await self.hub.bot.send_voice(
                    int(user),
                    state["last_voice"],
                    caption=texts.TELEPHONE_LAST if last else texts.TELEPHONE_REPEAT,
                )
            return await self.hub.bot.send_message(
                int(user), texts.TELEPHONE_FIRST.format(phrase=texts.escape(state["phrase"]))
            )

        sent = await self.hub.sender.send(int(user), send, priority=Priority.GAME)
        current = self.cache.get(game.id)
        if (
            not current
            or current.state.get("turn") != state["turn"]
            or current.state["phase"] != "turn_sending"
        ):
            return
        if not sent:
            await self.skip(current, utc_now())
            return

        def delivered(row):
            if row.state["phase"] != "turn_sending" or row.state["turn"] != state["turn"]:
                return False
            row.state["phase"] = "turn"
            row.state["input_from"] = utc_now().isoformat()
            row.phase_deadline_at = utc_now() + timedelta(minutes=2)

        await self.repo.transition(game.chat_id, game.id, delivered)
        await self.base.render(game.id)

    async def private_input(self, game, message):
        user, state = message.from_user, game.state
        if (
            not user
            or user.is_bot
            or message.chat.type != "private"
            or message.chat.id != user.id
            or not safe_submission(message)
        ):
            return texts.PRIVATE_GAME_INVALID
        if state["phase"] not in {"turn", "turn_sending"} or state["order"][state["turn"]] != str(
            user.id
        ):
            return texts.PRIVATE_GAME_INPUT_WAIT
        last = state["turn"] == len(state["order"]) - 1
        if last:
            if not message.text or not message.text.strip() or message.voice or message.photo:
                return texts.PRIVATE_GAME_INVALID
            item = {"kind": "text", "text": message.text.strip()}
        else:
            if (
                not message.voice
                or not message.voice.file_id
                or not engine.valid_voice(message.voice.duration)
                or message.photo
                or message.text
            ):
                return texts.PRIVATE_GAME_INVALID
            item = {"kind": "voice", "file_id": message.voice.file_id}
        key = str(user.id)

        def submit(row):
            current, now = row.state, utc_now()
            if (
                current["phase"] not in {"turn", "turn_sending"}
                or current["turn"] != state["turn"]
                or row.phase_deadline_at <= now
                or key in current["items"]
                or not self.hub.participants.contains(row.chat_id, user.id)
                or int(message.date.timestamp())
                < int(datetime.fromisoformat(current["input_from"]).timestamp())
            ):
                return False
            current["items"][key] = {
                **item,
                "user_id": user.id,
                "author_points": 0,
                "input_message_id": message.message_id,
                "turn": current["turn"],
            }
            if item["kind"] == "voice":
                current["last_voice"] = item["file_id"]
            current["turn"] += 1
            self.stage(row, now)

        updated = await self.repo.transition(game.chat_id, game.id, submit)
        if updated:
            self.schedule(updated)
            return texts.PRIVATE_GAME_SAVED
        return texts.PRIVATE_GAME_INPUT_WAIT

    def reveal_steps(self, state):
        last = state["order"][-1]
        return [None, last if last in state["items"] else "missing"] + [
            user
            for user in state["order"]
            if user in state["items"] and state["items"][user]["kind"] == "voice"
        ]

    async def reveal(self, game):
        while (current := self.cache.get(game.id)) and current.state["phase"] == "chain_reveal":
            steps = self.reveal_steps(current.state)
            step = current.state["reveal_step"]
            if step >= len(steps):

                def finish(row, step=step):
                    if row.state["phase"] != "chain_reveal" or row.state["reveal_step"] != step:
                        return False
                    scores = engine.rewards(row.state["items"])
                    row.state.update(phase="done", scores=scores)
                    row.status, row.phase_deadline_at = "finished", None
                    for user, item in row.state["items"].items():
                        item["author_points"] = scores.get(user, 0)
                    return [
                        Award(int(user), points, "telephone_submit", f"game:{row.id}:{user}")
                        for user, points in scores.items()
                    ]

                finished = await self.repo.transition(current.chat_id, current.id, finish)
                if finished:
                    await self.hub.finish(finished, texts.private_game_board(finished))
                return
            item_id = steps[step]

            async def send(step=step, item_id=item_id):
                live = self.cache.get(game.id)
                if (
                    not live
                    or live.state["phase"] != "chain_reveal"
                    or live.state["reveal_step"] != step
                ):
                    return None
                if item_id is None:
                    return await self.hub.bot.send_message(
                        game.chat_id,
                        texts.TELEPHONE_ORIGINAL.format(phrase=texts.escape(live.state["phrase"])),
                    )
                if item_id == "missing":
                    return await self.hub.bot.send_message(game.chat_id, texts.TELEPHONE_MISSING)
                item = live.state["items"][item_id]
                if item.get("hidden"):
                    return True
                markup = keyboards.hide(game.id, item_id)
                if item["kind"] == "voice":
                    if not await self.base.can_delete(game.chat_id):
                        return None
                    return await self.hub.bot.send_voice(
                        game.chat_id,
                        item["file_id"],
                        caption=texts.telephone_item(live, item_id),
                        reply_markup=markup,
                    )
                return await self.hub.bot.send_message(
                    game.chat_id, texts.telephone_item(live, item_id), reply_markup=markup
                )

            async with self.hub.board_locks.for_chat(game.id):
                sent = await self.hub.sender.send(game.chat_id, send, priority=Priority.GAME)
            if not sent:
                live = self.cache.get(game.id)
                if live:
                    await self.hub.cancel(live, texts.PRIVATE_GAME_DELIVERY_FAILED, defer=True)
                return

            def delivered(row, step=step, item_id=item_id, sent=sent):
                if row.state["phase"] != "chain_reveal" or row.state["reveal_step"] != step:
                    return False
                if item_id not in {None, "missing"} and hasattr(sent, "message_id"):
                    row.state["items"][item_id]["message_id"] = sent.message_id
                    row.state["items"][item_id]["origin_chat_id"] = row.chat_id
                row.state["reveal_step"] += 1
                row.phase_deadline_at = utc_now() + timedelta(seconds=90)

            updated = await self.repo.transition(current.chat_id, current.id, delivered)
            if not updated:
                return
