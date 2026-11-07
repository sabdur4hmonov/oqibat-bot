"""Synchronous O(1) challenge lookup. Repository owns all cache mutations."""

from collections import Counter

from sqlalchemy import select

from bot.db.models import Challenge


class PendingChallenges:
    def __init__(self) -> None:
        self.members: set[tuple[int, int]] = set()
        self._ids: dict[int, tuple[int, int]] = {}
        self._counts: Counter = Counter()
        self._by_chat: dict[int, set[int]] = {}
        self._by_member: dict[tuple[int, int], set[int]] = {}
        self._details: dict[int, tuple] = {}
        self.message_ids: dict[int, int | None] = {}

    async def load(self, sessions) -> None:
        async with sessions() as session:
            rows = (
                await session.execute(
                    select(
                        Challenge.id,
                        Challenge.chat_id,
                        Challenge.user_id,
                        Challenge.kind,
                        Challenge.deadline_at,
                        Challenge.created_at,
                        Challenge.message_id,
                        Challenge.origin_chat_id,
                    ).where(Challenge.status == "pending")
                )
            ).all()
        self.members.clear()
        self._ids.clear()
        self._counts.clear()
        self._by_chat.clear()
        self._by_member.clear()
        self._details.clear()
        self.message_ids.clear()
        for row in rows:
            self.add(row.id, row.chat_id, row.user_id, row.kind, row.deadline_at, row.created_at)
            self.message_ids[row.id] = (
                0 if row.origin_chat_id not in {None, row.chat_id} else row.message_id
            )

    def add(
        self, challenge_id: int, chat_id: int, user_id: int, kind=None, deadline=None, created=None
    ) -> None:
        if challenge_id in self._ids:
            self.remove(challenge_id)
        self._ids[challenge_id] = (chat_id, user_id)
        self.members.add((chat_id, user_id))
        self._counts[(chat_id, user_id)] += 1
        self._by_chat.setdefault(chat_id, set()).add(challenge_id)
        self._by_member.setdefault((chat_id, user_id), set()).add(challenge_id)
        self._details[challenge_id] = (kind, deadline, created)
        self.message_ids[challenge_id] = None

    def remove(self, challenge_id: int) -> None:
        key = self._ids.pop(challenge_id, None)
        if key is not None:
            self._details.pop(challenge_id, None)
            self.message_ids.pop(challenge_id, None)
            self._by_chat[key[0]].discard(challenge_id)
            self._by_member[key].discard(challenge_id)
            if not self._by_chat[key[0]]:
                del self._by_chat[key[0]]
            if not self._by_member[key]:
                del self._by_member[key]
            self._counts[key] -= 1
            if not self._counts[key]:
                del self._counts[key]
                self.members.discard(key)

    def contains(self, chat_id: int, user_id: int) -> bool:
        return (chat_id, user_id) in self.members

    def for_chat(self, chat_id: int) -> tuple[int, ...]:
        return tuple(self._by_chat.get(chat_id, ()))

    def match(self, chat_id: int, user_id: int, kind: str, sent_at) -> int | None:
        for challenge_id in self._by_member.get((chat_id, user_id), ()):
            expected, deadline, created = self._details[challenge_id]
            if (
                expected == kind
                and created is not None
                and deadline is not None
                and created.replace(microsecond=0) <= sent_at <= deadline
            ):
                return challenge_id
        return None
