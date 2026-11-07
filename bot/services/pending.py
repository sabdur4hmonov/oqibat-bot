"""Synchronous O(1) challenge lookup. Repository owns all cache mutations."""

from collections import Counter

from sqlalchemy import select

from bot.db.models import Challenge


class PendingChallenges:
    def __init__(self) -> None:
        self.members: set[tuple[int, int]] = set()
        self._ids: dict[int, tuple[int, int]] = {}
        self._counts: Counter = Counter()

    async def load(self, sessions) -> None:
        async with sessions() as session:
            rows = (
                await session.execute(
                    select(
                        Challenge.id,
                        Challenge.chat_id,
                        Challenge.user_id,
                    ).where(Challenge.status == "pending")
                )
            ).all()
        self._ids = {row.id: (row.chat_id, row.user_id) for row in rows}
        self.members = set(self._ids.values())
        self._counts = Counter(self._ids.values())

    def add(self, challenge_id: int, chat_id: int, user_id: int) -> None:
        if challenge_id in self._ids:
            self.remove(challenge_id)
        self._ids[challenge_id] = (chat_id, user_id)
        self.members.add((chat_id, user_id))
        self._counts[(chat_id, user_id)] += 1

    def remove(self, challenge_id: int) -> None:
        key = self._ids.pop(challenge_id, None)
        if key is not None:
            self._counts[key] -= 1
            if not self._counts[key]:
                del self._counts[key]
                self.members.discard(key)

    def contains(self, chat_id: int, user_id: int) -> bool:
        return (chat_id, user_id) in self.members
