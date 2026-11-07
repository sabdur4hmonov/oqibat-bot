from sqlalchemy import select

from bot.db.models import Membership


class Participants:
    def __init__(self) -> None:
        self.members: set[tuple[int, int]] = set()
        self.by_chat: dict[int, set[int]] = {}

    async def load(self, sessions) -> None:
        async with sessions() as session:
            self.members = set(
                (
                    await session.execute(
                        select(
                            Membership.chat_id,
                            Membership.user_id,
                        ).where(Membership.opted_in.is_(True), Membership.is_active.is_(True))
                    )
                ).all()
            )
        self.by_chat.clear()
        for chat_id, user_id in self.members:
            self.by_chat.setdefault(chat_id, set()).add(user_id)

    def set(self, chat_id: int, user_id: int, participating: bool) -> None:
        if participating:
            self.members.add((chat_id, user_id))
            self.by_chat.setdefault(chat_id, set()).add(user_id)
        else:
            self.members.discard((chat_id, user_id))
            users = self.by_chat.get(chat_id)
            if users is not None:
                users.discard(user_id)
                if not users:
                    self.by_chat.pop(chat_id, None)

    def contains(self, chat_id: int, user_id: int) -> bool:
        return (chat_id, user_id) in self.members

    def for_chat(self, chat_id: int) -> tuple[int, ...]:
        return tuple(sorted(self.by_chat.get(chat_id, ())))
