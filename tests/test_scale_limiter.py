import asyncio
from collections import Counter
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import SendMessage

from bot.services.sender import Priority, RateLimiter, Sender


def test_rolling_windows_with_fake_clock(fake_clock):
    limiter = RateLimiter()
    starts = []
    for index in range(500):
        chat_id = index % 4
        fake_clock.value = limiter.ready_at(chat_id, fake_clock.now())
        now = fake_clock.now()
        limiter.record(chat_id, now)
        starts.append((chat_id, now))
        assert sum(t > now - 1 for _, t in starts) <= 25
        assert sum(chat == chat_id and t > now - 60 for chat, t in starts) <= 18


async def test_queue_respects_both_rates(fake_clock):
    sender = Sender(None, clock=fake_clock)
    starts = []

    async def sent(chat):
        starts.append((chat, fake_clock.now()))
        return True

    try:
        assert all(
            await asyncio.gather(
                *[sender.send(i % 3, lambda chat=i % 3: sent(chat)) for i in range(120)]
            )
        )
        for chat, now in starts:
            assert sum(now - 1 < t <= now for _, t in starts) <= 25
            assert sum(c == chat and now - 60 < t <= now for c, t in starts) <= 18
        assert Counter(chat for chat, _ in starts) == {0: 40, 1: 40, 2: 40}
    finally:
        await sender.close()


async def test_priority_and_fifo_for_equal_priority(fake_clock):
    sender = Sender(None, clock=fake_clock)
    order = []

    async def sent(name):
        order.append(name)
        return True

    try:
        await asyncio.gather(
            *[
                sender.send(-chat, lambda name=name: sent(name), priority=priority)
                for chat, name, priority in [
                    (1, "bulk", Priority.BULK),
                    (2, "challenge", Priority.CHALLENGE),
                    (3, "game1", Priority.GAME),
                    (4, "game2", Priority.GAME),
                ]
            ]
        )
        assert order == ["game1", "game2", "challenge", "bulk"]
    finally:
        await sender.close()


async def test_paused_chat_does_not_block_other_chats(fake_clock):
    sender = Sender(None, clock=fake_clock)
    sender.limiter.pause(-1, 10)
    order = []

    async def sent(chat):
        order.append((chat, fake_clock.now()))

    try:
        await asyncio.gather(sender.send(-1, lambda: sent(-1)), sender.send(-2, lambda: sent(-2)))
        assert order[0] == (-2, 0)
        assert order[1][0] == -1 and order[1][1] >= 10
    finally:
        await sender.close()


async def test_callback_bypasses_global_pause_and_queue(fake_clock):
    sender = Sender(None, clock=fake_clock)
    sender.limiter.pause(None, 300)
    bot = AsyncMock()
    bot.answer_callback_query.return_value = True
    try:
        assert await sender.answer_callback_query(bot, "query-id") is True
        assert fake_clock.now() == 0
        assert sender.queue_length == 0
    finally:
        await sender.close()


async def test_retry_scope_and_one_retry(fake_clock):
    sender = Sender(None, clock=fake_clock)
    error = TelegramRetryAfter(
        method=SendMessage(chat_id=-1, text="test"), message="wait", retry_after=4
    )
    operation = AsyncMock(side_effect=[error, True])
    try:
        assert await sender.send(-1, operation, retry_scope="chat") is True
        assert operation.await_count == 2
        assert sender.limiter.global_pause == 0
        assert sender.limiter.chat_pauses[-1] == 4
        operation = AsyncMock(side_effect=error)
        assert await sender.send(-2, operation) is None
        assert operation.await_count == 2
        assert sender.limiter.global_pause >= 8
    finally:
        await sender.close()


async def test_shutdown_cancels_waiting_items():
    sender = Sender(None)
    blocked = asyncio.Event()
    task = asyncio.create_task(sender.send(-1, blocked.wait))
    await asyncio.sleep(0)
    await sender.close()
    result = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(result[0], asyncio.CancelledError)
    assert await sender.send(-1, AsyncMock()) is None
