"""One process-wide prioritized async queue; callback answers bypass it."""

import asyncio
import heapq
import itertools
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Literal, TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.repo.reachability import mark_inactive

logger = logging.getLogger(__name__)
T = TypeVar("T")


class Priority(IntEnum):
    GAME = 0
    CHALLENGE = 1
    BULK = 2


class Clock:
    def now(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class RateLimiter:
    """Rolling windows count attempt starts, including failures and retries."""

    def __init__(self) -> None:
        self.global_starts: deque[float] = deque()
        self.chat_starts: dict[int, deque[float]] = {}
        self.global_pause = 0.0
        self.chat_pauses: dict[int, float] = {}
        self.last_cleanup = 0.0

    def ready_at(self, chat_id: int | None, now: float) -> float:
        self._prune(self.global_starts, now - 1)
        ready = max(now, self.global_pause)
        if len(self.global_starts) >= 25:
            ready = max(ready, self.global_starts[0] + 1)
        if chat_id is not None:
            starts = self.chat_starts.get(chat_id, deque())
            self._prune(starts, now - 60)
            if len(starts) >= 18:
                ready = max(ready, starts[0] + 60)
            ready = max(ready, self.chat_pauses.get(chat_id, 0))
        return ready

    @staticmethod
    def _prune(starts: deque[float], cutoff: float) -> None:
        while starts and starts[0] <= cutoff:
            starts.popleft()

    def record(self, chat_id: int | None, now: float) -> None:
        self.global_starts.append(now)
        if chat_id is not None:
            self.chat_starts.setdefault(chat_id, deque()).append(now)
        if now - self.last_cleanup >= 60:
            self.chat_starts = {
                chat: starts
                for chat, starts in self.chat_starts.items()
                if starts and starts[-1] > now - 60
            }
            self.chat_pauses = {chat: end for chat, end in self.chat_pauses.items() if end > now}
            self.last_cleanup = now

    def pause(self, chat_id: int | None, until: float) -> None:
        if chat_id is None:
            self.global_pause = max(self.global_pause, until)
        else:
            self.chat_pauses[chat_id] = max(self.chat_pauses.get(chat_id, 0), until)


@dataclass(order=True)
class _Item:
    priority: int
    sequence: int
    chat_id: int | None = field(compare=False)
    operation: Callable[[], Awaitable[Any]] = field(compare=False)
    future: asyncio.Future = field(compare=False)
    retry_scope: Literal["chat", "global"] = field(compare=False, default="global")
    attempts: int = field(compare=False, default=0)


class Sender:
    def __init__(
        self,
        sessions: async_sessionmaker,
        *,
        clock: Clock | None = None,
        on_forbidden: Callable[[int], Awaitable[None]] | None = None,
    ) -> None:
        self.sessions = sessions
        self.clock = clock or Clock()
        self.limiter = RateLimiter()
        self.on_forbidden = on_forbidden
        self._queue: list[_Item] = []
        self._sequence = itertools.count()
        self._wake = asyncio.Event()
        self._worker: asyncio.Task | None = None
        self._active: set[asyncio.Task] = set()
        self._futures: set[asyncio.Future] = set()
        self._closed = False

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    async def send(
        self,
        chat_id: int | None,
        operation: Callable[[], Awaitable[T]],
        *,
        priority: Priority = Priority.GAME,
        retry_scope: Literal["chat", "global"] = "global",
    ) -> T | None:
        if self._closed or len(self._queue) >= 20_000:
            logger.warning("Outbound queue closed or full; operation rejected")
            return None
        future = asyncio.get_running_loop().create_future()
        self._futures.add(future)
        future.add_done_callback(self._futures.discard)
        self._enqueue(
            _Item(priority, next(self._sequence), chat_id, operation, future, retry_scope)
        )
        return await future

    def _enqueue(self, item: _Item) -> None:
        heapq.heappush(self._queue, item)
        self._wake.set()
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(), name="outbound-queue")

    async def _wait(self, delay: float | None) -> None:
        self._wake.clear()
        if delay is None:
            await self._wake.wait()
            return
        timer = asyncio.create_task(self.clock.sleep(max(0, delay)))
        wake = asyncio.create_task(self._wake.wait())
        try:
            await asyncio.wait([timer, wake], return_when=asyncio.FIRST_COMPLETED)
        finally:
            timer.cancel()
            wake.cancel()
            await asyncio.gather(timer, wake, return_exceptions=True)

    def _take_ready(self) -> tuple[_Item | None, float]:
        now = self.clock.now()
        global_ready = self.limiter.ready_at(None, now)
        if global_ready > now:
            return None, global_ready - now
        skipped = []
        earliest = float("inf")
        selected = None
        while self._queue:
            item = heapq.heappop(self._queue)
            if item.future.done():
                continue
            ready = self.limiter.ready_at(item.chat_id, now)
            if ready <= now:
                selected = item
                break
            earliest = min(earliest, ready)
            skipped.append(item)
        for item in skipped:
            heapq.heappush(self._queue, item)
        return selected, max(0, earliest - now)

    async def _run(self) -> None:
        while self._queue or self._active:
            if not self._queue or len(self._active) >= 25:
                await self._wait(None)
                continue
            item, delay = self._take_ready()
            if item is None:
                if self._queue:
                    await self._wait(delay)
                continue
            self.limiter.record(item.chat_id, self.clock.now())
            task = asyncio.create_task(self._execute(item))
            self._active.add(task)
            task.add_done_callback(self._completed)
            await asyncio.sleep(0)

    def _completed(self, task: asyncio.Task) -> None:
        self._active.discard(task)
        self._wake.set()

    async def _forbidden(self, chat_id: int | None) -> None:
        logger.warning("Telegram access denied for chat %s", chat_id)
        if chat_id is not None:
            try:
                if self.on_forbidden:
                    await self.on_forbidden(chat_id)
                await mark_inactive(self.sessions, chat_id)
            except Exception:
                logger.exception("Could not mark chat %s inactive", chat_id)

    async def _execute(self, item: _Item) -> None:
        result = None
        try:
            result = await item.operation()
        except TelegramRetryAfter as error:
            scope = item.chat_id if item.retry_scope == "chat" else None
            self.limiter.pause(scope, self.clock.now() + error.retry_after)
            logger.warning("Telegram rate limit: scope=%s retry_after=%s", scope, error.retry_after)
            if item.attempts == 0 and not item.future.done() and not self._closed:
                item.attempts += 1
                self._enqueue(item)
                return
        except TelegramForbiddenError:
            await self._forbidden(item.chat_id)
        except asyncio.CancelledError:
            item.future.cancel()
            return
        except Exception:
            logger.exception("Telegram operation failed for chat %s", item.chat_id)
        if not item.future.done():
            item.future.set_result(result)

    async def answer_callback_query(self, bot: Bot, callback_query_id: str, **kwargs) -> Any:
        """Never enter the queue or wait on message windows/global message pauses."""
        for attempt in range(2):
            try:
                return await bot.answer_callback_query(callback_query_id, **kwargs)
            except TelegramRetryAfter as error:
                self.limiter.pause(None, self.clock.now() + error.retry_after)
                self._wake.set()
                if attempt == 0:
                    await self.clock.sleep(error.retry_after)
            except Exception:
                logger.exception("Callback answer failed")
                return None
        return None

    async def close(self) -> None:
        self._closed = True
        for future in list(self._futures):
            future.cancel()
        if self._worker:
            self._worker.cancel()
        active = list(self._active)
        for task in active:
            task.cancel()
        await asyncio.gather(
            *([self._worker] if self._worker else []), *active, return_exceptions=True
        )
        for item in self._queue:
            item.future.cancel()
        self._queue.clear()
