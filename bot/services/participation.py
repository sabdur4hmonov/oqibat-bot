from sqlalchemy import select

from bot.db.models import Membership


class Participants:
    def __init__(self) -> None:
        self.members: set[tuple[int, int]] = set()

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

    def set(self, chat_id: int, user_id: int, participating: bool) -> None:
        if participating:
            self.members.add((chat_id, user_id))
        else:
            self.members.discard((chat_id, user_id))

    def contains(self, chat_id: int, user_id: int) -> bool:
        return (chat_id, user_id) in self.members
