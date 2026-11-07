"""One live lock per chat; weak references prevent an unbounded idle lock registry."""

import asyncio
from contextlib import asynccontextmanager
from weakref import WeakValueDictionary


class ChatLocks:
    def __init__(self) -> None:
        self._locks: WeakValueDictionary[int, asyncio.Lock] = WeakValueDictionary()
        self.resolve = lambda chat_id: chat_id

    def for_chat(self, chat_id: int) -> asyncio.Lock:
        lock = self._locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[chat_id] = lock
        return lock

    @asynccontextmanager
    async def hold(self, chat_id: int):
        while True:
            canonical = self.resolve(chat_id)
            lock = self.for_chat(canonical)
            await lock.acquire()
            if canonical == self.resolve(canonical):
                break
            lock.release()
        try:
            yield canonical
        finally:
            lock.release()
