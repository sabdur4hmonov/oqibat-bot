"""Explicit onboarding/membership/settings writes; ordinary messages use ActivityBuffer."""

from sqlalchemy import select

from bot.db.models import Challenge, Chat, Membership, User
from bot.services.scheduler import initialize_schedule
from bot.utils.admin import member_is_active, member_is_admin
from bot.utils.time import utc_now


class GroupRepository:
    def __init__(self, sessions, locks, pending) -> None:
        self.sessions, self.locks, self.pending = sessions, locks, pending

    async def get(self, chat_id: int) -> Chat | None:
        async with self.sessions() as session:
            return await session.get(Chat, chat_id)

    async def bot_membership(self, tg_chat, member) -> Chat:
        async with self.locks.for_chat(tg_chat.id):
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, tg_chat.id)
                if chat is None:
                    chat = Chat(id=tg_chat.id, title=tg_chat.title or "")
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
        async with self.locks.for_chat(chat_id):
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
            for challenge_id in removed:
                self.pending.remove(challenge_id)
        return True

    async def change_setting(self, chat_id: int, field: str, value) -> Chat | None:
        async with self.locks.for_chat(chat_id):
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if chat is None or not chat.is_active or not chat.bot_is_admin:
                    return None
                setattr(chat, field, value)
                initialize_schedule(chat, utc_now())
            return chat
