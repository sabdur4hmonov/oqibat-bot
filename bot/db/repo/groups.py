"""Explicit onboarding/membership/settings writes; ordinary messages use ActivityBuffer."""

from sqlalchemy import select

from bot.db.models import Challenge, Chat, GameSession, Membership, User
from bot.services.game_cache import view
from bot.services.scheduler import initialize_schedule
from bot.utils.admin import member_is_active, member_is_admin
from bot.utils.time import utc_now


class GroupRepository:
    def __init__(self, sessions, locks, pending, participants=None, game_cache=None) -> None:
        self.sessions, self.locks, self.pending = sessions, locks, pending
        self.participants = participants
        self.game_cache = game_cache
        self.on_game_resolved = None
        self.on_membership_changed = None

    async def get(self, chat_id: int) -> Chat | None:
        chat_id = self.locks.resolve(chat_id)
        async with self.sessions() as session:
            return await session.get(Chat, chat_id)

    async def bot_membership(self, tg_chat, member) -> Chat:
        async with self.locks.hold(tg_chat.id) as chat_id:
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if chat is None:
                    chat = Chat(id=chat_id, title=tg_chat.title or "")
                    session.add(chat)
                    await session.flush()
                chat.title = tg_chat.title or ""
                chat.is_active = member_is_active(member)
                chat.bot_is_admin = member_is_admin(member)
                initialize_schedule(chat, utc_now())
            return chat

    @staticmethod
    async def _user(session, tg_user) -> None:
        user = await session.get(User, tg_user.id)
        if user is None:
            user = User(id=tg_user.id)
            session.add(user)
        user.first_name, user.username = tg_user.first_name, tg_user.username
        await session.flush()

    async def membership(
        self, chat_id: int, tg_user, *, opted_in: bool | None = None, active: bool = True
    ) -> bool:
        removed = []
        cancelled_game = None
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if chat is None or (
                    opted_in is True and not (chat.is_active and chat.bot_is_admin)
                ):
                    return False
                await self._user(session, tg_user)
                member = await session.get(Membership, (chat_id, tg_user.id))
                if member is None:
                    member = Membership(chat_id=chat_id, user_id=tg_user.id)
                    session.add(member)
                member.is_active = active
                member.last_seen_at = utc_now()
                if opted_in is not None:
                    member.opted_in = opted_in
                    member.opted_in_at = utc_now() if opted_in else None
                if not active:
                    member.opted_in = False
                    member.opted_in_at = None
                if opted_in is False or not active:
                    challenges = (
                        await session.scalars(
                            select(Challenge).where(
                                Challenge.chat_id == chat_id,
                                Challenge.user_id == tg_user.id,
                                Challenge.status == "pending",
                            )
                        )
                    ).all()
                    for challenge in challenges:
                        challenge.status = "cancelled"
                        challenge.resolved_at = utc_now()
                        removed.append(challenge.id)
                    game = await session.scalar(
                        select(GameSession)
                        .where(
                            GameSession.chat_id == chat_id,
                            GameSession.game.in_(["hyj", "rps", "number", "math"]),
                            GameSession.status.in_(["lobby", "running"]),
                        )
                        .limit(1)
                    )
                    if game is not None and (
                        game.state.get("target") == tg_user.id
                        or (game.game == "rps" and tg_user.id in game.state.get("players", []))
                        or (game.game in {"number", "math"} and game.started_by == tg_user.id)
                    ):
                        game.status, game.phase_deadline_at = "cancelled", None
                        game.state = {
                            **game.state,
                            "phase": "done",
                            "result": "opted_out",
                            "rev": game.state.get("rev", 0) + 1,
                        }
                        cancelled_game = game
            for challenge_id in removed:
                self.pending.remove(challenge_id)
            if self.participants is not None:
                self.participants.set(chat_id, tg_user.id, member.opted_in and member.is_active)
            if cancelled_game is not None:
                if self.game_cache is not None:
                    self.game_cache.sync(cancelled_game)
                if self.on_game_resolved:
                    self.on_game_resolved(view(cancelled_game))
        if self.on_membership_changed:
            await self.on_membership_changed(chat_id, tg_user.id)
        return True

    async def change_setting(self, chat_id: int, field: str, value) -> Chat | None:
        game = None
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if chat is None or not chat.is_active or not chat.bot_is_admin:
                    return None
                setattr(chat, field, value)
                if field == "mafia_delete_dead_messages":
                    game = await session.scalar(
                        select(GameSession)
                        .where(
                            GameSession.chat_id == chat_id,
                            GameSession.game == "mafia",
                            GameSession.status.in_(["lobby", "running"]),
                        )
                        .limit(1)
                    )
                    if game:
                        game.state = {
                            **game.state,
                            "delete_dead": value,
                            "rev": game.state.get("rev", 0) + 1,
                        }
                initialize_schedule(chat, utc_now())
            if game is not None and self.game_cache is not None:
                self.game_cache.sync(game)
            return chat
