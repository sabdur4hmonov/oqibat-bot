"""Bounded private-input sessions, using the existing game repository and sender."""

import logging
import random
from datetime import datetime, timedelta
from html import escape

from aiogram.exceptions import TelegramRetryAfter

from bot import texts
from bot.db.models import GameSession
from bot.db.repo.games import Award, GameBusy
from bot.games.private_input import LOBBY_LIMITS, matches, repair_cycle, replacement, target_cycle
from bot.keyboards import private_games as keyboards
from bot.services.game_cache import view
from bot.services.points import record_event
from bot.services.sender import Priority
from bot.utils.time import utc_now

logger = logging.getLogger(__name__)


class PrivateGames:
    def __init__(self, hub, contexts, content, username):
        self.hub, self.repo, self.cache = hub, hub.repo, hub.cache
        self.contexts, self.content, self.username = contexts, content, username
        self.words = {}
        self.cache.listeners.append(self.sync_words)

    def sync_words(self, game, old=None):
        if game.game != "secret":
            return
        if old:
            self.words.pop(old.chat_id, None)
        self.words.pop(game.chat_id, None)
        if game.status == "running" and game.state.get("phase") == "hunt":
            self.words[game.chat_id] = {
                hunter: (game.state["targets"][hunter], word)
                for hunter, word in game.state["words"].items()
                if word
            }

    async def start(self, message, kind="secret"):
        user = message.from_user
        if not user or user.is_bot:
            return texts.GAME_JOIN_FIRST
        if kind == "telephone" and not await self.can_delete(message.chat.id):
            return texts.PRIVATE_GAME_NEED_DELETE
        state = {
            "phase": "lobby",
            "round": 0,
            "players": {},
            "hours": 24,
            "scores": {},
            "items": {},
            "message_floor": message.message_id,
        }
        try:
            game = await self.repo.start(
                message.chat.id,
                user.id,
                kind,
                state,
                utc_now() + timedelta(minutes=LOBBY_LIMITS[kind][2]),
                status="lobby",
            )
        except GameBusy:
            return texts.GAME_BUSY
        if not game:
            return texts.GAME_JOIN_FIRST
        sent = await self.hub.board(
            game, texts.private_game_board(game), keyboards.lobby(self.username, game)
        )
        await self.hub.attach_board(game, sent)
        return None

    async def can_delete(self, chat_id):
        try:
            member = await self.hub.bot.get_chat_member(chat_id, self.hub.bot.id)
            return member.status == "creator" or (
                member.status == "administrator"
                and bool(getattr(member, "can_delete_messages", False))
            )
        except TelegramRetryAfter as error:
            self.hub.sender.limiter.pause(None, self.hub.sender.clock.now() + error.retry_after)
            logger.warning(
                "Media permission rate limit chat=%s retry_after=%s", chat_id, error.retry_after
            )
            return False
        except Exception as error:
            logger.warning(
                "Media permission lookup failed chat=%s type=%s", chat_id, type(error).__name__
            )
            return False

    async def join(self, game_id, user, kind):
        async with self.contexts.lock:
            game = self.cache.get(game_id)
            if (
                user.is_bot
                or not game
                or game.game != kind
                or game.state["phase"] != "lobby"
                or game.phase_deadline_at <= utc_now()
            ):
                return texts.PRIVATE_GAME_CLOSED
            existing = self.contexts.get(user.id)
            if existing and existing.id != game.id:
                return texts.PRIVATE_GAME_BUSY
            if not self.hub.participants.contains(game.chat_id, user.id):
                return texts.MAFIA_OPT_IN
            if str(user.id) in game.state["players"]:
                return texts.PRIVATE_GAME_JOINED

            def add(row):
                if (
                    row.state["phase"] != "lobby"
                    or row.phase_deadline_at <= utc_now()
                    or len(row.state["players"]) >= LOBBY_LIMITS[kind][1]
                    or not self.hub.participants.contains(row.chat_id, user.id)
                ):
                    return False
                row.state["players"][str(user.id)] = user.first_name[:20]

            updated = await self.repo.transition(game.chat_id, game.id, add)
        if not updated:
            return texts.PRIVATE_GAME_CLOSED
        self.hub.effects.start(self.render(game.id))
        return texts.PRIVATE_GAME_JOINED

    async def render(self, game_id):
        game = self.cache.get(game_id)
        if game:
            await self.hub.board(
                game,
                texts.private_game_board(game),
                keyboards.lobby(self.username, game) if game.state["phase"] == "lobby" else None,
            )

    async def dm(self, game, user, text):
        async def send():
            # Privacy and lifecycle are rechecked at actual delivery, not queue admission.
            current = self.cache.get(game.id)
            if not current or str(user) not in current.state.get("players", {}):
                return None
            if game.game == "secret" and (
                current.state.get("words", {}).get(str(user))
                != game.state.get("words", {}).get(str(user))
                or current.state.get("targets", {}).get(str(user))
                != game.state.get("targets", {}).get(str(user))
            ):
                return None
            return await self.hub.bot.send_message(int(user), text)

        return await self.hub.sender.send(int(user), send, priority=Priority.GAME)

    def bank_words(self):
        from bot.utils.text_normalize import normalize_text

        return list(
            {
                normalize_text(item["word"]): item["word"]
                for item in self.content.banks["secret_words"]
            }.values()
        )

    async def advance(self, game, now):
        if game.state["phase"] == "lobby":
            players = game.state["players"]
            words = self.bank_words()
            if len(players) < 3 or len(words) < len(players) + 1:
                await self.hub.cancel(game, texts.PRIVATE_GAME_NOT_ENOUGH, defer=True)
                return
            chosen = random.sample(words, len(players))
            targets = target_cycle(players)

            def prepare(row):
                row.status = "running"
                row.state.update(
                    phase="preparing",
                    targets=targets,
                    words=dict(zip(players, chosen, strict=True)),
                    successes={},
                    accusations={},
                    cooldowns={},
                    last_messages={},
                )
                row.phase_deadline_at = now + timedelta(seconds=90)

            updated = await self.repo.transition(
                game.chat_id, game.id, prepare, expected_rev=game.state["rev"]
            )
            if updated:
                self.hub.effects.start(self.prepare_secret(updated))
        elif game.state["phase"] == "hunt":

            def finish(row):
                row.status, row.phase_deadline_at = "finished", None
                row.state["phase"] = "done"

            finished = await self.repo.transition(
                game.chat_id, game.id, finish, expected_rev=game.state["rev"]
            )
            if finished:
                self.hub.effects.start(
                    self.hub.finish(finished, texts.private_game_board(finished))
                )
        else:
            await self.hub.cancel(game, defer=True)

    async def secret_dm(self, game, hunter):
        word = game.state["words"].get(hunter)
        target = game.state["targets"].get(hunter)
        text = (
            texts.SECRET_WORD_DM.format(
                target=escape(game.state["players"].get(target, "")), word=escape(word)
            )
            if word
            else texts.SECRET_NO_MORE
        )
        return await self.dm(game, hunter, text)

    async def prepare_secret(self, game):
        # Membership may change while DMs are rate-limited. Re-send the repaired
        # assignment set, never confirm a snapshot that still contains a leaver.
        while (current := self.cache.get(game.id)) and current.state["phase"] == "preparing":
            revision = current.state["rev"]
            for hunter in current.state["players"]:
                if not await self.secret_dm(current, hunter):
                    latest = self.cache.get(game.id)
                    if latest and latest.state["rev"] != revision:
                        break
                    if latest:
                        await self.hub.cancel(latest, defer=True)
                    return
            else:

                def ready(row):
                    if row.state["phase"] != "preparing":
                        return False
                    row.state["phase"] = "hunt"
                    row.state["hunt_started_at"] = utc_now().isoformat()
                    row.phase_deadline_at = utc_now() + timedelta(hours=row.state["hours"])

                updated = await self.repo.transition(
                    game.chat_id, game.id, ready, expected_rev=revision
                )
                if updated:
                    await self.render(game.id)
                    return

    async def callback(self, query):
        try:
            prefix, number, round_number, action, value = query.data.split(":")
            game = self.cache.get(int(number))
            round_number = int(round_number)
        except (ValueError, AttributeError):
            return texts.PRIVATE_GAME_CLOSED
        if game and game.game != "secret":
            service = self.hub.services.get(game.game)
            return (
                await service.callback(query)
                if service and service is not self
                else texts.PRIVATE_GAME_CLOSED
            )
        if (
            prefix != "pg"
            or not game
            or game.game != "secret"
            or query.from_user.is_bot
            or not query.message
            or query.message.chat.id != game.chat_id
            or query.message.message_id != game.state.get("board_id")
            or game.state["round"] != round_number
            or game.state["phase"] != "lobby"
            or game.phase_deadline_at <= utc_now()
            or query.from_user.id != game.started_by
            or action != "h"
            or value not in {"2", "6", "24"}
        ):
            return texts.PRIVATE_GAME_CLOSED

        def change(row):
            row.state["hours"] = int(value)

        updated = await self.repo.transition(
            game.chat_id, game.id, change, expected_rev=game.state["rev"]
        )
        if updated:
            self.hub.effects.start(self.render(game.id))
        return texts.SECRET_DURATION.format(hours=value)

    async def private_input(self, game, message):
        if (
            game.game != "secret"
            and (service := self.hub.services.get(game.game))
            and service is not self
        ):
            return await service.private_input(game, message)
        return texts.PRIVATE_GAME_INPUT_WAIT

    def rotate_word(self, state, hunter):
        old = state["words"].pop(hunter, None)
        word = (
            None
            if state["successes"].get(hunter, 0) >= 3
            else replacement(self.bank_words(), state["words"], old or "")
        )
        state["words"][hunter] = word

    async def observe(self, game, message):
        index = self.words.get(message.chat.id)
        user = message.from_user
        if (
            not index
            or not user
            or user.is_bot
            or message.forward_origin
            or message.edit_date
            or message.sender_chat
            or message.message_id <= game.state["message_floor"]
        ):
            return
        value = message.text or message.caption or ""
        hits = [
            (hunter, word)
            for hunter, (target, word) in index.items()
            if target == str(user.id) and matches(word, value)
        ]
        if not hits or not self.hub.participants.contains(game.chat_id, user.id):
            return
        hunter, word = hits[0]

        def success(row):
            state = row.state
            if (
                state["phase"] != "hunt"
                or row.phase_deadline_at <= utc_now()
                or state["words"].get(hunter) != word
                or state["targets"].get(hunter) != str(user.id)
                or message.message_id <= state["last_messages"].get(str(user.id), 0)
                or int(message.date.timestamp())
                < int(datetime.fromisoformat(state["hunt_started_at"]).timestamp())
                or not self.hub.participants.contains(row.chat_id, int(hunter))
            ):
                return False
            state["last_messages"][str(user.id)] = message.message_id
            state["successes"][hunter] = state["successes"].get(hunter, 0) + 1
            state["scores"][hunter] = state["scores"].get(hunter, 0) + 10
            self.rotate_word(state, hunter)
            return [
                Award(
                    int(hunter),
                    10,
                    "secret_success",
                    f"game:{row.id}:{hunter}:{state['successes'][hunter]}",
                )
            ]

        updated = await self.repo.transition(game.chat_id, game.id, success)
        if updated:
            text = texts.SECRET_REVEAL.format(
                hunter=escape(updated.state["players"][hunter]),
                target=escape(user.first_name),
                word=escape(word),
            )
            self.hub.effects.start(self.secret_notice(updated, hunter, text))

    async def secret_notice(self, game, hunter, text):
        async def send():
            current = self.cache.get(game.id)
            if current:
                return await self.hub.bot.send_message(game.chat_id, text)

        await self.hub.sender.send(game.chat_id, send, priority=Priority.GAME)
        current = self.cache.get(game.id)
        if current and hunter in current.state["players"]:
            await self.secret_dm(current, hunter)

    async def accuse(self, message):
        game = self.cache.background(message.chat.id)
        reply, user = message.reply_to_message, message.from_user
        if (
            not game
            or game.state["phase"] != "hunt"
            or not user
            or user.is_bot
            or not reply
            or not reply.from_user
            or reply.from_user.is_bot
            or str(user.id) not in game.state["players"]
            or reply.chat.id != game.chat_id
        ):
            return texts.SECRET_ACCUSE_LIMIT
        accuser, hunter = str(user.id), str(reply.from_user.id)
        result = {}

        def accuse(row):
            state, now = row.state, utc_now()
            if (
                state["phase"] != "hunt"
                or row.phase_deadline_at <= now
                or not self.hub.participants.contains(row.chat_id, user.id)
                or accuser == hunter
                or state["accusations"].get(accuser, 0) >= 3
                or message.message_id <= state["last_messages"].get(accuser, 0)
                or state["cooldowns"].get(accuser, 0) > now.timestamp()
            ):
                return False
            state["last_messages"][accuser] = message.message_id
            state["accusations"][accuser] = state["accusations"].get(accuser, 0) + 1
            correct = state["targets"].get(hunter) == accuser and bool(state["words"].get(hunter))
            result.update(correct=correct, word=state["words"].get(hunter))
            points = 5 if correct else -2
            state["scores"][accuser] = state["scores"].get(accuser, 0) + points
            if correct:
                self.rotate_word(state, hunter)
            else:
                state["cooldowns"][accuser] = (now + timedelta(hours=1)).timestamp()
            return [
                Award(
                    user.id,
                    points,
                    "secret_accuse",
                    f"game:{row.id}:{accuser}:{state['accusations'][accuser]}",
                )
            ]

        updated = await self.repo.transition(game.chat_id, game.id, accuse)
        if not updated:
            return texts.SECRET_ACCUSE_LIMIT
        if result["correct"]:
            text = texts.SECRET_EXPOSED.format(
                accuser=escape(user.first_name),
                hunter=escape(updated.state["players"][hunter]),
                word=escape(result["word"]),
            )
            self.hub.effects.start(self.secret_notice(updated, hunter, text))
            return None
        return texts.SECRET_WRONG

    async def membership_changed(self, chat_id, user):
        for game in self.cache.for_chat(chat_id):
            if (
                game.game in {"kim", "telephone"}
                and str(user) in game.state.get("players", {})
                and not self.hub.participants.contains(chat_id, user)
            ):
                await self.hub.cancel(game, defer=True)
                continue
            if (
                game.game != "secret"
                or str(user) not in game.state.get("players", {})
                or self.hub.participants.contains(chat_id, user)
            ):
                continue

            def repair(row):
                state, key = row.state, str(user)
                state["players"].pop(key, None)
                if state["phase"] in {"hunt", "preparing"}:
                    state["words"].pop(key, None)
                    order, cursor = [], next(iter(state["targets"]))
                    while cursor not in order:
                        order.append(cursor)
                        cursor = state["targets"][cursor]
                    state["targets"] = repair_cycle([item for item in order if item != key])
                if len(state["players"]) < 3 and state["phase"] != "lobby":
                    row.status, row.phase_deadline_at = "cancelled", None
                    state["phase"] = "done"

            updated = await self.repo.transition(chat_id, game.id, repair)
            if updated and updated.status == "cancelled":
                self.hub.effects.start(self.hub.finish(updated, texts.GAME_CANCELLED))
            elif updated:
                self.hub.effects.start(self.repair_notice(updated))

    async def repair_notice(self, game):
        if game.state["phase"] == "hunt":
            for hunter in game.state["players"]:
                await self.secret_dm(game, hunter)
        await self.render(game.id)

    async def recover(self, game):
        await self.hub.cancel(game, defer=True)

    async def cleanup(self, game):
        for user in game.state.get("players", {}):

            async def send(user=user):
                async with self.repo.sessions() as session:
                    row = await session.get(GameSession, game.id)
                    if not row or row.state.get("erased") or self.contexts.get(int(user)):
                        return None
                return await self.hub.bot.send_message(int(user), texts.PRIVATE_GAME_ENDED)

            await self.hub.sender.send(int(user), send, priority=Priority.GAME)

    async def hide(self, query):
        try:
            prefix, number, item_id = query.data.split(":")
            game_id = int(number)
        except (AttributeError, ValueError):
            return texts.PRIVATE_GAME_CLOSED
        if (
            prefix != "ph"
            or query.from_user.is_bot
            or not query.message
            or query.message.chat.id >= 0
        ):
            return texts.PRIVATE_GAME_CLOSED
        chat_id = query.message.chat.id
        try:
            if query.from_user.id not in await self.hub.admins.get(chat_id):
                return texts.PRIVATE_GAME_HIDE_DENIED
        except Exception:
            return texts.ADMIN_CHECK_FAILED
        item = None
        async with self.repo.locks.hold(chat_id) as chat_id:
            async with self.repo.sessions.begin() as session:
                row = await session.get(GameSession, game_id)
                if not row or row.chat_id != chat_id or row.state.get("erased"):
                    return texts.PRIVATE_GAME_CLOSED
                from copy import deepcopy

                state = deepcopy(row.state)
                item = state.get("items", {}).get(item_id)
                if (
                    not item
                    or item.get("message_id") != query.message.message_id
                    or item.get("origin_chat_id", row.chat_id) != row.chat_id
                    or item.get("hidden")
                ):
                    return texts.PRIVATE_GAME_CLOSED
                item["hidden"] = True
                reward = item.get("author_points", 0)
                if reward:
                    await record_event(
                        session,
                        chat_id,
                        item["user_id"],
                        -reward,
                        "private_hidden",
                        f"game:{game_id}:{item_id}",
                    )
                    state["scores"][str(item["user_id"])] = (
                        state.get("scores", {}).get(str(item["user_id"]), 0) - reward
                    )
                    item["author_points"] = 0
                row.state = {**state, "rev": state.get("rev", 0) + 1}
            self.cache.sync(row)
            game = view(row)

        async with self.hub.board_locks.for_chat(game.id):
            return await self._apply_hide(query, game, item)

    async def _apply_hide(self, query, game, item):
        chat_id, game_id = game.chat_id, game.id

        async def remove():
            async with self.repo.sessions() as session:
                current = await session.get(GameSession, game_id)
                if not current or current.state.get("erased"):
                    return None
            member = await self.hub.bot.get_chat_member(chat_id, self.hub.bot.id)
            if member.status == "creator" or (
                member.status == "administrator" and getattr(member, "can_delete_messages", False)
            ):
                return await self.hub.bot.delete_message(chat_id, query.message.message_id)
            return False

        removed = await self.hub.sender.send(chat_id, remove, priority=Priority.GAME)
        marked = None
        if not removed:

            async def mark():
                async with self.repo.sessions() as session:
                    current = await session.get(GameSession, game_id)
                    if not current or current.state.get("erased"):
                        return None
                if item["kind"] == "text":
                    return await self.hub.bot.edit_message_text(
                        texts.PRIVATE_GAME_HIDDEN,
                        chat_id=chat_id,
                        message_id=query.message.message_id,
                    )
                return await self.hub.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=query.message.message_id,
                    caption=texts.PRIVATE_GAME_HIDDEN,
                )

            marked = await self.hub.sender.send(chat_id, mark, priority=Priority.GAME)
        if game.status in {"lobby", "running"}:
            self.hub.effects.start(self.render(game.id))
        elif game.status == "finished":
            async with self.repo.sessions() as session:
                current = await session.get(GameSession, game.id)
                if current and not current.state.get("erased"):
                    current = view(current)
                    self.hub.effects.start(
                        self.hub.board(current, texts.private_game_board(current))
                    )
        if not removed and not marked:
            return texts.PRIVATE_GAME_HIDE_FAILED
        return (
            texts.PRIVATE_GAME_HIDE_MEDIA
            if not removed and item["kind"] != "text"
            else texts.PRIVATE_GAME_HIDE_DONE
        )
