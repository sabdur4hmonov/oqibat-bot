"""Mafia lifecycle. State commits never wait for Telegram delivery."""

import asyncio
from datetime import datetime, timedelta

from aiogram.exceptions import TelegramForbiddenError

from bot import texts
from bot.db.models import Chat
from bot.db.repo.games import Award, GameBusy
from bot.games.mafia import engine
from bot.games.mafia.roles import MAFIA, assign
from bot.keyboards import mafia as keyboards
from bot.services.locks import ChatLocks
from bot.services.sender import Priority
from bot.utils.time import utc_now


class Mafia:
    def __init__(self, hub, sessions, username):
        self.hub, self.repo, self.cache = hub, hub.repo, hub.cache
        self.sessions, self.username = sessions, username
        self.members: dict[int, int] = {}
        self.join_lock = asyncio.Lock()
        self.private_locks = ChatLocks()
        self.refreshes: dict[int, set[str]] = {}
        self.last_render = {}
        self.deleting = set()
        self.cache.listeners.append(self.sync_members)

    def sync_members(self, game, old=None):
        if game.game != "mafia":
            return
        current = (
            set(game.state.get("players", {})) if game.status in {"lobby", "running"} else set()
        )
        previous = set(old.state.get("players", {})) if old else set(game.state.get("players", {}))
        for user in previous - current:
            if self.members.get(int(user)) == game.id:
                self.members.pop(int(user), None)
        for user in current:
            self.members[int(user)] = game.id

    def load(self):
        self.members = {
            int(user): game.id
            for game in self.cache.records.values()
            if game.game == "mafia"
            for user in game.state.get("players", {})
        }

    def _deadline(self, state, now, seconds):
        return min(now + timedelta(seconds=seconds), datetime.fromisoformat(state["hard_deadline"]))

    async def start(self, message):
        user = message.from_user
        if user is None or user.is_bot:
            return texts.GAME_JOIN_FIRST
        now = utc_now()
        async with self.sessions() as session:
            chat = await session.get(Chat, message.chat.id)
        state = {
            "phase": "lobby",
            "round": 0,
            "players": {},
            "dm_ids": {},
            "started_at": now.isoformat(),
            "hard_deadline": (now + timedelta(minutes=60)).isoformat(),
            "delete_dead": bool(chat and chat.mafia_delete_dead_messages),
            "removed": [],
            "setup_attempt": 0,
            "chat_title": chat.title if chat else "",
        }
        try:
            game = await self.repo.start(
                message.chat.id,
                user.id,
                "mafia",
                state,
                now + timedelta(seconds=90),
                status="lobby",
            )
        except GameBusy:
            return texts.GAME_BUSY
        if game is None:
            return texts.GAME_JOIN_FIRST
        sent = await self.hub.board(
            game, texts.mafia_group(game), keyboards.lobby(self.username, game.id)
        )
        if sent:
            self.last_render[(game.id, 0)] = (
                sent.message_id,
                texts.mafia_group(game),
                keyboards.lobby(self.username, game.id).model_dump_json(),
            )
        game = await self.hub.attach_board(game, sent)
        if game:
            self.refresh(game.id, "group")
        return None

    async def join(self, session_id, user):
        game = self.cache.get(session_id)
        if game is None or game.game != "mafia":
            return texts.MAFIA_LOBBY_CLOSED
        async with self.join_lock:
            existing_id = self.members.get(user.id)
            existing = self.cache.get(existing_id) if existing_id else None
            if (
                existing
                and existing.id != session_id
                and str(user.id) in existing.state.get("players", {})
            ):
                return texts.MAFIA_ALREADY_PLAYING
            if not self.hub.participants.contains(game.chat_id, user.id):
                return texts.MAFIA_OPT_IN

            def add(row):
                if row.state["phase"] != "lobby" or row.phase_deadline_at <= utc_now():
                    return False
                if not self.hub.participants.contains(row.chat_id, user.id):
                    return False
                if str(user.id) in row.state["players"]:
                    return False
                if len(row.state["players"]) >= 15:
                    return False
                row.state["players"][str(user.id)] = user.first_name

            updated = await self.repo.transition(game.chat_id, game.id, add)
            if updated is None:
                return texts.MAFIA_LOBBY_CLOSED
            self.members[user.id] = game.id
        self.refresh(game.id, "group")
        return texts.MAFIA_JOINED

    def refresh(self, game_id, *modes):
        if game_id in self.refreshes:
            self.refreshes[game_id].update(modes)
            return
        self.refreshes[game_id] = set(modes)
        self.hub.effects.start(self._refresh(game_id))

    async def _refresh(self, game_id):
        try:
            while self.refreshes.get(game_id):
                modes = set(self.refreshes[game_id])
                self.refreshes[game_id].clear()
                if "group" in modes:
                    await self.group_board(game_id)
                game = self.cache.get(game_id)
                if game and "roles" in game.state:
                    users = (
                        game.state["players"]
                        if "private" in modes
                        else (
                            [
                                user
                                for user in game.state["alive"]
                                if game.state["roles"][user] == MAFIA
                            ]
                            if "mafia" in modes
                            else []
                        )
                    )
                    for user in users:
                        await self.private_board(game_id, int(user))
        finally:
            self.refreshes.pop(game_id, None)

    async def group_board(self, game_id):
        async with self.hub.board_locks.for_chat(game_id):
            new_board = None

            async def send():
                nonlocal new_board
                game = self.cache.get(game_id)
                if game is None:
                    return None
                markup = (
                    keyboards.lobby(self.username, game.id)
                    if game.state["phase"] == "lobby"
                    else keyboards.actions(game)
                )
                text = texts.mafia_group(game)
                message_id = game.state.get("board_id")
                signature = (message_id, text, markup.model_dump_json() if markup else None)
                if self.last_render.get((game.id, 0)) == signature:
                    return True
                if message_id:
                    result = await self.hub.bot.edit_message_text(
                        text, chat_id=game.chat_id, message_id=message_id, reply_markup=markup
                    )
                else:
                    result = await self.hub.bot.send_message(
                        game.chat_id, text, reply_markup=markup
                    )
                    new_board = result.message_id
                    signature = (new_board, text, markup.model_dump_json() if markup else None)
                self.last_render[(game.id, 0)] = signature
                return result

            game = self.cache.get(game_id)
            if game:
                result = await self.hub.sender.send(game.chat_id, send, priority=Priority.GAME)
                if new_board is not None:

                    def attach(row):
                        if row.state.get("board_id") is not None:
                            return False
                        row.state["board_id"] = new_board

                    await self.repo.transition(game.chat_id, game.id, attach)
                return result
            return None

    async def private_board(self, game_id, user):
        async with self.private_locks.for_chat(user):

            async def send():
                game = self.cache.get(game_id)
                if (
                    game is None
                    or "roles" not in game.state
                    or str(user) not in game.state["dm_ids"]
                ):
                    return None
                markup = keyboards.actions(game, user)
                text = texts.mafia_private(game, user)
                signature = (text, markup.model_dump_json() if markup else None)
                if self.last_render.get((game.id, user)) == signature:
                    return True
                result = await self.hub.bot.edit_message_text(
                    text,
                    chat_id=user,
                    message_id=game.state["dm_ids"][str(user)],
                    reply_markup=markup,
                )
                self.last_render[(game.id, user)] = signature
                return result

            return await self.hub.sender.send(user, send, priority=Priority.GAME)

    async def _role_delivery(self, game, user, text):
        forbidden = False
        async with self.private_locks.for_chat(int(user)):

            async def send():
                nonlocal forbidden
                current = self.cache.get(game.id)
                if current is None or current.state["phase"] != "preparing":
                    return None
                try:
                    message_id = current.state["dm_ids"].get(user)
                    if message_id:
                        return await self.hub.bot.edit_message_text(
                            text, chat_id=int(user), message_id=message_id
                        )
                    return await self.hub.bot.send_message(int(user), text)
                except TelegramForbiddenError:
                    forbidden = True
                    raise

            sent = await self.hub.sender.send(int(user), send, priority=Priority.GAME)
        return sent, forbidden

    async def prepare(self, game):
        # Role proposals do not become assigned/usable until every remaining DM succeeds.
        # A forbidden player is removed and all proposals are discarded/recalculated.
        while (current := self.cache.get(game.id)) and current.state["phase"] == "preparing":
            if utc_now() >= datetime.fromisoformat(current.state["hard_deadline"]):
                await self.advance(current, utc_now())
                return
            users = list(current.state["players"])
            missing = [
                user
                for user in users
                if not self.hub.participants.contains(current.chat_id, int(user))
            ]
            if missing:
                await self.remove_unreachable(current, missing)
                continue
            if len(users) < 5:
                await self.hub.cancel(current, texts.MAFIA_TOO_FEW, defer=True)
                return

            def attempt(row):
                if row.state["phase"] != "preparing":
                    return False
                row.state["setup_attempt"] = row.state.get("setup_attempt", 0) + 1

            current = await self.repo.transition(current.chat_id, current.id, attempt)
            if current is None:
                return
            proposed = assign(users)
            deliveries = {}
            forbidden = []
            for user in users:
                sent, blocked = await self._role_delivery(
                    current, user, texts.mafia_proposal(current, user, proposed)
                )
                if blocked:
                    forbidden.append(user)
                elif sent is None:
                    if self.cache.get(game.id):
                        await self.hub.cancel(current, texts.MAFIA_DELIVERY_FAILED, defer=True)
                    return
                else:
                    deliveries[user] = sent.message_id
            if forbidden:

                def save_ids(row, deliveries=deliveries):
                    row.state["dm_ids"].update(deliveries)

                updated = await self.repo.transition(current.chat_id, current.id, save_ids)
                if updated:
                    await self.remove_unreachable(updated, forbidden)
                continue

            def confirm(row, proposed=proposed, deliveries=deliveries):
                if row.state["phase"] != "preparing" or set(row.state["players"]) != set(proposed):
                    return False
                if any(
                    not self.hub.participants.contains(row.chat_id, int(user)) for user in proposed
                ):
                    return False
                if utc_now() >= datetime.fromisoformat(row.state["hard_deadline"]):
                    return False
                row.state["dm_ids"].update(deliveries)
                row.state = engine.start(row.state, utc_now(), roles=proposed)
                row.phase_deadline_at = self._deadline(row.state, utc_now(), 60)

            updated = await self.repo.transition(current.chat_id, current.id, confirm)
            if updated:
                self.refresh(updated.id, "group", "private")
                return

    async def remove_unreachable(self, game, users):
        def remove(row):
            if row.state["phase"] != "preparing":
                return False
            for user in users:
                name = row.state["players"].pop(user, None)
                row.state["dm_ids"].pop(user, None)
                if name is not None:
                    row.state["removed"].append(name)

        updated = await self.repo.transition(game.chat_id, game.id, remove)
        async with self.join_lock:
            for user in users:
                if self.members.get(int(user)) == game.id:
                    self.members.pop(int(user), None)
        if updated:
            await self.group_board(game.id)  # announces removed names before confirming roles

    async def callback(self, query):
        try:
            prefix, session, round_number, operation, target = (query.data or "").split(":")
            session, round_number, target = int(session), int(round_number), int(target)
        except ValueError:
            return texts.MAFIA_STALE
        game = self.cache.get(session)
        if (
            prefix != "mf"
            or operation not in {"m", "d", "c", "v"}
            or game is None
            or game.game != "mafia"
            or game.state["round"] != round_number
            or query.message is None
        ):
            return texts.MAFIA_STALE
        user = query.from_user.id
        if operation == "v":
            if query.message.chat.id != game.chat_id:
                return texts.MAFIA_STALE
        elif query.message.chat.type != "private" or query.message.chat.id != user:
            return texts.MAFIA_STALE
        checked = None

        def choose(row):
            nonlocal checked
            if (
                row.state["round"] != round_number
                or row.phase_deadline_at <= utc_now()
                or datetime.fromisoformat(row.state["hard_deadline"]) <= utc_now()
                or not self.hub.participants.contains(row.chat_id, user)
            ):
                return False
            changed = engine.action(row.state, user, operation, target)
            if changed is None:
                return False
            row.state = changed
            if operation == "c":
                checked = changed["roles"][str(target)] == MAFIA

        updated = await self.repo.transition(game.chat_id, game.id, choose)
        if updated is None:
            return texts.MAFIA_STALE
        if operation == "m":
            self.refresh(game.id, "mafia")
        elif operation == "v":
            self.refresh(game.id, "group")
        if checked is not None:
            return texts.MAFIA_IS_MAFIA if checked else texts.MAFIA_NOT_MAFIA
        return texts.MAFIA_CHOICE_SAVED

    async def advance(self, game, now):
        phase = game.state["phase"]
        if phase == "lobby":
            if len(game.state["players"]) < 5:
                await self.hub.cancel(game, texts.MAFIA_TOO_FEW, defer=True)
                return

            def preparing(row):
                row.status = "running"
                row.state["phase"] = "preparing"
                row.phase_deadline_at = datetime.fromisoformat(row.state["hard_deadline"])

            updated = await self.repo.transition(
                game.chat_id, game.id, preparing, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.prepare(updated))
            return
        if phase == "preparing":

            def cap(row):
                row.state.update(phase="done", winner="draw", roles={}, alive=[])
                row.status, row.phase_deadline_at = "finished", None

            updated = await self.repo.transition(
                game.chat_id, game.id, cap, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.hub.finish(updated, texts.mafia_group(updated)))
            return

        def transition(row):
            row.state = engine.advance(row.state, now)
            if row.state["phase"] == "done":
                row.status, row.phase_deadline_at = "finished", None
                return [
                    Award(user, delta, reason, f"game:{row.id}")
                    for user, delta, reason in engine.awards(row.state)
                ]
            row.phase_deadline_at = self._deadline(
                row.state, now, engine.PHASE_SECONDS[row.state["phase"]]
            )

        updated = await self.repo.transition(
            game.chat_id, game.id, transition, expected_rev=game.state["rev"]
        )
        if updated:
            if updated.status == "finished":
                self.hub.effects.start(self.hub.finish(updated, texts.mafia_group(updated)))
            else:
                self.refresh(updated.id, "group", "private")

    async def membership_changed(self, chat_id, user):
        game = self.cache.main(chat_id)
        if (
            game is None
            or game.game != "mafia"
            or str(user) not in game.state["players"]
            or self.hub.participants.contains(chat_id, user)
        ):
            return

        def leave(row):
            if row.state["phase"] == "preparing":
                return False  # prepare() revalidates consent before role confirmation
            if row.state["phase"] == "lobby":
                row.state["players"].pop(str(user), None)
                return []
            changed = engine.forfeit(row.state, user)
            if changed is None:
                return False
            row.state = changed
            if changed["phase"] == "done":
                row.status, row.phase_deadline_at = "finished", None
                return [
                    Award(who, delta, reason, f"game:{row.id}")
                    for who, delta, reason in engine.awards(changed)
                ]

        updated = await self.repo.transition(chat_id, game.id, leave)
        if updated:
            if updated.status == "finished":
                self.hub.effects.start(self.hub.finish(updated, texts.mafia_group(updated)))
            else:
                self.refresh(game.id, "group", "private")

    async def observe(self, game, message):
        if not message.from_user:
            return
        user = message.from_user.id
        if not self.hub.participants.contains(game.chat_id, user):
            await self.membership_changed(game.chat_id, user)
            return
        if (
            not game.state.get("delete_dead")
            or "alive" not in game.state
            or str(user) not in game.state["players"]
            or str(user) in game.state["alive"]
        ):
            return
        key = (game.id, message.message_id)
        if key in self.deleting or len(self.deleting) >= 5000:
            return
        self.deleting.add(key)
        self.hub.effects.start(self.delete_message(game, message, key))

    async def delete_message(self, game, message, key):
        try:

            async def delete():
                current = self.cache.get(game.id)
                if (
                    current is None
                    or not current.state.get("delete_dead")
                    or str(message.from_user.id) in current.state["alive"]
                ):
                    return False
                me = await self.hub.bot.get_chat_member(current.chat_id, self.hub.bot.id)
                if me.status != "administrator" or not getattr(me, "can_delete_messages", False):
                    return False
                return await self.hub.bot.delete_message(current.chat_id, message.message_id)

            await self.hub.sender.send(game.chat_id, delete, priority=Priority.GAME)
        finally:
            self.deleting.discard(key)

    async def cleanup(self, game):
        async with self.join_lock:
            for user in game.state.get("players", {}):
                if self.members.get(int(user)) == game.id:
                    self.members.pop(int(user), None)
        for user in game.state.get("players", {}):
            async with self.private_locks.for_chat(int(user)):
                message_id = game.state.get("dm_ids", {}).get(user)
                text = texts.mafia_end_dm(game, int(user))

                async def send(user=user, message_id=message_id, text=text):
                    from bot.db.models import GameSession

                    async with self.sessions() as session:
                        row = await session.get(GameSession, game.id)
                        if row is None or row.state.get("erased"):
                            return None
                    if message_id:
                        return await self.hub.bot.edit_message_text(
                            text, chat_id=int(user), message_id=message_id
                        )
                    return await self.hub.bot.send_message(int(user), text)

                await self.hub.sender.send(int(user), send, priority=Priority.GAME)
            self.last_render.pop((game.id, int(user)), None)
        self.last_render.pop((game.id, 0), None)

    async def recover(self, game):
        await self.hub.cancel(game, texts.MAFIA_RESTART, defer=True)
