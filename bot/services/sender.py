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
from aiogram.exceptions import TelegramForbiddenError, TelegramMigrateToChat, TelegramRetryAfter
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
    migrations: int = field(compare=False, default=0)
    generation: int = field(compare=False, default=0)
    report_failures: bool = field(compare=False, default=True)


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
        self._delayed: list[tuple[float, int, _Item]] = []
        self._sequence = itertools.count()
        self._wake = asyncio.Event()
        self._worker: asyncio.Task | None = None
        self._active: set[asyncio.Task] = set()
        self._futures: set[asyncio.Future] = set()
        self._closed = False
        self._accepting = True
        self.generations = {}
        self._active_items = {}
        self.aliases = {}
        self.resolve_chat = lambda chat_id: self.aliases.get(chat_id, chat_id)
        self.on_migrate = None
        self.on_failure = None
        self._failures = deque(maxlen=3)
        self._failure_reporting = False

    @property
    def queue_length(self) -> int:
        return len(self._queue) + len(self._delayed)

    async def send(
        self,
        chat_id: int | None,
        operation: Callable[[], Awaitable[T]],
        *,
        priority: Priority = Priority.GAME,
        retry_scope: Literal["chat", "global"] = "global",
        report_failures: bool = True,
    ) -> T | None:
        if not self._accepting or self._closed or self.queue_length >= 20_000:
            logger.warning("Outbound queue closed or full; operation rejected")
            if self._accepting and not self._closed and report_failures:
                self._note_failure(OverflowError(), chat_id)
            return None
        future = asyncio.get_running_loop().create_future()
        self._futures.add(future)
        future.add_done_callback(self._futures.discard)
        self._enqueue(
            _Item(
                priority,
                next(self._sequence),
                chat_id,
                operation,
                future,
                retry_scope,
                generation=self.generations.get(chat_id, 0),
                report_failures=report_failures,
            )
        )
        return await asyncio.shield(future)

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
        while self._delayed and self._delayed[0][0] <= now:
            _, _, ready_item = heapq.heappop(self._delayed)
            if not ready_item.future.done():
                heapq.heappush(self._queue, ready_item)
        earliest = float("inf")
        selected = None
        while self._queue:
            item = heapq.heappop(self._queue)
            if item.future.done():
                continue
            item.chat_id = self.resolve_chat(item.chat_id)
            ready = self.limiter.ready_at(item.chat_id, now)
            if ready <= now:
                selected = item
                break
            earliest = min(earliest, ready)
            heapq.heappush(self._delayed, (ready, item.sequence, item))
        if self._delayed:
            earliest = min(earliest, self._delayed[0][0])
        return selected, max(0, earliest - now)

    async def _run(self) -> None:
        while self._queue or self._delayed or self._active:
            if (not self._queue and not self._delayed) or len(self._active) >= 25:
                await self._wait(None)
                continue
            item, delay = self._take_ready()
            if item is None:
                if self._queue or self._delayed:
                    await self._wait(delay)
                continue
            self.limiter.record(item.chat_id, self.clock.now())
            task = asyncio.create_task(self._execute(item))
            self._active_items[task] = item
            self._active.add(task)
            task.add_done_callback(self._completed)
            await asyncio.sleep(0)

    def _completed(self, task: asyncio.Task) -> None:
        self._active_items.pop(task, None)
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
        failure = None
        try:
            if item.generation == self.generations.get(item.chat_id, 0):
                result = await item.operation()
        except TelegramMigrateToChat as error:
            failure = error
            old_id, new_id = item.chat_id, error.migrate_to_chat_id
            logger.info("TelegramMigrateToChat: %s -> %s", old_id, new_id)
            try:
                if old_id is None or old_id == new_id or item.migrations >= 2:
                    raise ValueError("Invalid or repeated Telegram migration response")
                if self.on_migrate:
                    await self.on_migrate(old_id, new_id)
                elif self.sessions is not None:
                    from bot.db.repo.migrations import ChatMigrationRepository
                    from bot.services.locks import ChatLocks

                    await ChatMigrationRepository(self.sessions, ChatLocks()).migrate(
                        old_id, new_id
                    )
                self.aliases[old_id] = new_id
                starts = self.limiter.chat_starts.pop(old_id, deque())
                starts.extend(self.limiter.chat_starts.get(new_id, ()))
                self.limiter.chat_starts[new_id] = deque(sorted(starts))
                pause = self.limiter.chat_pauses.pop(old_id, 0)
                self.limiter.chat_pauses[new_id] = max(
                    pause, self.limiter.chat_pauses.get(new_id, 0)
                )
                item.chat_id, item.migrations = new_id, item.migrations + 1
                if not item.future.done() and not self._closed:
                    self._enqueue(item)
                    return
            except Exception as migration_error:
                logger.exception("Could not migrate Telegram chat %s -> %s", old_id, new_id)
                failure = migration_error
        except TelegramRetryAfter as error:
            scope = item.chat_id if item.retry_scope == "chat" else None
            self.limiter.pause(scope, self.clock.now() + error.retry_after)
            logger.warning("Telegram rate limit: scope=%s retry_after=%s", scope, error.retry_after)
            if item.attempts == 0 and not item.future.done() and not self._closed:
                item.attempts += 1
                self._enqueue(item)
                return
            failure = error
        except TelegramForbiddenError:
            await self._forbidden(item.chat_id)
        except asyncio.CancelledError:
            if not item.future.done():
                item.future.cancel()
            return
        except Exception as error:
            logger.exception("Telegram operation failed for chat %s", item.chat_id)
            failure = error
        if failure is not None and item.report_failures:
            self._note_failure(failure, item.chat_id)
        if not item.future.done():
            item.future.set_result(result)

    def _note_failure(self, error, chat_id):
        now = self.clock.now()
        if self._failures and now - self._failures[-1] >= 600:
            self._failure_reporting = False
        self._failures.append(now)
        if len(self._failures) == 3 and now - self._failures[0] <= 600 and self.on_failure:
            count = 1 if self._failure_reporting else 3
            self._failure_reporting = True
            try:
                self.on_failure(error, "sender", chat_id, count=count)
            except Exception:
                logger.warning("Sender failure summary could not be recorded")

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
                else:
                    self._note_failure(error, None)
            except Exception as error:
                logger.exception("Callback answer failed")
                self._note_failure(error, None)
                return None
        return None

    def discard_chats(self, chats):
        """Invalidate pending effects during confirmed self-deletion."""
        for chat in chats:
            self.generations[chat] = self.generations.get(chat, 0) + 1
        for item in [*self._queue, *(item for _, _, item in self._delayed)]:
            if item.chat_id in chats and not item.future.done():
                item.future.set_result(None)
        for task, item in tuple(self._active_items.items()):
            if item.chat_id in chats:
                if not item.future.done():
                    item.future.set_result(None)
                task.cancel()
        self._delayed = [entry for entry in self._delayed if not entry[2].future.done()]
        heapq.heapify(self._delayed)
        self._wake.set()

    async def drain(self, seconds=10) -> None:
        """Stop accepting new sends and allow accepted work a bounded grace period."""
        self._accepting = False
        try:
            async with asyncio.timeout(seconds):
                if self._worker:
                    await asyncio.shield(self._worker)
        except TimeoutError:
            logger.warning("Outbound drain deadline reached")

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
        for _, _, item in self._delayed:
            item.future.cancel()
        self._delayed.clear()
