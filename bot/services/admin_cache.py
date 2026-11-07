"""TTL admin IDs, with coalesced fetches and invalidation on membership updates."""

import time
from collections import OrderedDict

from bot.services.locks import ChatLocks


class AdminCache:
    def __init__(self, bot, *, clock=time.monotonic) -> None:
        self.bot, self.clock = bot, clock
        self.entries: OrderedDict[int, tuple[float, frozenset[int]]] = OrderedDict()
        self.locks = ChatLocks()
        self._fetch_versions: dict[int, int] = {}

    def invalidate(self, chat_id: int) -> None:
        self.entries.pop(chat_id, None)
        if chat_id in self._fetch_versions:
            self._fetch_versions[chat_id] += 1

    async def get(self, chat_id: int) -> frozenset[int]:
        async with self.locks.for_chat(chat_id):
            cached = self.entries.get(chat_id)
            if cached and cached[0] > self.clock():
                self.entries.move_to_end(chat_id)
                return cached[1]
            self.invalidate(chat_id)
            # Deliberately propagate errors: permission checks must not treat a failed fetch as []
            self._fetch_versions[chat_id] = 0
            try:
                while True:
                    version = self._fetch_versions[chat_id]
                    admins = await self.bot.get_chat_administrators(chat_id)
                    if version == self._fetch_versions[chat_id]:
                        break
            finally:
                self._fetch_versions.pop(chat_id, None)
            ids = frozenset(admin.user.id for admin in admins)
            self.entries[chat_id] = (self.clock() + 600, ids)
            if len(self.entries) > 20_000:
                self.entries.popitem(last=False)
            return ids

    async def refresh(self, chat_id: int) -> frozenset[int]:
        self.invalidate(chat_id)
        return await self.get(chat_id)
